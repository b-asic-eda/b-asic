"""Canvas navigation, independent of operation and wire interactions."""

from math import ceil, floor, hypot

from qtpy.QtCore import QPoint, QPointF, Qt
from qtpy.QtGui import QColor, QPainter, QPen, QPolygonF
from qtpy.QtWidgets import QGraphicsView

from b_asic.sfg_gui._preferences import GRID


class SFGGraphicsView(QGraphicsView):
    """Pan with the middle button before dispatching events to scene items."""

    def __init__(self, scene, parent=None) -> None:
        super().__init__(scene, parent)
        self._pan_position = None
        self._pan_cursor = None
        self._grid_visible = False
        scene.sceneRectChanged.connect(self._include_scene_rect)

    def set_grid_visible(self, visible: bool) -> None:
        """Show or hide the placement grid without changing snapping."""
        self._grid_visible = visible
        self.viewport().update()

    def drawBackground(self, painter, rect) -> None:
        super().drawBackground(painter, rect)
        if not self._grid_visible:
            return
        transform = painter.deviceTransform()
        scale = min(
            hypot(transform.m11(), transform.m12()),
            hypot(transform.m21(), transform.m22()),
        )
        if scale == 0:
            return
        # Only draw real grid points; skip whole grid intervals when zoomed out.
        step = GRID * max(1, ceil(5 / (GRID * scale)))
        points = QPolygonF(
            [
                QPointF(x * step, y * step)
                for x in range(ceil(rect.left() / step), floor(rect.right() / step) + 1)
                for y in range(ceil(rect.top() / step), floor(rect.bottom() / step) + 1)
            ]
        )
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)
        # A zero-width cosmetic pen covers one physical pixel, including on HiDPI.
        painter.setPen(QPen(QColor(105, 105, 105), 0))
        painter.drawPoints(points)
        painter.restore()

    def _include_scene_rect(self, rect) -> None:
        """Keep newly added operations reachable after expanding the pan area."""
        if not self.sceneRect().contains(rect):
            self._set_pan_rect(self.sceneRect().united(rect))

    def _set_pan_rect(self, rect) -> None:
        """Expand scroll ranges without rounding the scene's center repeatedly."""
        origin = self.mapToScene(QPoint(0, 0))
        self.setSceneRect(rect)
        offset = self.mapFromScene(origin)
        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() + offset.x()
        )
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + offset.y())

    def _extend_pan_area(self) -> None:
        # Scrollbars need room even when the graph fits entirely in the view.
        area = self.mapToScene(self.viewport().rect()).boundingRect()
        width, height = area.width(), area.height()
        if self.sceneRect().contains(
            area.adjusted(-width / 2, -height / 2, width / 2, height / 2)
        ):
            return
        self._set_pan_rect(
            self.sceneRect().united(area.adjusted(-width, -height, width, height))
        )

    def _end_pan(self) -> None:
        if self._pan_position is not None:
            self._pan_position = None
            self.viewport().setCursor(self._pan_cursor)
            self._pan_cursor = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MiddleButton:
            self._pan_position = self.mapToScene(event.pos())
            self._pan_cursor = self.viewport().cursor()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._pan_position is not None:
            if not event.buttons() & Qt.MiddleButton:
                self._end_pan()
                super().mouseMoveEvent(event)
                return
            self._extend_pan_area()
            # Pin the scene point grabbed at press time to the pointer. Adding
            # event deltas to the current scroll offsets also accumulates any
            # repositioning Qt performs when the scroll ranges change.
            delta = event.pos() - self.mapFromScene(self._pan_position)
            horizontal, vertical = self.horizontalScrollBar(), self.verticalScrollBar()
            horizontal.setValue(horizontal.value() - delta.x())
            vertical.setValue(vertical.value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MiddleButton and self._pan_position is not None:
            self._end_pan()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def focusOutEvent(self, event) -> None:
        self._end_pan()
        super().focusOutEvent(event)

    def wheelEvent(self, event) -> None:
        self._extend_pan_area()
        if event.modifiers() & Qt.ControlModifier:
            factor = max(0.01, 1 + event.angleDelta().y() / 2500)
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)
