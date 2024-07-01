from qtpy.QtCore import Qt
from qtpy.QtGui import QDoubleValidator
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class PropertiesWindow(QDialog):
    def __init__(self, operation, main_window):
        super().__init__()
        self.operation = operation
        self._window = main_window
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Properties")

        self._name_layout = QHBoxLayout()
        self._name_layout.setSpacing(50)
        self._name_label = QLabel("Name:")
        self._edit_name = QLineEdit(self.operation.name or self.operation.type_name)
        self._name_layout.addWidget(self._name_label)
        self._name_layout.addWidget(self._edit_name)
        self._latency_fields = {}

        self._vertical_layout = QVBoxLayout()
        self._vertical_layout.addLayout(self._name_layout)

        if hasattr(self.operation.operation, "value") or hasattr(
            self.operation.operation, "initial_value"
        ):
            self._constant_layout = QHBoxLayout()
            self._constant_layout.setSpacing(50)
            self._constant_value = QLabel("Value:")
            constant = (
                self.operation.operation.value
                if hasattr(self.operation.operation, "value")
                else self.operation.operation.initial_value
            )
            self._edit_constant = QLineEdit(str(constant))

            self._only_accept_float = QDoubleValidator()
            self._edit_constant.setValidator(self._only_accept_float)
            self._constant_layout.addWidget(self._constant_value)
            self._constant_layout.addWidget(self._edit_constant)
            self._vertical_layout.addLayout(self._constant_layout)

        self._show_name_layout = QHBoxLayout()
        self._check_show_name = QCheckBox("Show name?")
        self._check_show_name.setChecked(self.operation.show_name)
        self._check_show_name.setLayoutDirection(Qt.RightToLeft)
        self._check_show_name.setStyleSheet("spacing: 170px")
        self._show_name_layout.addWidget(self._check_show_name)
        self._vertical_layout.addLayout(self._show_name_layout)

        if self.operation.operation.input_count > 0:
            self._latency_layout = QHBoxLayout()
            self._latency_label = QLabel("Set latency for input ports (-1 for None):")
            self._latency_layout.addWidget(self._latency_label)
            self._vertical_layout.addLayout(self._latency_layout)

            input_grid = QGridLayout()
            x, y = 0, 0
            for i in range(self.operation.operation.input_count):
                input_layout = QHBoxLayout()
                input_layout.addStretch()
                if i % 2 == 0 and i > 0:
                    x += 1
                    y = 0

                input_label = QLabel(f"in{i}")
                input_layout.addWidget(input_label)
                input_value = QLineEdit()
                try:
                    input_value.setPlaceholderText(
                        str(self.operation.operation.latency)
                    )
                except ValueError:
                    input_value.setPlaceholderText("-1")
                int_valid = QDoubleValidator()
                int_valid.setBottom(-1)
                input_value.setValidator(int_valid)
                input_value.setFixedWidth(50)
                self._latency_fields[f"in{i}"] = input_value
                input_layout.addWidget(input_value)
                input_layout.addStretch()
                input_layout.setSpacing(10)
                input_grid.addLayout(input_layout, x, y)
                y += 1

            self._vertical_layout.addLayout(input_grid)

        if self.operation.operation.output_count > 0:
            self._latency_layout = QHBoxLayout()
            self._latency_label = QLabel("Set latency for output ports (-1 for None):")
            self._latency_layout.addWidget(self._latency_label)
            self._vertical_layout.addLayout(self._latency_layout)

            input_grid = QGridLayout()
            x, y = 0, 0
            for i in range(self.operation.operation.output_count):
                input_layout = QHBoxLayout()
                input_layout.addStretch()
                if i % 2 == 0 and i > 0:
                    x += 1
                    y = 0

                input_label = QLabel(f"out{i}")
                input_layout.addWidget(input_label)
                input_value = QLineEdit()
                try:
                    input_value.setPlaceholderText(
                        str(self.operation.operation.latency)
                    )
                except ValueError:
                    input_value.setPlaceholderText("-1")
                int_valid = QDoubleValidator()
                int_valid.setBottom(-1)
                input_value.setValidator(int_valid)
                input_value.setFixedWidth(50)
                self._latency_fields[f"out{i}"] = input_value
                input_layout.addWidget(input_value)
                input_layout.addStretch()
                input_layout.setSpacing(10)
                input_grid.addLayout(input_layout, x, y)
                y += 1

            self._vertical_layout.addLayout(input_grid)

        self._ok_button = QPushButton("OK")
        self._ok_button.clicked.connect(self.save_properties)
        self._vertical_layout.addWidget(self._ok_button)
        self.setLayout(self._vertical_layout)

    def save_properties(self):
        self._window._logger.info(
            f"Saving _properties of operation: {self.operation.name}."
        )
        self.operation.name = self._edit_name.text()
        self.operation.operation.name = self._edit_name.text()
        self.operation.label.setPlainText(self.operation.name)
        if hasattr(self.operation.operation, "value"):
            self.operation.operation.value = float(
                self._edit_constant.text().replace(",", ".")
            )
        elif hasattr(self.operation.operation, "initial_value"):
            self.operation.operation.initial_value = float(
                self._edit_constant.text().replace(",", ".")
            )

        if self._check_show_name.isChecked():
            self.operation.label.setOpacity(1)
            self.operation.show_name = True
        else:
            self.operation.label.setOpacity(0)
            self.operation.show_name = False

        self.operation.operation.set_latency_offsets(
            {
                port: (
                    float(latency_edit.text().replace(",", "."))
                    if latency_edit.text()
                    and float(latency_edit.text().replace(",", ".")) > 0
                    else None
                )
                for port, latency_edit in self._latency_fields.items()
            }
        )

        self.reject()
