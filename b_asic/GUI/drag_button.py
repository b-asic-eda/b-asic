"""
B-ASIC Drag Button Module.

Contains a GUI class for drag buttons.
"""

import os.path

from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QAction, QMenu, QPushButton

from b_asic.GUI._preferences import (
    GAP,
    GRID,
    MINBUTTONSIZE,
    PORTHEIGHT,
    PORTWIDTH,
)
from b_asic.GUI.port_button import PortButton
from b_asic.GUI.properties_window import PropertiesWindow
from b_asic.GUI.utils import decorate_class, handle_error
from b_asic.port import InputPort


@decorate_class(handle_error)
class DragButton(QPushButton):
    """
    Drag button class.

    This class creates a button which can be clicked, dragged and dropped.

    Parameters
    ----------
    name
    operation
    is_show_name
    window
    parent
    """

    connectionRequested = Signal(QPushButton)
    moved = Signal()

    def __init__(
        self,
        name,
        operation,
        is_show_name,
        window,
        parent=None,
    ):
        self.name = name
        self.ports = []
        self.is_show_name = is_show_name
        self._window = window
        self.operation = operation
        self.clicked = 0
        self.pressed = False
        self._m_press = False
        self._m_drag = False
        self._mouse_press_pos = None
        self._mouse_move_pos = None
        self._flipped = False
        self._properties_window = None
        self.label = None
        super().__init__(parent)

    def contextMenuEvent(self, event):
        menu = QMenu()
        properties = QAction("Properties")
        menu.addAction(properties)
        properties.triggered.connect(self.show_properties_window)

        delete = QAction("Delete")
        menu.addAction(delete)
        delete.triggered.connect(self.remove)

        flip = QAction("Flip horizontal")
        menu.addAction(flip)
        flip.triggered.connect(self._flip)
        menu.exec_(self.cursor().pos())

    def show_properties_window(self, event=None):
        self._properties_window = PropertiesWindow(self, self._window)
        self._properties_window.show()

    def add_label(self, label):
        self.label = label

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._m_press = True
            pos = event.pos()
            self._mouse_press_pos = pos
            self._mouse_move_pos = pos

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._m_press:
            self._m_drag = True
            self.move(self.mapToParent(event.pos() - self._mouse_press_pos))
            if self in self._window.pressed_operations:
                for button in self._window.pressed_operations:
                    if button is self:
                        continue

                    button.move(
                        button.mapToParent(event.pos() - self._mouse_press_pos)
                    )

        self._window.scene.update()
        self._window.graphic_view.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._m_press = False
        if self._m_drag:
            if self._mouse_press_pos is not None:
                moved = event.pos() - self._mouse_press_pos
                if moved.manhattanLength() > 3:
                    event.ignore()

            self._m_drag = False

        else:
            self.select_button(event.modifiers())

        # Snap
        point = self.pos()
        x = point.x()
        y = point.y()
        newx = GRID * round(x / GRID)
        newy = GRID * round(y / GRID)
        self.move(newx, newy)
        self._window.scene.update()
        self._window.graphic_view.update()
        super().mouseReleaseEvent(event)

    def _flip(self, event=None):
        self._flipped = not self._flipped
        for pb in self.ports:
            if isinstance(pb.port, InputPort):
                newx = MINBUTTONSIZE - PORTWIDTH if self._flipped else 0
            else:
                newx = 0 if self._flipped else MINBUTTONSIZE - PORTWIDTH
            text = "<" if self._flipped else ">"
            pb.move(newx, pb.pos().y())
            pb.setText(text)

        self._window.scene.update()
        self._window.graphic_view.update()

    def _toggle_button(self, pressed=False):
        self.pressed = not pressed
        self.setStyleSheet(
            f"background-color: {'white' if not self.pressed else 'grey'};"
            " border-style: solid;        border-color: black;"
            " border-width: 2px"
        )
        path_to_image = os.path.join(
            os.path.dirname(__file__),
            "operation_icons",
            f"{self.operation.type_name().lower()}{'_grey.png' if self.pressed else '.png'}",
        )
        self.setIcon(QIcon(path_to_image))
        self.setIconSize(QSize(MINBUTTONSIZE, MINBUTTONSIZE))

    def is_flipped(self):
        """Return True if the button is flipped (inputs to the right)."""
        return self._flipped

    def select_button(self, modifiers=None):
        if modifiers != Qt.KeyboardModifier.ControlModifier:
            for button in self._window.pressed_operations:
                button._toggle_button(button.pressed)

            self._toggle_button(self.pressed)
            self._window.pressed_operations = [self]

        else:
            self._toggle_button(self.pressed)
            if self in self._window.pressed_operations:
                self._window.pressed_operations.remove(self)
            else:
                self._window.pressed_operations.append(self)

        for signal in self._window.signalList:
            signal.update()

    def remove(self, event=None):
        """Remove button/operation from signal flow graph."""
        self._window.logger.info(
            f"Removing operation with name {self.operation.name}."
        )
        self._window.scene.removeItem(
            self._window.dragOperationSceneDict[self]
        )

        _signals = []
        for signal, ports in self._window.signalPortDict.items():
            if any(
                map(
                    lambda port: set(port).intersection(set(self.ports)),
                    ports,
                )
            ):
                self._window.logger.info(
                    f"Removed signal with name: {signal.signal.name} to/from"
                    f" operation: {self.operation.name}."
                )
                _signals.append(signal)

        for signal in _signals:
            signal.remove()

        if self in self._window.opToSFG:
            self._window.logger.info(
                "Operation detected in existing SFG, removing SFG with name:"
                f" {self._window.opToSFG[self].name}."
            )
            del self._window.sfg_dict[self._window.opToSFG[self].name]
            self._window.opToSFG = {
                op: self._window.opToSFG[op]
                for op in self._window.opToSFG
                if self._window.opToSFG[op] is not self._window.opToSFG[self]
            }

        for port in self._window.portDict[self]:
            if port in self._window.pressed_ports:
                self._window.pressed_ports.remove(port)

        if self in self._window.pressed_operations:
            self._window.pressed_operations.remove(self)

        if self in self._window.dragOperationSceneDict:
            del self._window.dragOperationSceneDict[self]

        if self.operation in self._window.operationDragDict:
            del self._window.operationDragDict[self.operation]

    def add_ports(self):
        def _determine_port_distance(opheight, ports):
            """
            Determine the distance between each port on the side of an operation.
            The method returns the distance that each port should have from 0.
            """
            return (
                [(opheight - PORTHEIGHT) // 2]
                if ports == 1
                else [(PORTHEIGHT + GAP) * no for no in range(ports)]
            )

        op = self.operation
        height = self.height()
        output_ports_dist = _determine_port_distance(height, op.output_count)
        input_ports_dist = _determine_port_distance(height, op.input_count)
        for i, dist in enumerate(input_ports_dist):
            port = PortButton(">", self, op.input(i), self._window)
            port.setFixedSize(PORTWIDTH, PORTHEIGHT)
            port.move(0, dist)
            port.show()
            self.ports.append(port)

        for i, dist in enumerate(output_ports_dist):
            port = PortButton(">", self, op.output(i), self._window)
            port.setFixedSize(PORTWIDTH, PORTHEIGHT)
            port.move(MINBUTTONSIZE - PORTWIDTH, dist)
            port.show()
            self.ports.append(port)
