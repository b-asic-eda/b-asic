"""
B-ASIC port button module.
"""
from typing import TYPE_CHECKING

from qtpy.QtCore import QMimeData, Qt, Signal
from qtpy.QtGui import QDrag
from qtpy.QtWidgets import QMenu, QPushButton

if TYPE_CHECKING:
    from b_asic.GUI.drag_button import DragButton
    from b_asic.port import Port


class PortButton(QPushButton):
    """
    A button corresponding to a port.

    Parameters
    ----------
    name : str
    operation : :class:`~b_asic.GUI.drag_button.DragButton`
    port : :class:`~b_asic.port.Port`
    """

    connectionRequested = Signal(QPushButton)
    moved = Signal()

    def __init__(self, name: str, operation: "DragButton", port: "Port"):
        super().__init__(name, parent=operation)
        self.pressed = False
        self._window = operation._window
        self.port = port
        self.operation = operation
        self.clicked = 0
        self._m_drag = False
        self._m_press = False
        self.setAcceptDrops(True)
        self.setCursor(Qt.ArrowCursor)

        self.setStyleSheet("background-color: white")
        self.connectionRequested.connect(self._window._connect_callback)

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.addAction("Connect", lambda: self.connectionRequested.emit(self))
        menu.exec_(self.cursor().pos())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._window.mouse_pressed = True
            self.select_port(event.modifiers())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._window.mouse_pressed:
            self._window.mouse_pressed = False
            if self._window.mouse_dragging:
                self._window.mouse_dragging = False
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self._window.mouse_pressed:
            self._window.mouse_draggin = True
            self._window.starting_port = self
            data = QMimeData()
            drag = QDrag(self)
            drag.setMimeData(data)
            drag.exec()
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event):
        event.acceptProposedAction()
        self.update()
        super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        self.update()
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event):
        event.acceptProposedAction()
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        event.acceptProposedAction()
        if self != self._window.starting_port:
            self.select_port(Qt.KeyboardModifier.ControlModifier)
            self._window._connect_callback()
        self.update()
        super().dropEvent(event)

    def _toggle_port(self, pressed: bool = False):
        self.pressed = not pressed
        self.setStyleSheet(
            f"background-color: {'white' if not self.pressed else 'grey'}"
        )

    def select_port(self, modifiers=None):
        if modifiers != Qt.KeyboardModifier.ControlModifier:
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

        for signal in self._window._arrow_list:
            signal.update()
