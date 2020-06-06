"""B-ASIC Drag Button Module.

Contains a GUI class for drag buttons.
"""

import os.path

from b_asic.GUI.properties_window import PropertiesWindow
from b_asic.GUI.utils import decorate_class, handle_error

from qtpy.QtWidgets import QPushButton, QMenu, QAction
from qtpy.QtCore import Qt, QSize, Signal
from qtpy.QtGui import QIcon


@decorate_class(handle_error)
class DragButton(QPushButton):
    """Drag button class.

    This class creates a drag button which can be clicked, dragged and dropped.
    """

    connectionRequested = Signal(QPushButton)
    moved = Signal()

    def __init__(self, name, operation, operation_path_name, is_show_name, window, parent=None):
        self.name = name
        self.ports = []
        self.is_show_name = is_show_name
        self._window = window
        self.operation = operation
        self.operation_path_name = operation_path_name
        self.clicked = 0
        self.pressed = False
        self._m_press = False
        self._m_drag = False
        self._mouse_press_pos = None
        self._mouse_move_pos = None
        super(DragButton, self).__init__(parent)

    def contextMenuEvent(self, event):
        menu = QMenu()
        properties = QAction("Properties")
        menu.addAction(properties)
        properties.triggered.connect(self.show_properties_window)

        delete = QAction("Delete")
        menu.addAction(delete)
        delete.triggered.connect(self.remove)
        menu.exec_(self.cursor().pos())

    def show_properties_window(self):
        self.properties_window = PropertiesWindow(self, self._window)
        self.properties_window.show()

    def add_label(self, label):
        self.label = label

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._m_press = True
            self._mouse_press_pos = event.pos()
            self._mouse_move_pos = event.pos()

        super(DragButton, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._m_press:
            self._m_drag = True
            self.move(self.mapToParent(event.pos() - self._mouse_press_pos))
            if self in self._window.pressed_operations:
                for button in self._window.pressed_operations:
                    if button is self:
                        continue

                    button.move(button.mapToParent(
                        event.pos() - self._mouse_press_pos))

        self._window.scene.update()
        self._window.graphic_view.update()
        super(DragButton, self).mouseMoveEvent(event)

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

        super(DragButton, self).mouseReleaseEvent(event)

    def _toggle_button(self, pressed=False):
        self.pressed = not pressed
        self.setStyleSheet(f"background-color: {'white' if not self.pressed else 'grey'}; border-style: solid;\
        border-color: black; border-width: 2px")
        path_to_image = os.path.join(os.path.dirname(
            __file__), 'operation_icons', f"{self.operation_path_name}{'_grey.png' if self.pressed else '.png'}")
        self.setIcon(QIcon(path_to_image))
        self.setIconSize(QSize(55, 55))

    def select_button(self, modifiers=None):
        if modifiers != Qt.ControlModifier:
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

    def remove(self):
        self._window.logger.info(
            f"Removing operation with name {self.operation.name}.")
        self._window.scene.removeItem(
            self._window.dragOperationSceneDict[self])

        _signals = []
        for signal, ports in self._window.signalPortDict.items():
            if any(map(lambda port: set(port).intersection(set(self._window.portDict[self])), ports)):
                self._window.logger.info(
                    f"Removed signal with name: {signal.signal.name} to/from operation: {self.operation.name}.")
                _signals.append(signal)

        for signal in _signals:
            signal.remove()

        if self in self._window.opToSFG:
            self._window.logger.info(
                f"Operation detected in existing sfg, removing sfg with name: {self._window.opToSFG[self].name}.")
            del self._window.sfg_dict[self._window.opToSFG[self].name]
            self._window.opToSFG = {
                op: self._window.opToSFG[op] for op in self._window.opToSFG if self._window.opToSFG[op] is not self._window.opToSFG[self]}

        for port in self._window.portDict[self]:
            if port in self._window.pressed_ports:
                self._window.pressed_ports.remove(port)

        if self in self._window.pressed_operations:
            self._window.pressed_operations.remove(self)

        if self in self._window.dragOperationSceneDict.keys():
            del self._window.dragOperationSceneDict[self]
