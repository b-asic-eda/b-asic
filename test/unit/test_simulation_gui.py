import pytest

try:
    from qtpy import QtCore
    from b_asic.gui_utils.plot_window import PlotWindow
except ImportError:
    pytestmark = pytest.mark.skip("Qt not setup")


@pytest.mark.filterwarnings("ignore:No artists with labels found to put in legend")
def test_start(qtbot):
    widget = PlotWindow({})
    qtbot.addWidget(widget)


def test_start_with_data(qtbot):
    sim_res = {
        "0": [0.5, 0.5, 0, 0],
        "add1": [0.5, 0.5, 0, 0],
        "cmul1": [0, 0.5, 0, 0],
        "cmul2": [0.5, 0, 0, 0],
        "in1": [1, 0, 0, 0],
        "t1": [0, 1, 0, 0],
    }
    widget = PlotWindow(sim_res)
    qtbot.addWidget(widget)

    assert widget._checklist.count() == 6
    assert len(widget._plot_axes.lines) == 1


@pytest.mark.filterwarnings("ignore:No artists with labels found to put in legend")
def test_click_buttons(qtbot):
    sim_res = {
        "0": [0.5, 0.5, 0, 0],
        "add1": [0.5, 0.5, 0, 0],
        "cmul1": [0, 0.5, 0, 0],
        "cmul2": [0.5, 0, 0, 0],
        "in1": [1, 0, 0, 0],
        "t1": [0, 1, 0, 0],
    }
    widget = PlotWindow(sim_res)
    qtbot.addWidget(widget)

    assert widget._checklist.count() == 6
    assert len(widget._plot_axes.lines) == 1

    qtbot.mouseClick(widget._button_all, QtCore.Qt.MouseButton.LeftButton)
    assert len(widget._plot_axes.lines) == 6

    qtbot.mouseClick(widget._button_none, QtCore.Qt.MouseButton.LeftButton)
    assert len(widget._plot_axes.lines) == 0
