"""
Qt button for use in preference dialogs, selecting color.
"""

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QPushButton


class ColorButton(QPushButton):
    """
    Button to select color.

    Parameters
    ----------
    color : QColor
        The initial color of the button.
    *args, **kwargs
        Additional arguments are passed to QPushButton.
    """

    __slots__ = ("_color", "_default", "_text_color")
    _color: QColor | None
    _text_color: QColor | None
    _color_changed = Signal(QColor)

    def __init__(self, color: QColor, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._color = None
        self._default = color
        self._text_color = None

        # Set the initial/default state.
        self.set_color(self._default)

    def set_color(self, color: QColor) -> None:
        """Set new color."""
        if color != self._color:
            self._color = color
            self._color_changed.emit(color)

        self._update_style()

    def set_text_color(self, color: QColor) -> None:
        """Set text color."""
        self._text_color = color
        self._update_style()

    def _update_style(self) -> None:
        styles = []
        if self._color:
            styles.append(f"background-color: {self._color.name()};")
        if self._text_color:
            styles.append(f"color: {self._text_color.name()};")
        self.setStyleSheet(" ".join(styles))

    @property
    def color(self) -> QColor | None:
        """Current color."""
        return self._color

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.set_color(self._default)

        return super().mousePressEvent(e)
