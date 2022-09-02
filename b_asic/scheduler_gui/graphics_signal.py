from typing     import Optional

from qtpy.QtWidgets import QGraphicsItem, QGraphicsPathItem
from qtpy.QtGui import QPainterPath, QPen
from qtpy.QtCore    import Qt, QPointF

# B-ASIC
from b_asic.signal import Signal
from b_asic.scheduler_gui.graphics_component_item    import GraphicsComponentItem

class GraphicsSignal(QGraphicsPathItem):
    _path: Optional[QPainterPath] = None
    _src_operation: GraphicsComponentItem
    _dest_operation: GraphicsComponentItem
    _signal: Signal
    def __init__(self,
                 src_operation: GraphicsComponentItem,
                 dest_operation: GraphicsComponentItem,
                 signal: Signal, pen: Optional[QPen] = None,
                 parent: Optional[QGraphicsItem] = None):
        super().__init__(parent=parent)
        self._src_operation = src_operation
        self._dest_operation = dest_operation
        self._signal = signal
        if pen is None:
            pen = QPen(Qt.black)
            pen.setWidthF(0.03)
        self.setPen(pen)
        self.update_path()

    def update_path(self):
        """
        Create a new path after moving connected operations.
        """
        source_point = self._src_operation.get_port_location(
            f"out{self._signal.source.index}")
        dest_point = self._dest_operation.get_port_location(
            f"in{self._signal.destination.index}")
        path = QPainterPath()
        path.moveTo(source_point)
        source_x = source_point.x()
        source_y = source_point.y()
        dest_x = dest_point.x()
        dest_y = dest_point.y()
        if abs(source_x - dest_x) <= 0.1:
            ctrl_point1 = QPointF(source_x + 0.5, source_y)
            ctrl_point2 = QPointF(source_x - 0.5, dest_y)
        else:
            mid_x = (source_x + dest_x)/2
            ctrl_point1 = QPointF(mid_x, source_y)
            ctrl_point2 = QPointF(mid_x, dest_y)

        path.cubicTo(ctrl_point1, ctrl_point2, dest_point)
        self.setPath(path)
