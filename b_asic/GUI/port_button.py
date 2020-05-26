
import sys

from PySide2.QtWidgets import QPushButton, QMenu
from PySide2.QtCore import Qt, Signal


class PortButton(QPushButton):
    connectionRequested = Signal(QPushButton)
    moved = Signal()
    def __init__(self, name, operation, port, window, parent=None):
        super(PortButton, self).__init__(name, operation, parent)
        self.pressed = False
        self._window = window
        self.port = port
        self.operation = operation
        self.clicked = 0
        self._m_drag = False
        self._m_press = False

        self.setStyleSheet("background-color: white")
        self.connectionRequested.connect(self._window._connect_button)

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.addAction("Connect", lambda: self.connectionRequested.emit(self))
        menu.exec_(self.cursor().pos())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.select_port(event.modifiers())

        super(PortButton, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super(PortButton, self).mouseReleaseEvent(event)

    def _toggle_port(self, pressed=False):
        self.pressed = not pressed
        self.setStyleSheet(f"background-color: {'white' if not self.pressed else 'grey'}")

    def select_port(self, modifiers=None):
        if modifiers != Qt.ControlModifier:
            for port in self._window.pressed_ports:
                port._toggle_port(port.pressed)

            self._toggle_port(self.pressed)
            self._window.pressed_ports = [self]

        else:
            self._toggle_port(self.pressed)
            if self in self._window.pressed_ports:
                self._window.pressed_ports.remove(self)
            else:
                self._window.pressed_ports.append(self)

        for signal in self._window.signalList:
            signal.update()

