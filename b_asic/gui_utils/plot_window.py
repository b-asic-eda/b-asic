"""PlotWindow is a window in which simulation results are plotted."""

# TODO's:
# * Solve the legend update. That isn't working at all.
# * Zoom etc. Might need to change FigureCanvas. Or just something very little.

import re
import sys

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence

# Intereme imports for the Plot class:
from qtpy.QtWidgets import (  # QFrame,; QScrollArea,; QLineEdit,; QSizePolicy,; QLabel,
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QShortcut,
    QVBoxLayout,
)


class PlotCanvas(FigureCanvas):
    """PlotCanvas is used as a part in the PlotWindow."""

    def __init__(self, logger, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(fig)
        self.axes = fig.add_subplot(111)
        self.axes.xaxis.set_major_locator(MaxNLocator(integer=True))
        self.legend = None
        self.logger = logger

        FigureCanvas.updateGeometry(self)
        self.save_figure = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_figure.activated.connect(self._save_plot_figure)

    def _save_plot_figure(self):
        self.logger.info(f"Saving plot of figure: {self.sfg.name}.")
        file_choices = "PNG (*.png)|*.png"
        path, ext = QFileDialog.getSaveFileName(self, "Save file", "", file_choices)
        path = path.encode("utf-8")
        if not path[-4:] == file_choices[-4:].encode("utf-8"):
            path += file_choices[-4:].encode("utf-8")

        if path:
            self.print_figure(path.decode(), dpi=self.dpi)
            self.logger.info(f"Saved plot: {self.sfg.name} to path: {path}.")


class PlotWindow(QDialog):
    """Dialog for plotting the result of a simulation."""

    def __init__(
        self,
        sim_result,
        # sfg_name="{sfg_name}",
        # window=None,
        logger=print,
        parent=None,
        # width=5,
        # height=4,
        # dpi=100,
    ):
        super().__init__(parent=parent)
        # self._window = window
        self.setWindowFlags(
            Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            # | Qt.WindowStaysOnTopHint
        )
        self.setWindowTitle("Simulation result")
        # self.sim_result = sim_result
        self._auto_redraw = False

        # Categorise sim_results into inputs, outputs, delays, others
        sim_res_ins = {}
        sim_res_outs = {}
        sim_res_delays = {}
        sim_res_others = {}

        for key in sim_result:
            if re.fullmatch("in[0-9]+", key):
                sim_res_ins[key] = sim_result[key]
            elif re.fullmatch("[0-9]+", key):
                sim_res_outs[key] = sim_result[key]
            elif re.fullmatch("t[0-9]+", key):
                sim_res_delays[key] = sim_result[key]
            else:
                sim_res_others[key] = sim_result[key]

        # Layout: ############################################
        # | list |       |
        # | ...  | plot  |
        # | misc |       |

        self.dialog_layout = QHBoxLayout()
        self.setLayout(self.dialog_layout)

        listlayout = QVBoxLayout()
        plotlayout = QVBoxLayout()

        self.dialog_layout.addLayout(listlayout)
        self.dialog_layout.addLayout(plotlayout)

        ########### Plot: ##############
        # Do this before the list layout, as the list layout will re/set visibility
        # Note: The order is of importens. Interesting lines last, to be on top.
        self.plotcanvas = PlotCanvas(
            logger=logger, parent=self, width=5, height=4, dpi=100
        )

        self._lines = {}
        for key in sim_res_others | sim_res_delays | sim_res_ins | sim_res_outs:
            line = self.plotcanvas.axes.plot(sim_result[key], visible=False, label=key)
            self._lines[key] = line
        self.plotcanvas.legend = self.plotcanvas.axes.legend()

        plotlayout.addWidget(NavigationToolbar(self.plotcanvas, self))
        plotlayout.addWidget(self.plotcanvas)

        ########### List layout: ##############

        # Add two buttons for selecting all/none:
        hlayout = QHBoxLayout()
        button_all = QPushButton("&All")
        button_all.clicked.connect(self._button_all_click)
        hlayout.addWidget(button_all)
        button_none = QPushButton("&None")
        button_none.clicked.connect(self._button_none_click)
        hlayout.addWidget(button_none)
        listlayout.addLayout(hlayout)

        # Add the entire list
        self.checklist = QListWidget()
        self.checklist.itemChanged.connect(self._item_change)
        listitems = {}
        for key in sim_res_ins | sim_res_outs | sim_res_delays | sim_res_others:
            listitem = QListWidgetItem(key)
            listitems[key] = listitem
            self.checklist.addItem(listitem)
            listitem.setCheckState(
                Qt.CheckState.Unchecked  # CheckState: Qt.CheckState.{Unchecked, PartiallyChecked, Checked}
            )
        for key in sim_res_outs:
            listitems[key].setCheckState(Qt.CheckState.Checked)
        self.checklist.setFixedWidth(150)
        listlayout.addWidget(self.checklist)

        # Add additional checkboxes
        self.legend_checkbox = QCheckBox("&Legend")
        self.legend_checkbox.stateChanged.connect(self._legend_checkbox_change)
        self.legend_checkbox.setCheckState(Qt.CheckState.Checked)
        listlayout.addWidget(self.legend_checkbox)
        # self.ontop_checkbox = QCheckBox("&On top")
        # self.ontop_checkbox.stateChanged.connect(self._ontop_checkbox_change)
        # self.ontop_checkbox.setCheckState(Qt.CheckState.Unchecked)
        # listlayout.addWidget(self.ontop_checkbox)

        # Add "Close" buttons
        buttonClose = QPushButton("&Close", self)
        buttonClose.clicked.connect(self.close)
        listlayout.addWidget(buttonClose)

        # Done. Tell the functions below to redraw the canvas when needed.
        # self.plotcanvas.draw()
        self._auto_redraw = True

    def _legend_checkbox_change(self, checkState):
        self.plotcanvas.legend.set(visible=(checkState == Qt.CheckState.Checked))
        if self._auto_redraw:
            if checkState == Qt.CheckState.Checked:
                self.plotcanvas.legend = self.plotcanvas.axes.legend()
            self.plotcanvas.draw()

    # def _ontop_checkbox_change(self, checkState):
    # Bugg: It seems the window closes if you change the WindowStaysOnTopHint.
    # (Nothing happens if "changing" from False to False or True to True)
    # self.setWindowFlag(Qt.WindowStaysOnTopHint, on = (checkState == Qt.CheckState.Checked))
    # self.setWindowFlag(Qt.WindowStaysOnTopHint, on = True)
    # print("_ontop_checkbox_change")

    def _button_all_click(self, event):
        self._auto_redraw = False
        for x in range(self.checklist.count()):
            self.checklist.item(x).setCheckState(Qt.CheckState.Checked)
        self._auto_redraw = True
        self.plotcanvas.draw()

    def _button_none_click(self, event):
        self._auto_redraw = False
        for x in range(self.checklist.count()):
            self.checklist.item(x).setCheckState(Qt.CheckState.Unchecked)
        self._auto_redraw = True
        self.plotcanvas.draw()

    def _item_change(self, listitem):
        key = listitem.text()
        self._lines[key][0].set(
            visible=(listitem.checkState() == Qt.CheckState.Checked)
        )
        if self._auto_redraw:
            if self.legend_checkbox.checkState == Qt.CheckState.Checked:
                self.plotcanvas.legend = self.plotcanvas.axes.legend()
            self.plotcanvas.draw()


# Simple test of the dialog
if __name__ == "__main__":
    app = QApplication(sys.argv)
    # sim_res = {"c1": [3, 6, 7], "c2": [4, 5, 5], "bfly1.0": [7, 0, 0], "bfly1.1": [-1, 0, 2], "0": [1, 2, 3]}
    sim_res = {
        '0': [0.5, 0.5, 0, 0],
        'add1': [0.5, 0.5, 0, 0],
        'cmul1': [0, 0.5, 0, 0],
        'cmul2': [0.5, 0, 0, 0],
        'in1': [1, 0, 0, 0],
        't1': [0, 1, 0, 0],
    }
    win = PlotWindow(
        # window=None, sim_result=sim_res, sfg_name="hej", logger=print
        sim_result=sim_res,
    )
    win.exec_()
    # win.show()
