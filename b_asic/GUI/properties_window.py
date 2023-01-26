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

        self.name_layout = QHBoxLayout()
        self.name_layout.setSpacing(50)
        self.name_label = QLabel("Name:")
        self.edit_name = QLineEdit(
            self.operation.name or self.operation.type_name
        )
        self.name_layout.addWidget(self.name_label)
        self.name_layout.addWidget(self.edit_name)
        self.latency_fields = {}

        self.vertical_layout = QVBoxLayout()
        self.vertical_layout.addLayout(self.name_layout)

        if hasattr(self.operation.operation, "value") or hasattr(
            self.operation.operation, "initial_value"
        ):
            self.constant_layout = QHBoxLayout()
            self.constant_layout.setSpacing(50)
            self.constant_value = QLabel("Value:")
            if hasattr(self.operation.operation, "value"):
                self.edit_constant = QLineEdit(
                    str(self.operation.operation.value)
                )
            else:
                self.edit_constant = QLineEdit(
                    str(self.operation.operation.initial_value)
                )

            self.only_accept_float = QDoubleValidator()
            self.edit_constant.setValidator(self.only_accept_float)
            self.constant_layout.addWidget(self.constant_value)
            self.constant_layout.addWidget(self.edit_constant)
            self.vertical_layout.addLayout(self.constant_layout)

        self.show_name_layout = QHBoxLayout()
        self.check_show_name = QCheckBox("Show name?")
        if self.operation.is_show_name:
            self.check_show_name.setChecked(1)
        else:
            self.check_show_name.setChecked(0)
        self.check_show_name.setLayoutDirection(Qt.RightToLeft)
        self.check_show_name.setStyleSheet("spacing: 170px")
        self.show_name_layout.addWidget(self.check_show_name)
        self.vertical_layout.addLayout(self.show_name_layout)

        if self.operation.operation.input_count > 0:
            self.latency_layout = QHBoxLayout()
            self.latency_label = QLabel(
                "Set latency for input ports (-1 for None):"
            )
            self.latency_layout.addWidget(self.latency_label)
            self.vertical_layout.addLayout(self.latency_layout)

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
                self.latency_fields[f"in{i}"] = input_value
                input_layout.addWidget(input_value)
                input_layout.addStretch()
                input_layout.setSpacing(10)
                input_grid.addLayout(input_layout, x, y)
                y += 1

            self.vertical_layout.addLayout(input_grid)

        if self.operation.operation.output_count > 0:
            self.latency_layout = QHBoxLayout()
            self.latency_label = QLabel(
                "Set latency for output ports (-1 for None):"
            )
            self.latency_layout.addWidget(self.latency_label)
            self.vertical_layout.addLayout(self.latency_layout)

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
                self.latency_fields[f"out{i}"] = input_value
                input_layout.addWidget(input_value)
                input_layout.addStretch()
                input_layout.setSpacing(10)
                input_grid.addLayout(input_layout, x, y)
                y += 1

            self.vertical_layout.addLayout(input_grid)

        self.ok = QPushButton("OK")
        self.ok.clicked.connect(self.save_properties)
        self.vertical_layout.addWidget(self.ok)
        self.setLayout(self.vertical_layout)

    def save_properties(self):
        self._window.logger.info(
            f"Saving properties of operation: {self.operation.name}."
        )
        self.operation.name = self.edit_name.text()
        self.operation.operation.name = self.edit_name.text()
        self.operation.label.setPlainText(self.operation.name)
        if hasattr(self.operation.operation, "value"):
            self.operation.operation.value = float(
                self.edit_constant.text().replace(",", ".")
            )
        elif hasattr(self.operation.operation, "initial_value"):
            self.operation.operation.initial_value = float(
                self.edit_constant.text().replace(",", ".")
            )

        if self.check_show_name.isChecked():
            self.operation.label.setOpacity(1)
            self.operation.is_show_name = True
        else:
            self.operation.label.setOpacity(0)
            self.operation.is_show_name = False

        self.operation.operation.set_latency_offsets(
            {
                port: float(self.latency_fields[port].text().replace(",", "."))
                if self.latency_fields[port].text()
                and float(self.latency_fields[port].text().replace(",", "."))
                > 0
                else None
                for port in self.latency_fields
            }
        )

        self.reject()
