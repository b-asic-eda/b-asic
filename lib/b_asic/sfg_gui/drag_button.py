"""
B-ASIC Drag Button Module.

Contains a GUI class for drag buttons.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import QPointF, QSize, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QAction, QMenu, QPushButton

from b_asic.gui_utils.decorators import decorate_class, handle_error
from b_asic.operation import Operation
from b_asic.port import InputPort
from b_asic.sfg_gui._preferences import GRID, MINBUTTONSIZE
from b_asic.sfg_gui.port_button import PortButton
from b_asic.sfg_gui.properties_window import PropertiesWindow
from b_asic.types import TypeName

if TYPE_CHECKING:
    from qtpy.QtWidgets import QGraphicsTextItem

    from b_asic.sfg_gui.main_window import SFGMainWindow


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
    window : :class:`~b_asic.sfg_gui.main_window.SFGMainWindow`
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
    ) -> None:
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
        self._rotation = 0
        self._properties_window = None
        self.label = None
        super().__init__(parent)

    def contextMenuEvent(self, event) -> None:
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
        menu.addAction("Rotate 90° clockwise", self.rotate_clockwise)
        menu.addAction("Rotate 90° counterclockwise", self.rotate_counterclockwise)
        menu.exec_(self.cursor().pos())

    def show_properties_window(self, event=None) -> None:
        """Display the properties window for the associated Operation."""
        self._properties_window = PropertiesWindow(self, self._window)
        self._properties_window.show()

    def type_name(self) -> TypeName:
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
        self._position_label()

    def mousePressEvent(self, event) -> None:
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

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and self._m_press:
            self._m_drag = True
            proxy = self.graphicsProxyWidget()
            delta = proxy.mapToScene(QPointF(event.pos())) - proxy.mapToScene(
                QPointF(self._mouse_press_pos)
            )
            buttons = (
                self._window._pressed_operations
                if self in self._window._pressed_operations
                else [self]
            )
            for button in buttons:
                item = button.graphicsProxyWidget()
                item.setPos(item.pos() + delta)

        self._window._update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
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

    def _flip(self, event=None) -> None:
        self._flipped = not self._flipped
        self._position_ports()

        self._window._update()

    def rotation_angle(self) -> int:
        """Return the clockwise rotation in degrees."""
        return self._rotation

    def set_rotation(self, angle: int) -> None:
        """Rotate the operation and its terminals in quarter turns."""
        if angle % 90:
            raise ValueError("Operation rotation must be a multiple of 90 degrees")
        self._rotation = angle % 360
        proxy = self.graphicsProxyWidget()
        proxy.setTransformOriginPoint(proxy.boundingRect().center())
        proxy.setRotation(self._rotation)
        self._position_label()
        self._window._update()

    def rotate_clockwise(self, event=None) -> None:
        self.set_rotation(self._rotation + 90)

    def rotate_counterclockwise(self, event=None) -> None:
        self.set_rotation(self._rotation - 90)

    def _position_label(self) -> None:
        if self.label is None:
            return
        proxy = self.graphicsProxyWidget()
        self.label.setTransformOriginPoint(QPointF())
        self.label.setRotation(-self._rotation)
        rect = proxy.sceneBoundingRect()
        position = QPointF(
            rect.center().x() - self.label.boundingRect().width() / 2,
            rect.top() - self.label.boundingRect().height(),
        )
        self.label.setPos(proxy.mapFromScene(position))

    def _toggle_button(self, pressed=False) -> None:
        self.pressed = not pressed
        self.setStyleSheet(
            f"background-color: {'white' if not self.pressed else 'grey'};"
            " border-style: solid;        border-color: black;"
            " border-width: 2px"
        )
        path_to_image = (
            Path(__file__).parent
            / "operation_icons"
            / f"{self.operation.type_name().lower()}{'_grey' if self.pressed else ''}.png"
        )
        self.setIcon(QIcon(str(path_to_image)))
        self.setIconSize(QSize(MINBUTTONSIZE, MINBUTTONSIZE))

    def is_flipped(self) -> bool:
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

    def remove(self, event=None) -> None:
        """Remove button/operation from signal flow graph."""
        self._window._logger.info(
            "Removing operation with name %s", self.operation.name
        )
        self._window._cancel_connection()
        self._window._scene.removeItem(self._window._drag_operation_scenes[self])

        _signals = []
        for signal, ports in self._window._arrow_ports.items():
            if any(set(port).intersection(set(self._ports)) for port in ports):
                self._window._logger.info(
                    "Removed signal with name: %s to/from operation: %s",
                    signal.signal.name,
                    self.operation.name,
                )
                _signals.append(signal)

        for signal in _signals:
            signal.remove()

        self._window._invalidate_sfg(self)

        for port in self._ports:
            if port in self._window._pressed_ports:
                self._window._pressed_ports.remove(port)

        if self in self._window._pressed_operations:
            self._window._pressed_operations.remove(self)

        if self in self._window._drag_operation_scenes:
            del self._window._drag_operation_scenes[self]

        self._window._ports.pop(self, None)
        self._window._update()

        if self.operation in self._window._drag_buttons:
            del self._window._drag_buttons[self.operation]

    def add_ports(self) -> None:
        """Add external terminals as children of the operation's scene proxy."""
        for port in (*self.operation.inputs, *self.operation.outputs):
            self._ports.append(PortButton("", self, port))
        self._position_ports()

    def _position_ports(self) -> None:
        for port in self._ports:
            ports = (
                self.operation.inputs
                if isinstance(port.port, InputPort)
                else self.operation.outputs
            )
            y = self.height() * (port.port.index + 1) / (len(ports) + 1)
            x = -12 if port.direction < 0 else self.width() + 12
            port.setPos(x, y)
            port.moved.emit()
