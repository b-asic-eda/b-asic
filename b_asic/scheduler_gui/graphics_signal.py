from typing import Optional

from qtpy.QtCore import QPointF
from qtpy.QtGui import QPainterPath, QPen
from qtpy.QtWidgets import QGraphicsItem, QGraphicsPathItem

from b_asic.scheduler_gui._preferences import (
    SIGNAL_ACTIVE,
    SIGNAL_INACTIVE,
    SIGNAL_WIDTH,
)
from b_asic.scheduler_gui.graphics_component_item import GraphicsComponentItem

# B-ASIC
from b_asic.signal import Signal


class GraphicsSignal(QGraphicsPathItem):
    _path: Optional[QPainterPath] = None
    _src_operation: GraphicsComponentItem
    _dest_operation: GraphicsComponentItem
    _signal: Signal
    _active_pen: QPen
    _inactive_pen: QPen

    def __init__(
        self,
        src_operation: GraphicsComponentItem,
        dest_operation: GraphicsComponentItem,
        signal: Signal,
        parent: Optional[QGraphicsItem] = None,
    ):
        super().__init__(parent=parent)
        self._src_operation = src_operation
        self._dest_operation = dest_operation
        self._signal = signal
        self.refresh_pens()
        self.set_inactive()
        self.update_path()

    def update_path(self):
        """
        Create a new path after moving connected operations.
        """
        source_point = self._src_operation.get_port_location(
            f"out{self._signal.source.index}"
        )
        dest_point = self._dest_operation.get_port_location(
            f"in{self._signal.destination.index}"
        )
        path = QPainterPath()
        path.moveTo(source_point)
        source_x = source_point.x()
        source_y = source_point.y()
        dest_x = dest_point.x()
        dest_y = dest_point.y()
        if (
            dest_x - source_x <= -0.1
            or self.parentItem().schedule._laps[self._signal.graph_id]
        ):
            offset = 0.2  # TODO: Get from parent/axes...
            laps = self.parentItem().schedule._laps[self._signal.graph_id]
            path.lineTo(
                self.parentItem().schedule.schedule_time + offset, source_y
            )
            path.moveTo(0 + offset, dest_y)
            path.lineTo(dest_x, dest_y)
        else:
            if abs(source_x - dest_x) <= 0.1:  # "== 0"
                ctrl_point1 = QPointF(source_x + 0.5, source_y)
                ctrl_point2 = QPointF(source_x - 0.5, dest_y)
            else:
                mid_x = (source_x + dest_x) / 2
                ctrl_point1 = QPointF(mid_x, source_y)
                ctrl_point2 = QPointF(mid_x, dest_y)

            path.cubicTo(ctrl_point1, ctrl_point2, dest_point)
        self.setPath(path)

    def refresh_pens(self):
        pen = QPen(SIGNAL_ACTIVE)
        pen.setWidthF(SIGNAL_WIDTH)
        self._active_pen = pen
        pen = QPen(SIGNAL_INACTIVE)
        pen.setWidthF(SIGNAL_WIDTH)
        self._inactive_pen = pen

    def set_active(self):
        self.setPen(self._active_pen)

    def set_inactive(self):
        self.setPen(self._inactive_pen)
