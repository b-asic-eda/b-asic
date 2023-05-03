#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B-ASIC Scheduler-GUI Operation Item Module.

Contains the scheduler_gui OperationItem class for drawing and maintain an operation
in the schedule.
"""
from typing import TYPE_CHECKING, Dict, List, Union, cast

# QGraphics and QPainter imports
from qtpy.QtCore import QPointF, Qt
from qtpy.QtGui import QBrush, QColor, QCursor, QPainterPath, QPen
from qtpy.QtWidgets import (
    QAction,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPathItem,
    QGraphicsSimpleTextItem,
    QMenu,
)

# B-ASIC
from b_asic.graph_component import GraphID
from b_asic.operation import Operation
from b_asic.scheduler_gui._preferences import (
    OPERATION_EXECUTION_TIME_INACTIVE,
    OPERATION_HEIGHT,
    OPERATION_LATENCY_ACTIVE,
    OPERATION_LATENCY_INACTIVE,
)

if TYPE_CHECKING:
    from b_asic.scheduler_gui.scheduler_item import SchedulerItem


class OperationItem(QGraphicsItemGroup):
    f"""
    Class to represent an operation in a graph.

    Parameters
    ----------
    operation : :class:`~b_asic.operation.Operation`
        The operation.
    parent : :class:`~b_asic.scheduler_gui.scheduler_item.SchedulerItem`
        Parent passed to QGraphicsItemGroup
    height : float, default: {OPERATION_HEIGHT}
        The height of the operation.
    """

    _scale: float = 1.0
    """Static, changed from MainWindow."""
    _operation: Operation
    _height: float
    _ports: Dict[str, Dict[str, Union[float, QPointF]]]  # ['port-id']['latency/pos']
    _end_time: int
    _latency_item: QGraphicsPathItem
    _execution_time_item: QGraphicsPathItem
    _label_item: QGraphicsSimpleTextItem
    _port_items: List[QGraphicsEllipseItem]

    def __init__(
        self,
        operation: Operation,
        parent: "SchedulerItem",
        height: float = OPERATION_HEIGHT,
    ):
        """
        Construct a OperationItem. *parent* is passed to QGraphicsItemGroup's
        constructor.
        """
        super().__init__(parent=parent)
        self._operation = operation
        self._height = height
        operation._check_all_latencies_set()
        latency_offsets = cast(Dict[str, int], operation.latency_offsets)
        self._ports = {k: {"latency": float(v)} for k, v in latency_offsets.items()}
        self._end_time = max(latency_offsets.values())
        self._port_items = []

        self.setFlag(QGraphicsItem.ItemIsMovable)  # mouse move events
        self.setFlag(QGraphicsItem.ItemIsSelectable)  # mouse move events
        # self.setAcceptHoverEvents(True)                 # mouse hover events
        self.setAcceptedMouseButtons(
            Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
        )  # accepted buttons for movements
        self.setCursor(
            QCursor(Qt.CursorShape.OpenHandCursor)
        )  # default cursor when hovering over object

        self._port_filling_brush = QBrush(Qt.GlobalColor.black)
        self._port_outline_pen = QPen(Qt.GlobalColor.black)
        self._port_outline_pen.setWidthF(0)

        self._port_filling_brush_active = QBrush(OPERATION_LATENCY_ACTIVE)
        self._port_outline_pen_active = QPen(OPERATION_LATENCY_ACTIVE)
        self._port_outline_pen_active.setWidthF(0)

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
    def graph_id(self) -> GraphID:
        """The graph-id of the operation that the item corresponds to."""
        return self._operation.graph_id

    @property
    def name(self) -> str:
        """The name of the operation that the item corresponds to."""
        return self._operation.name

    @property
    def operation(self) -> Operation:
        """The operation that the item corresponds to."""
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
        """
        Set height.

        Parameters
        ----------
        height : float
            The new height.
        """
        if self._height != height:
            self.clear()
            self._height = height
            self._make_component()

    @property
    def event_items(self) -> List[QGraphicsItem]:
        """List of objects that receives events."""
        return [self]

    def get_port_location(self, key: str) -> QPointF:
        """
        Return the location specified by *key*.

        Parameters
        ----------
        key : str
            The port key.

        Returns
        -------
        The location as a QPointF.
        """
        return self.mapToParent(self._ports[key]["pos"])

    def set_active(self) -> None:
        """Set the item as active, i.e., draw it in special colors."""
        self._set_background(OPERATION_LATENCY_ACTIVE)
        self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def set_inactive(self) -> None:
        """Set the item as inactive, i.e., draw it in standard colors."""
        self._set_background(OPERATION_LATENCY_INACTIVE)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def set_port_active(self, key: str):
        item = self._ports[key]["item"]
        item.setBrush(self._port_filling_brush_active)
        item.setPen(self._port_outline_pen_active)

    def set_port_inactive(self, key: str):
        item = self._ports[key]["item"]
        item.setBrush(self._port_filling_brush)
        item.setPen(self._port_outline_pen)

    def _set_background(self, color: QColor) -> None:
        brush = QBrush(color)
        self._latency_item.setBrush(brush)

    def _make_component(self) -> None:
        """Makes a new component out of the stored attributes."""
        latency_outline_pen = QPen(Qt.GlobalColor.black)  # used by component outline
        latency_outline_pen.setWidthF(2 / self._scale)
        # latency_outline_pen.setCapStyle(Qt.RoundCap)
        # Qt.FlatCap, Qt.SquareCap (default), Qt.RoundCap
        latency_outline_pen.setJoinStyle(
            Qt.RoundJoin
        )  # Qt.MiterJoin, Qt.BevelJoin (default), Qt.RoundJoin, Qt.SvgMiterJoin

        port_size = 7 / self._scale  # the diameter of a port

        execution_time_color = QColor(OPERATION_EXECUTION_TIME_INACTIVE)
        execution_time_color.setAlpha(200)  # 0-255
        execution_time_pen = QPen()  # used by execution time outline
        execution_time_pen.setColor(execution_time_color)
        execution_time_pen.setWidthF(3 / self._scale)

        def generate_path(points):
            path = QPainterPath(
                QPointF(points[0][0], points[0][1] * self._height)
            )  # starting point
            for _x, _y in points[1:]:
                path.lineTo(_x, _y * self._height)
            path.closeSubpath()
            return path

        # Set the starting position

        latency, execution_time = self._operation.get_plot_coordinates()
        latency_path = generate_path(latency)
        self._latency_item = QGraphicsPathItem(latency_path)
        self._latency_item.setPen(latency_outline_pen)

        if execution_time:
            execution_time_path = generate_path(execution_time)
            self._execution_time_item = QGraphicsPathItem(execution_time_path)
            self._execution_time_item.setPen(execution_time_pen)

        # component item
        self._set_background(OPERATION_LATENCY_INACTIVE)  # used by component filling

        def create_ports(io_coordinates, prefix):
            for i, (x, y) in enumerate(io_coordinates):
                pos = QPointF(x, y * self._height)
                key = f"{prefix}{i}"
                self._ports[key]["pos"] = pos
                port_pos = self.mapToParent(pos)
                new_port = QGraphicsEllipseItem(
                    -port_size / 2, -port_size / 2, port_size, port_size
                )
                new_port.setPen(self._port_outline_pen)
                new_port.setBrush(self._port_filling_brush)
                new_port.setPos(port_pos.x(), port_pos.y())
                self._ports[key]["item"] = new_port

        create_ports(self._operation.get_input_coordinates(), "in")
        create_ports(self._operation.get_output_coordinates(), "out")

        # op-id/label
        self._label_item = QGraphicsSimpleTextItem(self._operation.graph_id)
        self._label_item.setScale(self._label_item.scale() / self._scale)
        center = self._latency_item.boundingRect().center()
        center -= self._label_item.boundingRect().center() / self._scale
        self._label_item.setPos(self._latency_item.pos() + center)

        # item group, consist of component_item, port_items and execution_time_item
        self.addToGroup(self._latency_item)
        for port in self._ports.values():
            self.addToGroup(port["item"])
        self.addToGroup(self._label_item)
        if execution_time:
            self.addToGroup(self._execution_time_item)

        self.set_inactive()

    def _open_context_menu(self):
        menu = QMenu()
        swap = QAction("Swap")
        menu.addAction(swap)
        swap.setEnabled(self._operation.is_swappable)
        swap.triggered.connect(self._swap_io)
        menu.exec_(self.cursor().pos())

    def _swap_io(self, event=None) -> None:
        self._operation.swap_io()
