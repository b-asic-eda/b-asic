#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B-ASIC Scheduler-GUI Scheduler Item Module.

Contains the scheduler_gui SchedulerItem class for drawing and
maintaining a schedule.
"""
from collections import defaultdict
from math import floor
from pprint import pprint
from typing import Dict, List, Optional, Set, cast

# QGraphics and QPainter imports
from qtpy.QtWidgets import QGraphicsItem, QGraphicsItemGroup

# B-ASIC
from b_asic.gui_utils.mpl_window import MPLWindow
from b_asic.operation import Operation
from b_asic.port import InputPort
from b_asic.schedule import Schedule
from b_asic.scheduler_gui._preferences import (
    OPERATION_GAP,
    OPERATION_HEIGHT,
    SCHEDULE_INDENT,
)
from b_asic.scheduler_gui.axes_item import AxesItem
from b_asic.scheduler_gui.operation_item import OperationItem
from b_asic.scheduler_gui.scheduler_event import SchedulerEvent
from b_asic.scheduler_gui.signal_item import SignalItem


class SchedulerItem(SchedulerEvent, QGraphicsItemGroup):  # PySide2 / PyQt5
    """
    A class to represent a schedule in a QGraphicsScene.

    This class is a
    subclass of QGraphicsItemGroup and contains the objects, axes from
    AxesItem, as well as components from OperationItem. It
    also inherits from SchedulerEvent, which acts as a filter for events
    to OperationItem objects.

    Parameters
    ==========

    schedule : :class:`~b_asic.schedule.Schedule`
        The Schedule to draw.

    warnings : bool, default: True
        Whether to draw processes with execution time longer than schedule time in
        a different color.

    port_numbers : bool, default: False
        Whether to show port numbers on the operations.


    parent : QGraphicsItem, optional
        The parent. Passed to the constructor of QGraphicsItemGroup
    """

    _axes: Optional[AxesItem]
    _operation_items: Dict[str, OperationItem]
    _x_axis_indent: float
    _event_items: List[QGraphicsItem]
    _signal_dict: Dict[OperationItem, Set[SignalItem]]

    def __init__(
        self,
        schedule: Schedule,
        warnings: bool = True,
        show_port_numbers: bool = False,
        parent: Optional[QGraphicsItem] = None,
    ):
        """
        Construct a SchedulerItem. *parent* is passed to QGraphicsItemGroup's
        constructor.
        """
        # QGraphicsItemGroup.__init__(self, self)
        # SchedulerEvent.__init__(self)
        super().__init__(parent=parent)
        # if isinstance(parent, QGraphicsItem):
        #     super().__init__(parent=parent)
        # else:
        #     super().__init__(parent=self)
        self._schedule = schedule
        self._parent = parent
        self._warnings = not warnings  # To trigger redraw
        self._show_port_numbers = not show_port_numbers  # To trigger redraw
        self._axes = None
        self._operation_items = {}
        self._x_axis_indent = SCHEDULE_INDENT
        self._event_items = []
        self._execution_time_plot_dialogs = {}
        self._signal_dict = defaultdict(set)
        self._make_graph()
        self.set_warnings(warnings)
        self.set_port_numbers(show_port_numbers)

    def clear(self) -> None:
        """
        Set all children's parent to 'None' and delete the children objects.
        """
        self._event_items = []
        for item in self.childItems():
            item.setParentItem(None)
            del item

    def is_component_valid_pos(self, item: OperationItem, pos: float) -> bool:
        """
        Take in a component position and return True if the component's new
        position is valid, False otherwise.

        Parameters
        ----------
        item : :class:`b_asic.scheduler_gui.operation_item.OperationItem`
            The component.
        pos : float
            The x-position to check.
        """
        if self.schedule is None:
            raise ValueError("No schedule installed.")
        new_start_time = floor(pos) - floor(self._x_axis_indent)
        slacks = self.schedule.slacks(item.graph_id)
        op_start_time = self.schedule.start_time_of_operation(item.graph_id)
        if not -slacks[0] <= new_start_time - op_start_time <= slacks[1]:
            # Cannot move due to dependencies
            return False
        if self.schedule.cyclic:
            if new_start_time < -1:
                # Moving one position before left edge => wrap
                return False
        else:
            if pos < 0:
                return False
            if new_start_time + item.operation.latency > self.schedule.schedule_time:
                return False

        return True

    def _redraw_all_lines(self) -> None:
        """Redraw all lines in schedule."""
        s = set()
        for signals in self._signal_dict.values():
            s.update(signals)
        for signal in s:
            signal.update_path()

    def _redraw_lines(self, item: OperationItem) -> None:
        """Update lines connected to *item*."""
        for signal in self._signal_dict[item]:
            signal.update_path()

    def set_warnings(self, warnings: bool = True):
        """
        Set warnings for long execution times.

        Parameters
        ----------
        warnings : bool, default: True
            Whether to draw processes with execution time longer than schedule time in
            a different color.
        """
        if warnings != self._warnings:
            self._warnings = warnings
            s = set()
            for signals in self._signal_dict.values():
                s.update(signals)
            for signal in s:
                signal.set_inactive()

    def set_port_numbers(self, port_numbers: bool = True):
        """
        Set if port numbers are shown.

        Parameters
        ----------
        port_numbers : bool, default: True
            Whether to show port numbers on the operations.
        """
        if port_numbers != self._show_port_numbers:
            self._show_port_numbers = port_numbers
            for item in self._operation_items.values():
                item.set_show_port_numbers(port_numbers)

    def set_item_active(self, item: OperationItem) -> None:
        """
        Set *item* as active, i.e., draw it and connecting signals in special colors.

        Parameters
        ----------
        item : :class:`b_asic.scheduler_gui.operation_item.OperationItem`
            The item to set as active.

        """
        item.set_active()
        for signal in self._signal_dict[item]:
            signal.set_active()

    def set_item_inactive(self, item: OperationItem) -> None:
        """
        Set *item* as inactive, i.e., draw it and connecting signals in standard
        colors.

        Parameters
        ----------
        item : :class:`b_asic.scheduler_gui.operation_item.OperationItem`
            The item to set as active.

        """
        item.set_inactive()
        for signal in self._signal_dict[item]:
            signal.set_inactive()

    def set_new_start_time(self, item: OperationItem) -> None:
        """
        Set new start time for *item*.

        Parameters
        ----------
        item : :class:`b_asic.scheduler_gui.operation_item.OperationItem`
            The item to set as active.

        """
        pos = item.x()
        op_start_time = self.schedule.start_time_of_operation(item.graph_id)
        new_start_time = floor(pos) - floor(self._x_axis_indent)
        move_time = new_start_time - op_start_time
        if move_time:
            self.schedule.move_operation(item.graph_id, move_time)
            print(f"schedule.move_operation({item.graph_id!r}, {move_time})")

    def is_valid_delta_time(self, delta_time: int) -> bool:
        """
        Return True if the schedule time can be changed by *delta_time*.

        Parameters
        ----------
        delta_time : int
            The time difference to check for.

        """
        # TODO: implement
        # item = self.scene().mouseGrabberItem()
        if self.schedule is None:
            raise ValueError("No schedule installed.")
        return (
            self.schedule.schedule_time + delta_time >= self.schedule.get_max_end_time()
        )

    def change_schedule_time(self, delta_time: int) -> None:
        """
        Change the schedule time by *delta_time* and redraw the graph.

        Parameters
        ----------
        delta_time : int
            The time difference to change the schedule time with.
        """
        if self._axes is None:
            raise RuntimeError("No AxesItem!")
        if self.schedule is None:
            raise ValueError("No schedule installed.")
        self.schedule.set_schedule_time(self.schedule.schedule_time + delta_time)
        if delta_time:
            print(f"schedule.set_schedule_time({self.schedule.schedule_time})")
        self._axes.set_width(self._axes.width + delta_time)
        # Redraw all lines
        self._redraw_all_lines()

    @property
    def schedule(self) -> Schedule:
        """The schedule."""
        return self._schedule

    @property
    def axes(self) -> Optional[AxesItem]:
        return self._axes

    @property
    def components(self) -> List[OperationItem]:
        return list(component for component in self._operation_items.values())

    @property
    def event_items(self) -> List[QGraphicsItem]:
        """Return a list of objects that receives events."""
        return self._event_items

    def _set_position(self, graph_id) -> None:
        op_item = self._operation_items[graph_id]
        op_item.setPos(
            self._x_axis_indent + self.schedule.start_times[graph_id],
            self.schedule._get_y_position(graph_id, OPERATION_HEIGHT, OPERATION_GAP),
        )

    def _redraw_from_start(self) -> None:
        self.schedule._reset_y_locations()
        for graph_id in dict(
            sorted(self.schedule.start_times.items(), key=lambda item: item[1])
        ):
            self._set_position(graph_id)
        self._redraw_all_lines()
        self._update_axes()

    def _redraw_all(self) -> None:
        for graph_id in self._operation_items:
            self._set_position(graph_id)
        self._redraw_all_lines()
        self._update_axes()

    def _update_axes(self, build=False) -> None:
        # build axes
        schedule_time = self.schedule.schedule_time
        max_pos_graph_id = max(
            self.schedule._y_locations, key=self.schedule._y_locations.get
        )
        y_pos_min = self.schedule._get_y_position(
            max_pos_graph_id, OPERATION_HEIGHT, OPERATION_GAP
        )

        if self._axes is None or build:
            self._axes = AxesItem(schedule_time, y_pos_min + 0.5)
            self._event_items += self._axes.event_items
        else:
            self._axes.set_height(y_pos_min + 0.5)
        self._axes.setPos(0, y_pos_min + OPERATION_HEIGHT + OPERATION_GAP)

    def _make_graph(self) -> None:
        """Make a new graph out of the stored attributes."""
        # build components
        for graph_id in self.schedule.start_times.keys():
            operation = cast(Operation, self.schedule._sfg.find_by_id(graph_id))
            component = OperationItem(operation, height=OPERATION_HEIGHT, parent=self)
            self._operation_items[graph_id] = component
            self._set_position(graph_id)
            self._event_items += component.event_items

        # self._axes.width = schedule_time

        # add axes and components
        self._update_axes(build=True)
        self.addToGroup(self._axes)
        for component in self.components:
            self.addToGroup(component)

        # add signals
        for component in self.components:
            for output_port in component.operation.outputs:
                for signal in output_port.signals:
                    destination = cast(InputPort, signal.destination)
                    destination_component = self._operation_items[
                        destination.operation.graph_id
                    ]
                    gui_signal = SignalItem(
                        component, destination_component, signal, self
                    )
                    self.addToGroup(gui_signal)
                    self._signal_dict[component].add(gui_signal)
                    self._signal_dict[destination_component].add(gui_signal)

    def _swap_io_of_operation(self, graph_id: str) -> None:
        self._schedule.swap_io_of_operation(graph_id)
        print(f"schedule.swap_io_of_operation({graph_id!r})")
        self._signals.reopen.emit()

    def _execution_time_plot(self, type_name: str) -> None:
        self._execution_time_plot_dialogs[type_name] = MPLWindow(
            f"Execution times for {type_name}"
        )
        self._schedule.get_operations().get_by_type_name(type_name).plot(
            self._execution_time_plot_dialogs[type_name].axes
        )
        self._execution_time_plot_dialogs[type_name].show()


pprint(SchedulerItem.__mro__)
