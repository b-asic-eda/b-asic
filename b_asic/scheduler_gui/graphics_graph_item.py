#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-ASIC Scheduler-gui Graphics Graph Item Module.

Contains the scheduler-gui GraphicsGraphItem class for drawing and
maintain a component in a graph.
"""
from collections import defaultdict
from math import floor
from pprint import pprint
from typing import Dict, List, Optional, Set

# QGraphics and QPainter imports
from qtpy.QtWidgets import QGraphicsItem, QGraphicsItemGroup

# B-ASIC
from b_asic.schedule import Schedule
from b_asic.scheduler_gui.graphics_axes_item import GraphicsAxesItem
from b_asic.scheduler_gui.graphics_component_item import GraphicsComponentItem
from b_asic.scheduler_gui.graphics_graph_event import GraphicsGraphEvent
from b_asic.scheduler_gui.graphics_signal import GraphicsSignal


class GraphicsGraphItem(
    GraphicsGraphEvent, QGraphicsItemGroup
):  # PySide2 / PyQt5
    # class GraphicsGraphItem(QGraphicsItemGroup, GraphicsGraphEvent):      # PyQt5
    """A class to represent a graph in a QGraphicsScene. This class is a
    subclass of QGraphicsItemGroup and contains the objects, axes from
    GraphicsAxesItem, as well as components from GraphicsComponentItem. It
    also inherits from GraphicsGraphEvent, which acts as a filter for events
    to GraphicsComponentItem objects."""
    _schedule: Schedule
    _axes: GraphicsAxesItem
    _components: List[GraphicsComponentItem]
    _components_height: float
    _x_axis_indent: float
    _event_items: List[QGraphicsItem]
    _signal_dict: Dict[GraphicsComponentItem, Set[GraphicsSignal]]

    def __init__(
        self, schedule: Schedule, parent: Optional[QGraphicsItem] = None
    ):
        """Constructs a GraphicsGraphItem. 'parent' is passed to QGraphicsItemGroup's constructor.
        """
        # QGraphicsItemGroup.__init__(self, self)
        # GraphicsGraphEvent.__init__(self)
        super().__init__(parent=parent)
        # if isinstance(parent, QGraphicsItem):
        #     super().__init__(parent=parent)
        # else:
        #     super().__init__(parent=self)
        self._schedule = schedule
        self._axes = None
        self._components = []
        self._components_height = 0.0
        self._x_axis_indent = 0.2
        self._event_items = []
        self._signal_dict = defaultdict(set)
        self._make_graph()

    def clear(self) -> None:
        """Sets all children's parent to 'None' and delete the children objects.
        """
        self._event_items = []
        for item in self.childItems():
            item.setParentItem(None)
            del item

    def is_component_valid_pos(
        self, item: GraphicsComponentItem, pos: float
    ) -> bool:
        """Takes in a component position and returns true if the component's new
        position is valid, false otherwise."""
        # TODO: implement
        assert self.schedule is not None, "No schedule installed."
        end_time = item.end_time
        new_start_time = floor(pos) - floor(self._x_axis_indent)
        slacks = self.schedule.slacks(item.op_id)
        op_start_time = self.schedule.start_time_of_operation(item.op_id)
        if not -slacks[0] <= new_start_time - op_start_time <= slacks[1]:
            return False
        if pos < 0:
            return False
        if (
            self.schedule.cyclic
            and new_start_time > self.schedule.schedule_time
        ):
            return False
        if (
            not self.schedule.cyclic
            and new_start_time + end_time > self.schedule.schedule_time
        ):
            return False

        return True

    def _redraw_lines(self, item: GraphicsComponentItem):
        """Update lines connected to *item*."""
        for signal in self._signal_dict[item]:
            signal.update_path()

    def set_item_active(self, item: GraphicsComponentItem):
        item.set_active()
        for signal in self._signal_dict[item]:
            signal.set_active()

    def set_item_inactive(self, item: GraphicsComponentItem):
        item.set_inactive()
        for signal in self._signal_dict[item]:
            signal.set_inactive()

    def set_new_starttime(self, item: GraphicsComponentItem) -> None:
        """Set new starttime for *item*."""
        pos = item.x()
        op_start_time = self.schedule.start_time_of_operation(item.op_id)
        new_start_time = floor(pos) - floor(self._x_axis_indent)
        move_time = new_start_time - op_start_time
        if move_time:
            self.schedule.move_operation(item.op_id, move_time)

    def is_valid_delta_time(self, delta_time: int) -> bool:
        """Takes in a delta time and returns true if the new schedule time is
        valid, false otherwise."""
        # TODO: implement
        # item = self.scene().mouseGrabberItem()
        assert self.schedule is not None, "No schedule installed."
        return (
            self.schedule.schedule_time + delta_time
            >= self.schedule.get_max_end_time()
        )

    def set_schedule_time(self, delta_time: int) -> None:
        """Set the schedule time and redraw the graph."""
        assert self.schedule is not None, "No schedule installed."
        self.schedule.set_schedule_time(
            self.schedule.schedule_time + delta_time
        )
        self._axes.set_width(self._axes.width + delta_time)

    @property
    def schedule(self) -> Schedule:
        """The schedule."""
        return self._schedule

    @property
    def axes(self) -> GraphicsAxesItem:
        return self._axes

    @property
    def components(self) -> List[GraphicsComponentItem]:
        return self._components

    @property
    def event_items(self) -> List[QGraphicsItem]:
        """Returnes a list of objects, that receives events."""
        return self._event_items

    def _make_graph(self) -> None:
        """Makes a new graph out of the stored attributes."""
        # build components
        spacing = 0.2
        _components_dict = {}
        # print('Start times:')
        for op_id, op_start_time in self.schedule.start_times.items():
            operation = self.schedule.sfg.find_by_id(op_id)

            #            if not isinstance(op, (Input, Output)):
            self._components_height += spacing
            component = GraphicsComponentItem(operation, parent=self)
            component.setPos(
                self._x_axis_indent + op_start_time, self._components_height
            )
            self._components.append(component)
            _components_dict[operation] = component
            self._components_height += component.height
            self._event_items += component.event_items
        # self._components_height += spacing

        # build axes
        schedule_time = self.schedule.schedule_time
        self._axes = GraphicsAxesItem(
            schedule_time, self._components_height - spacing
        )
        self._axes.setPos(0, self._components_height + spacing * 2)
        self._event_items += self._axes.event_items
        # self._axes.width = schedule_time

        # add axes and components
        self.addToGroup(self._axes)
        # self._axes.update_axes(schedule_time - 2, self._components_height, self._x_axis_indent)
        for component in self._components:
            self.addToGroup(component)
        # self.addToGroup(self._components)

        # add signals
        for component in self._components:
            for output_port in component.operation.outputs:
                for signal in output_port.signals:
                    dest_component = _components_dict[
                        signal.destination.operation
                    ]
                    gui_signal = GraphicsSignal(
                        component, dest_component, signal, parent=self
                    )
                    self.addToGroup(gui_signal)
                    self._signal_dict[component].add(gui_signal)
                    self._signal_dict[dest_component].add(gui_signal)


pprint(GraphicsGraphItem.__mro__)
