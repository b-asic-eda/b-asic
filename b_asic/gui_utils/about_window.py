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
    QToolTip,
    QVBoxLayout,
)

from b_asic._version import __version__


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


# ONLY FOR DEBUG below


def start_about_window():
    app = QApplication(sys.argv)
    window = AboutWindow(QDialog)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    start_about_window()
