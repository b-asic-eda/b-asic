"""
B-ASIC window to show precedence graph.
"""
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QPushButton,
    QVBoxLayout,
)


class ShowPCWindow(QDialog):
    pc = Signal()

    def __init__(self, window):
        super().__init__()
        self._window = window
        self.check_box_dict = {}
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Show precedence graph")

        self.dialog_layout = QVBoxLayout()
        self.pc_btn = QPushButton("Show PG")
        self.pc_btn.clicked.connect(self.show_precedence_graph)
        self.dialog_layout.addWidget(self.pc_btn)
        self.setLayout(self.dialog_layout)

    def add_sfg_to_dialog(self):
        self.sfg_layout = QVBoxLayout()
        self.options_layout = QFormLayout()

        for sfg in self._window.sfg_dict:
            check_box = QCheckBox()
            self.options_layout.addRow(sfg, check_box)
            self.check_box_dict[check_box] = sfg

        self.sfg_layout.addLayout(self.options_layout)

        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        frame.setFrameShadow(QFrame.Sunken)
        self.dialog_layout.addWidget(frame)

        self.dialog_layout.addLayout(self.sfg_layout)

    def show_precedence_graph(self):
        for check_box, sfg in self.check_box_dict.items():
            if check_box.isChecked():
                self._window.logger.info(
                    f"Creating a precedence graph from SFG with name: {sfg}."
                )
                self._window.sfg_dict[sfg].show_precedence_graph()

        self.accept()
        self.pc.emit()
