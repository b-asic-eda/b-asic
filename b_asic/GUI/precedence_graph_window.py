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


class PrecedenceGraphWindow(QDialog):
    """Precedence graph window."""

    pc = Signal()

    def __init__(self, window):
        super().__init__()
        self._window = window
        self._check_box_dict = {}
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Show precedence graph")

        self._dialog_layout = QVBoxLayout()
        self._show_precedence_graph_button = QPushButton("Show precedence graph")
        self._show_precedence_graph_button.clicked.connect(self.show_precedence_graph)
        self._dialog_layout.addWidget(self._show_precedence_graph_button)
        self.setLayout(self._dialog_layout)

    def add_sfg_to_dialog(self):
        if not self._window._sfg_dict:
            self.accept()
            self.pc.emit()

        self._sfg_layout = QVBoxLayout()
        self._options_layout = QFormLayout()

        for sfg in self._window._sfg_dict:
            check_box = QCheckBox()
            self._options_layout.addRow(sfg, check_box)
            self._check_box_dict[check_box] = sfg

        self._sfg_layout.addLayout(self._options_layout)

        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        frame.setFrameShadow(QFrame.Sunken)
        self._dialog_layout.addWidget(frame)

        self._dialog_layout.addLayout(self._sfg_layout)
        if len(self._check_box_dict) == 1:
            check_box = list(self._check_box_dict.keys())[0]
            check_box.setChecked(True)

    def show_precedence_graph(self):
        for check_box, sfg in self._check_box_dict.items():
            if check_box.isChecked():
                self._window._logger.info(
                    f"Creating a precedence graph from SFG with name: {sfg}."
                )
                self._window._sfg_dict[sfg].show_precedence_graph()

        self.accept()
        self.pc.emit()
