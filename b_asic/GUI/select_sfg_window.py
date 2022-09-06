from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QComboBox, QDialog, QPushButton, QVBoxLayout


class SelectSFGWindow(QDialog):
    ok = Signal()

    def __init__(self, window):
        super().__init__()
        self._window = window
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Select SFG")

        self.dialog_layout = QVBoxLayout()
        self.ok_btn = QPushButton("Ok")
        self.ok_btn.clicked.connect(self.save_properties)
        self.dialog_layout.addWidget(self.ok_btn)
        self.combo_box = QComboBox()

        self.sfg = None
        self.setLayout(self.dialog_layout)
        self.add_sfgs_to_layout()

    def add_sfgs_to_layout(self):
        for sfg in self._window.sfg_dict:
            self.combo_box.addItem(sfg)

        self.dialog_layout.addWidget(self.combo_box)

    def save_properties(self):
        self.sfg = self._window.sfg_dict[self.combo_box.currentText()]
        self.accept()
        self.ok.emit()
