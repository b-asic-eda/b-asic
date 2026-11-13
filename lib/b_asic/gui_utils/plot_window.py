"""PlotWindow is a window in which simulation results are plotted."""

import re
import sys
from collections.abc import Mapping, Sequence

# from numpy import (array, real, imag, real_if_close, absolute, angle)
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
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
from scipy.signal import freqz

from b_asic._preferences import _with_default_plot_font
from b_asic.gui_utils.icons import get_icon
from b_asic.operation import ResultKey
from b_asic.types import Num


class PlotWindow(QWidget):
    """
    Dialog for plotting the result of a simulation.

    Time, frequency magnitude, and frequency phase can be selected independently
    and are stacked vertically. Frequency plots use :func:`scipy.signal.freqz`
    with each selected trace as the numerator coefficients.

    Parameters
    ----------
    sim_result : dict
        Simulation results of the form obtained from
        :attr:`~b_asic.simulation.Simulation.results`.
    sfg_name : str, optional
        The name of the SFG.
    """

    @_with_default_plot_font
    def __init__(
        self,
        sim_result: Mapping[ResultKey, Sequence[Num]],
        sfg_name: str | None = None,
    ) -> None:
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

        ########### Categorizing/sorting/renaming sim_results: ##############
        #  take: sim_results
        #  generate: key_order, initially_checked
        #  generate: updated_result
        initially_checked = []
        dict_to_sort = {}  # use key=m+1/n, where m:3=input, 4=output, 2=T, 1=others
        updated_result = {}
        n = 0
        for key, result in sim_result.items():
            key2 = key  # in most cases
            if re.fullmatch("in[0-9]+", key):
                m = 4
            elif re.fullmatch("[0-9]+", key):
                m = 3
                key2 = "o" + key
            elif re.fullmatch("t[0-9]+", key):
                m = 2
            else:
                m = 1

            if all(np.imag(np.real_if_close(result)) == 0):
                n = n + 1
                dict_to_sort[m + 1 / n] = key2
                updated_result[key2] = np.real(result)
                if m == 3:  # output
                    initially_checked.append(key2)
            else:
                # The same again, but split into several lines
                dict_to_sort[m + 1 / (n + 1)] = key2 + "_re"
                dict_to_sort[m + 1 / (n + 2)] = key2 + "_im"
                dict_to_sort[m + 1 / (n + 3)] = key2 + "_mag"
                dict_to_sort[m + 1 / (n + 4)] = key2 + "_ang"
                updated_result[key2 + "_re"] = np.real(result)
                updated_result[key2 + "_im"] = np.imag(result)
                updated_result[key2 + "_mag"] = np.absolute(result)
                updated_result[key2 + "_ang"] = np.unwrap(np.angle(result))
                n = n + 4
                if m == 3:  # output
                    initially_checked.append(key2 + "_re")
                    initially_checked.append(key2 + "_im")

        key_order = list(dict(sorted(dict_to_sort.items(), reverse=True)).values())
        self._results = {key: updated_result[key] for key in key_order}
        self._selected_keys = set(initially_checked)
        self._frequency_results = {}
        self._lines = {}

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

        self._plot_canvas = FigureCanvas(self._plot_fig)
        self._toolbar = NavigationToolbar(self._plot_canvas, self)

        plotlayout.addWidget(self._toolbar)
        plotlayout.addWidget(self._plot_canvas)

        ########### List layout: ##############

        # Add two buttons for selecting all/none:
        hlayout = QHBoxLayout()
        self._button_all = QPushButton(get_icon("all"), "&All")
        self._button_all.clicked.connect(self._button_all_click)
        hlayout.addWidget(self._button_all)
        self._button_none = QPushButton(get_icon("none"), "&None")
        self._button_none.clicked.connect(self._button_none_click)
        hlayout.addWidget(self._button_none)
        listlayout.addLayout(hlayout)

        # Add the entire list
        self._checklist = QListWidget()
        self._checklist.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self._checklist.itemChanged.connect(self._item_change)
        listitems = {}
        for key in key_order:
            list_item = QListWidgetItem(key)
            listitems[key] = list_item
            self._checklist.addItem(list_item)
            list_item.setCheckState(Qt.CheckState.Unchecked)
        for key in initially_checked:
            listitems[key].setCheckState(Qt.CheckState.Checked)
        # self._checklist.setFixedWidth(150)
        listlayout.addWidget(self._checklist)

        # Each plot can be enabled independently, in this vertical order.
        self._subplot_checkboxes = {}
        for name, label in (
            ("time", "&Time"),
            ("magnitude", "Frequency &magnitude"),
            ("phase", "Frequency &phase"),
        ):
            checkbox = QCheckBox(label)
            checkbox.setChecked(name == "time")
            checkbox.stateChanged.connect(self._subplot_change)
            self._subplot_checkboxes[name] = checkbox
            listlayout.addWidget(checkbox)

        # Add additional checkboxes
        self._legend_checkbox = QCheckBox("&Legend")
        self._legend_checkbox.setCheckState(Qt.CheckState.Checked)
        self._legend_checkbox.stateChanged.connect(self._legend_checkbox_change)
        self._legend_checkbox.setIcon(get_icon("legend"))
        listlayout.addWidget(self._legend_checkbox)
        # self.ontop_checkbox = QCheckBox("&On top")
        # self.ontop_checkbox.stateChanged.connect(self._ontop_checkbox_change)
        # self.ontop_checkbox.setCheckState(Qt.CheckState.Unchecked)
        # listlayout.addWidget(self.ontop_checkbox)

        relim_button = QPushButton("&Recompute limits")
        relim_button.clicked.connect(self._relim)
        listlayout.addWidget(relim_button)

        # Add "Close" buttons
        button_close = QPushButton(get_icon("close"), "&Close", self)
        button_close.clicked.connect(self.close)
        listlayout.addWidget(button_close)
        self._subplot_change()

        # Done. Tell the functions below to redraw the canvas when needed.
        # self.plotcanvas.draw()
        self._auto_redraw = True

    @_with_default_plot_font
    def _legend_checkbox_change(self, check_state) -> None:
        for legend in self._legends:
            legend.set_visible(self._legend_checkbox.isChecked())
        if self._auto_redraw:
            self._plot_canvas.draw()

    @_with_default_plot_font
    def _subplot_change(self, check_state=None) -> None:
        self._plot_fig.clear()
        selected = [
            name
            for name, checkbox in self._subplot_checkboxes.items()
            if checkbox.isChecked()
        ]
        self._axes = {}
        self._lines = {key: {} for key in self._results}
        for index, name in enumerate(selected, start=1):
            axes = self._plot_fig.add_subplot(len(selected), 1, index)
            self._axes[name] = axes
            if name == "time":
                axes.set_xlabel("Sample")
                axes.set_ylabel("Value")
                axes.xaxis.set_major_locator(MaxNLocator(integer=True))
            else:
                axes.set_xlabel("Normalized frequency (π rad/sample)")
                axes.set_ylabel("Magnitude" if name == "magnitude" else "Phase (rad)")
            for key, result in self._results.items():
                if name == "time":
                    (line,) = axes.plot(result, label=key)
                else:
                    if key not in self._frequency_results:
                        # Empty simulation traces have no frequency response.
                        self._frequency_results[key] = (
                            freqz(result)
                            if len(result)
                            else (np.array([]), np.array([]))
                        )
                    frequency, response = self._frequency_results[key]
                    values = (
                        np.abs(response)
                        if name == "magnitude"
                        else np.unwrap(np.angle(response))
                    )
                    (line,) = axes.plot(frequency / np.pi, values, label=key)
                self._lines[key][name] = line
                if key not in self._selected_keys:
                    line.remove()
        self._plot_axes = self._axes.get("time")
        self._toolbar.update()
        self._update_legend()
        self._relim()

    def _button_all_click(self, event) -> None:
        self._auto_redraw = False
        for x in range(self._checklist.count()):
            self._checklist.item(x).setCheckState(Qt.CheckState.Checked)
        self._auto_redraw = True
        self._update_legend()

    @_with_default_plot_font
    def _update_legend(self) -> None:
        self._legends = []
        for axes in self._axes.values():
            legend = axes.legend() if axes.lines else axes.legend([], [])
            legend.set_visible(self._legend_checkbox.isChecked())
            self._legends.append(legend)
        self._legend = self._legends[0] if self._legends else None
        self._plot_canvas.draw()

    def _button_none_click(self, event) -> None:
        self._auto_redraw = False
        for x in range(self._checklist.count()):
            self._checklist.item(x).setCheckState(Qt.CheckState.Unchecked)
        self._auto_redraw = True
        self._update_legend()

    def _item_change(self, listitem) -> None:
        key = listitem.text()
        if listitem.checkState() == Qt.CheckState.Checked:
            self._selected_keys.add(key)
        else:
            self._selected_keys.discard(key)
        for name, line in self._lines.get(key, {}).items():
            if key in self._selected_keys:
                if line.axes is None:
                    self._axes[name].add_line(line)
            elif line.axes is not None:
                line.remove()
        if self._auto_redraw:
            self._update_legend()

    def _relim(self, event=None) -> None:
        for axes in self._axes.values():
            axes.relim(True)
            axes.autoscale(True)
            axes.autoscale(axis="x", tight=True)
            axes.autoscale(axis="y")
        self._plot_canvas.draw()


def start_simulation_dialog(
    sim_results: dict[str, list[complex]], sfg_name: str | None = None
) -> None:
    """
    Display the simulation results window.

    Parameters
    ----------
    sim_results : dict
        Simulation results of the form obtained from
        :attr:`~b_asic.simulation.Simulation.results`.
    sfg_name : str, optional
        The name of the SFG.
    """
    if not QApplication.instance():
        # QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    win = PlotWindow(sim_result=sim_results, sfg_name=sfg_name)
    win.show()
    app.exec_()


# Simple test of the dialog
if __name__ == "__main__":
    sim_res = {
        "0": [0.5, 0.6, 0.5, 0],
        "1": [0.0, 1.0 + 0.3j, 0.5, 0.1j],
        "add1": [0.5, 0.5, 0, 0],
        "cmul1": [0, 0.5, 0, 0],
        "cmul2": [0.5, 0, 0, 0],
        "in1": [1, 0, 0, 0],
        "in2": [0.1, 2, 0, 0],
        "t1": [0, 1, 0, 0],
        "t2": [0, 0, 1, 0],
        "t3": [0, 0, 0, 1],
    }
    start_simulation_dialog(sim_res, "Test data")
