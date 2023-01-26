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
from b_asic.operation import Operation
from b_asic.scheduler_gui._preferences import (
    OPERATION_EXECUTION_TIME_INACTIVE,
    OPERATION_LATENCY_ACTIVE,
    OPERATION_LATENCY_INACTIVE,
)


class GraphicsComponentItem(QGraphicsItemGroup):
    """Class to represent a component in a graph."""

    _scale: float = 1.0
    """Static, changed from MainWindow."""
    _operation: Operation
    _height: float
    _ports: Dict[
        str, Dict[str, Union[float, QPointF]]
    ]  # ['port-id']['latency/pos']
    _end_time: int
    _latency_item: QGraphicsPathItem
    _execution_time_item: QGraphicsRectItem
    _label_item: QGraphicsSimpleTextItem
    _port_items: List[QGraphicsEllipseItem]

    def __init__(
        self,
        operation: Operation,
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
    def operation(self) -> Operation:
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
        self._latency_item.setBrush(brush)

    def _make_component(self) -> None:
        """Makes a new component out of the stored attributes."""
        latency_outline_pen = QPen(
            Qt.GlobalColor.black
        )  # used by component outline
        latency_outline_pen.setWidthF(2 / self._scale)
        # latency_outline_pen.setCapStyle(Qt.RoundCap)     # Qt.FlatCap, Qt.SquareCap (default), Qt.RoundCap
        latency_outline_pen.setJoinStyle(
            Qt.RoundJoin
        )  # Qt.MiterJoin, Qt.BevelJoin (default), Qt.RoundJoin, Qt.SvgMiterJoin

        port_filling_brush = QBrush(
            Qt.GlobalColor.black
        )  # used by port filling
        port_outline_pen = QPen(Qt.GlobalColor.black)  # used by port outline
        port_outline_pen.setWidthF(0)
        # port_outline_pen.setCosmetic(True)
        port_size = 7 / self._scale  # the diameter of a port

        execution_time_color = QColor(OPERATION_EXECUTION_TIME_INACTIVE)
        execution_time_color.setAlpha(200)  # 0-255
        execution_time_pen = QPen()  # used by execution time outline
        execution_time_pen.setColor(execution_time_color)
        execution_time_pen.setWidthF(3 / self._scale)

        # Set the starting position

        latency, execution_time = self._operation.get_plot_coordinates()
        latency_path = QPainterPath(
            QPointF(latency[0][0], latency[0][1] * self._height)
        )  # starting point
        for _x, _y in latency[1:]:
            latency_path.lineTo(_x, _y * self._height)
        latency_path.closeSubpath()
        self._latency_item = QGraphicsPathItem(latency_path)
        self._latency_item.setPen(latency_outline_pen)

        if execution_time:
            execution_time_path = QPainterPath(
                QPointF(
                    execution_time[0][0], execution_time[0][1] * self._height
                )
            )  # starting point
            for _x, _y in execution_time[1:]:
                execution_time_path.lineTo(_x, _y * self._height)
            execution_time_path.closeSubpath()
            self._execution_time_item = QGraphicsPathItem(execution_time_path)
            self._execution_time_item.setPen(execution_time_pen)

        # component item
        self._set_background(
            OPERATION_LATENCY_INACTIVE
        )  # used by component filling

        inputs, outputs = self._operation.get_io_coordinates()
        for i, (x, y) in enumerate(inputs):
            pos = QPointF(x, y * self._height)
            key = f"in{i}"
            self._ports[key]["pos"] = pos
            port_pos = self.mapToParent(pos)
            port = QGraphicsEllipseItem(
                -port_size / 2, -port_size / 2, port_size, port_size
            )
            port.setPen(port_outline_pen)
            port.setBrush(port_filling_brush)
            port.setPos(port_pos.x(), port_pos.y())
            self._port_items.append(port)

        for i, (x, y) in enumerate(outputs):
            pos = QPointF(x, y * self._height)
            key = f"out{i}"
            self._ports[key]["pos"] = pos
            port_pos = self.mapToParent(pos)
            port = QGraphicsEllipseItem(
                -port_size / 2, -port_size / 2, port_size, port_size
            )
            port.setPen(port_outline_pen)
            port.setBrush(port_filling_brush)
            port.setPos(port_pos.x(), port_pos.y())
            self._port_items.append(port)

        # op-id/label
        self._label_item = QGraphicsSimpleTextItem(self._operation.graph_id)
        self._label_item.setScale(self._label_item.scale() / self._scale)
        center = self._latency_item.boundingRect().center()
        center -= self._label_item.boundingRect().center() / self._scale
        self._label_item.setPos(self._latency_item.pos() + center)

        # item group, consist of component_item, port_items and execution_time_item
        self.addToGroup(self._latency_item)
        for port in self._port_items:
            self.addToGroup(port)
        self.addToGroup(self._label_item)
        if execution_time:
            self.addToGroup(self._execution_time_item)

        self.set_inactive()
