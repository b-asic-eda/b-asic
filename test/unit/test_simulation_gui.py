from itertools import product

import numpy as np
import pytest
from scipy.signal import freqz

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
    assert widget._plot_axes.xaxis.label.get_fontfamily() == ["DejaVu Serif"]
    assert widget._legend.get_texts()[0].get_fontfamily() == ["DejaVu Serif"]
    widget._update_legend()
    assert widget._legend.get_texts()[0].get_fontfamily() == ["DejaVu Serif"]


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


@pytest.mark.parametrize("enabled", list(product((False, True), repeat=3)))
def test_subplot_combinations(qtbot, enabled):
    widget = PlotWindow({"0": [1, 0.5, 0]})
    qtbot.addWidget(widget)

    for checkbox, checked in zip(
        widget._subplot_checkboxes.values(), enabled, strict=True
    ):
        checkbox.setChecked(checked)

    names = ["time", "magnitude", "phase"]
    selected = [name for name, checked in zip(names, enabled, strict=True) if checked]
    assert list(widget._axes) == selected
    assert widget._plot_fig.axes == list(widget._axes.values())
    for index, axes in enumerate(widget._plot_fig.axes):
        assert axes.get_subplotspec().num1 == index
        assert axes.get_subplotspec().get_gridspec().nrows == len(selected)
        assert axes.get_subplotspec().get_gridspec().ncols == 1
        assert len(axes.lines) == 1


def test_frequency_data_and_controls(qtbot):
    result = [0, 0, 0.5, 0.5]
    widget = PlotWindow({"0": result, "in0": [1, 0, 0]})
    qtbot.addWidget(widget)
    for checkbox in widget._subplot_checkboxes.values():
        checkbox.setChecked(True)

    frequency, response = freqz(result)
    for name, expected in (
        ("magnitude", np.abs(response)),
        ("phase", np.unwrap(np.angle(response))),
    ):
        line = widget._axes[name].lines[0]
        np.testing.assert_allclose(line.get_xdata(), frequency / np.pi)
        np.testing.assert_allclose(line.get_ydata(), expected)

    widget._legend_checkbox.setChecked(False)
    widget._button_all.click()
    assert all(len(axes.lines) == 2 for axes in widget._axes.values())
    assert all(not legend.get_visible() for legend in widget._legends)
    widget._subplot_checkboxes["time"].setChecked(False)
    assert all(len(axes.lines) == 2 for axes in widget._axes.values())
    assert all(not legend.get_visible() for legend in widget._legends)

    widget._button_none.click()
    assert all(not axes.lines for axes in widget._axes.values())
    widget._checklist.item(0).setCheckState(QtCore.Qt.CheckState.Checked)
    widget._relim()
    assert all(len(axes.lines) == 1 for axes in widget._axes.values())
    widget._legend_checkbox.setChecked(True)
    assert all(legend.get_visible() for legend in widget._legends)


def test_empty_frequency_results(qtbot):
    widget = PlotWindow({"0": []})
    qtbot.addWidget(widget)
    for checkbox in widget._subplot_checkboxes.values():
        checkbox.setChecked(True)
    assert all(len(axes.lines[0].get_ydata()) == 0 for axes in widget._axes.values())
