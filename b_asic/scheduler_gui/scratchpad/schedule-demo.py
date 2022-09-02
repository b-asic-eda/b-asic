from qtpy import QtCore, QtGui, QtWidgets
from scheduler import Scheduler


app = QtWidgets.QApplication([])
schedule = Scheduler()
schedule.show()
app.exec_()