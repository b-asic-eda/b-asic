from qtpy.QtCore import QPointF
from qtpy.QtGui import QPen, QPainterPath
from qtpy.QtWidgets import QGraphicsPathItem, QMenu

from b_asic.GUI._preferences import GRID, LINECOLOR, PORTHEIGHT, PORTWIDTH
from b_asic.signal import Signal


class Arrow(QGraphicsPathItem):
    """Arrow/connection in signal flow graph GUI."""

    def __init__(self, source, destination, window, signal=None, parent=None):
        """
        Parameters
        ==========

        source :
            Source operation.
        destination :
            Destination operation.
        window :
            Window containing signal flow graph.
        signal : Signal, optional
            Let arrow represent *signal*.
        parent : optional
            Parent.
        """
        super().__init__(parent)
        self.source = source
        if signal is None:
            signal = Signal(source.port, destination.port)
        self.signal = signal
        self.destination = destination
        self._window = window
        self.moveLine()
        self.source.moved.connect(self.moveLine)
        self.destination.moved.connect(self.moveLine)

    def contextMenuEvent(self, event):
        """Open right-click menu."""
        menu = QMenu()
        menu.addAction("Delete", self.remove)
        menu.exec_(self.cursor().pos())

    def remove(self):
        """Remove line and connections to signals etc."""
        self.signal.remove_destination()
        self.signal.remove_source()
        self._window.scene.removeItem(self)
        if self in self._window.signalList:
            self._window.signalList.remove(self)

        if self in self._window.signalPortDict:
            for port1, port2 in self._window.signalPortDict[self]:
                for (
                    operation,
                    operation_ports,
                ) in self._window.portDict.items():
                    if (
                        port1 in operation_ports or port2 in operation_ports
                    ) and operation in self._window.opToSFG:
                        self._window.logger.info(
                            "Operation detected in existing SFG, removing SFG"
                            " with name:"
                            f" {self._window.opToSFG[operation].name}."
                        )
                        del self._window.sfg_dict[
                            self._window.opToSFG[operation].name
                        ]
                        self._window.opToSFG = {
                            op: self._window.opToSFG[op]
                            for op in self._window.opToSFG
                            if self._window.opToSFG[op]
                            is not self._window.opToSFG[operation]
                        }

        del self._window.signalPortDict[self]

    def moveLine(self):
        """
        Draw a line connecting self.source with self.destination. Used as callback when moving operations.
        """
        ORTHOGONAL = True
        OFFSET = 2 * PORTWIDTH
        self.setPen(QPen(LINECOLOR, 3))
        source_flipped = self.source.operation.is_flipped()
        destination_flipped = self.destination.operation.is_flipped()
        x0 = (
            self.source.operation.x()
            + self.source.x()
            + (PORTWIDTH if not source_flipped else 0)
        )
        y0 = self.source.operation.y() + self.source.y() + PORTHEIGHT / 2
        x1 = (
            self.destination.operation.x()
            + self.destination.x()
            + (0 if not destination_flipped else PORTWIDTH)
        )
        y1 = (
            self.destination.operation.y()
            + self.destination.y()
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
                offset = -OFFSET if source_flipped else -OFFSET
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
