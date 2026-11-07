"""Scene interaction for click-to-connect and drag-to-connect."""

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QGraphicsScene


class ConnectionScene(QGraphicsScene):
    def __init__(self, window, parent=None) -> None:
        super().__init__(parent)
        self.window = window

    def mouseMoveEvent(self, event) -> None:
        self.window._preview_connection(event.scenePos())
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if self.window._starting_port is not None and event.button() == Qt.RightButton:
            self.window._cancel_connection()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.window._cancel_connection()
            event.accept()
            return
        super().keyPressEvent(event)
