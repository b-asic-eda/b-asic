from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.figure import Figure
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QShortcut,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
)


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
        self.simulate_btn = QPushButton("Simulate")
        self.simulate_btn.clicked.connect(self.save_properties)
        self.dialog_layout.addWidget(self.simulate_btn)
        self.setLayout(self.dialog_layout)

    def add_sfg_to_dialog(self, sfg):
        sfg_layout = QVBoxLayout()
        options_layout = QFormLayout()

        name_label = QLabel(f"{sfg.name}")
        sfg_layout.addWidget(name_label)

        spin_box = QSpinBox()
        spin_box.setRange(0, 2147483647)
        options_layout.addRow("Iteration count: ", spin_box)

        check_box_plot = QCheckBox()
        options_layout.addRow("Plot results: ", check_box_plot)

        check_box_all = QCheckBox()
        options_layout.addRow("Get all results: ", check_box_all)

        sfg_layout.addLayout(options_layout)

        self.input_fields[sfg] = {
            "iteration_count": spin_box,
            "show_plot": check_box_plot,
            "all_results": check_box_all,
            "input_values": [],
        }

        if sfg.input_count > 0:
            input_label = QHBoxLayout()
            input_label = QLabel("Input values:")
            options_layout.addRow(input_label)

            input_grid = QGridLayout()
            x, y = 0, 0
            for i in range(sfg.input_count):
                input_layout = QHBoxLayout()
                input_layout.addStretch()
                if i % 2 == 0 and i > 0:
                    x += 1
                    y = 0

                input_label = QLabel("in" + str(i))
                input_layout.addWidget(input_label)
                input_value = QLineEdit()
                input_value.setPlaceholderText("e.g 0, 0, 0")
                input_value.setFixedWidth(100)
                input_layout.addWidget(input_value)
                input_layout.addStretch()
                input_layout.setSpacing(10)
                input_grid.addLayout(input_layout, x, y)

                self.input_fields[sfg]["input_values"].append(input_value)
                y += 1

            sfg_layout.addLayout(input_grid)

        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        frame.setFrameShadow(QFrame.Sunken)
        self.dialog_layout.addWidget(frame)

        self.sfg_to_layout[sfg] = sfg_layout
        self.dialog_layout.addLayout(sfg_layout)

    def parse_input_values(self, input_values):
        _input_values = []
        for _list in input_values:
            _list_values = []
            for val in _list:
                val = val.strip()
                try:
                    if not val:
                        val = 0

                    _list_values.append(complex(val))
                except ValueError:
                    self._window.logger.warning(
                        f"Skipping value: {val}, not a digit."
                    )
                    continue

            _input_values.append(_list_values)

        return _input_values

    def save_properties(self):
        for sfg, _properties in self.input_fields.items():
            input_values = self.parse_input_values(
                [
                    widget.text().split(",") if widget.text() else [0]
                    for widget in self.input_fields[sfg]["input_values"]
                ]
            )
            max_len = max(len(list_) for list_ in input_values)
            min_len = min(len(list_) for list_ in input_values)
            ic_value = self.input_fields[sfg]["iteration_count"].value()
            if max_len != min_len:
                self._window.logger.error(
                    "Minimum length of input lists are not equal to maximum "
                    f"length of input lists: {max_len} != {min_len}."
                )
            elif ic_value > min_len:
                self._window.logger.error(
                    "Minimum length of input lists are less than the "
                    f"iteration count: {ic_value} > {min_len}."
                )
            else:
                self.properties[sfg] = {
                    "iteration_count": ic_value,
                    "show_plot": self.input_fields[sfg][
                        "show_plot"
                    ].isChecked(),
                    "all_results": self.input_fields[sfg][
                        "all_results"
                    ].isChecked(),
                    "input_values": input_values,
                }

                # If we plot we should also print the entire data,
                # since you cannot really interact with the graph.
                if self.properties[sfg]["show_plot"]:
                    self.properties[sfg]["all_results"] = True

                continue

            self._window.logger.info(
                f"Skipping simulation of SFG with name: {sfg.name}, "
                "due to previous errors."
            )

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

        FigureCanvas.setSizePolicy(
            self, QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        FigureCanvas.updateGeometry(self)
        self.save_figure = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_figure.activated.connect(self._save_plot_figure)
        self._plot_values_sfg()

    def _save_plot_figure(self):
        self._window.logger.info(f"Saving plot of figure: {self.sfg.name}.")
        file_choices = "PNG (*.png)|*.png"
        path, ext = QFileDialog.getSaveFileName(
            self, "Save file", "", file_choices
        )
        path = path.encode("utf-8")
        if not path[-4:] == file_choices[-4:].encode("utf-8"):
            path += file_choices[-4:].encode("utf-8")

        if path:
            self.print_figure(path.decode(), dpi=self.dpi)
            self._window.logger.info(
                f"Saved plot: {self.sfg.name} to path: {path}."
            )

    def _plot_values_sfg(self):
        x_axis = list(range(len(self.simulation.results["0"])))
        for _output in range(self.sfg.output_count):
            y_axis = self.simulation.results[str(_output)]

            self.axes.plot(x_axis, y_axis)
