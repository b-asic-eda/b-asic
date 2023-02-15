import sys  # ONLY FOR DEBUG

from qtpy.QtCore import Qt
from qtpy.QtGui import QCursor, QPixmap
from qtpy.QtWidgets import QApplication  # ONLY FOR DEBUG
from qtpy.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolTip,
    QVBoxLayout,
)

from b_asic._version import __version__

QUESTIONS = {
    "Adding operations": (
        "Select an operation under 'Special operations' or 'Core operations' "
        "to add it to the workspace."
    ),
    "Moving operations": (
        "To drag an operation, select the operation on the workspace and drag "
        "it around."
    ),
    "Selecting operations": (
        "To select one operation just press it once, it will then turn grey."
    ),
    "Selecting multiple operations using dragging": (
        "To select multiple operations using your mouse, \n"
        "drag the mouse while pressing left mouse button, any operation under "
        "the selection box will then be selected."
    ),
    "Selecting multiple operations using without dragging": (
        "To select multiple operations using without dragging, \n"
        "press 'Ctrl+LMouseButton' on any operation."
    ),
    "Remove operations": (
        "To remove an operation, select the operation to be deleted, \n"
        "finally press RMouseButton to bring up the context menu, then press "
        "'Delete'."
    ),
    "Remove multiple operations": (
        "To remove multiple operations, \nselect all operations to be deleted "
        "and press 'Delete' on your keyboard."
    ),
    "Connecting operations": (
        "To connect operations, select the ports on the operation to connect "
        "from, \nthen select the next port by pressing 'Ctrl+LMouseButton' on "
        "the destination port. Tip: You can chain connection by selecting the "
        "ports in the order they should be connected."
    ),
    "Creating a signal-flow-graph": (
        "To create a signal-flow-graph (SFG), \ncouple together the "
        "operations you wish to create a sfg from, then select all operations "
        "you wish to include in the sfg, \nfinally press 'Create SFG' in the "
        "upper left corner and enter the name of the sfg."
    ),
    "Simulating a signal-flow-graph": (
        "To simulate a signal-flow-graph (SFG), press the run button in the "
        "toolbar, \nthen press 'Simulate SFG' and enter the properties of the "
        "simulation."
    ),
    "Properties of simulation": (
        "The properties of the simulation are, 'Iteration Count': The number "
        "of iterations to run the simulation for, \n'Plot Results': Open a "
        "plot over the output in matplotlib, \n'Get All Results': Print the "
        "detailed output from simulating the sfg in the terminal, \n"
        "'Input Values': The input values to the SFG by index of the port."
    ),
}


class KeybindsWindow(QDialog):
    def __init__(self, window):
        super().__init__()
        self._window = window
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("B-ASIC Keybindings")

        self.dialog_layout = QVBoxLayout()
        self.setLayout(self.dialog_layout)

        self.add_information_to_layout()

    def add_information_to_layout(self):
        information_layout = QVBoxLayout()

        title_label = QLabel("B-ASIC / Better ASIC Toolbox")
        subtitle_label = QLabel("Keybindings in the GUI.")

        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        frame.setFrameShadow(QFrame.Sunken)
        self.dialog_layout.addWidget(frame)

        keybinds_label = QLabel(
            "'Ctrl+R' - Reload the operation list to add any new operations "
            "created.\n"
            "'Ctrl+Q' - Quit the application.\n"
            "'Ctrl+LMouseButton' - On a operation will select the operation, "
            "without deselecting the other operations.\n"
            "'Ctrl+S' (Plot) - Save the plot if a plot is visible.\n"
            "'Ctrl+?' - Open the FAQ section."
        )

        information_layout.addWidget(title_label)
        information_layout.addWidget(subtitle_label)

        self.dialog_layout.addLayout(information_layout)
        self.dialog_layout.addWidget(frame)

        self.dialog_layout.addWidget(keybinds_label)


class AboutWindow(QDialog):
    def __init__(self, window):
        super().__init__()
        self._window = window
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("About B-ASIC")

        self.dialog_layout = QVBoxLayout()
        self.setLayout(self.dialog_layout)

        self.add_information_to_layout()

    def hoverText(self, url):
        # self.setWindowTitle(url) # When removing mouse, the title gets "B-ASIC Scheduler". Where does THAT come from?
        if url:
            QToolTip.showText(QCursor.pos(), url)
        else:
            QToolTip.hideText()

    def add_information_to_layout(self):
        # |1 Title   |2        |
        # |  License |  Logo   |  <- layout12
        # |  Version |         |
        # ----------------------
        # |3 links     |4  OK  |  <- layout34

        label1 = QLabel(
            "# B-ASIC / Better ASIC Toolbox\n*Construct, simulate and analyze"
            " components of an ASIC.*\n\nB-ASIC is an open source tool using"
            " the B-ASIC library to construct, simulate and analyze"
            " ASICs.\n\nB-ASIC is developed under the MIT-license and any"
            " extension to the program should follow that same license.\n\nTo"
            " read more about how the GUI works please refer to the FAQ under"
            f" 'Help'.\n\n*Version: {__version__}*"
        )
        label1.setTextFormat(Qt.MarkdownText)
        label1.setWordWrap(True)
        label1.setOpenExternalLinks(True)
        label1.linkHovered.connect(self.hoverText)

        self.logo2 = QLabel(self)
        self.logo2.setPixmap(
            QPixmap("../../small_logo.png").scaledToWidth(100)
        )
        self.logo2.setFixedWidth(100)

        label3 = QLabel(
            """See: <a href="https://da.gitlab-pages.liu.se/B-ASIC/">documentation</a>,"""
            """ <a href="https://gitlab.liu.se/da/B-ASIC/">git</a>,"""
            """ <a href="https://www.liu.se/?l=en">liu.se</a>,"""
            """ <a href="https://liu.se/organisation/liu/isy/da">Computer Engineering</a>."""
        )
        label3.setOpenExternalLinks(True)
        label3.linkHovered.connect(self.hoverText)

        button4 = QPushButton()
        button4.setText("OK")
        button4.setFixedWidth(80)
        button4.clicked.connect(self.close)

        layout12 = QHBoxLayout()
        layout34 = QHBoxLayout()

        layout12.addWidget(label1)
        layout12.addWidget(self.logo2)

        layout34.addWidget(label3)
        layout34.addWidget(button4)

        hline = QFrame()
        hline.setFrameShape(QFrame.HLine)
        hline.setFrameShadow(QFrame.Sunken)

        self.dialog_layout.addLayout(layout12)
        self.dialog_layout.addWidget(hline)
        self.dialog_layout.addLayout(layout34)


class FaqWindow(QDialog):
    def __init__(self, window):
        super().__init__()
        self._window = window
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Frequently Asked Questions")

        self.dialog_layout = QVBoxLayout()
        self.scroll_area = QScrollArea()
        self.setLayout(self.dialog_layout)
        for question, answer in QUESTIONS.items():
            self.add_question_to_layout(question, answer)

        self.scroll_area.setWidget(self)
        self.scroll_area.setWidgetResizable(True)

    def add_question_to_layout(self, question, answer):
        question_layout = QVBoxLayout()
        answer_layout = QHBoxLayout()

        question_label = QLabel(question)
        question_layout.addWidget(question_label)

        answer_label = QLabel(answer)
        answer_layout.addWidget(answer_label)

        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        frame.setFrameShadow(QFrame.Sunken)
        self.dialog_layout.addWidget(frame)

        question_layout.addLayout(answer_layout)
        self.dialog_layout.addLayout(question_layout)


# ONLY FOR DEBUG below


def start_about_window():
    app = QApplication(sys.argv)
    window = AboutWindow(QDialog)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    start_about_window()
