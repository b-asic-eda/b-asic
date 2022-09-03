#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-ASIC Scheduler-gui Graphics Graph Event Module.

Contains the scheduler-gui GraphicsGraphEvent class containing event filters and handlers for GraphicsGraphItem objects.
"""

from typing     import Optional, overload, List

# QGraphics and QPainter imports
from qtpy.QtCore    import Qt, QObject, Signal, QEvent, QPointF
from qtpy.QtGui     import QCursor, QFocusEvent
from qtpy.QtWidgets import (
    QGraphicsItem, QGraphicsSceneMouseEvent, QGraphicsSceneHoverEvent,
    QGraphicsSceneContextMenuEvent, QGraphicsSceneDragDropEvent, QGraphicsSceneWheelEvent)

from b_asic.scheduler_gui.graphics_component_item    import GraphicsComponentItem
from b_asic.scheduler_gui.graphics_axes_item         import GraphicsAxesItem
from b_asic.scheduler_gui.graphics_timeline_item     import GraphicsTimelineItem


# sys.settrace
# class GraphicsGraphEvent(QGraphicsItemGroup, QObject):          # PySide2
class GraphicsGraphEvent:                                       # PyQt5
    """Event filter and handlers for GraphicsGraphItem"""
    class Signals(QObject):                                     # PyQt5
        """A class respresenting signals."""
        component_selected = Signal(str)
        schedule_time_changed = Signal()

    _axes:          GraphicsAxesItem
    _current_pos:   QPointF
    _delta_time:    int
    _signals:       Signals             # PyQt5
    # component_selected = Signal(str)  # PySide2
    # schedule_time_changed = Signal()  # PySide2


    #@overload
    def is_component_valid_pos(self, item: GraphicsComponentItem, pos: float) -> bool: ...
    #@overload
    def is_valid_delta_time(self, delta_time: int) -> bool: ...
    #@overload
    def set_schedule_time(self, delta_time: int) -> None: ...

    # def __init__(self, parent: Optional[QGraphicsItem] = None):     # PySide2
    #     QObject.__init__(self)
    #     QGraphicsItemGroup.__init__(self, parent)

    def __init__(self, parent: Optional[QGraphicsItem] = None):     # PyQt5
        # QGraphicsItemGroup.__init__(self, parent)
        # QObject.__init__(self)
        super().__init__(parent=parent)
        self._signals = self.Signals()

    #################
    #### Filters ####
    #################
    @overload
    def installSceneEventFilters(self, filterItems: QGraphicsItem) -> None: ...
    @overload
    def installSceneEventFilters(self, filterItems: List[QGraphicsItem]) -> None: ...
    def installSceneEventFilters(self, filterItems) -> None:
        """Installs an event filter for 'filterItems' on 'self', causing all events
        for 'filterItems' to first pass through 'self's sceneEventFilter()
        function. 'filterItems' can be one object or a list of objects."""
        item: GraphicsComponentItem
        for item in filterItems:
            item.installSceneEventFilter(self)

    @overload
    def removeSceneEventFilters(self, filterItems: QGraphicsItem) -> None: ...
    @overload
    def removeSceneEventFilters(self, filterItems: List[QGraphicsItem]) -> None: ...
    def removeSceneEventFilters(self, filterItems) -> None:
        """Removes an event filter on 'filterItems' from 'self'. 'filterItems' can
        be one object or a list of objects."""
        item: GraphicsComponentItem
        for item in filterItems:
            item.removeSceneEventFilter(self)


    def sceneEventFilter(self, item: QGraphicsItem, event: QEvent) -> bool:
        """Returns true if the event was filtered (i.e. stopped), otherwise false.
        If false is returned, the event is forwarded to the appropriate child in
        the event chain."""
        handler = None

        if isinstance(item, GraphicsComponentItem):     # one component
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
                QEvent.GraphicsSceneMouseMove:          self.comp_mouseMoveEvent,
                QEvent.GraphicsSceneMousePress:         self.comp_mousePressEvent,
                QEvent.GraphicsSceneMouseRelease:       self.comp_mouseReleaseEvent,
                # QEvent.GraphicsSceneMouseDoubleClick:   self.comp_mouseDoubleClickEvent,
                # QEvent.GraphicsSceneWheel:              self.comp_wheelEvent
            }
            handler = switch.get(event.type())

        elif isinstance(item, GraphicsTimelineItem):       # the timeline
            switch = {
                # QEvent.GraphicsSceneHoverEnter:         self.timeline_hoverEnterEvent,
                # QEvent.GraphicsSceneHoverLeave:         self.timeline_hoverLeaveEvent,
                QEvent.GraphicsSceneMouseMove:          self.timeline_mouseMoveEvent,
                QEvent.GraphicsSceneMousePress:         self.timeline_mousePressEvent,
                QEvent.GraphicsSceneMouseRelease:       self.timeline_mouseReleaseEvent,
            }
            handler = switch.get(event.type())

        else:
            raise TypeError(f"Received an unexpected event '{event.type()}' "
                            f"from an '{type(item).__name__}' object.")

        if handler is not None:
            handler(event)
            return True
        return False    # returns False if event is ignored and pass through event to its child

    # def sceneEvent(self, event: QEvent) -> bool:
    #     print(f'sceneEvent() --> {event.type()}')
    #     # event.accept()
    #     # QApplication.sendEvent(self.scene(), event)
    #     return False


    ###############################################
    #### Event Handlers: GraphicsComponentItem ####
    ###############################################
    def comp_focusInEvent(self, event: QFocusEvent) -> None: ...
    def comp_contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None: ...
    def comp_dragEnterEvent(self, event: QGraphicsSceneDragDropEvent) -> None: ...
    def comp_dragMoveEvent(self, event: QGraphicsSceneDragDropEvent) -> None: ...
    def comp_dragLeaveEvent(self, event: QGraphicsSceneDragDropEvent) -> None: ...
    def comp_dropEvent(self, event: QGraphicsSceneDragDropEvent) -> None: ...
    def comp_hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None: ...
    def comp_hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None: ...
    def comp_hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None: ...

    def comp_mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Set the position of the graphical element in the graphic scene,
        translate coordinates of the cursor within the graphic element in the
        coordinate system of the parent object. The object can only move
        horizontally in x-axis scale steps."""
        # Qt.DragMoveCursor
        # button = event.button()
        def update_pos(item, delta_x):
            pos = item.x() + delta_x
            if self.is_component_valid_pos(item, pos):
                # self.prepareGeometryChange()
                item.setX(pos)
                self._current_pos.setX(self._current_pos.x() + delta_x)
                self._redraw_lines(item)

        item: GraphicsComponentItem = self.scene().mouseGrabberItem()
        delta_x = (item.mapToParent(event.pos()) - self._current_pos).x()
        if delta_x > 0.505:
            update_pos(item, 1)
        elif delta_x < -0.505:
            update_pos(item, -1)

    def comp_mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Changes the cursor to ClosedHandCursor when grabbing an object and
        stores the current position in item's parent coordinates. 'event' will
        by default be accepted, and this item is then the mouse grabber. This
        allows the item to receive future move, release and double-click events."""
        item: GraphicsComponentItem = self.scene().mouseGrabberItem()
        self._signals.component_selected.emit(item.op_id)
        # self.component_selected.emit(item.op_id)
        self._current_pos = item.mapToParent(event.pos())
        self.set_item_active(item)
        event.accept()

    def comp_mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Changes the cursor to OpenHandCursor when releasing an object."""
        item: GraphicsComponentItem = self.scene().mouseGrabberItem()
        self.set_item_inactive(item)
        self.set_new_starttime(item)


    def comp_mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None: ...
    def comp_wheelEvent(self, event: QGraphicsSceneWheelEvent) -> None: ...



    ###############################################
    #### Event Handlers: GraphicsLineTem       ####
    ###############################################
    def timeline_mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Set the position of the graphical element in the graphic scene,
        translate coordinates of the cursor within the graphic element in the
        coordinate system of the parent object. The object can only move
        horizontally in x-axis scale steps."""
        # Qt.DragMoveCursor
        # button = event.button()
        def update_pos(item, delta_x):
            pos = item.x() + delta_x
            if self.is_valid_delta_time(self._delta_time + delta_x):
                # self.prepareGeometryChange()
                item.setX(pos)
                self._current_pos.setX(self._current_pos.x() + delta_x)
                self._delta_time += delta_x
                item.set_text(self._delta_time)

        item: GraphicsTimelineItem = self.scene().mouseGrabberItem()
        delta_x = (item.mapToParent(event.pos()) - self._current_pos).x()
        if delta_x > 0.505:
            update_pos(item, 1)
        elif delta_x < -0.505:
            update_pos(item, -1)

    def timeline_mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Stores the current position in item's parent coordinates. 'event' will
        by default be accepted, and this item is then the mouse grabber. This
        allows the item to receive future move, release and double-click events."""
        item: GraphicsTimelineItem = self.scene().mouseGrabberItem()
        self._delta_time = 0
        item.set_text(self._delta_time)
        item.show_label()
        self._current_pos = item.mapToParent(event.pos())
        event.accept()

    def timeline_mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Updates the schedule time."""
        item: GraphicsTimelineItem = self.scene().mouseGrabberItem()
        item.hide_label()
        if self._delta_time != 0:
            self.set_schedule_time(self._delta_time)
            self._signals.schedule_time_changed.emit()
