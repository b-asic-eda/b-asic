"""
B-ASIC Architecture-GUI Resource Item Module.

Contains the ResourceItem class, drawing a single
:class:`~b_asic.architecture.ProcessingElement` or
:class:`~b_asic.architecture.Memory` as a labeled box.
"""

from typing import TYPE_CHECKING

from qtpy.QtCore import QPointF, Qt
from qtpy.QtGui import QBrush, QColor, QCursor, QFont, QPen
from qtpy.QtWidgets import QGraphicsLineItem, QGraphicsRectItem, QGraphicsSimpleTextItem

from b_asic._preferences import MEMORY_COLOR, PE_COLOR
from b_asic.architecture import ProcessingElement, Resource
from b_asic.architecture_gui.process_item import HEIGHT as PROCESS_HEIGHT
from b_asic.architecture_gui.process_item import WIDTH as PROCESS_WIDTH

if TYPE_CHECKING:
    from b_asic.architecture_gui.main_window import ArchitectureMainWindow

PADDING = 8.0
PROCESS_GAP = 4.0
LABEL_HEIGHT = 22.0
PORT_TICK_LENGTH = 7.0
_DRAG_THRESHOLD = 4.0


class ResourceItem(QGraphicsRectItem):
    """
    Box representing a :class:`~b_asic.architecture.Resource` (a
    :class:`~b_asic.architecture.ProcessingElement` or
    :class:`~b_asic.architecture.Memory`).

    Parameters
    ----------
    resource : :class:`~b_asic.architecture.Resource`
        The resource this item represents.
    window : :class:`~b_asic.architecture_gui.main_window.ArchitectureMainWindow`
        Main window, used to report clicks.
    """

    def __init__(self, resource: Resource, window: "ArchitectureMainWindow") -> None:
        process_count = max(len(resource.collection), 1)
        width = (
            process_count * (PROCESS_WIDTH + PROCESS_GAP) + PROCESS_GAP + 2 * PADDING
        )
        height = PROCESS_HEIGHT + LABEL_HEIGHT + 2 * PROCESS_GAP + PADDING
        super().__init__(0, 0, width, height)
        self.resource = resource
        self._window = window

        color = PE_COLOR if isinstance(resource, ProcessingElement) else MEMORY_COLOR
        self.setBrush(QBrush(QColor(*color)))
        self.setPen(QPen(Qt.GlobalColor.black, 1.5))
        self.setZValue(0)

        label = QGraphicsSimpleTextItem(resource.entity_name, self)
        font: QFont = label.font()
        font.setBold(True)
        label.setFont(font)
        label.setPos(PADDING, PADDING / 2)

        self._add_port_markers(resource.input_count, is_input=True)
        self._add_port_markers(resource.output_count, is_input=False)

        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self._press_scene_pos = None
        self._press_item_pos = None
        self._dragging = False

    def _add_port_markers(self, count: int, is_input: bool) -> None:
        """Draw small tick marks with index labels for each input/output port."""
        width = self.rect().width()
        x = 0.0 if is_input else width
        dx = -PORT_TICK_LENGTH if is_input else PORT_TICK_LENGTH
        for i in range(max(count, 0)):
            y = self._port_y(i, max(count, 1))
            tick = QGraphicsLineItem(x, y, x + dx, y, self)
            tick.setPen(QPen(Qt.GlobalColor.black, 1.0))
            label = QGraphicsSimpleTextItem(str(i), self)
            label.setScale(0.65)
            label_width = label.boundingRect().width() * 0.65
            label.setPos(
                x + dx - (label_width + 2 if is_input else -2),
                y - label.boundingRect().height() * 0.65 / 2,
            )

    def _port_y(self, index: int, count: int) -> float:
        height = self.rect().height()
        return LABEL_HEIGHT + (height - LABEL_HEIGHT) * (index + 0.5) / count

    def input_port_pos(self, index: int) -> QPointF:
        """Local position of the *index*-th input port (left edge)."""
        return QPointF(0.0, self._port_y(index, max(self.resource.input_count, 1)))

    def output_port_pos(self, index: int) -> QPointF:
        """Local position of the *index*-th output port (right edge)."""
        return QPointF(
            self.rect().width(), self._port_y(index, max(self.resource.output_count, 1))
        )

    def process_slot_pos(self, index: int) -> QPointF:
        """Return the local position of the *index*-th process slot."""
        x = PADDING + index * (PROCESS_WIDTH + PROCESS_GAP)
        y = LABEL_HEIGHT + PROCESS_GAP
        return QPointF(x, y)

    def mousePressEvent(self, event) -> None:
        self._press_scene_pos = event.scenePos()
        self._press_item_pos = self.pos()
        self._dragging = False
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        delta = event.scenePos() - self._press_scene_pos
        if not self._dragging and delta.manhattanLength() > _DRAG_THRESHOLD:
            self._dragging = True
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        if self._dragging:
            self.setPos(self._press_item_pos + delta)
            self._window.on_resource_moved(self)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        if not self._dragging:
            self._window.show_resource_inspector(self.resource)
        self._dragging = False
        event.accept()
