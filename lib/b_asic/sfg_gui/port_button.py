"""
Graphics connection points outside operation boxes.

The PortButton name is retained for callers of the editor's existing API.
"""

from typing import TYPE_CHECKING

from qtpy.QtCore import QPointF, QRectF, Qt, Signal
from qtpy.QtGui import QColor, QPen
from qtpy.QtWidgets import QGraphicsObject

from b_asic.port import InputPort
from b_asic.sfg_gui._preferences import PORT_STUB

if TYPE_CHECKING:
    from b_asic.operation import Operation
    from b_asic.port import Port
    from b_asic.sfg_gui.drag_button import DragButton


class PortButton(QGraphicsObject):
    """A scene-native terminal with a generous hit area and indexed tooltip."""

    moved = Signal()

    def __init__(self, name: str, operation_button: "DragButton", port: "Port") -> None:
        super().__init__(operation_button.graphicsProxyWidget())
        self._operation_button = operation_button
        self._window = operation_button._window
        self.port = port
        self.pressed = False
        self._direction_override: int | None = None
        self.setZValue(2)
        self.setCursor(Qt.CrossCursor)
        self.setAcceptHoverEvents(True)
        kind = "Input" if isinstance(port, InputPort) else "Output"
        self.setToolTip(f"{kind} {port.index}: click or drag to connect")

    @property
    def operation(self) -> "Operation":
        return self._operation_button.operation

    @property
    def direction(self) -> int:
        """Outward horizontal direction from the operation body."""
        if self._direction_override is not None:
            return self._direction_override
        left = isinstance(self.port, InputPort) != self._operation_button.is_flipped()
        return -1 if left else 1

    def set_outward_direction(self, direction: int, rotation: int = 0) -> None:
        """Orient a stub independently of whether it carries an input or output."""
        self._direction_override = direction
        self.setRotation(rotation)
        self.update()

    def scene_direction(self) -> tuple[int, int]:
        """Return the outward unit vector after operation rotation."""
        vector = self.mapToScene(QPointF(self.direction, 0)) - self.mapToScene(
            QPointF()
        )
        return round(vector.x()), round(vector.y())

    def anchor(self) -> QPointF:
        """Return the terminal center in scene coordinates."""
        return self.scenePos()

    def boundingRect(self) -> QRectF:
        return QRectF(-PORT_STUB, -9, 2 * PORT_STUB, 18)

    def paint(self, painter, option, widget=None) -> None:
        painter.setPen(QPen(QColor("#34495e"), 2))
        painter.drawLine(QPointF(-self.direction * PORT_STUB, 0), QPointF())
        # Output stubs point away from the box; input stubs point into it.
        # The parent scene transform carries these arrowheads through rotation.
        flow = -self.direction if isinstance(self.port, InputPort) else self.direction
        center = -self.direction * PORT_STUB * 2 / 3
        tip = QPointF(center + flow * 2, 0)
        painter.setPen(QPen(QColor("#34495e"), 1.5))
        painter.drawLine(QPointF(center - flow * 1.5, -2.5), tip)
        painter.drawLine(QPointF(center - flow * 1.5, 2.5), tip)
        painter.setBrush(QColor("#2980b9" if self.pressed else "white"))
        painter.drawEllipse(QRectF(-4, -4, 8, 8))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            if event.modifiers() & Qt.ControlModifier:
                self.select_port(event.modifiers())
            else:
                self._window._port_clicked(self)
            event.accept()
        else:
            self._window._cancel_connection()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._window._starting_port is not None:
            self._window._finish_connection_at(event.scenePos(), ignore=self)
        event.accept()

    def _toggle_port(self, pressed: bool = False) -> None:
        self.pressed = not pressed
        self.update()

    def select_port(self, modifiers=None) -> None:
        if not modifiers or not modifiers & Qt.ControlModifier:
            for port in self._window._pressed_ports:
                port._toggle_port(True)
            self._window._pressed_ports.clear()
        if self in self._window._pressed_ports:
            self._window._pressed_ports.remove(self)
            self._toggle_port(True)
        else:
            self._window._pressed_ports.append(self)
            self._toggle_port(False)
