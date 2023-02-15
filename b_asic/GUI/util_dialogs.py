from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
)

_QUESTIONS = {
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


class FaqWindow(QDialog):
    def __init__(self, window):
        super().__init__()
        self._window = window
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Frequently Asked Questions")

        self.dialog_layout = QVBoxLayout()
        self.scroll_area = QScrollArea()
        self.setLayout(self.dialog_layout)
        for question, answer in _QUESTIONS.items():
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
