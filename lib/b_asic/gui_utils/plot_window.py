"""PlotWindow is a window in which simulation results are plotted."""

import re
import sys
from collections.abc import Collection, Mapping, Sequence

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
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
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
from b_asic.utils import interleave


def _trace_values(key, result):
    """Generate time-domain views while retaining the underlying complex signal."""
    if np.all(np.imag(np.real_if_close(result)) == 0):
        return {key: np.real(result)}
    return {
        key + "_re": np.real(result),
        key + "_im": np.imag(result),
        key + "_mag": np.absolute(result),
        key + "_ang": np.unwrap(np.angle(result)),
    }


def _interleave_results(results, sources):
    """Validate and reconstruct aligned parallel simulation streams."""
    if len(sources) < 2:
        raise ValueError("Choose at least two streams.")
    if len(set(sources)) != len(sources):
        raise ValueError("Choose each stream only once.")
    if len({len(results[key]) for key in sources}) != 1:
        raise ValueError("Streams must have the same number of samples.")
    return np.asarray(interleave(*(results[key] for key in sources)))


def _signal_names(name):
    """Reserve both a signal name and its possible complex time-domain views."""
    return {name, *(name + suffix for suffix in ("_re", "_im", "_mag", "_ang"))}


class _InterleaveDialog(QDialog):
    """Choose stream order and preview the reconstructed signal before saving."""

    @_with_default_plot_font
    def __init__(
        self,
        results: Mapping[str, Sequence[Num]],
        selected: Sequence[str] = (),
        name: str | None = None,
        reserved_names: Collection[str] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit interleaved signal" if name else "Interleave streams")
        self.resize(900, 650)
        self._results = results
        self._reserved_names = set(reserved_names)

        layout = QVBoxLayout(self)
        body = QHBoxLayout()
        layout.addLayout(body)
        controls = QVBoxLayout()
        body.addLayout(controls)
        controls.addWidget(QLabel("Streams in sampling order:"))
        self._source_list = QListWidget()
        self._source_list.setMinimumWidth(180)
        ordered = [*selected, *(key for key in results if key not in selected)]
        for key in ordered:
            item = QListWidgetItem(key)
            item.setCheckState(
                Qt.CheckState.Checked if key in selected else Qt.CheckState.Unchecked
            )
            item.setToolTip(f"{len(results[key])} samples")
            self._source_list.addItem(item)
        controls.addWidget(self._source_list)
        move_layout = QHBoxLayout()
        self._button_up = QPushButton("&Up")
        self._button_up.clicked.connect(lambda: self._move_source(-1))
        move_layout.addWidget(self._button_up)
        self._button_down = QPushButton("&Down")
        self._button_down.clicked.connect(lambda: self._move_source(1))
        move_layout.addWidget(self._button_down)
        controls.addLayout(move_layout)
        controls.addWidget(QLabel("Signal name:"))
        self._name_edit = QLineEdit(name or "")
        controls.addWidget(self._name_edit)
        self._error_label = QLabel()
        self._error_label.setWordWrap(True)
        controls.addWidget(self._error_label)

        preview_layout = QVBoxLayout()
        body.addLayout(preview_layout, 1)
        self._preview_fig = Figure(figsize=(6, 5), layout="compressed")
        self._preview_canvas = FigureCanvas(self._preview_fig)
        preview_layout.addWidget(NavigationToolbar(self._preview_canvas, self))
        preview_layout.addWidget(self._preview_canvas)
        self._preview_axes = {
            plot: self._preview_fig.add_subplot(3, 1, index)
            for index, plot in enumerate(("time", "magnitude", "phase"), start=1)
        }
        rate_label = QLabel(
            "Streams must be aligned and share a sample rate. With M streams, "
            "the reconstructed sample rate is M times each stream's rate. "
            "Sample indices and normalized frequency use this reconstructed rate."
        )
        rate_label.setWordWrap(True)
        preview_layout.addWidget(rate_label)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Save" if name else "Create"
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self._source_list.itemChanged.connect(self._update_preview)
        self._source_list.currentRowChanged.connect(self._update_move_buttons)
        self._name_edit.textChanged.connect(self._validate)
        self._source_list.setCurrentRow(0)
        self._update_move_buttons(self._source_list.currentRow())
        self._update_preview()

    @property
    def source_names(self) -> tuple[str, ...]:
        return tuple(
            self._source_list.item(index).text()
            for index in range(self._source_list.count())
            if self._source_list.item(index).checkState() == Qt.CheckState.Checked
        )

    @property
    def signal_name(self) -> str:
        return self._name_edit.text().strip() or self._default_name()

    def _default_name(self) -> str:
        return f"interleave({', '.join(self.source_names)})"

    def _update_move_buttons(self, row) -> None:
        self._button_up.setEnabled(row > 0)
        self._button_down.setEnabled(0 <= row < self._source_list.count() - 1)

    def _move_source(self, offset) -> None:
        row = self._source_list.currentRow()
        target = row + offset
        if row < 0 or not 0 <= target < self._source_list.count():
            return
        item = self._source_list.takeItem(row)
        self._source_list.insertItem(target, item)
        self._source_list.setCurrentRow(target)
        self._update_preview()

    def _validate(self) -> None:
        sources = self.source_names
        error = ""
        if len(sources) < 2:
            error = "Choose at least two streams."
        elif len({len(self._results[key]) for key in sources}) != 1:
            error = "Streams must have the same number of samples."
        elif _signal_names(self.signal_name) & self._reserved_names:
            error = "A signal with this name already exists. Choose another name."
        self._error_label.setText(error)
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(not error)

    @_with_default_plot_font
    def _update_preview(self, item=None) -> None:
        self._name_edit.setPlaceholderText(self._default_name())
        for name, axes in self._preview_axes.items():
            axes.clear()
            if name == "time":
                axes.set_xlabel("Sample")
                axes.set_ylabel("Value")
                axes.xaxis.set_major_locator(MaxNLocator(integer=True))
            else:
                axes.set_xlabel("Normalized frequency (π rad/sample)")
                axes.set_ylabel("Magnitude" if name == "magnitude" else "Phase (rad)")
        try:
            result = _interleave_results(self._results, self.source_names)
        except ValueError:
            result = None
        if result is not None:
            time_axes = self._preview_axes["time"]
            if np.any(np.imag(np.real_if_close(result)) != 0):
                time_axes.plot(np.real(result), label="Real")
                time_axes.plot(np.imag(result), label="Imaginary")
                time_axes.legend()
            else:
                time_axes.plot(np.real(result))
            if len(result):
                frequency, response = freqz(result)
                self._preview_axes["magnitude"].plot(
                    frequency / np.pi, np.abs(response)
                )
                self._preview_axes["phase"].plot(
                    frequency / np.pi, np.unwrap(np.angle(response))
                )
        self._validate()
        self._preview_canvas.toolbar.update()
        self._preview_canvas.draw()

    def accept(self) -> None:
        self._validate()
        if self._buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled():
            super().accept()


class PlotWindow(QWidget):
    """
    Dialog for plotting the result of a simulation.

    Time, frequency magnitude, and frequency phase can be selected independently
    and are stacked vertically. Frequency plots use :func:`scipy.signal.freqz`
    with each selected signal as the numerator coefficients. Complex time-domain
    views share the frequency response of their underlying complex signal.
    Parallel simulation streams can be interleaved into additional signals.

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
        self._raw_results = {}
        self._results = {}
        self._trace_sources = {}
        self._source_traces = {}
        self._interleaved_signals = {}
        self._frequency_results = {}
        self._lines = {}

        ########### Categorizing/sorting/renaming sim_results: ##############
        initially_checked = []
        dict_to_sort = {}  # use key=m+1/n, where m:3=input, 4=output, 2=T, 1=others
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

            keys = self._register_result(key2, result)
            for trace in keys:
                n += 1
                dict_to_sort[m + 1 / n] = trace
            if m == 3:  # output: real, or real and imaginary components
                initially_checked.extend(keys[:2])

        key_order = list(dict(sorted(dict_to_sort.items(), reverse=True)).values())
        self._results = {key: self._results[key] for key in key_order}
        self._original_keys = tuple(
            dict.fromkeys(self._trace_sources[key] for key in key_order)
        )
        self._selected_keys = set(initially_checked)

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
        self._checklist.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._checklist.customContextMenuRequested.connect(self._checklist_context_menu)
        self._refresh_checklist()
        # self._checklist.setFixedWidth(150)
        listlayout.addWidget(self._checklist)

        self._button_interleave = QPushButton("&Interleave…")
        self._button_interleave.setEnabled(len(self._original_keys) >= 2)
        self._button_interleave.clicked.connect(self._create_interleaved_signal)
        listlayout.addWidget(self._button_interleave)

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

    def _register_result(self, key, result) -> tuple[str, ...]:
        self._raw_results[key] = np.asarray(result).copy()
        traces = _trace_values(key, self._raw_results[key])
        self._results.update(traces)
        self._trace_sources.update(dict.fromkeys(traces, key))
        self._source_traces[key] = tuple(traces)
        return tuple(traces)

    def _refresh_checklist(self) -> None:
        blocked = self._checklist.blockSignals(True)
        try:
            self._checklist.clear()
            for key in self._results:
                item = QListWidgetItem(key)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if key in self._selected_keys
                    else Qt.CheckState.Unchecked
                )
                source = self._trace_sources[key]
                if source in self._interleaved_signals:
                    sources = self._interleaved_signals[source]
                    item.setToolTip(
                        f"Sampling order: {', '.join(sources)}\n"
                        f"Sample rate: {len(sources)} times each stream's rate\n"
                        "Right-click to edit or remove this interleaving."
                    )
                self._checklist.addItem(item)
        finally:
            self._checklist.blockSignals(blocked)

    def _reserved_names(self, exclude=None) -> set[str]:
        names = set(self._raw_results) | set(self._results)
        if exclude is not None:
            names.difference_update((exclude, *self._source_traces[exclude]))
        return names

    def _create_interleaved_signal(self) -> None:
        self._edit_interleaved_signal()

    def _edit_interleaved_signal(self, name=None) -> None:
        selected = (
            self._interleaved_signals[name]
            if name is not None
            else tuple(
                key
                for key in self._original_keys
                if any(
                    trace in self._selected_keys for trace in self._source_traces[key]
                )
            )
        )
        dialog = _InterleaveDialog(
            {key: self._raw_results[key] for key in self._original_keys},
            selected=selected,
            name=name,
            reserved_names=self._reserved_names(name),
            parent=self,
        )
        try:
            if dialog.exec_() == QDialog.DialogCode.Accepted:
                self._set_interleaved_signal(
                    dialog.signal_name, dialog.source_names, previous_name=name
                )
        finally:
            dialog.deleteLater()

    def _set_interleaved_signal(self, name, sources, previous_name=None) -> None:
        name = name.strip()
        if not name:
            raise ValueError("Enter a signal name.")
        if any(key not in self._original_keys for key in sources):
            raise ValueError("Choose simulation streams to interleave.")
        result = _interleave_results(self._raw_results, sources)
        if _signal_names(name) & self._reserved_names(previous_name):
            raise ValueError("A signal with this name already exists.")
        selected_suffixes = None
        if previous_name is not None:
            selected_suffixes = {
                key[len(previous_name) :]
                for key in self._source_traces[previous_name]
                if key in self._selected_keys
            }
            self._discard_interleaved_signal(previous_name)
        keys = self._register_result(name, result)
        self._interleaved_signals[name] = tuple(sources)
        if selected_suffixes is None:
            self._selected_keys.update(keys[:2])
        else:
            selected = [key for key in keys if key[len(name) :] in selected_suffixes]
            if selected_suffixes and not selected:
                selected = keys[:2]
            self._selected_keys.update(selected)
        self._refresh_checklist()
        self._subplot_change()

    def _discard_interleaved_signal(self, name) -> None:
        for key in self._source_traces.pop(name):
            del self._results[key]
            del self._trace_sources[key]
            self._selected_keys.discard(key)
        del self._raw_results[name]
        del self._interleaved_signals[name]
        self._frequency_results.pop(name, None)

    def _remove_interleaved_signal(self, name) -> None:
        self._discard_interleaved_signal(name)
        self._refresh_checklist()
        self._subplot_change()

    def _checklist_context_menu(self, position) -> None:
        item = self._checklist.itemAt(position)
        if item is None:
            return
        source = self._trace_sources[item.text()]
        if source not in self._interleaved_signals:
            return
        menu = QMenu(self)
        edit = menu.addAction("Edit interleaving…")
        edit.triggered.connect(lambda: self._edit_interleaved_signal(source))
        remove = menu.addAction("Remove interleaving")
        remove.triggered.connect(lambda: self._remove_interleaved_signal(source))
        menu.exec_(self._checklist.viewport().mapToGlobal(position))
        menu.deleteLater()

    def _trace_selected(self, key, plot) -> bool:
        if plot == "time":
            return key in self._selected_keys
        return any(
            trace in self._selected_keys
            for trace in self._source_traces[self._trace_sources[key]]
        )

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
            frequency_lines = {}
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
                    source = self._trace_sources[key]
                    if source not in self._frequency_results:
                        raw_result = self._raw_results[source]
                        # Empty simulation traces have no frequency response.
                        self._frequency_results[source] = (
                            freqz(raw_result)
                            if len(raw_result)
                            else (np.array([]), np.array([]))
                        )
                    if source not in frequency_lines:
                        frequency, response = self._frequency_results[source]
                        values = (
                            np.abs(response)
                            if name == "magnitude"
                            else np.unwrap(np.angle(response))
                        )
                        (line,) = axes.plot(frequency / np.pi, values, label=source)
                        frequency_lines[source] = line
                    line = frequency_lines[source]
                self._lines[key][name] = line
                if not self._trace_selected(key, name) and line.axes is not None:
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
            if self._trace_selected(key, name):
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
