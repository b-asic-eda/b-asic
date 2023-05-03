"""
B-ASIC Scheduler-GUI Signal Item Module.

Contains the scheduler_gui SignalItem class for drawing and maintaining a signal
in the schedule.
"""


from typing import TYPE_CHECKING, cast

from qtpy.QtCore import QPointF
from qtpy.QtGui import QPainterPath, QPen
from qtpy.QtWidgets import QGraphicsPathItem

# B-ASIC
from b_asic.scheduler_gui._preferences import (
    SCHEDULE_INDENT,
    SIGNAL_ACTIVE,
    SIGNAL_INACTIVE,
    SIGNAL_WIDTH,
    SIGNAL_WIDTH_ACTIVE,
)
from b_asic.scheduler_gui.operation_item import OperationItem
from b_asic.signal import Signal

if TYPE_CHECKING:
    from b_asic.scheduler_gui.scheduler_item import SchedulerItem


class SignalItem(QGraphicsPathItem):
    """
    Class representing a signal in the scheduler GUI.

    Parameters
    ----------
    src_operation : :class:`~b_asic.scheduler_gui.operation_item.OperationItem`
        The operation that the signal is drawn from.
    dest_operation : :class:`~b_asic.scheduler_gui.operation_item.OperationItem`
        The operation that the signal is drawn to.
    signal : :class:`~b_asic.signal.Signal`
        The signal on the SFG level.
    parent : QGraphicsItem, optional
        The parent QGraphicsItem passed to QGraphicsPathItem.
    """

    _src_operation: OperationItem
    _dest_operation: OperationItem
    _signal: Signal
    _active_pen: QPen
    _inactive_pen: QPen

    def __init__(
        self,
        src_operation: OperationItem,
        dest_operation: OperationItem,
        signal: Signal,
        parent: "SchedulerItem",
    ):
        super().__init__(parent=parent)
        self._src_operation = src_operation
        self._dest_operation = dest_operation
        self._signal = signal
        self._src_key = f"out{self._signal.source.index}"
        self._dest_key = f"in{self._signal.destination.index}"
        self._refresh_pens()
        self.set_inactive()
        self.update_path()

    def update_path(self) -> None:
        """
        Create a new path after moving connected operations.
        """
        source_point = self._src_operation.get_port_location(self._src_key)
        dest_point = self._dest_operation.get_port_location(self._dest_key)
        path = QPainterPath()
        path.moveTo(source_point)
        source_x = source_point.x()
        source_y = source_point.y()
        dest_x = dest_point.x()
        dest_y = dest_point.y()
        schedule = cast("SchedulerItem", self.parentItem()).schedule
        if dest_x - source_x <= -0.1 or schedule._laps[self._signal.graph_id]:
            offset = SCHEDULE_INDENT  # TODO: Get from parent/axes...
            path.lineTo(schedule.schedule_time + offset, source_y)
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

    def _refresh_pens(self) -> None:
        """Create pens."""
        pen = QPen(SIGNAL_ACTIVE)
        pen.setWidthF(SIGNAL_WIDTH_ACTIVE)
        self._active_pen = pen
        pen = QPen(SIGNAL_INACTIVE)
        pen.setWidthF(SIGNAL_WIDTH)
        self._inactive_pen = pen

    def set_active(self) -> None:
        """
        Set the signal color to represent that a connected operation is selected.
        """
        self.setPen(self._active_pen)
        self._src_operation.set_port_active(self._src_key)
        self._dest_operation.set_port_active(self._dest_key)

    def set_inactive(self) -> None:
        """Set the signal color to the default color."""
        self.setPen(self._inactive_pen)
        self._src_operation.set_port_inactive(self._src_key)
        self._dest_operation.set_port_inactive(self._dest_key)
