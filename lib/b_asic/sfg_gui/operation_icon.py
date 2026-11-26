"""Shared SVG operation icons, independent of selection state."""

from functools import lru_cache
from pathlib import Path

from qtpy.QtCore import QByteArray, QRectF, Qt
from qtpy.QtGui import QIcon, QImage, QPainter, QPixmap
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import QGraphicsObject

from b_asic.gui_utils.theme import current_theme

_ICON_DIRECTORY = Path(__file__).parent / "operation_icons"
_SOURCE_COLOR = "#17212b"


def operation_svg_path(type_name: str) -> Path:
    """Resolve the vector artwork, including the fallback for custom types."""
    path = _ICON_DIRECTORY / f"{type_name.lower()}.svg"
    if not path.is_file():
        path = _ICON_DIRECTORY / "custom_operation.svg"
    return path


@lru_cache(maxsize=256)
def _themed_svg(type_name: str, color: str) -> bytes:
    source = operation_svg_path(type_name).read_text()
    return source.replace(_SOURCE_COLOR, color).encode()


@lru_cache(maxsize=256)
def _themed_icon(type_name: str, color: str) -> QIcon:
    image = QImage(64, 64, QImage.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(_themed_svg(type_name, color)))
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return QIcon(QPixmap.fromImage(image))


def operation_icon(type_name: str) -> QIcon:
    """Return a theme-aware icon, with a vector fallback for custom types."""
    return _themed_icon(type_name, current_theme().text.name())


class OperationSymbol(QGraphicsObject):
    """Render SVG directly in scene coordinates, without a widget pixmap cache."""

    def __init__(self, type_name: str, size: float, parent=None) -> None:
        super().__init__(parent)
        self._bounds = QRectF(-size / 2, -size / 2, size, size)
        self._type_name = type_name
        self._renderer = QSvgRenderer()
        self.refresh_theme()
        self.setCacheMode(QGraphicsObject.NoCache)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setZValue(1)

    def boundingRect(self) -> QRectF:
        return QRectF(self._bounds)

    def paint(self, painter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        self._renderer.render(painter, self._bounds)

    def refresh_theme(self) -> None:
        """Reload the vector glyph using the current semantic text color."""
        color = current_theme().text.name()
        self._renderer.load(QByteArray(_themed_svg(self._type_name, color)))
        self.update()
