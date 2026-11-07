"""Shared SVG operation icons, independent of selection state."""

from functools import lru_cache
from pathlib import Path

from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QIcon, QPainter
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import QGraphicsObject

_ICON_DIRECTORY = Path(__file__).parent / "operation_icons"


def operation_svg_path(type_name: str) -> Path:
    """Resolve the vector artwork, including the fallback for custom types."""
    path = _ICON_DIRECTORY / f"{type_name.lower()}.svg"
    if not path.is_file():
        path = _ICON_DIRECTORY / "custom_operation.svg"
    return path


@lru_cache(maxsize=128)
def operation_icon(type_name: str) -> QIcon:
    """Return an icon for widget use, with a vector fallback for custom types."""
    return QIcon(str(operation_svg_path(type_name)))


class OperationSymbol(QGraphicsObject):
    """Render SVG directly in scene coordinates, without a widget pixmap cache."""

    def __init__(self, type_name: str, size: float, parent=None) -> None:
        super().__init__(parent)
        self._bounds = QRectF(-size / 2, -size / 2, size, size)
        self._renderer = QSvgRenderer(str(operation_svg_path(type_name)), self)
        self.setCacheMode(QGraphicsObject.NoCache)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setZValue(1)

    def boundingRect(self) -> QRectF:
        return QRectF(self._bounds)

    def paint(self, painter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        self._renderer.render(painter, self._bounds)
