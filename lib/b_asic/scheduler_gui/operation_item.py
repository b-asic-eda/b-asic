#!/usr/bin/env python3
"""
B-ASIC Scheduler-GUI Operation Item Module.

Contains the scheduler_gui OperationItem class for drawing and maintain an operation
in the schedule.
"""

import math
from typing import TYPE_CHECKING, cast

# QGraphics and QPainter imports
from qtpy.QtCore import QPointF, QRectF, Qt
from qtpy.QtGui import QBrush, QColor, QCursor, QFont, QPainterPath, QPen
from qtpy.QtWidgets import (
    QAction,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPathItem,
    QGraphicsSimpleTextItem,
    QMenu,
)

from b_asic.graph_component import GraphID

# B-ASIC
from b_asic.gui_utils.icons import get_icon
from b_asic.operation import Operation
from b_asic.scheduler_gui._preferences import (
    ACTIVE_COLOR_TYPE,
    EXECUTION_TIME_COLOR_TYPE,
    LATENCY_COLOR_TYPE,
    OPERATION_HEIGHT,
    SIGNAL_COLOR_TYPE,
    SIGNAL_WARNING_COLOR_TYPE,
)
from b_asic.special_operations import Input, Output
from b_asic.types import ShapeCoordinates
from b_asic.utility_operations import Sink

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
    _ports: dict[str, dict[str, float | QPointF]]  # ['port-id']['latency/pos']
    _end_time: int
    _latency_path: QPainterPath
    _execution_time_path: QPainterPath | None
    _latency_item: QGraphicsPathItem
    _execution_time_item: QGraphicsPathItem
    _label_item: QGraphicsSimpleTextItem
    _label_center: QPointF
    _port_items: list[QGraphicsEllipseItem]
    _port_number_items: list[QGraphicsSimpleTextItem]
    _port_number_items_by_key: dict[str, QGraphicsSimpleTextItem]
    _port_cycle_offsets: dict[str, float]
    _inactive_color: QColor = LATENCY_COLOR_TYPE.DEFAULT

    def __init__(
        self,
        operation: Operation,
        parent: "SchedulerItem",
        height: float = OPERATION_HEIGHT,
    ) -> None:
        """
        Construct a OperationItem.

        *parent* is passed to QGraphicsItemGroup's constructor.
        """
        super().__init__(parent=parent)
        self._operation = operation
        self._height = height
        operation._check_all_latencies_set()
        latency_offsets = cast(dict[str, int], operation.latency_offsets)
        self._ports = {k: {"latency": float(v)} for k, v in latency_offsets.items()}
        self._end_time = max(latency_offsets.values())
        self._execution_time_path = None
        self._port_items = []
        self._port_number_items = []
        self._port_number_items_by_key = {}
        self._port_cycle_offsets = {}
        self._parent = parent

        self.setFlag(QGraphicsItem.ItemIsMovable)  # mouse move events
        self.setFlag(QGraphicsItem.ItemIsSelectable)  # mouse move events
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        # self.setAcceptHoverEvents(True)                 # mouse hover events
        self.setAcceptedMouseButtons(
            Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
        )  # accepted buttons for movements
        self.setCursor(
            QCursor(Qt.CursorShape.OpenHandCursor)
        )  # default cursor when hovering over object

        if SIGNAL_COLOR_TYPE.changed:
            self._port_filling_brush = QBrush(SIGNAL_COLOR_TYPE.current_color)
            self._port_outline_pen = QPen(SIGNAL_COLOR_TYPE.current_color)
        else:
            self._port_filling_brush = QBrush(SIGNAL_COLOR_TYPE.DEFAULT)
            self._port_outline_pen = QPen(SIGNAL_COLOR_TYPE.DEFAULT)
        self._port_outline_pen.setWidthF(0)

        if ACTIVE_COLOR_TYPE.changed:
            self._port_filling_brush_active = QBrush(ACTIVE_COLOR_TYPE.current_color)
            self._port_outline_pen_active = QPen(ACTIVE_COLOR_TYPE.current_color)
        else:
            self._port_filling_brush_active = QBrush(ACTIVE_COLOR_TYPE.DEFAULT)
            self._port_outline_pen_active = QPen(ACTIVE_COLOR_TYPE.DEFAULT)
        self._port_outline_pen_active.setWidthF(0)

        if SIGNAL_WARNING_COLOR_TYPE.changed:
            self._port_filling_brush_warning = QBrush(
                SIGNAL_WARNING_COLOR_TYPE.current_color
            )
            self._port_outline_pen_warning = QPen(
                SIGNAL_WARNING_COLOR_TYPE.current_color
            )
        else:
            self._port_filling_brush_warning = QBrush(SIGNAL_WARNING_COLOR_TYPE.DEFAULT)
            self._port_outline_pen_warning = QPen(SIGNAL_WARNING_COLOR_TYPE.DEFAULT)
        self._port_outline_pen_warning.setWidthF(0)

        self._make_component()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._update_cycle_paths()
        return super().itemChange(change, value)

    # def sceneEvent(self, event: QEvent) -> bool:
    #     print(f'Component -->\t\t\t\t{event.type()}')
    #     # event.accept()
    #     # QApplication.sendEvent(self.scene(), event)
    #     return True

    def clear(self) -> None:
        """Set all children's parent to None and delete the axis."""
        for item in self.childItems():
            item.setParentItem(None)
            del item

    @property
    def graph_id(self) -> GraphID:
        """GraphID of the operation that the item corresponds to."""
        return self._operation.graph_id

    @property
    def name(self) -> str:
        """Name of the operation that the item corresponds to."""
        return self._operation.name

    @property
    def operation(self) -> Operation:
        """The operation that the item corresponds to."""
        return self._operation

    @property
    def height(self) -> float:
        """
        Get or set the current component height.

        Setting the height to a new value will update the component automatically.
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
    def event_items(self) -> list[QGraphicsItem]:
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
        pos = QPointF(cast(QPointF, self._ports[key]["pos"]))
        pos += QPointF(self._port_cycle_offsets.get(key, 0), 0)
        return self.mapToParent(pos)

    def set_active(self) -> None:
        """Set the item as active, i.e., draw it in special colors."""
        if ACTIVE_COLOR_TYPE.changed:
            self._set_background(ACTIVE_COLOR_TYPE.current_color)
        else:
            self._set_background(ACTIVE_COLOR_TYPE.DEFAULT)
        self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def set_inactive(self) -> None:
        """Set the item as inactive, i.e., draw it in standard colors."""
        if LATENCY_COLOR_TYPE.changed:
            self._set_background(self._inactive_color)
        else:
            self._set_background(LATENCY_COLOR_TYPE.DEFAULT)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def set_font(self, font: QFont) -> None:
        """Set the items font settings to *font*."""
        self._label_item.prepareGeometryChange()
        self._label_item.setFont(font)
        self._position_label()

    def _position_label(self) -> None:
        center = QPointF(self._label_center)
        center -= self._label_item.boundingRect().center() / self._scale
        self._label_item.setPos(self._latency_item.pos() + center)

    def set_font_color(self, color: QColor) -> None:
        """Set the items font color settings to *color*."""
        self._label_item.prepareGeometryChange()
        self._label_item.setBrush(color)

    def set_show_port_numbers(self, port_number: bool = True) -> None:
        """Set if port numbers are shown."""
        for item in self._port_number_items:
            item.setVisible(port_number)

    def set_port_active(self, key: str) -> None:
        """Set the port as active, i.e., draw it in special colors."""
        item = cast(QGraphicsEllipseItem, self._ports[key]["item"])
        if ACTIVE_COLOR_TYPE.changed:
            self._port_filling_brush_active = QBrush(ACTIVE_COLOR_TYPE.current_color)
            self._port_outline_pen_active = QPen(ACTIVE_COLOR_TYPE.current_color)
        else:
            self._port_filling_brush_active = QBrush(ACTIVE_COLOR_TYPE.DEFAULT)
            self._port_outline_pen_active = QPen(ACTIVE_COLOR_TYPE.DEFAULT)

        self._port_outline_pen_active.setWidthF(0)
        item.setBrush(self._port_filling_brush_active)
        item.setPen(self._port_outline_pen_active)

    def set_port_inactive(self, key: str, warning: bool = False) -> None:
        """Set the port as inactive, i.e., draw it in standard colors."""
        item = cast(QGraphicsEllipseItem, self._ports[key]["item"])
        item.setBrush(
            self._port_filling_brush_warning if warning else self._port_filling_brush
        )
        item.setPen(
            self._port_outline_pen_warning if warning else self._port_outline_pen
        )

    def _set_background(self, color: QColor) -> None:
        brush = QBrush(color)
        self._latency_item.setBrush(brush)

    def _make_component(self) -> None:
        """Make a new component out of the stored attributes."""
        latency_outline_pen = QPen(Qt.GlobalColor.black)  # used by component outline
        latency_outline_pen.setWidthF(2 / self._scale)
        # latency_outline_pen.setCapStyle(Qt.RoundCap)
        # Qt.FlatCap, Qt.SquareCap (default), Qt.RoundCap
        latency_outline_pen.setJoinStyle(
            Qt.RoundJoin
        )  # Qt.MiterJoin, Qt.BevelJoin (default), Qt.RoundJoin, Qt.SvgMiterJoin

        port_size = 7 / self._scale  # the diameter of a port

        if EXECUTION_TIME_COLOR_TYPE.changed:
            execution_time_color = QColor(EXECUTION_TIME_COLOR_TYPE.current_color)
        else:
            execution_time_color = QColor(EXECUTION_TIME_COLOR_TYPE.DEFAULT)
        execution_time_color.setAlpha(200)  # 0-255
        execution_time_pen = QPen()  # used by execution time outline
        execution_time_pen.setColor(execution_time_color)
        execution_time_pen.setWidthF(3 / self._scale)

        def generate_path(points: ShapeCoordinates) -> QPainterPath:
            """Create a QPainterPath for the *points*."""
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
        self._latency_path = latency_path
        self._latency_item = QGraphicsPathItem(latency_path)
        self._latency_item.setPen(latency_outline_pen)

        if execution_time:
            execution_time_path = generate_path(execution_time)
            self._execution_time_path = execution_time_path
            self._execution_time_item = QGraphicsPathItem(execution_time_path)
            self._execution_time_item.setPen(execution_time_pen)

        # component item
        self._set_background(LATENCY_COLOR_TYPE.DEFAULT)  # used by component filling

        def create_ports(io_coordinates: ShapeCoordinates, prefix: str) -> None:
            """Draw port markers."""
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
                # Add port numbers
                port_item = QGraphicsSimpleTextItem(str(i))
                port_item.setScale(port_item.scale() / self._scale)
                center = port_item.boundingRect().center() / self._scale
                x_offset = center.x() if prefix == "in" else -3 * center.x()
                port_item.setPos(QPointF(x + x_offset, y * self._height - center.y()))
                self._port_number_items.append(port_item)
                self._port_number_items_by_key[key] = port_item

        create_ports(self._operation.get_input_coordinates(), "in")
        create_ports(self._operation.get_output_coordinates(), "out")

        # op-id/label
        self._label_item = QGraphicsSimpleTextItem(self._operation.graph_id)
        self._label_item.setScale(self._label_item.scale() / self._scale)
        self._label_center = self._latency_item.boundingRect().center()
        self._position_label()

        # item group, consist of component_item, port_items and execution_time_item
        self.addToGroup(self._latency_item)
        for port in self._ports.values():
            self.addToGroup(port["item"])
        self.addToGroup(self._label_item)
        for item in self._port_number_items:
            self.addToGroup(item)
        if execution_time:
            self.addToGroup(self._execution_time_item)

        self.set_inactive()
        self._update_cycle_paths()

    def _update_cycle_paths(self) -> None:
        schedule = self._parent.schedule
        start_time = self.x() - self._parent._x_axis_indent
        period = schedule.schedule_time if schedule.cyclic else 0
        at_left_boundary = (
            period > 0
            and math.isclose(start_time, period, abs_tol=1e-9)
            and not isinstance(self._operation, Output | Sink)
        )
        preserve_boundary_shape = (
            isinstance(self._operation, Input)
            and math.isclose(start_time, 0, abs_tol=1e-9)
        ) or (
            isinstance(self._operation, Output | Sink)
            and math.isclose(start_time, period, abs_tol=1e-9)
        )

        if at_left_boundary:
            latency_fragments = [self._latency_path.translated(-period, 0)]
        elif preserve_boundary_shape or period <= 0:
            latency_fragments = [self._latency_path]
        else:
            latency_fragments = self._cycle_path_fragments(
                self._latency_path, start_time, period
            )
        self._update_port_positions(start_time, period)

        self._latency_item.setPath(self._combine_path_fragments(latency_fragments))
        largest_fragment = max(
            latency_fragments,
            key=lambda fragment: fragment.boundingRect().width(),
            default=self._latency_path,
        )
        self._label_center = largest_fragment.boundingRect().center()
        self._position_label()

        if self._execution_time_path is not None:
            if at_left_boundary:
                self._execution_time_item.setPath(
                    self._execution_time_path.translated(-period, 0)
                )
            elif preserve_boundary_shape or period <= 0:
                self._execution_time_item.setPath(self._execution_time_path)
            else:
                self._execution_time_item.setPath(
                    self._path_with_cycle_wrap(
                        self._execution_time_path, start_time, period
                    )
                )

    def _update_port_positions(self, start_time: float, period: int) -> None:
        for key, port in self._ports.items():
            pos = cast(QPointF, port["pos"])
            offset = 0.0
            port_time = start_time + pos.x()
            if period > 0:
                if math.isclose(start_time, period, abs_tol=1e-9) and not isinstance(
                    self._operation, Output | Sink
                ):
                    offset = -period
                elif port_time > period:
                    cycles = math.ceil((port_time - period) / period)
                    wrapped_time = port_time - cycles * period
                    if wrapped_time >= 1:
                        offset = -cycles * period
                elif port_time < 0:
                    cycles = math.ceil(-port_time / period)
                    wrapped_time = port_time + cycles * period
                    if wrapped_time <= period - 1:
                        offset = cycles * period

            self._port_cycle_offsets[key] = offset
            port_item = cast(QGraphicsEllipseItem, port["item"])
            port_item.setPos(pos.x() + offset, pos.y())

            port_number = self._port_number_items_by_key[key]
            center = port_number.boundingRect().center() / self._scale
            x_offset = center.x() if key.startswith("in") else -3 * center.x()
            port_number.setPos(
                QPointF(pos.x() + x_offset + offset, pos.y() - center.y())
            )

    @staticmethod
    def _cycle_path_fragments(
        path: QPainterPath, start_time: float, period: int
    ) -> list[QPainterPath]:
        bounds = path.boundingRect()
        clip = QRectF(
            -start_time,
            bounds.top() - 1,
            period,
            bounds.height() + 2,
        )
        clip_path = QPainterPath()
        clip_path.addRect(clip)
        first_cycle = math.ceil((-start_time - bounds.right()) / period)
        last_cycle = math.floor((period - start_time - bounds.left()) / period)
        fragments = []

        for cycle in range(first_cycle, last_cycle + 1):
            cycle_path = path.translated(cycle * period, 0)
            fragment = (
                cycle_path
                if clip.contains(cycle_path.boundingRect())
                else cycle_path.intersected(clip_path)
            )
            if not fragment.isEmpty() and (
                bounds.width() == 0 or fragment.boundingRect().width() > 0
            ):
                fragments.append(fragment)

        return fragments

    @staticmethod
    def _combine_path_fragments(fragments: list[QPainterPath]) -> QPainterPath:
        combined_path = QPainterPath()
        for fragment in fragments:
            combined_path.addPath(fragment)
        return combined_path

    @staticmethod
    def _path_with_cycle_wrap(
        path: QPainterPath, start_time: float, period: int
    ) -> QPainterPath:
        return OperationItem._combine_path_fragments(
            OperationItem._cycle_path_fragments(path, start_time, period)
        )

    def _open_context_menu(self) -> None:
        """Create and open context menu."""
        menu = QMenu()
        swap = QAction(get_icon("swap"), "Swap")
        menu.addAction(swap)
        swap.setEnabled(self._operation.is_swappable)
        swap.triggered.connect(self._swap_io)
        slacks = self._parent.schedule.slacks(self._operation.graph_id)
        asap = QAction(get_icon("asap"), "Move as soon as possible")
        asap.triggered.connect(self._move_asap)
        asap.setEnabled(slacks[0] > 0)
        menu.addAction(asap)
        alap = QAction(get_icon("alap"), "Move as late as possible")
        alap.triggered.connect(self._move_alap)
        alap.setEnabled(slacks[1] > 0)
        menu.addAction(alap)
        menu.addSeparator()
        execution_time_plot = QAction(
            f"Show execution times for {self._operation.type_name()}"
        )
        menu.addAction(execution_time_plot)
        execution_time_plot.triggered.connect(self._execution_time_plot)
        total_execution_time_plot = QAction(
            f"Show total execution times for {self._operation.type_name()}"
        )
        menu.addAction(total_execution_time_plot)
        total_execution_time_plot.triggered.connect(self._total_execution_time_plot)
        menu.exec_(self.cursor().pos())

    def _swap_io(self, event=None) -> None:
        self._parent._swap_io_of_operation(self._operation.graph_id)

    def _execution_time_plot(self, event=None) -> None:
        self._parent._execution_time_plot(self._operation.type_name())

    def _total_execution_time_plot(self, event=None) -> None:
        self._parent._total_execution_time_plot(self._operation.type_name())

    def _move_asap(self, event=None) -> None:
        graph_id = self._operation.graph_id
        self._parent.schedule.move_operation_asap(graph_id)
        print(f"schedule.move_operation_asap({graph_id!r})")
        self._parent._signals.reopen.emit()

    def _move_alap(self, event=None) -> None:
        graph_id = self._operation.graph_id
        self._parent.schedule.move_operation_alap(graph_id)
        print(f"schedule.move_operation_alap({graph_id!r})")
        self._parent._signals.reopen.emit()
