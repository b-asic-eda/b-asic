"""
B-ASIC select SFG window.
"""
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QComboBox, QDialog, QPushButton, QVBoxLayout

if TYPE_CHECKING:
    from b_asic.GUI.main_window import MainWindow


class SelectSFGWindow(QDialog):
    ok = Signal()

    def __init__(self, window: "MainWindow"):
        super().__init__()
        self._window = window
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Select SFG")

        self._dialog_layout = QVBoxLayout()
        self._ok_button = QPushButton("Ok")
        self._ok_button.clicked.connect(self.save_properties)
        self._dialog_layout.addWidget(self._ok_button)
        self._sfg_combo_box = QComboBox()

        self.sfg = None
        self.setLayout(self._dialog_layout)

        # Add SFGs to layout
        for sfg in self._window._sfg_dict:
            self._sfg_combo_box.addItem(sfg)

        self._dialog_layout.addWidget(self._sfg_combo_box)

    def save_properties(self):
        self.sfg = self._window._sfg_dict[self._sfg_combo_box.currentText()]
        self.accept()
        self.ok.emit()
