"""
B-ASIC GUI Arrow Module.

Contains a GUI class for arrows.
"""

from typing import TYPE_CHECKING, cast

from qtpy.QtCore import Qt
from qtpy.QtGui import QPainterPath, QPainterPathStroker, QPen
from qtpy.QtWidgets import QGraphicsPathItem, QMenu

from b_asic.sfg_gui._preferences import LINECOLOR
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
        self.branch_parent = None
        self.branch_fraction = 0.0
        self._crossings = []
        self._paint_path = QPainterPath()
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
        for arrow in self._window._arrow_ports:
            if arrow.branch_parent is self:
                arrow.branch_parent = None
        self._window._arrow_ports.pop(self, None)
        self._window._reroute_arrows()

    def shape(self) -> QPainterPath:
        """Make thin signals easy to target when branching or deleting."""
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        stroker.setCapStyle(Qt.FlatCap)
        return stroker.createStroke(self._paint_path)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            if self._window._starting_port is not None:
                self._window._complete_connection(self, event.scenePos())
            else:
                self._window._signal_clicked(self, event.scenePos())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._window._starting_port is not None:
            self._window._finish_connection_at(event.scenePos(), ignore=self)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def fraction_at(self, position) -> float:
        """Project a scene position onto this wire and return its length fraction."""
        path = self.path()
        traveled = 0.0
        closest = (float("inf"), 0.0)
        for i in range(1, path.elementCount()):
            a, b = path.elementAt(i - 1), path.elementAt(i)
            dx, dy = b.x - a.x, b.y - a.y
            squared = dx * dx + dy * dy
            if not squared:
                continue
            t = max(
                0,
                min(
                    1, ((position.x() - a.x) * dx + (position.y() - a.y) * dy) / squared
                ),
            )
            distance = (position.x() - a.x - t * dx) ** 2 + (
                position.y() - a.y - t * dy
            ) ** 2
            if distance < closest[0]:
                closest = (distance, traveled + t * squared**0.5)
            traveled += squared**0.5
        return closest[1] / traveled if traveled else 0.0

    def branch_prefix(self, fraction):
        """Return the shared trunk up to a relative distance along this wire."""
        path = self.path()
        remaining = fraction * path.length()
        points = []
        for i in range(path.elementCount()):
            element = path.elementAt(i)
            point = (element.x, element.y)
            if points:
                a = points[-1]
                length = abs(point[0] - a[0]) + abs(point[1] - a[1])
                if length > remaining:
                    t = remaining / length
                    points.append(
                        (a[0] + t * (point[0] - a[0]), a[1] + t * (point[1] - a[1]))
                    )
                    break
                remaining -= length
            points.append(point)
        return points

    def update_arrow(self) -> None:
        """Request coordinated routing so connections reserve separate lanes."""
        self._window._schedule_reroute_arrows()

    def apply_route(self, points, blocked):
        """Paint a changed path returned by the persistent native engine."""
        start = self.source_port_button.anchor()
        path = QPainterPath(start)
        for x, y in points[1:]:
            path.lineTo(x, y)
        self.setPen(QPen(LINECOLOR, 2, Qt.DashLine if blocked else Qt.SolidLine))
        self.setZValue(0.5 if blocked else -1)
        self.setToolTip(
            "Route blocked by an operation; move the overlapping operations"
            if blocked
            else ""
        )
        if path != self.path():
            self.setPath(path)
            self._update_paint_path()

    def set_crossings(self, points) -> None:
        """Leave a visible gap under unrelated crossing wires."""
        self._crossings = points
        self._update_paint_path()
        self.update()

    def _update_paint_path(self) -> None:
        # Keep the full logical path for branching and length. Crossing gaps
        # also keep clicks on the upper wire from targeting the lower wire.
        path = self.path()
        if not self._crossings:
            self._paint_path = QPainterPath(path)
            return
        painted = QPainterPath()
        for i in range(1, path.elementCount()):
            a, b = path.elementAt(i - 1), path.elementAt(i)
            painted.moveTo(a.x, a.y)
            if (a.x == b.x) != (a.y == b.y):
                vertical = a.x == b.x
                lane = a.x if vertical else a.y
                low, high = sorted((a.y, b.y) if vertical else (a.x, b.x))
                gaps = sorted(
                    (max(low, position - 5), min(high, position + 5))
                    for x, y in self._crossings
                    for position, offset in [(y, x) if vertical else (x, y)]
                    if offset == lane and low <= position <= high
                )

                def point(position, lane=lane, vertical=vertical):
                    return (lane, position) if vertical else (position, lane)

                cursor = low
                painted.moveTo(*point(low))
                for start, end in gaps:
                    if start > cursor:
                        painted.lineTo(*point(start))
                    cursor = max(cursor, end)
                    painted.moveTo(*point(cursor))
                painted.lineTo(*point(high))
            else:
                painted.lineTo(b.x, b.y)
        self._paint_path = painted

    def paint(self, painter, option, widget=None) -> None:
        """Distinguish unconnected crossings without obscuring branch dots."""
        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self._paint_path)
