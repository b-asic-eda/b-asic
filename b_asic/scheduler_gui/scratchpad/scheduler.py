"""B-ASIC Schedule-gui Schedule Module.

Contains the Schedule class for painting an schedule.
"""
# This Python file uses the following encoding: utf-8

from qtpy import QtCore
#from qtpy import QtGui
from qtpy import QtWidgets
from qtpy.QtCore import Qt
from qtpy.QtGui import (
    QPaintEvent, QPainter, QPainterPath, QColor, QBrush, QPen, QFont, QPolygon,
    QLinearGradient)




class _Component(QtWidgets.QWidget):
    """Contains the Component of each hardware block of an Scheduler."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.MinimumExpanding
        )

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(40,120)

    def paintEvent(self, e) -> None:
        painter = QPainter(self)
        pen = QPen()
        pen.setColor(Qt.green)
        pen.setWidth(10)
        painter.setPen(pen)
        #brush.setStyle(Qt.SolidPattern)
        #rect = QtCore.QRect(0, 0, painter.device().width(), painter.device().height())
        #painter.fillRect(rect, brush)
        painter.drawRect(0, 0, painter.device().width(), painter.device().height())

# QPaintEvent is a class
class Scheduler(QtWidgets.QWidget):
    """Contains the the Scheduler painter widget placed in MainWindow."""

    _antialiasing: bool = False
    _component: _Component = []

    def __init__(self, *args, **kwargs):
        super(Scheduler, self).__init__(*args, **kwargs)

        layout = QtWidgets.QVBoxLayout()
        self._component.append(_Component())
        self._component.append(_Component())
        layout.addWidget(self._component[0])
        layout.addWidget(self._component[1])

        self.setLayout(layout)
        

    def add_component(self) -> None:
        pass


