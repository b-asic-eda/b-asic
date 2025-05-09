"""
B-ASIC window to simulate an SFG.
"""

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from b_asic.GUI.signal_generator_input import _GENERATOR_MAPPING

if TYPE_CHECKING:
    from b_asic.signal_flow_graph import SFG


class SimulateSFGWindow(QDialog):
    """Simulation window."""

    simulate = Signal()

    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self._properties = {}
        self._sfg_to_layout = {}
        self._input_fields = {}
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Simulate SFG")

        self._dialog_layout = QVBoxLayout()
        self._dialog_layout.setSizeConstraint(QLayout.SetFixedSize)
        self._simulate_btn = QPushButton("Simulate")
        self._simulate_btn.clicked.connect(self.save_properties)
        self._dialog_layout.addWidget(self._simulate_btn)
        self.setLayout(self._dialog_layout)
        self._input_grid = QGridLayout()
        self._input_files = {}

    def add_sfg_to_dialog(self, sfg: "SFG") -> None:
        """
        Add a signal flow graph to the dialog.

        Parameters
        ----------
        sfg : SFG
            The signal flow graph to add.
        """
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

        self._input_fields[sfg] = {
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
                self._input_grid.addWidget(input_label, i, 0)

                input_dropdown = QComboBox()
                input_dropdown.insertItems(0, list(_GENERATOR_MAPPING.keys()))
                input_dropdown.currentTextChanged.connect(
                    lambda text, i=i: self.change_input_format(i, text)
                )
                self._input_grid.addWidget(input_dropdown, i, 1, alignment=Qt.AlignLeft)

                self.change_input_format(i, "Constant")

                y += 1

            sfg_layout.addLayout(self._input_grid)

        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        frame.setFrameShadow(QFrame.Sunken)
        self._dialog_layout.addWidget(frame)

        self._sfg_to_layout[sfg] = sfg_layout
        self._dialog_layout.addLayout(sfg_layout)

    def change_input_format(self, i: int, text: str) -> None:
        """
        Change the input format selector.

        Parameters
        ----------
        i : int
            Input number to change for.
        text : str
            Name of generator.
        """
        grid = self._input_grid.itemAtPosition(i, 2)
        if grid:
            for j in reversed(range(grid.count())):
                item = grid.itemAt(j)
                widget = item.widget()
                if widget:
                    widget.hide()
            self._input_grid.removeItem(grid)

        if text in _GENERATOR_MAPPING:
            param_grid = _GENERATOR_MAPPING[text](self._window._logger)
        else:
            raise ValueError("Input selection is not implemented")

        self._input_grid.addLayout(param_grid, i, 2)

    def save_properties(self) -> None:
        """Save the simulation properties and emit a signal to start the simulation."""
        for sfg in self._input_fields:
            ic_value = self._input_fields[sfg]["iteration_count"].value()
            if ic_value == 0:
                self._window._logger.error("Iteration count is set to zero.")

            input_values = []

            for i in range(self._input_grid.rowCount()):
                in_format = self._input_grid.itemAtPosition(i, 1).widget().currentText()
                in_param = self._input_grid.itemAtPosition(i, 2)

                if in_format in _GENERATOR_MAPPING:
                    tmp2 = in_param.get_generator()
                else:
                    raise ValueError("Input selection is not implemented")

                input_values.append(tmp2)

            self._properties[sfg] = {
                "iteration_count": ic_value,
                "show_plot": self._input_fields[sfg]["show_plot"].isChecked(),
                "all_results": self._input_fields[sfg]["all_results"].isChecked(),
                "input_values": input_values,
            }

            # If we plot we should also print the entire data,
            # since you cannot really interact with the graph.
            if self._properties[sfg]["show_plot"]:
                self._properties[sfg]["all_results"] = True

        self.accept()
        self.simulate.emit()

    @property
    def properties(self) -> dict:
        """Return the simulation properties."""
        return self._properties
