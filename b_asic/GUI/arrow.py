from qtpy.QtWidgets import QApplication, QWidget, QMainWindow, QLabel, QAction,\
QStatusBar, QMenuBar, QLineEdit, QPushButton, QSlider, QScrollArea, QVBoxLayout,\
QHBoxLayout, QDockWidget, QToolBar, QMenu, QLayout, QSizePolicy, QListWidget, QListWidgetItem,\
QGraphicsLineItem, QGraphicsWidget
from qtpy.QtCore import Qt, QSize, QLineF, QPoint, QRectF
from qtpy.QtGui import QIcon, QFont, QPainter, QPen

from b_asic.signal import Signal

class Arrow(QGraphicsLineItem):

    def __init__(self, source, destination, window, signal=None, parent=None):
        super(Arrow, self).__init__(parent)
        self.source = source
        self.signal = Signal(source.port, destination.port) if signal is None else signal
        self.destination = destination
        self._window = window
        self.moveLine()
        self.source.moved.connect(self.moveLine)
        self.destination.moved.connect(self.moveLine)

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.addAction("Delete", self.remove)
        menu.exec_(self.cursor().pos())

    def remove(self):
        self.signal.remove_destination()
        self.signal.remove_source()
        self._window.scene.removeItem(self)
        if self in self._window.signalList:
            self._window.signalList.remove(self)

        if self in self._window.signalPortDict:
            for port1, port2 in self._window.signalPortDict[self]:
                for operation, operation_ports in self._window.portDict.items():
                    if (port1 in operation_ports or port2 in operation_ports) and operation in self._window.opToSFG:
                        self._window.logger.info(f"Operation detected in existing sfg, removing sfg with name: {self._window.opToSFG[operation].name}.")
                        del self._window.sfg_dict[self._window.opToSFG[operation].name]
                        self._window.opToSFG = {op: self._window.opToSFG[op] for op in self._window.opToSFG if self._window.opToSFG[op] is not self._window.opToSFG[operation]}

        del self._window.signalPortDict[self]

    def moveLine(self):
        self.setPen(QPen(Qt.black, 3))
        self.setLine(QLineF(self.source.operation.x()+self.source.x()+14,\
             self.source.operation.y()+self.source.y()+7.5,\
             self.destination.operation.x()+self.destination.x(),\
             self.destination.operation.y()+self.destination.y()+7.5))
