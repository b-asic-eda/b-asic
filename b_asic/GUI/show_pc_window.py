from b_asic.signal_flow_graph import SFG

from qtpy.QtWidgets import QDialog, QPushButton, QVBoxLayout, QCheckBox,\
QFrame, QFormLayout
from qtpy.QtCore import Qt, Signal


class ShowPCWindow(QDialog):
    pc = Signal()

    def __init__(self, window):
        super(ShowPCWindow, self).__init__()
        self._window = window
        self.check_box_dict = dict()
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Show PC")

        self.dialog_layout = QVBoxLayout()
        self.pc_btn = QPushButton("Show PC")
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
                self._window.logger.info(f"Creating a precedence chart from sfg with name: {sfg}.")
                self._window.sfg_dict[sfg].show_precedence_graph()

        self.accept()
        self.pc.emit()
