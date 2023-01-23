#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B-ASIC Scheduler-gui Graphics Component Item Module.

Contains the scheduler-gui GraphicsComponentItem class for drawing and maintain a component in a graph.
"""
from typing import Dict, List, Optional, Union

# QGraphics and QPainter imports
from qtpy.QtCore import QPointF, Qt
from qtpy.QtGui import QBrush, QColor, QCursor, QPainterPath, QPen
from qtpy.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
)

# B-ASIC
from b_asic.graph_component import GraphComponent
from b_asic.scheduler_gui._preferences import (
    OPERATION_EXECUTION_TIME_INACTIVE,
    OPERATION_LATENCY_ACTIVE,
    OPERATION_LATENCY_INACTIVE,
)


class GraphicsComponentItem(QGraphicsItemGroup):
    """Class to represent a component in a graph."""

    _scale: float = 1.0
    """Static, changed from MainWindow."""
    _operation: GraphComponent
    _height: float
    _ports: Dict[
        str, Dict[str, Union[float, QPointF]]
    ]  # ['port-id']['latency/pos']
    _end_time: int
    _component_item: QGraphicsPathItem
    _execution_time_item: QGraphicsRectItem
    _label_item: QGraphicsSimpleTextItem
    _port_items: List[QGraphicsEllipseItem]

    def __init__(
        self,
        operation: GraphComponent,
        height: float = 0.75,
        parent: Optional[QGraphicsItem] = None,
    ):
        """
        Construct a GraphicsComponentItem. *parent* is passed to QGraphicsItemGroup's constructor.
        """
        super().__init__(parent=parent)
        self._operation = operation
        self._height = height
        self._ports = {
            k: {"latency": float(v)}
            for k, v in operation.latency_offsets.items()
        }
        self._end_time = max(operation.latency_offsets.values())
        self._port_items = []

        self.setFlag(QGraphicsItem.ItemIsMovable)  # mouse move events
        self.setFlag(QGraphicsItem.ItemIsSelectable)  # mouse move events
        # self.setAcceptHoverEvents(True)                 # mouse hover events
        self.setAcceptedMouseButtons(
            Qt.MouseButton.LeftButton
        )  # accepted buttons for movements
        self.setCursor(
            QCursor(Qt.CursorShape.OpenHandCursor)
        )  # default cursor when hovering over object

        self._make_component()

    # def sceneEvent(self, event: QEvent) -> bool:
    #     print(f'Component -->\t\t\t\t{event.type()}')
    #     # event.accept()
    #     # QApplication.sendEvent(self.scene(), event)
    #     return True

    def clear(self) -> None:
        """Sets all children's parent to None and delete the axis."""
        for item in self.childItems():
            item.setParentItem(None)
            del item

    @property
    def op_id(self) -> str:
        """Get the op-id."""
        return self._operation.graph_id

    @property
    def operation(self) -> GraphComponent:
        """Get the operation."""
        return self._operation

    @property
    def height(self) -> float:
        """
        Get or set the current component height. Setting the height to a new
        value will update the component automatically.
        """
        return self._height

    @height.setter
    def height(self, height: float) -> None:
        if self._height != height:
            self.clear()
            self._height = height
            self._make_component()

    @property
    def end_time(self) -> int:
        """Get the relative end time."""
        return self._end_time

    @property
    def event_items(self) -> List[QGraphicsItem]:
        """Returns a list of objects, that receives events."""
        return [self]

    def get_port_location(self, key) -> QPointF:
        return self.mapToParent(self._ports[key]["pos"])

    def set_active(self):
        self._set_background(OPERATION_LATENCY_ACTIVE)
        self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def set_inactive(self):
        self._set_background(OPERATION_LATENCY_INACTIVE)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def _set_background(self, color: QColor):
        brush = QBrush(color)
        self._component_item.setBrush(brush)

    def _make_component(self) -> None:
        """Makes a new component out of the stored attributes."""
        pen1 = QPen(Qt.GlobalColor.black)  # used by component outline
        pen1.setWidthF(2 / self._scale)
        # pen1.setCapStyle(Qt.RoundCap)     # Qt.FlatCap, Qt.SquareCap (default), Qt.RoundCap
        pen1.setJoinStyle(
            Qt.RoundJoin
        )  # Qt.MiterJoin, Qt.BevelJoin (default), Qt.RoundJoin, Qt.SvgMiterJoin

        brush2 = QBrush(Qt.GlobalColor.black)  # used by port filling
        pen2 = QPen(Qt.GlobalColor.black)  # used by port outline
        pen2.setWidthF(0)
        # pen2.setCosmetic(True)
        port_size = 7 / self._scale  # the diameter of a port

        execution_time = QColor(OPERATION_EXECUTION_TIME_INACTIVE)
        execution_time.setAlpha(200)  # 0-255
        pen3 = QPen()  # used by execution time outline
        pen3.setColor(execution_time)
        pen3.setWidthF(3 / self._scale)

        # component path
        def draw_component_path(keys: List[str], reversed: bool) -> None:
            """
            Draws component path and also register port positions in self._ports dictionary.
            """
            nonlocal x
            nonlocal y
            nonlocal old_x
            nonlocal old_y
            neg = -1 if reversed else 1
            for key in keys:
                # draw 1 or 2 lines
                x = self._ports[key]["latency"]
                if x != old_x:  # Draw horizontal line only
                    component_path.lineTo(x, y)  # if we need to.
                y = old_y + neg * (self._height / len(keys))
                component_path.lineTo(x, y)  # vertical line
                # register the port pos in dictionary
                port_x = x  # Port coordinates is at the center
                port_y = (
                    y - neg * abs(y - old_y) / 2
                )  # of previous vertical line.
                self._ports[key]["pos"] = QPointF(port_x, port_y)
                # update last pos
                old_x = x
                old_y = y

        # make lists of sorted keys. reverse output port list.
        input_keys = [
            key for key in self._ports.keys() if key.lower().startswith("in")
        ]
        input_keys = sorted(input_keys)
        output_keys = [
            key for key in self._ports.keys() if key.lower().startswith("out")
        ]
        output_keys = sorted(output_keys, reverse=True)

        # Set the starting position

        x = old_x = self._ports[input_keys[0]]["latency"] if input_keys else 0
        y = old_y = 0
        component_path = QPainterPath(QPointF(x, y))  # starting point

        # draw the path
        if input_keys:
            draw_component_path(input_keys, False)  # draw input side
        else:
            y = old_y = self._height

        draw_component_path(output_keys, True)  # draw output side
        component_path.closeSubpath()

        # component item
        self._component_item = QGraphicsPathItem(component_path)
        self._component_item.setPen(pen1)
        self._set_background(
            Qt.GlobalColor.lightGray
        )  # used by component filling

        # ports item
        for port_dict in self._ports.values():
            port_pos = self.mapToParent(port_dict["pos"])
            port = QGraphicsEllipseItem(
                -port_size / 2, -port_size / 2, port_size, port_size
            )  # center of circle is in origo
            port.setPen(pen2)
            port.setBrush(brush2)
            port.setPos(port_pos.x(), port_pos.y())
            self._port_items.append(port)

        # op-id/label
        self._label_item = QGraphicsSimpleTextItem(self._operation.graph_id)
        self._label_item.setScale(self._label_item.scale() / self._scale)
        center = self._component_item.boundingRect().center()
        center -= self._label_item.boundingRect().center() / self._scale
        self._label_item.setPos(self._component_item.pos() + center)

        # execution time
        if self._operation.execution_time is not None:
            self._execution_time_item = QGraphicsRectItem(
                0, 0, self._operation.execution_time, self._height
            )
            self._execution_time_item.setPen(pen3)
            # self._execution_time_item.setBrush(brush3)

        # item group, consist of component_item, port_items and execution_time_item
        self.addToGroup(self._component_item)
        for port in self._port_items:
            self.addToGroup(port)
        self.addToGroup(self._label_item)
        if self._operation.execution_time:
            self.addToGroup(self._execution_time_item)

        self.set_inactive()
