"""
B-ASIC GUI Arrow Module.

Contains a GUI class for arrows.
"""

from typing import TYPE_CHECKING, cast

from qtpy.QtGui import QPainterPath, QPainterPathStroker, QPen
from qtpy.QtWidgets import QGraphicsPathItem, QMenu

from b_asic.sfg_gui._preferences import LINECOLOR
from b_asic.sfg_gui.routing import route_orthogonal
from b_asic.signal import Signal

if TYPE_CHECKING:
    from b_asic.operation import Operation
    from b_asic.port import InputPort, OutputPort
    from b_asic.sfg_gui.drag_button import DragButton
    from b_asic.sfg_gui.main_window import SFGMainWindow
    from b_asic.sfg_gui.port_button import PortButton


class Arrow(QGraphicsPathItem):
    """
    Arrow/connection in signal flow graph GUI.

    Parameters
    ----------
    source_port_button : :class:`~b_asic.sfg_gui.port_button.PortButton`
        Source port button.
    destination_port_button : :class:`~b_asic.sfg_gui.port_button.PortButton`
        Destination port button.
    window : :class:`~b_asic.sfg_gui.main_window.SFGMainWindow`
        Window containing signal flow graph.
    signal : :class:`~b_asic.signal.Signal`, optional
        Let arrow represent *signal*.
    parent : optional
        Parent.
    """

    def __init__(
        self,
        source_port_button: "PortButton",
        destination_port_button: "PortButton",
        window: "SFGMainWindow",
        signal: Signal | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._source_port_button = source_port_button
        if signal is None:
            signal = Signal(source_port_button.port, destination_port_button.port)
        self.signal = signal
        self._destination_port_button = destination_port_button
        self._window = window
        self.setZValue(-1)
        self._source_port_button.moved.connect(self.update_arrow)
        self._destination_port_button.moved.connect(self.update_arrow)

    def contextMenuEvent(self, event) -> None:
        """
        Open right-click menu.

        Parameters
        ----------
        event : QEvent
            The event.
        """
        menu = QMenu()
        menu.addAction("Delete", self.remove)
        menu.exec_(event.screenPos())

    @property
    def source_operation_button(self) -> "DragButton":
        """The source DragButton."""
        return self._source_port_button._operation_button

    @property
    def destination_operation_button(self) -> "DragButton":
        """The destination DragButton."""
        return self._destination_port_button._operation_button

    @property
    def source_operation(self) -> "Operation":
        """The source Operation."""
        return self._source_port_button.operation

    @property
    def destination_operation(self) -> "Operation":
        """The destination Operation."""
        return self._destination_port_button.operation

    @property
    def source_port_button(self) -> "PortButton":
        """The source PortButton."""
        return self._source_port_button

    @property
    def destination_port_button(self) -> "PortButton":
        """The destination PortButton."""
        return self._destination_port_button

    @property
    def source_port(self) -> "OutputPort":
        """The source OutputPort."""
        return cast("OutputPort", self._source_port_button.port)

    @property
    def destination_port(self) -> "InputPort":
        """The destination InputPort."""
        return cast("InputPort", self._destination_port_button.port)

    def set_source_operation(self, source: "Operation") -> None:
        """
        Set operation of the source DragButton.

        Parameters
        ----------
        source : :class:`~b_asic.operation.Operation`
            The operation to use as source.
        """
        self._source_port_button._operation_button.operation = source

    def set_destination_operation(self, destination: "Operation") -> None:
        """
        Set operation of the destination DragButton.

        Parameters
        ----------
        destination : :class:`~b_asic.operation.Operation`
            The operation to use as destination.
        """
        self._destination_port_button._operation_button.operation = destination

    def remove(self) -> None:
        """Remove line and connections to signals etc."""
        self._window._cancel_connection()
        self._source_port_button.moved.disconnect(self.update_arrow)
        self._destination_port_button.moved.disconnect(self.update_arrow)
        self.signal.remove_destination()
        self.signal.remove_source()
        self._window._scene.removeItem(self)

        self._window._invalidate_sfg(self.source_operation_button)
        self._window._invalidate_sfg(self.destination_operation_button)
        self._window._arrow_ports.pop(self, None)
        self._window._reroute_arrows()

    def shape(self) -> QPainterPath:
        """Make thin signals easy to target when branching or deleting."""
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        return stroker.createStroke(self.path())

    def mousePressEvent(self, event) -> None:
        if self._window._starting_port is not None:
            self._window._complete_connection(self)
            event.accept()
        else:
            super().mousePressEvent(event)

    def update_arrow(self) -> None:
        """Request coordinated routing so connections reserve separate lanes."""
        self._window._reroute_arrows()

    def route(self, obstacles, occupied, shared=()):
        """Route this signal around boxes and previously routed wire segments."""
        start = self.source_port_button.anchor()
        end = self.destination_port_button.anchor()
        sx, sy = self.source_port_button.scene_direction()
        dx, dy = self.destination_port_button.scene_direction()
        a = (start.x() + sx * 12, start.y() + sy * 12)
        b = (end.x() + dx * 12, end.y() + dy * 12)
        # Reserve our terminal stubs too, so the middle route never doubles
        # back over its own exit or approach segment.
        stubs = [((start.x(), start.y()), a), (b, (end.x(), end.y()))]
        route = route_orthogonal(a, b, obstacles, [*occupied, *stubs], list(shared))
        path = QPainterPath(start)
        points = []
        if route:
            points = [(start.x(), start.y()), *route, (end.x(), end.y())]
            for x, y in points[1:]:
                path.lineTo(x, y)
        # Overlapping boxes may enclose a terminal. Do not draw through a box.
        self.setPen(QPen(LINECOLOR, 2))
        if path != self.path():
            self.setPath(path)
        return points
