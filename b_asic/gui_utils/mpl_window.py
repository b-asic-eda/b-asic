"""MPLWindow is a dialog that provides an Axes for plotting in."""

from matplotlib.axes import Axes
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog, QVBoxLayout


class MPLWindow(QDialog):
    """
    Dialog for plotting Matplotlib things.
    """

    def __init__(self, title: str = "B-ASIC", subplots=(1, 1)) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )
        self.setWindowTitle(title)

        self._dialog_layout = QVBoxLayout()
        self.setLayout(self._dialog_layout)

        self._plot_fig = Figure(figsize=(5, 4), layout="constrained")
        self._plot_axes = self._plot_fig.subplots(*subplots)

        self._plot_canvas = FigureCanvas(self._plot_fig)
        self._toolbar = NavigationToolbar(self._plot_canvas, self)

        self._dialog_layout.addWidget(self._toolbar)
        self._dialog_layout.addWidget(self._plot_canvas)

    @property
    def axes(self) -> Axes | list[Axes]:
        return self._plot_axes

    def redraw(self) -> None:
        self._plot_canvas.draw()
