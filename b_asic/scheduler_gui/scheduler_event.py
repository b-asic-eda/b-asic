#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B-ASIC Scheduler-gui Graphics Graph Event Module.

Contains the scheduler-gui SchedulerEvent class containing event filters and handlers for SchedulerItem objects.
"""

from typing import List, Optional, overload

# QGraphics and QPainter imports
from qtpy.QtCore import QEvent, QObject, QPointF, Signal
from qtpy.QtGui import QFocusEvent
from qtpy.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneContextMenuEvent,
    QGraphicsSceneDragDropEvent,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QGraphicsSceneWheelEvent,
)

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

    _axes: Optional[AxesItem]
    _current_pos: QPointF
    _delta_time: int
    _signals: Signals  # PyQt5
    _schedule: Schedule

    def __init__(self, parent: Optional[QGraphicsItem] = None):  # PyQt5
        super().__init__(parent=parent)
        self._signals = self.Signals()

    def is_component_valid_pos(self, item: OperationItem, pos: float) -> bool:
        raise NotImplementedError

    def is_valid_delta_time(self, delta_time: int) -> bool:
        raise NotImplementedError

    def set_schedule_time(self, delta_time: int) -> None:
        raise NotImplementedError

    def set_item_active(self, item: OperationItem) -> None:
        raise NotImplementedError

    def set_item_inactive(self, item: OperationItem) -> None:
        raise NotImplementedError

    #################
    #### Filters ####
    #################
    @overload
    def installSceneEventFilters(self, filterItems: QGraphicsItem) -> None:
        ...

    @overload
    def installSceneEventFilters(
        self, filterItems: List[QGraphicsItem]
    ) -> None:
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
    def removeSceneEventFilters(
        self, filterItems: List[QGraphicsItem]
    ) -> None:
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
        handler = None

        if isinstance(item, OperationItem):  # one component
            switch = {
                # QEvent.FocusIn:                         self.comp_focusInEvent,
                # QEvent.GraphicsSceneContextMenu:        self.comp_contextMenuEvent,
                # QEvent.GraphicsSceneDragEnter:          self.comp_dragEnterEvent,
                # QEvent.GraphicsSceneDragMove:           self.comp_dragMoveEvent,
                # QEvent.GraphicsSceneDragLeave:          self.comp_dragLeaveEvent,
                # QEvent.GraphicsSceneDrop:               self.comp_dropEvent,
                # QEvent.GraphicsSceneHoverEnter:         self.comp_hoverEnterEvent,
                # QEvent.GraphicsSceneHoverMove:          self.comp_hoverMoveEvent,
                # QEvent.GraphicsSceneHoverLeave:         self.comp_hoverLeaveEvent,
                QEvent.GraphicsSceneMouseMove: self.comp_mouseMoveEvent,
                QEvent.GraphicsSceneMousePress: self.comp_mousePressEvent,
                QEvent.GraphicsSceneMouseRelease: self.comp_mouseReleaseEvent,
                # QEvent.GraphicsSceneMouseDoubleClick:   self.comp_mouseDoubleClickEvent,
                # QEvent.GraphicsSceneWheel:              self.comp_wheelEvent
            }
            handler = switch.get(event.type())

        elif isinstance(item, TimelineItem):  # the timeline
            switch = {
                # QEvent.GraphicsSceneHoverEnter:         self.timeline_hoverEnterEvent,
                # QEvent.GraphicsSceneHoverLeave:         self.timeline_hoverLeaveEvent,
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
        return False  # returns False if event is ignored and pass through event to its child

    # def sceneEvent(self, event: QEvent) -> bool:
    #     print(f'sceneEvent() --> {event.type()}')
    #     # event.accept()
    #     # QApplication.sendEvent(self.scene(), event)
    #     return False

    ###############################################
    #### Event Handlers: OperationItem ####
    ###############################################
    def comp_focusInEvent(self, event: QFocusEvent) -> None:
        ...

    def comp_contextMenuEvent(
        self, event: QGraphicsSceneContextMenuEvent
    ) -> None:
        ...

    def comp_dragEnterEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        ...

    def comp_dragMoveEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        ...

    def comp_dragLeaveEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        ...

    def comp_dropEvent(self, event: QGraphicsSceneDragDropEvent) -> None:
        ...

    def comp_hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        ...

    def comp_hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        ...

    def comp_hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        ...

    def comp_mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Set the position of the graphical element in the graphic scene,
        translate coordinates of the cursor within the graphic element in the
        coordinate system of the parent object. The object can only move
        horizontally in x-axis scale steps.
        """

        def update_pos(item, dx, dy):
            posx = item.x() + dx
            posy = item.y() + dy * (OPERATION_GAP + OPERATION_HEIGHT)
            if self.is_component_valid_pos(item, posx):
                item.setX(posx)
                item.setY(posy)
                self._current_pos.setX(self._current_pos.x() + dx)
                self._current_pos.setY(self._current_pos.y() + dy)
                self._redraw_lines(item)
                self._schedule._y_locations[item.operation.graph_id] += dy

        item: OperationItem = self.scene().mouseGrabberItem()
        delta_x = (item.mapToParent(event.pos()) - self._current_pos).x()
        delta_y = (item.mapToParent(event.pos()) - self._current_pos).y()

        delta_y_steps = round(delta_y / (OPERATION_GAP + OPERATION_HEIGHT))
        if delta_x > 0.505:
            update_pos(item, 1, delta_y_steps)
        elif delta_x < -0.505:
            update_pos(item, -1, delta_y_steps)
        elif delta_y_steps != 0:
            update_pos(item, 0, delta_y_steps)

    def comp_mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Changes the cursor to ClosedHandCursor when grabbing an object and
        stores the current position in item's parent coordinates. *event* will
        by default be accepted, and this item is then the mouse grabber. This
        allows the item to receive future move, release and double-click events.
        """
        item: OperationItem = self.scene().mouseGrabberItem()
        self._signals.component_selected.emit(item.graph_id)
        self._current_pos = item.mapToParent(event.pos())
        self.set_item_active(item)
        event.accept()

    def comp_mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Change the cursor to OpenHandCursor when releasing an object."""
        item: OperationItem = self.scene().mouseGrabberItem()
        self.set_item_inactive(item)
        self.set_new_starttime(item)
        posx = item.x()
        redraw = False
        if posx < 0:
            posx += self._schedule.schedule_time
            redraw = True
        if posx > self._schedule.schedule_time:
            posx = posx % self._schedule.schedule_time
            redraw = True
        if redraw:
            item.setX(posx)
            self._redraw_lines(item)

    def comp_mouseDoubleClickEvent(
        self, event: QGraphicsSceneMouseEvent
    ) -> None:
        ...

    def comp_wheelEvent(self, event: QGraphicsSceneWheelEvent) -> None:
        ...

    ###############################################
    #### Event Handlers: GraphicsLineTem       ####
    ###############################################
    def timeline_mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Set the position of the graphical element in the graphic scene,
        translate coordinates of the cursor within the graphic element in the
        coordinate system of the parent object. The object can only move
        horizontally in x-axis scale steps.
        """

        def update_pos(item, dx):
            pos = item.x() + dx
            if self.is_valid_delta_time(self._delta_time + dx):
                item.setX(pos)
                self._current_pos.setX(self._current_pos.x() + dx)
                self._delta_time += dx
                item.set_text(self._delta_time)

        item: TimelineItem = self.scene().mouseGrabberItem()
        delta_x = (item.mapToParent(event.pos()) - self._current_pos).x()
        if delta_x > 0.505:
            update_pos(item, 1)
        elif delta_x < -0.505:
            update_pos(item, -1)

    def timeline_mousePressEvent(
        self, event: QGraphicsSceneMouseEvent
    ) -> None:
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

    def timeline_mouseReleaseEvent(
        self, event: QGraphicsSceneMouseEvent
    ) -> None:
        """Updates the schedule time."""
        item: TimelineItem = self.scene().mouseGrabberItem()
        item.hide_label()
        if self._delta_time != 0:
            self.set_schedule_time(self._delta_time)
            self._signals.schedule_time_changed.emit()
