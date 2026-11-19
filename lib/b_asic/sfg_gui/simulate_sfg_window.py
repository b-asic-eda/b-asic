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

from b_asic.data_type import DataType, NumRepresentation
from b_asic.quantization import OverflowMode, QuantizationMode
from b_asic.sfg_gui.signal_generator_input import _GENERATOR_MAPPING

if TYPE_CHECKING:
    from b_asic.sfg import SFG


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
        self.setLayout(self._dialog_layout)
        self._input_files = {}

    def add_sfg_to_dialog(self, sfg: "SFG") -> None:
        """
        Add a signal flow graph to the dialog.

        Parameters
        ----------
        sfg : :class:`~b_asic.sfg.SFG`
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

        input_grid = QGridLayout()
        check_box_plot = QCheckBox()
        check_box_plot.setCheckState(Qt.CheckState.Checked)
        options_layout.addRow("Plot results: ", check_box_plot)

        check_box_all = QCheckBox()
        check_box_all.setCheckState(Qt.CheckState.Checked)
        options_layout.addRow("Get all results: ", check_box_all)

        data_type_combo = QComboBox()
        data_type_combo.addItem("Native", None)
        data_type_combo.addItem("Fixed point", NumRepresentation.FIXED_POINT)
        data_type_combo.addItem("Floating point", NumRepresentation.FLOATING_POINT)
        options_layout.addRow("Data type: ", data_type_combo)

        word_length_1 = QSpinBox()
        word_length_1.setRange(1, 1024)
        word_length_1.setValue(1)
        word_length_1_label = QLabel("Integer bits:")
        options_layout.addRow(word_length_1_label, word_length_1)

        word_length_2 = QSpinBox()
        word_length_2.setRange(0, 1024)
        word_length_2.setValue(15)
        word_length_2_label = QLabel("Fractional bits:")
        options_layout.addRow(word_length_2_label, word_length_2)

        complex_check_box = QCheckBox()
        options_layout.addRow("Complex-valued: ", complex_check_box)

        quantization_combo = QComboBox()
        for mode in QuantizationMode:
            quantization_combo.addItem(mode.name.replace("_", " ").title(), mode)
        quantization_combo.setCurrentIndex(
            quantization_combo.findData(QuantizationMode.TRUNCATION)
        )
        options_layout.addRow("Quantization: ", quantization_combo)

        overflow_combo = QComboBox()
        for mode in OverflowMode:
            overflow_combo.addItem(mode.name.replace("_", " ").title(), mode)
        options_layout.addRow("Overflow: ", overflow_combo)

        sfg_layout.addLayout(options_layout)

        fields = {
            "iteration_count": spin_box,
            "show_plot": check_box_plot,
            "all_results": check_box_all,
            "data_type": data_type_combo,
            "word_length_1": word_length_1,
            "word_length_2": word_length_2,
            "word_length_1_label": word_length_1_label,
            "word_length_2_label": word_length_2_label,
            "is_complex": complex_check_box,
            "quantization": quantization_combo,
            "overflow": overflow_combo,
            "input_grid": input_grid,
        }
        self._input_fields[sfg] = fields

        data_type_combo.currentIndexChanged.connect(
            lambda _, fields=fields: self._update_data_type_controls(fields)
        )
        self._update_data_type_controls(fields)

        if sfg.input_count > 0:
            input_label = QLabel("Input values:")
            options_layout.addRow(input_label)

            for i in range(sfg.input_count):
                input_label = QLabel(f"in{i}")
                input_grid.addWidget(input_label, i, 0)

                input_dropdown = QComboBox()
                input_dropdown.insertItems(0, list(_GENERATOR_MAPPING.keys()))
                input_dropdown.currentTextChanged.connect(
                    lambda text, i=i, grid=input_grid: self.change_input_format(
                        grid, i, text
                    )
                )
                input_grid.addWidget(input_dropdown, i, 1, alignment=Qt.AlignLeft)

                self.change_input_format(input_grid, i, "Constant")

            sfg_layout.addLayout(input_grid)

        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        frame.setFrameShadow(QFrame.Sunken)
        self._dialog_layout.addWidget(frame)

        self._sfg_to_layout[sfg] = sfg_layout
        self._dialog_layout.addLayout(sfg_layout)
        self._dialog_layout.addWidget(self._simulate_btn)

    @staticmethod
    def _update_data_type_controls(fields: dict) -> None:
        """Update the word-length controls for the selected representation."""
        num_repr = fields["data_type"].currentData()
        finite = num_repr is not None
        floating = num_repr == NumRepresentation.FLOATING_POINT

        fields["word_length_1"].setEnabled(finite)
        fields["word_length_2"].setEnabled(finite)
        fields["is_complex"].setEnabled(finite)
        fields["quantization"].setEnabled(finite and not floating)
        fields["overflow"].setEnabled(finite and not floating)

        if floating:
            fields["word_length_1_label"].setText("Exponent bits:")
            fields["word_length_2_label"].setText("Mantissa bits:")
            fields["word_length_1"].setValue(4)
            fields["word_length_2"].setRange(1, 1024)
            fields["word_length_2"].setValue(23)
        else:
            fields["word_length_1_label"].setText("Integer bits:")
            fields["word_length_2_label"].setText("Fractional bits:")
            fields["word_length_2"].setRange(0, 1024)
            if finite:
                fields["word_length_1"].setValue(1)
                fields["word_length_2"].setValue(15)

    def change_input_format(self, input_grid: QGridLayout, i: int, text: str) -> None:
        """
        Change the input format selector.

        Parameters
        ----------
        input_grid : QGridLayout
            Input grid for the signal flow graph.
        i : int
            Input number to change for.
        text : str
            Name of generator.
        """
        grid = input_grid.itemAtPosition(i, 2)
        if grid:
            for j in reversed(range(grid.count())):
                item = grid.itemAt(j)
                widget = item.widget()
                if widget:
                    widget.hide()
            input_grid.removeItem(grid)

        if text in _GENERATOR_MAPPING:
            param_grid = _GENERATOR_MAPPING[text](self._window._logger)
        else:
            raise ValueError("Input selection is not implemented")

        input_grid.addLayout(param_grid, i, 2)

    def save_properties(self) -> None:
        """Save the simulation properties and emit a signal to start the simulation."""
        for sfg in self._input_fields:
            ic_value = self._input_fields[sfg]["iteration_count"].value()
            if ic_value == 0:
                self._window._logger.error("Iteration count is set to zero.")

            input_values = []
            input_grid = self._input_fields[sfg]["input_grid"]

            for i in range(sfg.input_count):
                in_format = input_grid.itemAtPosition(i, 1).widget().currentText()
                in_param = input_grid.itemAtPosition(i, 2)

                if in_format in _GENERATOR_MAPPING:
                    tmp2 = in_param.get_generator()
                else:
                    raise ValueError("Input selection is not implemented")

                input_values.append(tmp2)

            fields = self._input_fields[sfg]
            num_repr = fields["data_type"].currentData()
            data_type = None
            if num_repr is not None:
                data_type = DataType(
                    wl=(
                        fields["word_length_1"].value(),
                        fields["word_length_2"].value(),
                    ),
                    num_repr=num_repr,
                    is_complex=fields["is_complex"].isChecked(),
                    quantization_mode=fields["quantization"].currentData(),
                    overflow_mode=fields["overflow"].currentData(),
                )

            self._properties[sfg] = {
                "iteration_count": ic_value,
                "show_plot": self._input_fields[sfg]["show_plot"].isChecked(),
                "all_results": self._input_fields[sfg]["all_results"].isChecked(),
                "input_values": input_values,
                "data_type": data_type,
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
