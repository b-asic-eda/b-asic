"""
Qt button for use in preference dialogs, selecting color.
"""

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QColorDialog, QPushButton


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

    _color_changed = Signal(QColor)

    def __init__(self, color: QColor, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._color = None
        self._default = color
        self.pressed.connect(self.pick_color)

        # Set the initial/default state.
        self.set_color(self._default)

    def set_color(self, color: QColor):
        """Set new color."""
        if color != self._color:
            self._color = color
            self._color_changed.emit(color)

        if self._color:
            self.setStyleSheet("background-color: %s;" % self._color)
        else:
            self.setStyleSheet("")

    @property
    def color(self):
        """Current color."""
        return self._color

    def pick_color(self):
        """Show color-picker dialog to select color."""
        dlg = QColorDialog(self)
        if self._color:
            dlg.setCurrentColor(self._color)

        if dlg.exec_():
            self.set_color(dlg.currentColor())

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.set_color(self._default)

        return super().mousePressEvent(e)
