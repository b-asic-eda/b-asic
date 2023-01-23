from qtpy.QtCore import QLineF, Qt
from qtpy.QtGui import QPen
from qtpy.QtWidgets import QGraphicsLineItem, QMenu

from b_asic.GUI._preferences import LINECOLOR
from b_asic.signal import Signal


class Arrow(QGraphicsLineItem):
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
        self.setPen(QPen(LINECOLOR, 3))
        self.setLine(
            QLineF(
                self.source.operation.x() + self.source.x() + 14,
                self.source.operation.y() + self.source.y() + 7.5,
                self.destination.operation.x() + self.destination.x(),
                self.destination.operation.y() + self.destination.y() + 7.5,
            )
        )
