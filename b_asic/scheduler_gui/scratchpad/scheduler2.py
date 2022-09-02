from qtpy import QtGui
from qtpy.QtWidgets import QApplication, QMainWindow
import sys
from qtpy.QtGui import QPainter, QBrush, QPen
from qtpy.QtCore import Qt

class Window(QMainWindow):

    def __init__(self):
        super().__init__()
        self.title = "PyQt5 Drawing Tutorial"
        self.top= 150
        self.left= 150
        self.width = 500
        self.height = 500
        self.InitWindow()

    def InitWindow(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.top, self.left, self.width, self.height)
        self.show()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(Qt.green,  8, Qt.SolidLine))
        painter.setBrush(QBrush(Qt.red, Qt.SolidPattern))
        painter.drawEllipse(40, 40, 400, 400)

App = QApplication(sys.argv)
window = Window()
sys.exit(App.exec())