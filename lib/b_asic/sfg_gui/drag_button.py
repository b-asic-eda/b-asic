"""
B-ASIC Drag Button Module.

Contains a GUI class for drag buttons.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from qtpy.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from qtpy.QtGui import QIcon, QPainterPath, QPen
from qtpy.QtWidgets import (
    QAction,
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QMenu,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QStylePainter,
)

from b_asic.gui_utils.decorators import decorate_class, handle_error
from b_asic.operation import Operation
from b_asic.port import InputPort, OutputPort
from b_asic.sfg import SFG
from b_asic.sfg_gui._preferences import GAP, GRID, MINBUTTONSIZE, PORT_STUB, PORTHEIGHT
from b_asic.sfg_gui.operation_icon import OperationSymbol, operation_icon
from b_asic.sfg_gui.port_button import PortButton
from b_asic.sfg_gui.properties_window import PropertiesWindow
from b_asic.special_operations import Input, Output
from b_asic.types import TypeName
from b_asic.utility_operations import DontCare, Sink
from b_asic.wdf_operations import (
    ReflectionFreeParallelThreePortAdaptor,
    ReflectionFreeSeriesThreeportAdaptor,
    _Adaptor,
)

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
        self._reflection_marker = None
        self._symbol = None
        self._circular_body = None
        self._road_sign_body = None
        super().__init__(parent)
        if self.is_circular() or self.is_road_sign():
            self.setAttribute(Qt.WA_TranslucentBackground)
        self.setIcon(operation_icon(operation.type_name()))
        self.setIconSize(QSize(MINBUTTONSIZE - 8, MINBUTTONSIZE - 8))

    def _geometry_changed(self) -> None:
        """Notify the window without retaining this widget in a signal closure."""
        self._window._operation_geometry_changed(self)

    def paintEvent(self, event) -> None:
        """Paint the box; the SVG glyph is rendered separately by the scene."""
        if self.is_circular() or self.is_road_sign():
            return
        painter = QStylePainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.icon = QIcon()
        painter.drawControl(QStyle.CE_PushButton, option)

    def is_circular(self) -> bool:
        """Return whether this operation is drawn as a small circular terminal."""
        return isinstance(self.operation, (DontCare, Sink))

    def is_road_sign(self) -> bool:
        """Return whether the operation uses a pentagonal input/output body."""
        return isinstance(self.operation, (Input, Output))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._symbol is not None:
            self._symbol.setPos(self.width() / 2, self.height() / 2)
        self._position_road_sign_body()

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
        flip.triggered.connect(self.flip_horizontal)
        menu.addAction("Flip vertical", self.flip_vertical)
        menu.addAction("Rotate 90° clockwise", self.rotate_clockwise)
        menu.addAction("Rotate 90° counterclockwise", self.rotate_counterclockwise)
        menu.exec_(self.cursor().pos())

    def show_properties_window(self, event=None) -> None:
        """Display the properties window for the associated Operation."""
        self._properties_window = PropertiesWindow(self, self._window)
        self._properties_window.show()

    def expand_sfg(self, event=None) -> None:
        """Open or close the editor for this nested SFG."""
        self._window._toggle_expanded_sfg(self)

    def replace_sfg(self, replacement: SFG) -> None:
        """Replace the represented SFG while retaining matching external wires."""
        current = self.operation
        if not isinstance(current, SFG):
            raise TypeError("Only SFG operations can be replaced")

        old_input_ports = list(current.inputs)
        old_output_ports = list(current.outputs)
        old_port_buttons = {
            port_button.port: port_button for port_button in self._ports
        }
        copies = replacement._original_components_to_new
        new_input_indexes = {
            new_index: old_index
            for old_index, inner in enumerate(current.input_operations)
            if (copy := copies.get(inner)) in replacement.input_operations
            for new_index in [list(replacement.input_operations).index(copy)]
        }
        new_output_indexes = {
            new_index: old_index
            for old_index, inner in enumerate(current.output_operations)
            if (copy := copies.get(inner)) in replacement.output_operations
            for new_index in [list(replacement.output_operations).index(copy)]
        }

        retained_buttons = {}
        for new_index, old_index in new_input_indexes.items():
            port = (
                old_input_ports[old_index] if old_index < len(old_input_ports) else None
            )
            button = old_port_buttons.get(port)
            if button is not None:
                retained_buttons[replacement.input(new_index)] = button
        for new_index, old_index in new_output_indexes.items():
            port = (
                old_output_ports[old_index]
                if old_index < len(old_output_ports)
                else None
            )
            button = old_port_buttons.get(port)
            if button is not None:
                retained_buttons[replacement.output(new_index)] = button

        retained_old_ports = {
            *[
                old_input_ports[index]
                for index in new_input_indexes.values()
                if index < len(old_input_ports)
            ],
            *[
                old_output_ports[index]
                for index in new_output_indexes.values()
                if index < len(old_output_ports)
            ],
        }
        removed_buttons = [
            button
            for port, button in old_port_buttons.items()
            if port not in retained_old_ports
        ]
        for port_button in removed_buttons:
            for arrow in list(self._window._arrow_ports):
                if port_button in {
                    arrow.source_port_button,
                    arrow.destination_port_button,
                }:
                    arrow.remove()
            if port_button in self._window._pressed_ports:
                self._window._pressed_ports.remove(port_button)
            self._window._scene.removeItem(port_button)

        for new_index, old_index in new_input_indexes.items():
            if old_index >= len(old_input_ports):
                continue
            for signal in list(old_input_ports[old_index].signals):
                signal.set_destination(replacement.input(new_index))
        for new_index, old_index in new_output_indexes.items():
            if old_index >= len(old_output_ports):
                continue
            for signal in list(old_output_ports[old_index].signals):
                signal.set_source(replacement.output(new_index))

        current.__dict__.clear()
        current.__dict__.update(replacement.__dict__)
        current._input_ports = replacement._input_ports
        current._output_ports = replacement._output_ports
        current._execution_time = replacement._execution_time
        for port in (*current.inputs, *current.outputs):
            port._operation = current

        self._ports = []
        for port in (*current.inputs, *current.outputs):
            port_button = retained_buttons.get(port)
            if port_button is None:
                port_button = PortButton("", self, port)
            else:
                port_button.port = port
            self._ports.append(port_button)
        self._window._ports[self] = self._ports
        self._refresh_sfg_interface()

    def sync_sfg_interface(
        self, inputs: Sequence[Input], outputs: Sequence[Output]
    ) -> None:
        """Update external ports without requiring the internal graph to be valid."""
        current = self.operation
        if not isinstance(current, SFG):
            raise TypeError("Only SFG operations can be synchronized")

        old_input_buttons = {
            button.port.index: button
            for button in self._ports
            if isinstance(button.port, InputPort)
        }
        old_output_buttons = {
            button.port.index: button
            for button in self._ports
            if not isinstance(button.port, InputPort)
        }
        retained_inputs = {
            id(operation): old_input_buttons[index]
            for index, operation in enumerate(current.input_operations)
        }
        retained_outputs = {
            id(operation): old_output_buttons[index]
            for index, operation in enumerate(current.output_operations)
        }
        retained_input_buttons = [retained_inputs.get(id(op)) for op in inputs]
        retained_output_buttons = [retained_outputs.get(id(op)) for op in outputs]

        old_ports = set(old_input_buttons.values()) | set(old_output_buttons.values())
        retained_buttons = {
            *[button for button in retained_input_buttons if button is not None],
            *[button for button in retained_output_buttons if button is not None],
        }
        for port_button in old_ports - retained_buttons:
            for arrow in list(self._window._arrow_ports):
                if port_button in {
                    arrow.source_port_button,
                    arrow.destination_port_button,
                }:
                    arrow.remove()
            if port_button in self._window._pressed_ports:
                self._window._pressed_ports.remove(port_button)
            self._window._scene.removeItem(port_button)

        new_inputs = [InputPort(current, index) for index in range(len(inputs))]
        new_outputs = [OutputPort(current, index) for index in range(len(outputs))]
        current._input_ports = new_inputs
        current._output_ports = new_outputs
        self._ports = []
        for port, retained in zip(new_inputs, retained_input_buttons, strict=True):
            if retained is not None:
                port_button = retained
                for signal in list(port_button.port.signals):
                    signal.set_destination(port)
                port_button.port = port
            else:
                port_button = PortButton("", self, port)
            self._ports.append(port_button)
        for port, retained in zip(new_outputs, retained_output_buttons, strict=True):
            if retained is not None:
                port_button = retained
                for signal in list(port_button.port.signals):
                    signal.set_source(port)
                port_button.port = port
            else:
                port_button = PortButton("", self, port)
            self._ports.append(port_button)

        current._input_operations = list(inputs)
        current._output_operations = list(outputs)
        self._window._ports[self] = self._ports
        self._refresh_sfg_interface(defer=True)

    def _refresh_sfg_interface(self, *, defer: bool = False) -> None:
        """Resize, position, and repaint SFG interface ports."""
        current = self.operation
        if not isinstance(current, SFG):
            return
        max_ports = max(current.input_count, current.output_count)
        self.setFixedHeight(
            max(MINBUTTONSIZE, max_ports * PORTHEIGHT + (max_ports - 1) * GAP)
        )
        proxy = self.graphicsProxyWidget()
        if proxy is not None:
            proxy.resize(self.width(), self.height())
            proxy.update()
        for port in self._ports:
            port.setVisible(True)
            port.update()
        self._position_ports()
        self.update()
        self._window._scene.update()
        self._window._invalidate_sfg(self)
        self._window._update()
        if defer:
            QTimer.singleShot(0, self._refresh_sfg_interface_items)

    def _refresh_sfg_interface_items(self) -> None:
        """Refresh newly parented Qt scene items after the native resize pass."""
        proxy = self.graphicsProxyWidget()
        if proxy is None:
            return
        for port in self._ports:
            port.setParentItem(proxy)
            port.setVisible(True)
            port.update()
        self._position_ports()
        proxy.update()
        self._window._scene.update()
        self._window._graphics_view.viewport().update()

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

        self._window._schedule_reroute_arrows()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return
        self._m_press = False
        if self._m_drag:
            if self._mouse_press_pos is not None:
                moved = event.pos() - self._mouse_press_pos
                if moved.manhattanLength() > 3:
                    event.ignore()

            self._m_drag = False
            # Snap the scene geometry, retaining fractional proxy positions for
            # transformed items and the relative positions of a dragged group.
            corner = self.graphicsProxyWidget().sceneBoundingRect().topLeft()
            snapped = QPointF(
                GRID * round(corner.x() / GRID), GRID * round(corner.y() / GRID)
            )
            buttons = (
                self._window._pressed_operations
                if self in self._window._pressed_operations
                else [self]
            )
            for button in buttons:
                button.graphicsProxyWidget().moveBy(
                    snapped.x() - corner.x(), snapped.y() - corner.y()
                )

        else:
            self.select_button(event.modifiers())

        self._window._update()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and isinstance(
            self.operation, SFG
        ):
            self.expand_sfg()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _flip(self, event=None) -> None:
        self._flipped = not self._flipped
        self._position_ports()
        self._position_label()

        self._window._update()

    def flip_horizontal(self, event=None) -> None:
        """Mirror left/right on the canvas, keeping the glyph upright."""
        self._reflect(vertical=False)

    def flip_vertical(self, event=None) -> None:
        """Mirror top/bottom on the canvas, keeping the glyph upright."""
        self._reflect(vertical=True)

    def _reflect(self, vertical: bool) -> None:
        # A vertical reflection is a horizontal reflection plus a half turn.
        # Swap the local axes at odd quarter turns to reflect in canvas axes.
        half_turn = bool(self._rotation % 180) != vertical
        self._flipped = not self._flipped
        self._position_ports()
        self.set_rotation(self._rotation + (180 if half_turn else 0))

    def default_rotation(self) -> int:
        """Twoport adaptors have paired terminals on the top and bottom."""
        return (
            90
            if isinstance(self.operation, _Adaptor) and self.operation.input_count == 2
            else 0
        )

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
        if self._symbol is not None:
            self._symbol.setRotation(-self._rotation)
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
        top = rect.top()
        for port in self._ports:
            top = min(top, port.sceneBoundingRect().top())
        position = QPointF(
            rect.center().x() - self.label.boundingRect().width() / 2,
            top - self.label.boundingRect().height(),
        )
        self.label.setPos(proxy.mapFromScene(position))

    def _toggle_button(self, pressed=False) -> None:
        self.pressed = not pressed
        if self._circular_body is not None:
            self._circular_body.setBrush(Qt.gray if self.pressed else Qt.white)
            return
        if self._road_sign_body is not None:
            self._road_sign_body.setBrush(Qt.gray if self.pressed else Qt.white)
            return
        self.setStyleSheet(
            f"background-color: {'white' if not self.pressed else 'grey'};"
            " border-style: solid;        border-color: black;"
            " border-width: 2px"
        )

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
        expanded = self._window._expanded_sfg_windows.pop(self, None)
        if expanded is not None:
            expanded._close_state_preserved = False
            expanded.close()
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
        if self.operation in self._window._drag_buttons:
            del self._window._drag_buttons[self.operation]
        self._window._sync_expanded_sfg_interface()
        self._window._update()

    def add_ports(self) -> None:
        """Add external terminals as children of the operation's scene proxy."""
        if self.is_circular():
            self._circular_body = QGraphicsEllipseItem(
                QRectF(1, 1, self.width() - 2, self.height() - 2),
                self.graphicsProxyWidget(),
            )
            self._circular_body.setPen(QPen(Qt.black, 2))
            self._circular_body.setBrush(Qt.white)
            self._circular_body.setAcceptedMouseButtons(Qt.NoButton)
        elif self.is_road_sign():
            self._road_sign_body = QGraphicsPathItem(self.graphicsProxyWidget())
            self._road_sign_body.setPen(QPen(Qt.black, 2))
            self._road_sign_body.setBrush(Qt.white)
            self._road_sign_body.setAcceptedMouseButtons(Qt.NoButton)
        else:
            size = min(self.iconSize().width(), self.width() - 8, self.height() - 8)
            size -= size % 2
            self._symbol = OperationSymbol(
                self.operation.type_name(), size, self.graphicsProxyWidget()
            )
            self._symbol.setPos(self.width() / 2, self.height() / 2)
            self._symbol.setRotation(-self._rotation)
        for port in (*self.operation.inputs, *self.operation.outputs):
            self._ports.append(PortButton("", self, port))
        self._position_ports()

    def _position_ports(self) -> None:
        self._position_road_sign_body()
        paired = isinstance(self.operation, _Adaptor)
        for port in self._ports:
            if paired:
                self._position_adaptor_port(port)
            else:
                ports = (
                    self.operation.inputs
                    if isinstance(port.port, InputPort)
                    else self.operation.outputs
                )
                if len(ports) == 1:
                    y = self.height() / 2
                else:
                    y = PORTHEIGHT + (
                        self.height() - 2 * PORTHEIGHT
                    ) * port.port.index / (len(ports) - 1)
                y = GRID * round(y / GRID)
                left = isinstance(port.port, InputPort) != self.is_flipped()
                port.set_outward_direction(-1 if left else 1)
                port.setPos(-PORT_STUB if left else self.width() + PORT_STUB, y)
        self._position_reflection_marker()
        for port in self._ports:
            port.moved.emit()

    def _position_road_sign_body(self) -> None:
        """Keep the road-sign point on the side carrying its terminal."""
        if self._road_sign_body is None:
            return
        width, height = self.width(), self.height()
        shoulder = width - 1 - min(width / 3, height / 2)
        points = [
            QPointF(1, 1),
            QPointF(shoulder, 1),
            QPointF(width - 1, height / 2),
            QPointF(shoulder, height - 1),
            QPointF(1, height - 1),
        ]
        if isinstance(self.operation, Output) != self.is_flipped():
            points = [QPointF(width - point.x(), point.y()) for point in points]
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        path.closeSubpath()
        self._road_sign_body.setPath(path)

    def _position_reflection_marker(self) -> None:
        """Place the T inside the box, with its base at reflection-free output 1."""
        if not isinstance(
            self.operation,
            (
                ReflectionFreeSeriesThreeportAdaptor,
                ReflectionFreeParallelThreePortAdaptor,
            ),
        ):
            return
        if self._reflection_marker is None:
            self._reflection_marker = QGraphicsPathItem(self.graphicsProxyWidget())
            self._reflection_marker.setPen(QPen(Qt.black, 1.5))
            self._reflection_marker.setAcceptedMouseButtons(Qt.NoButton)
            self._reflection_marker.setZValue(3)
        outgoing = self._ports[self.operation.input_count + 1]
        outward = outgoing.mapToParent(QPointF(outgoing.direction, 0)) - outgoing.pos()
        base = outgoing.pos() - outward * (PORT_STUB + 2)
        center = base - outward * 8
        tangent = QPointF(-outward.y(), outward.x()) * 5
        path = QPainterPath(base)
        path.lineTo(center)
        path.moveTo(center - tangent)
        path.lineTo(center + tangent)
        self._reflection_marker.setPath(path)

    def _position_adaptor_port(self, terminal: PortButton) -> None:
        """Pair input i with output i on a shared physical adaptor side."""
        index = terminal.port.index
        incoming = isinstance(terminal.port, InputPort)
        # Keep the same corner clearance as a regular two-input operation.
        side_length = self.width() if index == 2 else self.height()
        gap = side_length / 2 - PORTHEIGHT
        rotation = 0
        if index == 0:
            # At the twoport default rotation (90°), both pairs read
            # input-left/output-right. Threeport adaptors keep their layout.
            offset = gap if incoming else -gap
            if self.operation.input_count != 2:
                offset = -offset
            x, y = -PORT_STUB, self.height() / 2 + offset
            direction = -1
        elif index == 1:
            x, y = (
                self.width() + PORT_STUB,
                self.height() / 2 + (gap if incoming else -gap),
            )
            direction = 1
        else:
            x, y = (
                self.width() / 2 + (-gap if incoming else gap),
                self.height() + PORT_STUB,
            )
            direction, rotation = 1, 90
        if self.is_flipped():
            x = self.width() - x
            if rotation == 0:
                direction = -direction
        terminal.set_outward_direction(direction, rotation)
        terminal.setPos(x, y)
