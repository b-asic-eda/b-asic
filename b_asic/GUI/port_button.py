"""
B-ASIC port button module.
"""

from typing import TYPE_CHECKING

from qtpy.QtCore import QMimeData, Qt, Signal
from qtpy.QtGui import QDrag
from qtpy.QtWidgets import QMenu, QPushButton

if TYPE_CHECKING:
    from b_asic.GUI.drag_button import DragButton
    from b_asic.operation import Operation
    from b_asic.port import Port


class PortButton(QPushButton):
    """
    A button corresponding to a port.

    Parameters
    ----------
    name : str
        The name of the button.
    operation_button : :class:`~b_asic.GUI.drag_button.DragButton`
        The parent DragButton.
    port : :class:`~b_asic.port.Port`
        The SFG Port.
    """

    connectionRequested = Signal(QPushButton)
    moved = Signal()

    def __init__(self, name: str, operation_button: "DragButton", port: "Port") -> None:
        super().__init__(name, parent=operation_button)
        self.pressed = False
        self._window = operation_button._window
        self.port = port
        self._operation_button = operation_button
        self._m_drag = False
        self._m_press = False
        self.setAcceptDrops(True)
        self.setCursor(Qt.ArrowCursor)

        self.setStyleSheet("background-color: white")
        self.connectionRequested.connect(self._window._connect_callback)

    @property
    def operation(self) -> "Operation":
        """Operation associated with PortButton."""
        return self._operation_button.operation

    def contextMenuEvent(self, event) -> None:
        menu = QMenu()
        menu.addAction("Connect", lambda: self.connectionRequested.emit(self))
        menu.exec_(self.cursor().pos())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._window._mouse_pressed = True
            self.select_port(event.modifiers())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._window._mouse_pressed:
            self._window._mouse_pressed = False
            if self._window._mouse_dragging:
                self._window._mouse_dragging = False
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._window._mouse_pressed:
            self._window._mouse_dragging = True
            self._window._starting_port = self
            data = QMimeData()
            drag = QDrag(self)
            drag.setMimeData(data)
            drag.exec()
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event) -> None:
        event.acceptProposedAction()
        self.update()
        super().dragEnterEvent(event)

    def dragLeaveEvent(self, event) -> None:
        self.update()
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction()
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        event.acceptProposedAction()
        if self != self._window._starting_port:
            self.select_port(Qt.KeyboardModifier.ControlModifier)
            self._window._connect_callback()
        self.update()
        super().dropEvent(event)

    def _toggle_port(self, pressed: bool = False) -> None:
        self.pressed = not pressed
        self.setStyleSheet(
            f"background-color: {'white' if not self.pressed else 'grey'}"
        )

    def select_port(self, modifiers=None) -> None:
        """
        Select the port taking *modifiers* into account.

        Parameters
        ----------
        modifiers : optional
            Qt keyboard modifier.
        """
        if modifiers != Qt.KeyboardModifier.ControlModifier:
            for port in self._window._pressed_ports:
                port._toggle_port(port.pressed)

            self._toggle_port(self.pressed)
            self._window._pressed_ports = [self]
        else:
            self._toggle_port(self.pressed)
            if self in self._window._pressed_ports:
                self._window._pressed_ports.remove(self)
            else:
                self._window._pressed_ports.append(self)

        for arrow in self._window._arrow_ports:
            arrow.update()
