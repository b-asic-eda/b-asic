"""
B-ASIC Architecture-GUI Process Item Module.

Contains the ProcessItem class, a draggable object representing a single
:class:`~b_asic.process.Process` assigned to a resource.
"""

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtGui import QBrush, QColor, QCursor, QPen
from qtpy.QtWidgets import QGraphicsRectItem, QGraphicsSimpleTextItem

from b_asic.process import Process

if TYPE_CHECKING:
    from b_asic.architecture_gui.main_window import ArchitectureMainWindow

WIDTH = 70.0
HEIGHT = 26.0
_DRAG_THRESHOLD = 4.0


class ProcessItem(QGraphicsRectItem):
    """
    Draggable object representing a process assigned to a resource.

    Parameters
    ----------
    process : :class:`~b_asic.process.Process`
        The process this item represents.
    resource_name : str
        Entity name of the resource that currently owns *process*.
    window : :class:`~b_asic.architecture_gui.main_window.ArchitectureMainWindow`
        Main window, used to report clicks and drops.
    """

    def __init__(
        self,
        process: Process,
        resource_name: str,
        window: "ArchitectureMainWindow",
    ) -> None:
        super().__init__(0, 0, WIDTH, HEIGHT)
        self.process = process
        self.resource_name = resource_name
        self._window = window

        self.setBrush(QBrush(QColor("white")))
        self.setPen(QPen(Qt.GlobalColor.black))
        self.setZValue(5)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

        label = QGraphicsSimpleTextItem(process.name, self)
        label.setPos(4, 5)

        self._press_scene_pos = None
        self._press_item_pos = None
        self._dragging = False

    def mousePressEvent(self, event) -> None:
        self._press_scene_pos = event.scenePos()
        self._press_item_pos = self.pos()
        self._dragging = False
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        delta = event.scenePos() - self._press_scene_pos
        if not self._dragging and delta.manhattanLength() > _DRAG_THRESHOLD:
            self._dragging = True
            self.setZValue(20)
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        if self._dragging:
            self.setPos(self._press_item_pos + delta)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        was_dragging = self._dragging
        self._dragging = False
        if was_dragging:
            center = self.sceneBoundingRect().center()
            target = self._window.resource_item_at(center)
            if target is not None and target.resource.entity_name != self.resource_name:
                self._window.try_move_process(
                    self.process, self.resource_name, target.resource.entity_name
                )
            else:
                # Dropped on its own resource or outside any resource: snap back.
                self._window.snap_process_back(self)
        else:
            self._window.show_process_inspector(self.process, self.resource_name)
        event.accept()
