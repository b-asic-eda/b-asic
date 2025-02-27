"""
B-ASIC Drag Button Module.

Contains a GUI class for drag buttons.
"""

import os.path
from typing import TYPE_CHECKING

from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QAction, QMenu, QPushButton

from b_asic.GUI._preferences import GAP, GRID, MINBUTTONSIZE, PORTHEIGHT, PORTWIDTH
from b_asic.GUI.port_button import PortButton
from b_asic.GUI.properties_window import PropertiesWindow
from b_asic.gui_utils.decorators import decorate_class, handle_error
from b_asic.operation import Operation
from b_asic.port import InputPort

if TYPE_CHECKING:
    from qtpy.QtWidgets import QGraphicsTextItem

    from b_asic.GUI.main_window import SFGMainWindow


@decorate_class(handle_error)
class DragButton(QPushButton):
    """
    Drag button class.

    This class creates a button which can be clicked, dragged and dropped.

    Parameters
    ----------
    operation : :class:`~b_asic.operation.Operation`
        The operation that the drag button corresponds to.
    show_name : bool
        Whether to show the name.
    window : SFGMainWindow
        Parent MainWindow.
    parent : unknown, optional
        Passed to QPushButton.
    *args, **kwargs
        Additional arguments are passed to QPushButton.
    """

    connectionRequested = Signal(QPushButton)
    moved = Signal()

    def __init__(
        self,
        operation: Operation,
        show_name: bool,
        window: "SFGMainWindow",
        parent=None,
    ):
        self.name = operation.name or operation.graph_id
        self._ports: list[PortButton] = []
        self.show_name = show_name
        self._window = window
        self.operation = operation
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

    def show_properties_window(self, event=None) -> None:
        """Display the properties window for the associated Operation."""
        self._properties_window = PropertiesWindow(self, self._window)
        self._properties_window.show()

    def type_name(self):
        """Return the type name of the underlying operation."""
        return self.operation.type_name()

    def add_label(self, label: "QGraphicsTextItem") -> None:
        """
        Add label to button.

        Parameters
        ----------
        label : QGraphicsTextItem
            The label to add.
        """
        self.label = label

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._m_press = True
            pos = event.pos()
            self._mouse_press_pos = pos
            self._mouse_move_pos = pos

        super().mousePressEvent(event)

    @property
    def port_list(self) -> list[PortButton]:
        """Return a list of PortButtons."""
        return self._ports

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._m_press:
            self._m_drag = True
            self.move(self.mapToParent(event.pos() - self._mouse_press_pos))
            if self in self._window._pressed_operations:
                for button in self._window._pressed_operations:
                    if button is self:
                        continue

                    button.move(button.mapToParent(event.pos() - self._mouse_press_pos))

        self._window._update()
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
        self._window._update()
        super().mouseReleaseEvent(event)

    def _flip(self, event=None):
        self._flipped = not self._flipped
        for pb in self._ports:
            if isinstance(pb.port, InputPort):
                newx = MINBUTTONSIZE - PORTWIDTH if self._flipped else 0
            else:
                newx = 0 if self._flipped else MINBUTTONSIZE - PORTWIDTH
            text = "<" if self._flipped else ">"
            pb.move(newx, pb.pos().y())
            pb.setText(text)

        self._window._update()

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
            f"{self.operation.type_name().lower()}"
            f"{'_grey.png' if self.pressed else '.png'}",
        )
        self.setIcon(QIcon(path_to_image))
        self.setIconSize(QSize(MINBUTTONSIZE, MINBUTTONSIZE))

    def is_flipped(self):
        """Return True if the button is flipped (inputs to the right)."""
        return self._flipped

    def select_button(self, modifiers=None) -> None:
        """
        Select button taking *modifiers* into account.

        Parameters
        ----------
        modifiers : optional
            Qt keyboard modifier.
        """
        if modifiers != Qt.KeyboardModifier.ControlModifier:
            for button in self._window._pressed_operations:
                button._toggle_button(button.pressed)

            self._toggle_button(self.pressed)
            self._window._pressed_operations = [self]

        else:
            self._toggle_button(self.pressed)
            if self in self._window._pressed_operations:
                self._window._pressed_operations.remove(self)
            else:
                self._window._pressed_operations.append(self)

        for arrow in self._window._arrow_ports:
            arrow.update()

    def remove(self, event=None):
        """Remove button/operation from signal flow graph."""
        self._window._logger.info("Removing operation with name " + self.operation.name)
        self._window._scene.removeItem(self._window._drag_operation_scenes[self])

        _signals = []
        for signal, ports in self._window._arrow_ports.items():
            if any(
                map(
                    lambda port: set(port).intersection(set(self._ports)),
                    ports,
                )
            ):
                self._window._logger.info(
                    "Removed signal with name: %s to/from operation: %s."
                    % (signal.signal.name, self.operation.name)
                )
                _signals.append(signal)

        for signal in _signals:
            signal.remove()

        if self in self._window._operation_to_sfg:
            self._window._logger.info(
                "Operation detected in existing SFG, removing SFG with name: "
                + self._window._operation_to_sfg[self].name
            )
            del self._window._sfg_dict[self._window._operation_to_sfg[self].name]
            self._window._operation_to_sfg = {
                op: self._window._operation_to_sfg[op]
                for op in self._window._operation_to_sfg
                if self._window._operation_to_sfg[op]
                is not self._window._operation_to_sfg[self]
            }

        for port in self._ports:
            if port in self._window._pressed_ports:
                self._window._pressed_ports.remove(port)

        if self in self._window._pressed_operations:
            self._window._pressed_operations.remove(self)

        if self in self._window._drag_operation_scenes:
            del self._window._drag_operation_scenes[self]

        if self.operation in self._window._drag_buttons:
            del self._window._drag_buttons[self.operation]

    def add_ports(self):
        """Add ports to button."""

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
            port = PortButton(">", self, op.input(i))
            port.setFixedSize(PORTWIDTH, PORTHEIGHT)
            port.move(0, dist)
            port.show()
            self._ports.append(port)

        for i, dist in enumerate(output_ports_dist):
            port = PortButton(">", self, op.output(i))
            port.setFixedSize(PORTWIDTH, PORTHEIGHT)
            port.move(MINBUTTONSIZE - PORTWIDTH, dist)
            port.show()
            self._ports.append(port)
