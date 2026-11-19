from itertools import product

import numpy as np
import pytest
from scipy.signal import freqz

try:
    from qtpy import QtCore, QtWidgets

    from b_asic.core_operations import Addition
    from b_asic.gui_utils.plot_window import PlotWindow, _InterleaveDialog
    from b_asic.sfg import SFG
    from b_asic.special_operations import Input, Output
except ImportError:
    pytestmark = pytest.mark.skip("Qt not setup")


def _visible_data_lines(axes):
    stems = [
        container
        for container in axes.containers
        if hasattr(container, "markerline") and container.markerline.get_visible()
    ]
    lines = [
        line
        for line in axes.lines
        if line.get_visible() and not line.get_label().startswith("_")
    ]
    return [*stems, *lines]


@pytest.mark.filterwarnings("ignore:No artists with labels found to put in legend")
def test_start(qtbot):
    widget = PlotWindow({})
    qtbot.addWidget(widget)
    assert widget.windowTitle() == "Simulation results"


@pytest.mark.parametrize("output_key", ["0", "out0"])
def test_named_nodes_use_names_and_graph_ids_for_result_labels(qtbot, output_key):
    source = Input()
    addition = Addition(source, source, name="Named addition")
    sfg = SFG([source], [Output(addition, name="y(n)")], name="Named graph")
    operation = sfg.find_by_name("Named addition")[0]
    key = operation.key(0, operation.graph_id)
    widget = PlotWindow(
        {key: [1, 2, 3], output_key: [1, 2, 3]},
        sfg=sfg,
    )
    qtbot.addWidget(widget)

    assert widget.windowTitle() == "Simulation results: Named graph"
    assert {
        f"Named addition ({key})",
        "y(n) (out0)",
    } == {
        widget._checklist.item(index).text()
        for index in range(widget._checklist.count())
    }
    assert [entry.get_text() for entry in widget._legend.get_texts()] == ["y(n) (out0)"]


@pytest.mark.parametrize("output_key", ["0", "out0"])
def test_start_with_data(qtbot, output_key):
    sim_res = {
        output_key: [0.5, 0.5, 0, 0],
        "add1": [0.5, 0.5, 0, 0],
        "cmul1": [0, 0.5, 0, 0],
        "cmul2": [0.5, 0, 0, 0],
        "in1": [1, 0, 0, 0],
        "t1": [0, 1, 0, 0],
    }
    widget = PlotWindow(sim_res)
    qtbot.addWidget(widget)

    assert widget._checklist.count() == 6
    assert len(_visible_data_lines(widget._plot_axes)) == 1
    assert widget._lines["out0"]["time"].get_label() == "out0"
    np.testing.assert_array_equal(
        widget._lines["out0"]["time"].markerline.get_ydata(), [0.5, 0.5, 0, 0]
    )
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
    assert len(_visible_data_lines(widget._plot_axes)) == 1

    qtbot.mouseClick(widget._button_all, QtCore.Qt.MouseButton.LeftButton)
    assert len(_visible_data_lines(widget._plot_axes)) == 6

    qtbot.mouseClick(widget._button_none, QtCore.Qt.MouseButton.LeftButton)
    assert len(_visible_data_lines(widget._plot_axes)) == 0


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
        assert len(_visible_data_lines(axes)) == 1


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
    assert all(len(_visible_data_lines(axes)) == 2 for axes in widget._axes.values())
    assert all(not legend.get_visible() for legend in widget._legends)
    widget._subplot_checkboxes["time"].setChecked(False)
    assert all(len(_visible_data_lines(axes)) == 2 for axes in widget._axes.values())
    assert all(not legend.get_visible() for legend in widget._legends)

    widget._button_none.click()
    assert all(not _visible_data_lines(axes) for axes in widget._axes.values())
    widget._checklist.item(0).setCheckState(QtCore.Qt.CheckState.Checked)
    widget._relim()
    assert all(len(_visible_data_lines(axes)) == 1 for axes in widget._axes.values())
    widget._legend_checkbox.setChecked(True)
    assert all(legend.get_visible() for legend in widget._legends)


def test_empty_frequency_results(qtbot):
    widget = PlotWindow({"0": []})
    qtbot.addWidget(widget)
    for checkbox in widget._subplot_checkboxes.values():
        checkbox.setChecked(True)
    assert all(len(axes.lines[0].get_ydata()) == 0 for axes in widget._axes.values())


@pytest.mark.parametrize("style", ["Stem", "Line"])
def test_common_time_scale_aligns_interleaved_and_original_results(qtbot, style):
    widget = PlotWindow({"0": [10, 20, 30], "1": [1, 2, 3]})
    qtbot.addWidget(widget)
    widget._set_interleaved_signal("Combined", ("out0", "out1"))
    widget._button_all.click()
    widget._time_plot_style.setCurrentText(style)

    def time_line(key):
        trace = widget._lines[key]["time"]
        return trace.markerline if style == "Stem" else trace

    original_line = time_line("out0")
    combined_line = time_line("Combined")
    np.testing.assert_array_equal(original_line.get_xdata(), [0, 1, 2])
    np.testing.assert_array_equal(combined_line.get_xdata(), np.arange(6))

    widget._common_time_scale_checkbox.setChecked(True)
    original_line = time_line("out0")
    combined_line = time_line("Combined")
    np.testing.assert_array_equal(original_line.get_xdata(), [0, 2, 4])
    np.testing.assert_array_equal(combined_line.get_xdata(), np.arange(6))
    assert widget._axes["time"].get_xlabel() == "Common sample"


def test_switch_time_plot_style_preserves_trace_selection(qtbot):
    widget = PlotWindow({"out0": [1, 2], "in0": [3, 4]})
    qtbot.addWidget(widget)
    widget._subplot_checkboxes["magnitude"].setChecked(True)
    stem = widget._axes["time"].containers[1]
    color = stem.markerline.get_color()
    assert stem.get_label() == "out0"

    widget._time_plot_style.setCurrentText("Line")
    assert not widget._axes["time"].containers
    (line,) = _visible_data_lines(widget._axes["time"])
    assert line.get_label() == "out0"
    assert line.get_color() == color
    np.testing.assert_array_equal(line.get_ydata(), [1, 2])
    assert not widget._axes["magnitude"].containers

    widget._button_all.click()
    assert len(_visible_data_lines(widget._axes["time"])) == 2
    widget._time_plot_style.setCurrentText("Stem")
    assert len(_visible_data_lines(widget._axes["time"])) == 2
    assert len(_visible_data_lines(widget._axes["magnitude"])) == 2


def test_switch_time_plot_style_preserves_zoom_and_navigation(qtbot):
    widget = PlotWindow({"out0": [1, 2, 3, 4]})
    qtbot.addWidget(widget)
    widget._subplot_checkboxes["magnitude"].setChecked(True)
    time_axes = widget._axes["time"]
    magnitude_axes = widget._axes["magnitude"]
    home_xlim, home_ylim = time_axes.get_xlim(), time_axes.get_ylim()
    widget._toolbar.push_current()

    time_axes.set(xlim=(1.25, 2.75), ylim=(2, 3.5))
    magnitude_axes.set(xlim=(0.2, 0.6), ylim=(2, 5))
    widget._toolbar.push_current()

    for style in ("Line", "Stem"):
        widget._time_plot_style.setCurrentText(style)
        assert widget._axes["time"].get_xlim() == (1.25, 2.75)
        assert widget._axes["time"].get_ylim() == (2, 3.5)
        assert widget._axes["magnitude"].get_xlim() == (0.2, 0.6)
        assert widget._axes["magnitude"].get_ylim() == (2, 5)

    widget._toolbar.back()
    assert widget._axes["time"].get_xlim() == home_xlim
    assert widget._axes["time"].get_ylim() == home_ylim
    widget._toolbar.forward()
    assert widget._axes["time"].get_xlim() == (1.25, 2.75)
    assert widget._axes["time"].get_ylim() == (2, 3.5)
    widget._relim()
    assert widget._axes["time"].get_xlim() == home_xlim
    assert widget._axes["time"].get_ylim() == home_ylim


def test_new_interleaved_entries_use_distinct_stem_colors(qtbot):
    widget = PlotWindow({"0": [0, 2], "1": [1, 3]})
    qtbot.addWidget(widget)
    widget._set_interleaved_signal("Combined", ("out0", "out1"))

    colors = [
        widget._lines[key]["time"].markerline.get_color()
        for key in ("out0", "out1", "Combined")
    ]
    assert len(set(colors)) == 3


def test_interleave_preview_plots_and_order(qtbot):
    dialog = _InterleaveDialog(
        {"o0": [0, 2, 4], "o1": [1, 3, 5]}, selected=("o0", "o1")
    )
    qtbot.addWidget(dialog)
    np.testing.assert_array_equal(
        dialog._preview_axes["time"].lines[0].get_ydata(), np.arange(6)
    )
    frequency, response = freqz(np.arange(6))
    for name, expected in (
        ("magnitude", np.abs(response)),
        ("phase", np.unwrap(np.angle(response))),
    ):
        line = dialog._preview_axes[name].lines[0]
        np.testing.assert_allclose(line.get_xdata(), frequency / np.pi)
        np.testing.assert_allclose(line.get_ydata(), expected)
    assert dialog.signal_name == "interleave(o0, o1)"
    assert not dialog._button_up.isEnabled()

    qtbot.mouseClick(dialog._button_down, QtCore.Qt.MouseButton.LeftButton)
    assert dialog.source_names == ("o1", "o0")
    assert dialog.signal_name == "interleave(o1, o0)"
    np.testing.assert_array_equal(
        dialog._preview_axes["time"].lines[0].get_ydata(), [1, 0, 3, 2, 5, 4]
    )
    _, response = freqz([1, 0, 3, 2, 5, 4])
    np.testing.assert_allclose(
        dialog._preview_axes["magnitude"].lines[0].get_ydata(), np.abs(response)
    )
    assert not dialog._button_down.isEnabled()
    qtbot.mouseClick(dialog._button_up, QtCore.Qt.MouseButton.LeftButton)
    assert dialog.source_names == ("o0", "o1")


@pytest.mark.parametrize(
    ("results", "selected", "error"),
    [
        ({"o0": [1], "o1": [2]}, (), "at least two"),
        ({"o0": [1], "o1": [2]}, ("o0",), "at least two"),
        ({"o0": [1], "o1": [2, 3]}, ("o0", "o1"), "same number"),
    ],
)
def test_interleave_preview_invalid_streams(qtbot, results, selected, error):
    dialog = _InterleaveDialog(results, selected=selected)
    qtbot.addWidget(dialog)
    assert error in dialog._error_label.text()
    assert not dialog._buttons.button(
        QtWidgets.QDialogButtonBox.StandardButton.Ok
    ).isEnabled()
    assert all(not axes.lines for axes in dialog._preview_axes.values())
    dialog.accept()
    assert dialog.result() == QtWidgets.QDialog.DialogCode.Rejected


def test_interleave_preview_selection_and_name_validation(qtbot):
    dialog = _InterleaveDialog(
        {"o0": [1, 2], "o1": [3, 4]}, reserved_names={"o0", "taken_re"}
    )
    qtbot.addWidget(dialog)
    create = dialog._buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
    for index in range(dialog._source_list.count()):
        dialog._source_list.item(index).setCheckState(QtCore.Qt.CheckState.Checked)
    assert create.isEnabled()
    assert len(_visible_data_lines(dialog._preview_axes["time"])) == 1
    for name in ("o0", "taken"):
        dialog._name_edit.setText(name)
        assert not create.isEnabled()
        assert "already exists" in dialog._error_label.text()
    dialog._name_edit.setText("Custom signal")
    assert create.isEnabled()
    assert dialog.signal_name == "Custom signal"
    dialog._source_list.item(0).setCheckState(QtCore.Qt.CheckState.Unchecked)
    assert not create.isEnabled()
    assert all(not axes.lines for axes in dialog._preview_axes.values())


def test_create_interleaved_signal_from_dialog(qtbot, monkeypatch):
    widget = PlotWindow({"0": [0, 2, 4], "1": [1, 3, 5]})
    qtbot.addWidget(widget)

    def create(dialog):
        assert dialog.source_names == ("out0", "out1")
        dialog._name_edit.setText("Combined")
        dialog._buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).click()
        return dialog.result()

    monkeypatch.setattr(_InterleaveDialog, "exec_", create)
    widget._button_interleave.click()
    assert widget._interleaved_signals == {"Combined": ("out0", "out1")}
    np.testing.assert_array_equal(widget._results["Combined"], np.arange(6))
    assert widget._checklist.count() == 3
    widget._button_none.click()
    item = widget._checklist.findItems("Combined", QtCore.Qt.MatchFlag.MatchExactly)[0]
    item.setCheckState(QtCore.Qt.CheckState.Checked)
    for checkbox in widget._subplot_checkboxes.values():
        checkbox.setChecked(True)
    np.testing.assert_array_equal(
        widget._lines["Combined"]["time"].markerline.get_ydata(), np.arange(6)
    )
    frequency, response = freqz(np.arange(6))
    for name, expected in (
        ("magnitude", np.abs(response)),
        ("phase", np.unwrap(np.angle(response))),
    ):
        line = widget._axes[name].lines[0]
        np.testing.assert_allclose(line.get_xdata(), frequency / np.pi)
        np.testing.assert_allclose(line.get_ydata(), expected)


def test_cancel_interleaved_signal(qtbot, monkeypatch):
    widget = PlotWindow({"0": [1, 2], "1": [3, 4]})
    qtbot.addWidget(widget)

    def cancel(dialog):
        dialog.reject()
        return dialog.result()

    monkeypatch.setattr(_InterleaveDialog, "exec_", cancel)
    widget._button_interleave.click()
    assert not widget._interleaved_signals
    assert widget._checklist.count() == 2
    assert widget._selected_keys == {"out0", "out1"}


def test_complex_interleaving_and_frequency_visibility(qtbot):
    widget = PlotWindow({"0": [1 + 2j, 3 - 4j], "1": [5 + 6j, 7 - 8j]})
    qtbot.addWidget(widget)
    widget._button_none.click()
    widget._set_interleaved_signal("Combined", ("out0", "out1"))
    expected = np.array([1 + 2j, 5 + 6j, 3 - 4j, 7 - 8j])
    np.testing.assert_array_equal(widget._raw_results["Combined"], expected)
    np.testing.assert_array_equal(widget._results["Combined_re"], expected.real)
    np.testing.assert_array_equal(widget._results["Combined_im"], expected.imag)
    for checkbox in widget._subplot_checkboxes.values():
        checkbox.setChecked(True)
    assert len(_visible_data_lines(widget._axes["time"])) == 2
    frequency, response = freqz(expected)
    for name, values in (
        ("magnitude", np.abs(response)),
        ("phase", np.unwrap(np.angle(response))),
    ):
        assert len(widget._axes[name].lines) == 1
        line = widget._axes[name].lines[0]
        np.testing.assert_allclose(line.get_xdata(), frequency / np.pi)
        np.testing.assert_allclose(line.get_ydata(), values)

    for suffix, count in (("_re", 1), ("_im", 0)):
        item = widget._checklist.findItems(
            "Combined" + suffix, QtCore.Qt.MatchFlag.MatchExactly
        )[0]
        item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        assert len(widget._axes["magnitude"].lines) == count
    item = widget._checklist.findItems(
        "Combined_mag", QtCore.Qt.MatchFlag.MatchExactly
    )[0]
    item.setCheckState(QtCore.Qt.CheckState.Checked)
    assert len(widget._axes["magnitude"].lines) == 1
    widget._button_all.click()
    assert len(widget._axes["magnitude"].lines) == 3
    widget._button_none.click()
    assert all(not _visible_data_lines(axes) for axes in widget._axes.values())


def test_complex_interleave_preview(qtbot):
    dialog = _InterleaveDialog({"o0": [1 + 2j], "o1": [3 - 4j]}, selected=("o0", "o1"))
    qtbot.addWidget(dialog)
    assert len(_visible_data_lines(dialog._preview_axes["time"])) == 2
    _, response = freqz([1 + 2j, 3 - 4j])
    np.testing.assert_allclose(
        dialog._preview_axes["magnitude"].lines[0].get_ydata(), np.abs(response)
    )


def test_edit_and_remove_interleaved_signals(qtbot, monkeypatch):
    widget = PlotWindow({"0": [0, 2, 4], "1": [1, 3, 5]})
    qtbot.addWidget(widget)
    widget._set_interleaved_signal("First", ("out0", "out1"))
    widget._set_interleaved_signal("Second", ("out1", "out0"))
    widget._subplot_checkboxes["magnitude"].setChecked(True)
    old_response = widget._frequency_results["First"][1].copy()
    widget._set_interleaved_signal("First", ("out1", "out0"), previous_name="First")
    expected = [1, 0, 3, 2, 5, 4]
    _, response = freqz(expected)
    assert not np.allclose(old_response, response)
    np.testing.assert_allclose(widget._frequency_results["First"][1], response)

    def edit(dialog):
        assert dialog.source_names == ("out1", "out0")
        dialog._name_edit.setText("Renamed")
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(_InterleaveDialog, "exec_", edit)
    widget._edit_interleaved_signal("First")
    assert "First" not in widget._raw_results
    assert "First" not in widget._frequency_results
    assert "First" not in widget._selected_keys
    assert "Renamed" in widget._selected_keys
    np.testing.assert_array_equal(widget._results["Renamed"], expected)
    widget._remove_interleaved_signal("Renamed")
    assert set(widget._raw_results) == {"out0", "out1", "Second"}
    assert "Renamed" not in widget._frequency_results
    assert "Renamed" not in widget._lines
    assert widget._checklist.count() == 3
    np.testing.assert_array_equal(widget._results["Second"], expected)


@pytest.mark.parametrize(
    ("name", "sources", "error"),
    [
        ("Combined", ("out0",), "at least two"),
        ("Combined", ("out0", "out0"), "only once"),
        ("Combined", ("out0", "out2"), "same number"),
        ("out0", ("out0", "out1"), "already exists"),
        ("taken", ("out0", "out1"), "already exists"),
        ("", ("out0", "out1"), "Enter a signal name"),
    ],
)
def test_invalid_interleaving_leaves_signals_unchanged(qtbot, name, sources, error):
    widget = PlotWindow({"0": [1], "1": [2], "2": [3, 4], "taken_re": [5]})
    qtbot.addWidget(widget)
    with pytest.raises(ValueError, match=error):
        widget._set_interleaved_signal(name, sources)
    assert not widget._interleaved_signals
    assert widget._checklist.count() == 4


def test_empty_interleaved_signal_and_no_subplots(qtbot):
    dialog = _InterleaveDialog({"o0": [], "o1": []}, selected=("o0", "o1"))
    qtbot.addWidget(dialog)
    assert dialog._buttons.button(
        QtWidgets.QDialogButtonBox.StandardButton.Ok
    ).isEnabled()
    assert all(not axes.lines for axes in list(dialog._preview_axes.values())[1:])
    widget = PlotWindow({"0": [], "1": []})
    qtbot.addWidget(widget)
    widget._subplot_checkboxes["time"].setChecked(False)
    widget._set_interleaved_signal("Empty", ("out0", "out1"))
    assert not widget._axes
    widget._subplot_checkboxes["magnitude"].setChecked(True)
    assert len(widget._lines["Empty"]["magnitude"].get_ydata()) == 0


@pytest.mark.parametrize("results", [{}, {"0": [1]}])
def test_interleave_button_needs_multiple_sources(qtbot, results):
    widget = PlotWindow(results)
    qtbot.addWidget(widget)
    assert not widget._button_interleave.isEnabled()


@pytest.mark.parametrize("action_index", [0, 1])
def test_interleaving_context_menu(qtbot, monkeypatch, action_index):
    widget = PlotWindow({"0": [1 + 2j], "1": [3]})
    qtbot.addWidget(widget)
    widget._set_interleaved_signal("Combined", ("out0", "out1"))
    widget.show()
    item = widget._checklist.findItems("Combined_im", QtCore.Qt.MatchFlag.MatchExactly)[
        0
    ]
    widget._checklist.scrollToItem(item)

    def choose_action(menu, position):
        menu.actions()[action_index].trigger()

    def edit(dialog):
        assert dialog.source_names == ("out0", "out1")
        dialog._button_down.click()
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(QtWidgets.QMenu, "exec_", choose_action)
    monkeypatch.setattr(_InterleaveDialog, "exec_", edit)
    widget._checklist_context_menu(widget._checklist.visualItemRect(item).center())
    if action_index == 0:
        assert widget._interleaved_signals["Combined"] == ("out1", "out0")
        np.testing.assert_array_equal(widget._raw_results["Combined"], [3, 1 + 2j])
    else:
        assert not widget._interleaved_signals
        assert "Combined_re" not in widget._results
        assert "Combined_im" not in widget._selected_keys


def test_interleaved_signal_visibility_after_edit(qtbot):
    widget = PlotWindow({"0": [1 + 2j], "1": [3], "2": [4]})
    qtbot.addWidget(widget)
    widget._button_none.click()
    widget._set_interleaved_signal("Combined", ("out0", "out1"))
    widget._set_interleaved_signal(
        "Combined", ("out1", "out2"), previous_name="Combined"
    )
    assert widget._selected_keys == {"Combined"}
    assert "Combined_re" not in widget._results
    np.testing.assert_array_equal(widget._results["Combined"], [3, 4])
    widget._button_none.click()
    widget._set_interleaved_signal(
        "Renamed", ("out0", "out1"), previous_name="Combined"
    )
    assert not widget._selected_keys
    assert not _visible_data_lines(widget._axes["time"])
