#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B-ASIC Scheduler-GUI Graphics Scheduler Event Module.

Contains the scheduler_ui SchedulerEvent class containing event filters and
handlers for SchedulerItem objects.
"""
import math
from typing import List, Optional, overload

# QGraphics and QPainter imports
from qtpy.QtCore import QEvent, QObject, QPointF, Qt, Signal
from qtpy.QtWidgets import QGraphicsItem, QGraphicsSceneMouseEvent

from b_asic.schedule import Schedule
from b_asic.scheduler_gui._preferences import OPERATION_GAP, OPERATION_HEIGHT
from b_asic.scheduler_gui.axes_item import AxesItem
from b_asic.scheduler_gui.operation_item import OperationItem
from b_asic.scheduler_gui.timeline_item import TimelineItem


class SchedulerEvent:  # PyQt5
    """
    Event filter and handlers for SchedulerItem.

    Parameters
    ----------
    parent : QGraphicsItem, optional
        The parent QGraphicsItem.
    """

    class Signals(QObject):  # PyQt5
        """A class representing signals."""

        component_selected = Signal(str)
        schedule_time_changed = Signal()
        component_moved = Signal(str)
        redraw_all = Signal()
        reopen = Signal()

    _axes: Optional[AxesItem]
    _current_pos: QPointF
    _delta_time: int
    _signals: Signals  # PyQt5
    _schedule: Schedule
    _old_op_position: int = -1

    def __init__(self, parent: Optional[QGraphicsItem] = None):  # PyQt5
        super().__init__(parent=parent)
        self._signals = self.Signals()

    def is_component_valid_pos(self, item: OperationItem, pos: float) -> bool:
        raise NotImplementedError

    def is_valid_delta_time(self, delta_time: int) -> bool:
        raise NotImplementedError

    def change_schedule_time(self, delta_time: int) -> None:
        raise NotImplementedError

    def set_item_active(self, item: OperationItem) -> None:
        raise NotImplementedError

    def set_item_inactive(self, item: OperationItem) -> None:
        raise NotImplementedError

    ###########
    # Filters #
    ###########
    @overload
    def installSceneEventFilters(self, filterItems: QGraphicsItem) -> None:
        ...

    @overload
    def installSceneEventFilters(self, filterItems: List[QGraphicsItem]) -> None:
        ...

    def installSceneEventFilters(self, filterItems) -> None:
        """
        Installs an event filter for *filterItems* on 'self', causing all events
        for *filterItems* to first pass through 'self's ``sceneEventFilter()``
        method. *filterItems* can be one object or a list of objects.
        """
        item: OperationItem
        for item in filterItems:
            item.installSceneEventFilter(self)

    @overload
    def removeSceneEventFilters(self, filterItems: QGraphicsItem) -> None:
        ...

    @overload
    def removeSceneEventFilters(self, filterItems: List[QGraphicsItem]) -> None:
        ...

    def removeSceneEventFilters(self, filterItems) -> None:
        """
        Removes an event filter on *filterItems* from *self*. *filterItems* can
        be one object or a list of objects.
        """
        item: OperationItem
        for item in filterItems:
            item.removeSceneEventFilter(self)

    def sceneEventFilter(self, item: QGraphicsItem, event: QEvent) -> bool:
        """
        Returns True if the event was filtered (i.e. stopped), otherwise False.
        If False is returned, the event is forwarded to the appropriate child in
        the event chain.
        """

        if isinstance(item, OperationItem):  # one component
            switch = {
                QEvent.GraphicsSceneMouseMove: self.operation_mouseMoveEvent,
                QEvent.GraphicsSceneMousePress: self.operation_mousePressEvent,
                QEvent.GraphicsSceneMouseRelease: self.operation_mouseReleaseEvent,
            }
            handler = switch.get(event.type())

        elif isinstance(item, TimelineItem):  # the timeline
            switch = {
                QEvent.GraphicsSceneMouseMove: self.timeline_mouseMoveEvent,
                QEvent.GraphicsSceneMousePress: self.timeline_mousePressEvent,
                QEvent.GraphicsSceneMouseRelease: self.timeline_mouseReleaseEvent,
            }
            handler = switch.get(event.type())

        else:
            raise TypeError(
                f"Received an unexpected event '{event.type()}' "
                f"from an '{type(item).__name__}' object."
            )

        if handler is not None:
            handler(event)
            return True
        return False

    #################################
    # Event Handlers: OperationItem #
    #################################

    def operation_mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Set the position of the graphical element in the graphic scene,
        translate coordinates of the cursor within the graphic element in the
        coordinate system of the parent object.
        """

        def update_pos(operation_item, dx, dy):
            pos_x = operation_item.x() + dx
            if self.is_component_valid_pos(operation_item, pos_x):
                pos_y = operation_item.y() + dy * (OPERATION_GAP + OPERATION_HEIGHT)
                operation_item.setX(pos_x)
                operation_item.setY(pos_y)
                self._current_pos.setX(self._current_pos.x() + dx)
                self._current_pos.setY(self._current_pos.y() + dy)
                self._redraw_lines(operation_item)
                gid = operation_item.operation.graph_id
                self._schedule.set_y_location(
                    gid, dy + self._schedule.get_y_location(gid)
                )

        item: OperationItem = self.scene().mouseGrabberItem()
        delta_x = (item.mapToParent(event.pos()) - self._current_pos).x()
        delta_y = (item.mapToParent(event.pos()) - self._current_pos).y()

        delta_y_steps = round(2 * delta_y / (OPERATION_GAP + OPERATION_HEIGHT)) / 2
        if delta_x > 0.505:
            update_pos(item, 1, delta_y_steps)
        elif delta_x < -0.505:
            update_pos(item, -1, delta_y_steps)
        elif delta_y_steps != 0:
            update_pos(item, 0, delta_y_steps)

    def operation_mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Changes the cursor to ClosedHandCursor when grabbing an object and
        stores the current position in item's parent coordinates. *event* will
        by default be accepted, and this item is then the mouse grabber. This
        allows the item to receive future move, release and double-click events.
        """
        item: OperationItem = self.scene().mouseGrabberItem()
        if event.button() == Qt.MouseButton.LeftButton:
            self._old_op_position = self._schedule.get_y_location(
                item.operation.graph_id
            )
            self._signals.component_selected.emit(item.graph_id)
            self._current_pos = item.mapToParent(event.pos())
            self.set_item_active(item)
            event.accept()
        else:  # Right-button
            item._open_context_menu()
            self._signals.redraw_all.emit()

    def operation_mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Change the cursor to OpenHandCursor when releasing an object."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        item: OperationItem = self.scene().mouseGrabberItem()
        self.set_new_start_time(item)
        self.set_item_inactive(item)
        pos_x = item.x()
        redraw = False
        if pos_x < 0:
            pos_x += self._schedule.schedule_time
            redraw = True
        if pos_x > self._schedule.schedule_time:
            # If zero execution time, keep operation at the edge
            if (
                pos_x > self._schedule.schedule_time + 1
                or item.operation.execution_time
            ):
                pos_x = pos_x % self._schedule.schedule_time
                redraw = True
        pos_y = self._schedule.get_y_location(item.operation.graph_id)
        # Check move in y-direction
        if pos_y != self._old_op_position:
            self._schedule.move_y_location(
                item.operation.graph_id,
                math.ceil(pos_y),
                (pos_y % 1) != 0,
            )
            print(
                f"schedule.move_y_location({item.operation.graph_id!r},"
                f" {math.ceil(pos_y)}, {(pos_y % 1) != 0})"
            )
            self._signals.redraw_all.emit()
        # Operation has been moved in x-direction
        if redraw:
            item.setX(pos_x)
            self._redraw_lines(item)
        self._signals.component_moved.emit(item.graph_id)

    ###################################
    # Event Handlers: GraphicsLineTem #
    ###################################
    def timeline_mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Set the position of the graphical element in the graphic scene,
        translate coordinates of the cursor within the graphic element in the
        coordinate system of the parent object. The object can only move
        horizontally in x-axis scale steps.
        """

        def update_pos(timeline_item, dx):
            pos = timeline_item.x() + dx
            if self.is_valid_delta_time(self._delta_time + dx):
                timeline_item.setX(pos)
                self._current_pos.setX(self._current_pos.x() + dx)
                self._delta_time += dx
                timeline_item.set_text(self._delta_time)

        item: TimelineItem = self.scene().mouseGrabberItem()
        delta_x = (item.mapToParent(event.pos()) - self._current_pos).x()
        if delta_x > 0.505:
            update_pos(item, 1)
        elif delta_x < -0.505:
            update_pos(item, -1)

    def timeline_mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Store the current position in item's parent coordinates. *event* will
        by default be accepted, and this item is then the mouse grabber. This
        allows the item to receive future move, release and double-click events.
        """
        item: TimelineItem = self.scene().mouseGrabberItem()
        self._delta_time = 0
        item.set_text(self._delta_time)
        item.show_label()
        self._current_pos = item.mapToParent(event.pos())
        event.accept()

    def timeline_mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Updates the schedule time."""
        item: TimelineItem = self.scene().mouseGrabberItem()
        item.hide_label()
        if self._delta_time != 0:
            self.change_schedule_time(self._delta_time)
            self._signals.schedule_time_changed.emit()
