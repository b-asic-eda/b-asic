import pathlib
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
    """About window."""

    def __init__(self, window):
        super().__init__()
        self._window = window
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("About B-ASIC")

        self._dialog_layout = QVBoxLayout()
        self.setLayout(self._dialog_layout)

        self._add_information_to_layout()

    def _hover_text(self, url):
        # self.setWindowTitle(url)
        # When removing mouse, the title gets "B-ASIC Scheduler".
        # Where does THAT come from?
        if url:
            QToolTip.showText(QCursor.pos(), url)
        else:
            QToolTip.hideText()

    def _add_information_to_layout(self):
        # |1 Title   |2        |
        # |  License |  Logo   |  <- layout12
        # |  Version |         |
        # ----------------------
        # |3 links     |4  OK  |  <- layout34

        label1 = QLabel(
            "# B-ASIC\n__Better ASIC and FPGA Signal Processing"
            " Toolbox__\n\n*Construct, simulate and analyze signal processing"
            " algorithms aimed at implementation on an ASIC or"
            " FPGA.*\n\nB-ASIC is developed by the <a"
            " href=\"https://liu.se/en/organisation/liu/isy/elda\">Division of"
            " Electronics and Computer Engineering</a> at <a"
            " href=\"https://liu.se/?l=en\">Linköping University</a>,"
            " Sweden.\n\nB-ASIC is released under the <a"
            " href=\"https://gitlab.liu.se/da/B-ASIC/-/blob/master/LICENSE\">"
            "MIT-license</a>"
            " and any extension to the program should follow that same"
            f" license.\n\n*Version: {__version__}*\n\nCopyright 2020-2025,"
            " Oscar Gustafsson et al."
        )
        label1.setTextFormat(Qt.MarkdownText)
        label1.setWordWrap(True)
        label1.setOpenExternalLinks(True)
        label1.linkHovered.connect(self._hover_text)

        self.logo2 = QLabel(self)
        self.logo2.setPixmap(
            QPixmap(
                str(pathlib.Path(__file__).parent.resolve())
                + "/../../logos/small_logo.png"
            ).scaledToWidth(100)
        )
        self.logo2.setFixedWidth(100)

        label3 = QLabel(
            'Additional resources: <a href="https://da.gitlab-pages.liu.se/B-ASIC/">'
            'documentation</a>,'
            ' <a href="https://gitlab.liu.se/da/B-ASIC/">git repository</a>,'
            ' <a href="https://gitlab.liu.se/da/B-ASIC/-/issues">report issues and'
            ' suggestions</a>.'
        )
        label3.setOpenExternalLinks(True)
        label3.linkHovered.connect(self._hover_text)

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

        self._dialog_layout.addLayout(layout12)
        self._dialog_layout.addWidget(hline)
        self._dialog_layout.addLayout(layout34)


# ONLY FOR DEBUG below


def show_about_window():
    """Simply show the about window."""
    app = QApplication(sys.argv)
    window = AboutWindow(QDialog)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    show_about_window()
