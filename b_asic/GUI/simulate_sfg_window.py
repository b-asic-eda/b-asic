"""
B-ASIC window to simulate an SFG.
"""
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QShortcut,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
)

from b_asic.GUI.signal_generator_input import _GENERATOR_MAPPING
from b_asic.signal_generator import FromFile


class SimulateSFGWindow(QDialog):
    simulate = Signal()

    def __init__(self, window):
        super().__init__()
        self._window = window
        self.properties = {}
        self.sfg_to_layout = {}
        self.input_fields = {}
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Simulate SFG")

        self.dialog_layout = QVBoxLayout()
        self.dialog_layout.setSizeConstraint(QLayout.SetFixedSize)
        self.simulate_btn = QPushButton("Simulate")
        self.simulate_btn.clicked.connect(self.save_properties)
        self.dialog_layout.addWidget(self.simulate_btn)
        self.setLayout(self.dialog_layout)
        self.input_grid = QGridLayout()
        self.input_files = {}

    def add_sfg_to_dialog(self, sfg):
        sfg_layout = QVBoxLayout()
        options_layout = QFormLayout()

        name_label = QLabel(f"{sfg.name}")
        sfg_layout.addWidget(name_label)

        spin_box = QSpinBox()
        spin_box.setRange(0, 2147483647)
        spin_box.setValue(100)
        options_layout.addRow("Iteration count: ", spin_box)

        check_box_plot = QCheckBox()
        check_box_plot.setCheckState(Qt.CheckState.Checked)
        options_layout.addRow("Plot results: ", check_box_plot)

        check_box_all = QCheckBox()
        check_box_all.setCheckState(Qt.CheckState.Checked)
        options_layout.addRow("Get all results: ", check_box_all)

        sfg_layout.addLayout(options_layout)

        self.input_fields[sfg] = {
            "iteration_count": spin_box,
            "show_plot": check_box_plot,
            "all_results": check_box_all,
        }

        if sfg.input_count > 0:
            input_label = QLabel("Input values:")
            options_layout.addRow(input_label)

            x, y = 0, 0
            for i in range(sfg.input_count):
                if i % 2 == 0 and i > 0:
                    x += 1
                    y = 0

                input_label = QLabel(f"in{i}")
                self.input_grid.addWidget(input_label, i, 0)

                input_dropdown = QComboBox()
                input_dropdown.insertItems(0, list(_GENERATOR_MAPPING.keys()))
                input_dropdown.currentTextChanged.connect(
                    lambda text, i=i: self.change_input_format(i, text)
                )
                self.input_grid.addWidget(input_dropdown, i, 1, alignment=Qt.AlignLeft)

                self.change_input_format(i, "Constant")

                y += 1

            sfg_layout.addLayout(self.input_grid)

        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        frame.setFrameShadow(QFrame.Sunken)
        self.dialog_layout.addWidget(frame)

        self.sfg_to_layout[sfg] = sfg_layout
        self.dialog_layout.addLayout(sfg_layout)

    def change_input_format(self, i, text):
        grid = self.input_grid.itemAtPosition(i, 2)
        if grid:
            for j in reversed(range(grid.count())):
                item = grid.itemAt(j)
                widget = item.widget()
                if widget:
                    widget.hide()
            self.input_grid.removeItem(grid)

        param_grid = QGridLayout()

        if text in _GENERATOR_MAPPING:
            param_grid = _GENERATOR_MAPPING[text](self._window.logger)
        else:
            raise Exception("Input selection is not implemented")

        self.input_grid.addLayout(param_grid, i, 2)

        return

    def save_properties(self):
        for sfg, _properties in self.input_fields.items():
            ic_value = self.input_fields[sfg]["iteration_count"].value()
            if ic_value == 0:
                self._window.logger.error("Iteration count is set to zero.")

            input_values = []

            for i in range(self.input_grid.rowCount()):
                in_format = self.input_grid.itemAtPosition(i, 1).widget().currentText()
                in_param = self.input_grid.itemAtPosition(i, 2)

                if in_format in _GENERATOR_MAPPING:
                    tmp2 = in_param.get_generator()
                else:
                    raise Exception("Input selection is not implemented")

                input_values.append(tmp2)

            self.properties[sfg] = {
                "iteration_count": ic_value,
                "show_plot": self.input_fields[sfg]["show_plot"].isChecked(),
                "all_results": self.input_fields[sfg]["all_results"].isChecked(),
                "input_values": input_values,
            }

            # If we plot we should also print the entire data,
            # since you cannot really interact with the graph.
            if self.properties[sfg]["show_plot"]:
                self.properties[sfg]["all_results"] = True

        self.accept()
        self.simulate.emit()


class Plot(FigureCanvas):
    def __init__(
        self, simulation, sfg, window, parent=None, width=5, height=4, dpi=100
    ):
        self.simulation = simulation
        self.sfg = sfg
        self.dpi = dpi
        self._window = window

        fig = Figure(figsize=(width, height), dpi=dpi)
        fig.suptitle(sfg.name, fontsize=20)
        self.axes = fig.add_subplot(111)

        FigureCanvas.__init__(self, fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.save_figure = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_figure.activated.connect(self._save_plot_figure)
        self._plot_values_sfg()

    def _save_plot_figure(self):
        self._window.logger.info(f"Saving plot of figure: {self.sfg.name}.")
        file_choices = "PNG (*.png)|*.png"
        path, ext = QFileDialog.getSaveFileName(self, "Save file", "", file_choices)
        path = path.encode("utf-8")
        if not path[-4:] == file_choices[-4:].encode("utf-8"):
            path += file_choices[-4:].encode("utf-8")

        if path:
            self.print_figure(path.decode(), dpi=self.dpi)
            self._window.logger.info(f"Saved plot: {self.sfg.name} to path: {path}.")

    def _plot_values_sfg(self):
        x_axis = list(range(len(self.simulation.results["0"])))
        for _output in range(self.sfg.output_count):
            y_axis = self.simulation.results[str(_output)]

            self.axes.plot(x_axis, y_axis)
