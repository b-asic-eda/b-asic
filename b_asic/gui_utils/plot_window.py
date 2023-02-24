"""PlotWindow is a window in which simulation results are plotted."""

# TODO's:
# * Solve the legend update. That isn't working at all.
# * Add a function to run this as a "stand-alone".

import re
import sys
from typing import Dict, List, Optional, Tuple

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from qtpy.QtCore import Qt

# Intereme imports for the Plot class:
from qtpy.QtWidgets import (  # QFrame,; QScrollArea,; QLineEdit,; QSizePolicy,; QLabel,; QFileDialog,; QShortcut,
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)


class PlotWindow(QDialog):
    """Dialog for plotting the result of a simulation."""

    def __init__(
        self,
        sim_result: Dict[str, List[complex]],
        logger=print,
        sfg_name: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent=parent)
        self.setWindowFlags(
            Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )
        title = (
            f"Simulation results: {sfg_name}"
            if sfg_name is not None
            else "Simulation results"
        )
        self.setWindowTitle(title)
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
        # | list | icons |
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
        # self.plotcanvas = PlotCanvas(
        #    logger=logger, parent=self, width=5, height=4, dpi=100
        # )
        self._plot_fig = Figure(figsize=(5, 4), layout="compressed")
        self._plot_axes = self._plot_fig.add_subplot(111)
        self._plot_axes.xaxis.set_major_locator(MaxNLocator(integer=True))

        self._lines = {}
        for key in sim_res_others | sim_res_delays | sim_res_ins | sim_res_outs:
            line = self._plot_axes.plot(sim_result[key], label=key)
            self._lines[key] = line[0]

        self._plot_canvas = FigureCanvas(self._plot_fig)

        plotlayout.addWidget(NavigationToolbar(self._plot_canvas, self))
        plotlayout.addWidget(self._plot_canvas)

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
        self.checklist.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
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
        # self.checklist.setFixedWidth(150)
        listlayout.addWidget(self.checklist)

        # Add additional checkboxes
        self._legend = self._plot_axes.legend()
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
        self._legend.set(visible=(checkState == Qt.CheckState.Checked))
        if self._auto_redraw:
            if checkState == Qt.CheckState.Checked:
                self._legend = self._plot_axes.legend()
            self._plot_canvas.draw()

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
        self._update_legend()

    def _update_legend(self):
        self._legend = self._plot_axes.legend()
        self._plot_canvas.draw()

    def _button_none_click(self, event):
        self._auto_redraw = False
        for x in range(self.checklist.count()):
            self.checklist.item(x).setCheckState(Qt.CheckState.Unchecked)
        self._auto_redraw = True
        self._update_legend()

    def _item_change(self, listitem):
        key = listitem.text()
        if listitem.checkState() == Qt.CheckState.Checked:
            self._plot_axes.add_line(self._lines[key])
        else:
            self._lines[key].remove()
        if self._auto_redraw:
            self._update_legend()


def start_simulation_dialog(
    sim_results: Dict[str, List[complex]], sfg_name: Optional[str] = None
):
    app = QApplication(sys.argv)
    win = PlotWindow(sim_result=sim_results, sfg_name=sfg_name)
    win.exec_()


# Simple test of the dialog
if __name__ == "__main__":
    sim_res = {
        '0': [0.5, 0.5, 0, 0],
        'add1': [0.5, 0.5, 0, 0],
        'cmul1': [0, 0.5, 0, 0],
        'cmul2': [0.5, 0, 0, 0],
        'in1': [1, 0, 0, 0],
        't1': [0, 1, 0, 0],
    }
    start_simulation_dialog(sim_res, "Test data")
