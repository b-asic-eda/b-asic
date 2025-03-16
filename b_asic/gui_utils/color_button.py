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

    __slots__ = ("_color", "_default")
    _color: None | QColor
    _color_changed = Signal(QColor)

    def __init__(self, color: QColor, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._color = None
        self._default = color

        # Set the initial/default state.
        self.set_color(self._default)

    def set_color(self, color: QColor) -> None:
        """Set new color."""
        if color != self._color:
            self._color = color
            self._color_changed.emit(color)

        if self._color:
            self.setStyleSheet(f"background-color: {self._color.name()};")
        else:
            self.setStyleSheet("")

    def set_text_color(self, color: QColor) -> None:
        """Set text color."""
        self.setStyleSheet(f"color: {color.name()};")

    @property
    def color(self) -> None | QColor:
        """Current color."""
        return self._color

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.set_color(self._default)

        return super().mousePressEvent(e)
