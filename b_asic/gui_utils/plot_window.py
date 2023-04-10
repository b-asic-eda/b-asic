"""PlotWindow is a window in which simulation results are plotted."""

import re
import sys
from typing import Dict, List, Mapping, Optional, Sequence, Union

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (  # QFrame,; QScrollArea,; QLineEdit,; QSizePolicy,; QLabel,; QFileDialog,; QShortcut,
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from b_asic.gui_utils.icons import get_icon
from b_asic.operation import ResultKey
from b_asic.types import Num


class PlotWindow(QWidget):
    """
    Dialog for plotting the result of a simulation.

    Parameters
    ----------
    sim_result : dict
        Simulation results of the form obtained from :attr:`~b_asic.simulation.Simulation.results`.
    sfg_name : str, optional
        The name of the SFG.
    parent : optional
        The parent window.
    """

    def __init__(
        self,
        sim_result: Mapping[ResultKey, Sequence[Num]],
        sfg_name: Optional[str] = None,
    ):
        super().__init__()
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

        self._dialog_layout = QHBoxLayout()
        self.setLayout(self._dialog_layout)

        listlayout = QVBoxLayout()
        plotlayout = QVBoxLayout()

        self._dialog_layout.addLayout(listlayout)
        self._dialog_layout.addLayout(plotlayout)

        ########### Plot: ##############
        # Do this before the list layout, as the list layout will re/set visibility
        # Note: The order is of importens. Interesting lines last, to be on top.
        # self.plotcanvas = PlotCanvas(
        #    logger=logger, parent=self, width=5, height=4, dpi=100
        # )
        self._plot_fig = Figure(figsize=(5, 4), layout="compressed")
        self._plot_axes = self._plot_fig.add_subplot(111)
        self._plot_axes.xaxis.set_major_locator(MaxNLocator(integer=True))

        # Use | when dropping support for Python 3.8
        ordered_for_plotting = {}
        ordered_for_plotting.update(sim_res_others)
        ordered_for_plotting.update(sim_res_delays)
        ordered_for_plotting.update(sim_res_ins)
        ordered_for_plotting.update(sim_res_outs)
        self._lines = {}
        for key, result in ordered_for_plotting.items():
            line = self._plot_axes.plot(sim_result[key], label=key)
            self._lines[key] = line[0]

        self._plot_canvas = FigureCanvas(self._plot_fig)

        plotlayout.addWidget(NavigationToolbar(self._plot_canvas, self))
        plotlayout.addWidget(self._plot_canvas)

        ########### List layout: ##############

        # Add two buttons for selecting all/none:
        hlayout = QHBoxLayout()
        self._button_all = QPushButton(get_icon('all'), "&All")
        self._button_all.clicked.connect(self._button_all_click)
        hlayout.addWidget(self._button_all)
        self._button_none = QPushButton(get_icon('none'), "&None")
        self._button_none.clicked.connect(self._button_none_click)
        hlayout.addWidget(self._button_none)
        listlayout.addLayout(hlayout)

        # Add the entire list
        self._checklist = QListWidget()
        self._checklist.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self._checklist.itemChanged.connect(self._item_change)
        listitems = {}
        # Use | when dropping support for Python 3.8
        ordered_for_checklist = {}
        ordered_for_checklist.update(sim_res_ins)
        ordered_for_checklist.update(sim_res_outs)
        ordered_for_checklist.update(sim_res_delays)
        ordered_for_checklist.update(sim_res_others)
        for key in ordered_for_checklist:
            list_item = QListWidgetItem(key)
            listitems[key] = list_item
            self._checklist.addItem(list_item)
            list_item.setCheckState(
                Qt.CheckState.Unchecked  # CheckState: Qt.CheckState.{Unchecked, PartiallyChecked, Checked}
            )
        for key in sim_res_outs:
            listitems[key].setCheckState(Qt.CheckState.Checked)
        # self._checklist.setFixedWidth(150)
        listlayout.addWidget(self._checklist)

        # Add additional checkboxes
        self._legend = self._plot_axes.legend()
        self._legend_checkbox = QCheckBox("&Legend")
        self._legend_checkbox.stateChanged.connect(self._legend_checkbox_change)
        self._legend_checkbox.setCheckState(Qt.CheckState.Checked)
        self._legend_checkbox.setIcon(get_icon('legend'))
        listlayout.addWidget(self._legend_checkbox)
        # self.ontop_checkbox = QCheckBox("&On top")
        # self.ontop_checkbox.stateChanged.connect(self._ontop_checkbox_change)
        # self.ontop_checkbox.setCheckState(Qt.CheckState.Unchecked)
        # listlayout.addWidget(self.ontop_checkbox)

        relim_button = QPushButton("&Recompute limits")
        relim_button.clicked.connect(self._relim)
        listlayout.addWidget(relim_button)

        # Add "Close" buttons
        button_close = QPushButton(get_icon('close'), "&Close", self)
        button_close.clicked.connect(self.close)
        listlayout.addWidget(button_close)
        self._relim()

        # Done. Tell the functions below to redraw the canvas when needed.
        # self.plotcanvas.draw()
        self._auto_redraw = True

    def _legend_checkbox_change(self, check_state):
        self._legend.set(visible=(check_state == Qt.CheckState.Checked))
        if self._auto_redraw:
            if check_state == Qt.CheckState.Checked:
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
        for x in range(self._checklist.count()):
            self._checklist.item(x).setCheckState(Qt.CheckState.Checked)
        self._auto_redraw = True
        self._update_legend()

    def _update_legend(self):
        self._legend = self._plot_axes.legend()
        self._plot_canvas.draw()

    def _button_none_click(self, event):
        self._auto_redraw = False
        for x in range(self._checklist.count()):
            self._checklist.item(x).setCheckState(Qt.CheckState.Unchecked)
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

    def _relim(self, event=None):
        self._plot_axes.relim(True)
        self._plot_axes.autoscale(True)
        self._plot_axes.autoscale(axis='x', tight=True)
        self._plot_axes.autoscale(axis='y')
        self._plot_canvas.draw()


def start_simulation_dialog(
    sim_results: Dict[str, List[complex]], sfg_name: Optional[str] = None
):
    """
    Display the simulation results window.

    Parameters
    ----------
    sim_results : dict
        Simulation results of the form obtained from :attr:`~b_asic.simulation.Simulation.results`.
    sfg_name : str, optional
        The name of the SFG.
    """
    app = QApplication(sys.argv)
    win = PlotWindow(sim_result=sim_results, sfg_name=sfg_name)
    win.show()
    sys.exit(app.exec_())


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
