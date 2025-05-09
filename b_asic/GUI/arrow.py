"""
B-ASIC GUI Arrow Module.

Contains a GUI class for arrows.
"""

from typing import TYPE_CHECKING, cast

from qtpy.QtCore import QPointF
from qtpy.QtGui import QPainterPath, QPen
from qtpy.QtWidgets import QGraphicsPathItem, QMenu

from b_asic.GUI._preferences import GRID, LINECOLOR, PORTHEIGHT, PORTWIDTH
from b_asic.signal import Signal

if TYPE_CHECKING:
    from b_asic.GUI.drag_button import DragButton
    from b_asic.GUI.main_window import SFGMainWindow
    from b_asic.GUI.port_button import PortButton
    from b_asic.operation import Operation
    from b_asic.port import InputPort, OutputPort


class Arrow(QGraphicsPathItem):
    """
    Arrow/connection in signal flow graph GUI.

    Parameters
    ----------
    source_port_button : :class:`~b_asic.GUI.port_button.PortButton`
        Source port button.
    destination_port_button : :class:`~b_asic.GUI.port_button.PortButton`
        Destination port button.
    window : :class:`~b_asic.GUI.main_window.SFGMainWindow`
        Window containing signal flow graph.
    signal : Signal, optional
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
    ):
        super().__init__(parent)
        self._source_port_button = source_port_button
        if signal is None:
            signal = Signal(source_port_button.port, destination_port_button.port)
        self.signal = signal
        self._destination_port_button = destination_port_button
        self._window = window
        self.update_arrow()
        self._source_port_button.moved.connect(self.update_arrow)
        self._destination_port_button.moved.connect(self.update_arrow)

    def contextMenuEvent(self, event):
        """
        Open right-click menu.

        Parameters
        ----------
        event : QEvent
            The event.
        """
        menu = QMenu()
        menu.addAction("Delete", self.remove)
        menu.exec_(self.cursor().pos())

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

    def set_source_operation(self, source: "Operation"):
        """
        Set operation of the source DragButton.

        Parameters
        ----------
        source : :class:`~b_asic.operation.Operation`
            The operation to use as source.
        """
        self._source_port_button._operation_button.operation = source

    def set_destination_operation(self, destination: "Operation"):
        """
        Set operation of the destination DragButton.

        Parameters
        ----------
        destination : :class:`~b_asic.operation.Operation`
            The operation to use as destination.
        """
        self._destination_port_button._operation_button.operation = destination

    def remove(self):
        """Remove line and connections to signals etc."""
        self.signal.remove_destination()
        self.signal.remove_source()
        self._window._scene.removeItem(self)

        if self in self._window._arrow_ports:
            for port1, port2 in self._window._arrow_ports[self]:
                for (
                    operation,
                    operation_ports,
                ) in self._window._ports.items():
                    if (
                        port1 in operation_ports or port2 in operation_ports
                    ) and operation in self._window._operation_to_sfg:
                        self._window._logger.info(
                            "Operation detected in existing SFG, removing SFG"
                            " with name: %s",
                            self._window._operation_to_sfg[operation].name,
                        )
                        del self._window._sfg_dict[
                            self._window._operation_to_sfg[operation].name
                        ]
                        self._window._operation_to_sfg = {
                            op: self._window._operation_to_sfg[op]
                            for op in self._window._operation_to_sfg
                            if self._window._operation_to_sfg[op]
                            is not self._window._operation_to_sfg[operation]
                        }

        del self._window._arrow_ports[self]

    def update_arrow(self):
        """
        Update coordinates for arrow.

        Used as callback when moving operations.
        """
        ORTHOGONAL = True
        OFFSET = 2 * PORTWIDTH
        self.setPen(QPen(LINECOLOR, 3))
        source_flipped = self.source_operation_button.is_flipped()
        destination_flipped = self.destination_operation_button.is_flipped()
        x0 = (
            self.source_operation_button.x()
            + self.source_port_button.x()
            + (PORTWIDTH if not source_flipped else 0)
        )
        y0 = (
            self.source_operation_button.y()
            + self.source_port_button.y()
            + PORTHEIGHT / 2
        )
        x1 = (
            self.destination_operation_button.x()
            + self.destination_port_button.x()
            + (0 if not destination_flipped else PORTWIDTH)
        )
        y1 = (
            self.destination_operation_button.y()
            + self._destination_port_button.y()
            + PORTHEIGHT / 2
        )
        xmid = (x0 + x1) / 2
        ymid = (y0 + y1) / 2
        both_flipped = source_flipped and destination_flipped
        any_flipped = source_flipped or destination_flipped
        p = QPainterPath(QPointF(x0, y0))
        # TODO: Simplify or create a better router
        if not ORTHOGONAL:
            pass
        elif y0 == y1:
            if not any_flipped:
                if x0 <= x1:
                    pass
                else:
                    p.lineTo(QPointF(x0 + OFFSET, y0))
                    p.lineTo(QPointF(x0 + OFFSET, y0 + OFFSET))
                    p.lineTo(QPointF(x1 - OFFSET, y0 + OFFSET))
                    p.lineTo(QPointF(x1 - OFFSET, y0))
            elif both_flipped:
                if x1 <= x0:
                    pass
                else:
                    p.lineTo(QPointF(x0 + OFFSET, y0))
                    p.lineTo(QPointF(x0 + OFFSET, y0 + OFFSET))
                    p.lineTo(QPointF(x1 - OFFSET, y0 + OFFSET))
                    p.lineTo(QPointF(x1 - OFFSET, y0))
            elif source_flipped:
                if x0 <= x1:
                    p.lineTo(QPointF(x0 - OFFSET, y0))
                    p.lineTo(QPointF(x0 - OFFSET, y0 + OFFSET))
                    p.lineTo(QPointF(xmid, y0 + OFFSET))
                    p.lineTo(QPointF(xmid, y0))
                else:
                    p.lineTo(QPointF(x0 + OFFSET, y0))
                    p.lineTo(QPointF(x0 + OFFSET, y0 + OFFSET))
                    p.lineTo(QPointF(xmid, y0 + OFFSET))
                    p.lineTo(QPointF(xmid, y0))
            else:
                if x1 <= x0:
                    p.lineTo(QPointF(x0 + OFFSET, y0))
                    p.lineTo(QPointF(x0 + OFFSET, y0 + OFFSET))
                    p.lineTo(QPointF(xmid, y0 + OFFSET))
                    p.lineTo(QPointF(xmid, y0))
                else:
                    p.lineTo(QPointF(xmid, y0))
                    p.lineTo(QPointF(xmid, y0 + OFFSET))
                    p.lineTo(QPointF(x1 + OFFSET, y0 + OFFSET))
                    p.lineTo(QPointF(x1 + OFFSET, y0))

        elif abs(x0 - x1) <= GRID:
            if both_flipped or not any_flipped:
                offset = -OFFSET if both_flipped else OFFSET
                p.lineTo(QPointF(x0 + offset, y0))
                p.lineTo(QPointF(x0 + offset, ymid))
                p.lineTo(QPointF(x0 - offset, ymid))
                p.lineTo(QPointF(x0 - offset, y1))
            else:
                offset = -OFFSET
                p.lineTo(QPointF(x0 + offset, y0))
                p.lineTo(QPointF(x0 + offset, y1))
        else:
            if not any_flipped:
                if x0 <= x1:
                    p.lineTo(QPointF(xmid, y0))
                    p.lineTo(QPointF(xmid, y1))
                else:
                    p.lineTo(x0 + OFFSET, y0)
                    p.lineTo(x0 + OFFSET, ymid)
                    p.lineTo(x1 - OFFSET, ymid)
                    p.lineTo(x1 - OFFSET, y1)
            elif both_flipped:
                if x0 >= x1:
                    p.lineTo(QPointF(xmid, y0))
                    p.lineTo(QPointF(xmid, y1))
                else:
                    p.lineTo(x0 - OFFSET, y0)
                    p.lineTo(x0 - OFFSET, ymid)
                    p.lineTo(x1 + OFFSET, ymid)
                    p.lineTo(x1 + OFFSET, y1)
            elif source_flipped:
                xmin = min(x0, x1) - OFFSET
                p.lineTo(QPointF(xmin, y0))
                p.lineTo(QPointF(xmin, y1))
            else:
                xmax = max(x0, x1) + OFFSET
                p.lineTo(QPointF(xmax, y0))
                p.lineTo(QPointF(xmax, y1))

        p.lineTo(QPointF(x1, y1))
        self.setPath(p)
