"""SFG editor selection, simulation, and precedence graph actions."""

import numpy as np
import pytest
from graphviz import Digraph

pytest.importorskip("qtpy.QtWidgets", exc_type=ImportError)

from qtpy.QtCore import QSettings, Qt, QThread
from qtpy.QtWidgets import QDialog, QPushButton

from b_asic.port import InputPort, OutputPort
from b_asic.sfg_gui import main_window
from b_asic.sfg_gui.main_window import SFGMainWindow
from b_asic.sfg_gui.simulation_worker import SimulationWorker
from b_asic.special_operations import Input
from b_asic.special_operations import Output as SFGOutput


@pytest.fixture
def sfg_window(qtbot, monkeypatch, tmp_path):
    settings = QSettings(str(tmp_path / "sfg.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(main_window, "QSettings", lambda: settings)
    widget = SFGMainWindow()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def loaded_sfg_window(sfg_window, sfg_two_tap_fir):
    sfg_window._load_sfg(sfg_two_tap_fir)
    return sfg_window


def _assert_selected(widget, selected):
    assert set(widget._pressed_operations) == set(selected)
    assert len(widget._pressed_operations) == len(selected)
    for button in widget._drag_buttons.values():
        assert button.pressed == (button in selected)


@pytest.mark.parametrize(
    ("action_name", "message"),
    [
        ("select_all", "No operations to select"),
        ("unselect_all", "No operations to unselect"),
        ("actionSimulateSFG", "No SFG to simulate"),
        ("actionShowPC", "No SFG to show"),
    ],
)
def test_actions_without_operations(sfg_window, action_name, message):
    getattr(sfg_window._ui, action_name).trigger()

    assert sfg_window._statusbar.currentMessage() == message
    assert not sfg_window._pressed_operations
    assert not sfg_window._plot
    assert not hasattr(sfg_window, "_simulation_dialog")
    assert not hasattr(sfg_window, "_precedence_graph_dialog")


def test_click_selects_operation_and_replaces_previous_selection(
    loaded_sfg_window, qtbot
):
    widget = loaded_sfg_window
    first, second, *_ = widget._drag_buttons.values()
    _assert_selected(widget, [])

    qtbot.mouseClick(first, Qt.MouseButton.LeftButton)
    _assert_selected(widget, [first])

    qtbot.mouseClick(first, Qt.MouseButton.LeftButton)
    _assert_selected(widget, [first])

    qtbot.mouseClick(second, Qt.MouseButton.LeftButton)
    _assert_selected(widget, [second])


def test_control_click_selects_and_unselects_individual_operations(
    loaded_sfg_window, qtbot
):
    widget = loaded_sfg_window
    first, second, *_ = widget._drag_buttons.values()

    for button, selected in (
        (first, [first]),
        (second, [first, second]),
        (first, [second]),
        (second, []),
    ):
        qtbot.mouseClick(
            button, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier
        )
        _assert_selected(widget, selected)


def test_nested_sfg_can_be_expanded_and_closed(sfg_window, sfg_two_tap_fir, qtbot):
    sfg_window._insert_generated_sfg(sfg_two_tap_fir)
    button = sfg_window._drag_buttons[sfg_two_tap_fir]
    assert not button.findChild(QPushButton, "expandSfgButton")

    qtbot.mouseDClick(button, Qt.MouseButton.LeftButton)
    expanded = sfg_window._expanded_sfg_windows[button]
    assert expanded.isVisible()
    assert {op.graph_id for op in expanded._drag_buttons} == {
        op.graph_id for op in sfg_two_tap_fir.split()
    }

    expanded.close()
    assert not expanded.isVisible()

    assert button.operation.input_count == sfg_two_tap_fir.input_count
    assert button.operation.output_count == sfg_two_tap_fir.output_count


def test_expanded_sfg_retains_removed_operation_after_reopen(
    sfg_window, sfg_two_tap_fir, qtbot
):
    sfg_window._insert_generated_sfg(sfg_two_tap_fir)
    button = sfg_window._drag_buttons[sfg_two_tap_fir]
    qtbot.mouseDClick(button, Qt.MouseButton.LeftButton)
    expanded = sfg_window._expanded_sfg_windows[button]

    removed = next(iter(expanded._drag_buttons.values()))
    removed.remove()
    expanded.close()
    qtbot.mouseDClick(button, Qt.MouseButton.LeftButton)
    assert sfg_window._expanded_sfg_windows[button] is expanded
    assert expanded.isVisible()
    assert removed.operation not in expanded._drag_buttons
    qtbot.mouseDClick(button, Qt.MouseButton.LeftButton)
    assert not expanded.isVisible()


def test_expanded_io_immediately_updates_collapsed_ports(
    sfg_window, sfg_two_inputs_two_outputs, qtbot
):
    sfg = sfg_two_inputs_two_outputs
    sfg_window._insert_generated_sfg(sfg)
    button = sfg_window._drag_buttons[sfg]
    qtbot.mouseDClick(button, Qt.MouseButton.LeftButton)
    expanded = sfg_window._expanded_sfg_windows[button]

    input_button = next(
        child
        for child in expanded._drag_buttons.values()
        if isinstance(child.operation, Input)
    )
    input_button.remove()
    assert button.operation.input_count == 1
    assert button.operation.output_count == 2
    assert (
        len([port for port in button.port_list if isinstance(port.port, InputPort)])
        == 1
    )
    assert (
        len([port for port in button.port_list if isinstance(port.port, OutputPort)])
        == 2
    )

    expanded.add_operation(Input())
    qtbot.wait(10)
    assert button.operation.input_count == 2
    assert (
        len([port for port in button.port_list if isinstance(port.port, InputPort)])
        == 2
    )
    input_ports = [
        port for port in button.port_list if isinstance(port.port, InputPort)
    ]
    assert len({(port.x(), port.y()) for port in input_ports}) == 2
    assert all(port.scene() is sfg_window._scene for port in input_ports)

    expanded.add_operation(Input())
    expanded.add_operation(Input())
    expanded.add_operation(SFGOutput())
    qtbot.wait(10)
    assert button.operation.input_count == 4
    assert button.operation.output_count == 3
    assert (
        len([port for port in button.port_list if isinstance(port.port, InputPort)])
        == 4
    )
    assert (
        len([port for port in button.port_list if isinstance(port.port, OutputPort)])
        == 3
    )
    expanded.close()
    assert button.operation.input_count == 4
    assert (
        len([port for port in button.port_list if isinstance(port.port, InputPort)])
        == 4
    )


def test_scene_selection_updates_selected_operations(loaded_sfg_window):
    widget = loaded_sfg_window
    first, second, *_ = widget._drag_buttons.values()

    first.graphicsProxyWidget().setSelected(True)
    _assert_selected(widget, [first])
    second.graphicsProxyWidget().setSelected(True)
    _assert_selected(widget, [first, second])
    first.graphicsProxyWidget().setSelected(False)
    _assert_selected(widget, [second])
    widget._scene.clearSelection()
    _assert_selected(widget, [])


@pytest.mark.parametrize("initial_count", [0, 1, None], ids=["none", "one", "all"])
def test_select_all_action(loaded_sfg_window, qtbot, initial_count):
    widget = loaded_sfg_window
    buttons = list(widget._drag_buttons.values())
    for button in buttons[:initial_count]:
        qtbot.mouseClick(
            button, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier
        )

    for _ in range(2):
        widget._ui.select_all.trigger()
        _assert_selected(widget, buttons)
        assert widget._statusbar.currentMessage() == "Selected all operations"


@pytest.mark.parametrize("initial_count", [0, 1, None], ids=["none", "one", "all"])
def test_unselect_all_action(loaded_sfg_window, qtbot, initial_count):
    widget = loaded_sfg_window
    buttons = list(widget._drag_buttons.values())
    for button in buttons[:initial_count]:
        qtbot.mouseClick(
            button, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier
        )

    for _ in range(2):
        widget._ui.unselect_all.trigger()
        _assert_selected(widget, [])
        assert widget._statusbar.currentMessage() == "Unselected all operations"


def test_simulation_plot_runs_on_gui_thread(loaded_sfg_window, qtbot, monkeypatch):
    from b_asic.signal_generator import Impulse

    widget = loaded_sfg_window
    sfg = widget._sfg_dict["twotapfir"]
    plot_calls = []

    class Plot:
        def __init__(self, sim_result, sfg):
            plot_calls.append(("create", QThread.currentThread()))

        def show(self):
            plot_calls.append(("show", QThread.currentThread()))

    # Record the thread without creating a QWidget there, so regressions fail
    # with an assertion instead of aborting the macOS test process.
    monkeypatch.setattr(main_window, "PlotWindow", Plot)
    worker = SimulationWorker(
        sfg,
        {"input_values": [Impulse()], "iteration_count": 5, "all_results": True},
    )
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.start_simulation)
    worker.finished.connect(widget._show_plot_window)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)

    try:
        with qtbot.waitSignal(thread.finished, timeout=10000):
            thread.start()
        qtbot.waitUntil(lambda: len(plot_calls) == 2)
        assert plot_calls == [("create", widget.thread()), ("show", widget.thread())]
    finally:
        thread.quit()
        assert thread.wait(10000), "Simulation thread did not stop"


@pytest.mark.parametrize("show_plot", [False, True])
@pytest.mark.parametrize("all_results", [False, True])
def test_simulate_sfg_and_display_results(
    loaded_sfg_window, qtbot, monkeypatch, show_plot, all_results
):
    widget = loaded_sfg_window
    sfg = widget._sfg_dict["twotapfir"]
    widget._ui.actionSimulateSFG.trigger()
    dialog = widget._simulation_dialog
    qtbot.addWidget(dialog)
    assert dialog.isVisible()
    assert dialog.windowTitle() == "Simulate SFG"
    assert set(dialog._input_fields) == {sfg}

    fields = dialog._input_fields[sfg]
    assert fields["iteration_count"].value() == 100
    assert fields["show_plot"].isChecked()
    assert fields["all_results"].isChecked()
    fields["iteration_count"].setValue(5)
    fields["show_plot"].setChecked(show_plot)
    fields["all_results"].setChecked(all_results)
    fields["input_grid"].itemAtPosition(0, 1).widget().setCurrentText("Impulse")

    # Connect before starting the real worker so even fast simulations are captured.
    simulations = []

    def create_worker(sfg, properties):
        worker = SimulationWorker(sfg, properties)
        worker.finished.connect(simulations.append)
        return worker

    monkeypatch.setattr(main_window, "SimulationWorker", create_worker)
    thread = QThread()
    thread_destroyed = []
    thread.destroyed.connect(lambda: thread_destroyed.append(True))
    monkeypatch.setattr(main_window, "QThread", lambda: thread)

    try:
        with qtbot.waitSignal(thread.finished, timeout=10000):
            qtbot.mouseClick(dialog._simulate_btn, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: len(simulations) == 1)

        assert not dialog.isVisible()
        assert dialog.result() == QDialog.DialogCode.Accepted
        properties = dialog.properties[sfg]
        assert properties["iteration_count"] == 5
        assert properties["show_plot"] == show_plot
        assert properties["all_results"] == (show_plot or all_results)
        simulation = simulations[0]
        assert simulation.sfg.name == "twotapfir"
        assert simulation.iteration == 5

        if show_plot or all_results:
            np.testing.assert_array_equal(
                simulation.results["out0"], [0.5, 0.5, 0, 0, 0]
            )

            assert len(simulation.results) == len(widget._drag_buttons)
            assert all(len(values) == 5 for values in simulation.results.values())
        else:
            assert not simulation.results

        if show_plot:
            qtbot.waitUntil(lambda: simulation in widget._plot)
            plot = widget._plot[simulation]
            assert plot.isVisible()
            assert plot.windowTitle() == "Simulation results: twotapfir"
            assert plot._checklist.count() == len(simulation.results)
            output = simulation.sfg.output_operations[0]
            output_label = (
                f"{output.name} ({output.graph_id})" if output.name else output.graph_id
            )
            line = plot._lines[output_label]["time"].markerline
            assert plot._lines[output_label]["time"].get_label() == output_label
            np.testing.assert_array_equal(line.get_xdata(), np.arange(5))
            np.testing.assert_array_equal(line.get_ydata(), [0.5, 0.5, 0, 0, 0])
        else:
            assert not widget._plot
    finally:
        if not thread_destroyed:
            thread.quit()
            assert thread.wait(10000), "Simulation thread did not stop"
        for plot in widget._plot.values():
            qtbot.addWidget(plot)


@pytest.mark.parametrize(
    "graph_order", [(0,), (0, 1, 2), (2, 1, 0)], ids=["no-input", "forward", "reverse"]
)
def test_simulation_dialog_inputs_per_sfg(
    sfg_window, qtbot, sfg_two_tap_fir, sfg_two_inputs_two_outputs, graph_order
):
    from b_asic import SFG, Constant, Output
    from b_asic.sfg_gui.simulate_sfg_window import SimulateSFGWindow

    graphs = [
        SFG([], [Output(Constant(7))]),
        sfg_two_tap_fir,
        sfg_two_inputs_two_outputs,
    ]
    dialog = SimulateSFGWindow(sfg_window)
    qtbot.addWidget(dialog)
    for index in graph_order:
        dialog.add_sfg_to_dialog(graphs[index])
        dialog._input_fields[graphs[index]]["iteration_count"].setValue(3)

    if 1 in graph_order:
        grid = dialog._input_fields[graphs[1]]["input_grid"]
        grid.itemAtPosition(0, 1).widget().setCurrentText("Impulse")
    if 2 in graph_order:
        grid = dialog._input_fields[graphs[2]]["input_grid"]
        grid.itemAtPosition(0, 1).widget().setCurrentText("Impulse")
        grid.itemAtPosition(1, 1).widget().setCurrentText("Step")

    with qtbot.waitSignal(dialog.simulate):
        qtbot.mouseClick(dialog._simulate_btn, Qt.MouseButton.LeftButton)

    expected = ([7, 7, 7], [0.5, 0.5, 0], [2, 1, 1])
    for index in graph_order:
        graph = graphs[index]
        properties = dialog.properties[graph]
        assert len(properties["input_values"]) == graph.input_count
        worker = SimulationWorker(graph, properties)
        with qtbot.waitSignal(worker.finished) as signal:
            worker.start_simulation()
        np.testing.assert_array_equal(signal.args[0].results["out0"], expected[index])


def test_cancel_simulation(loaded_sfg_window, qtbot):
    widget = loaded_sfg_window
    widget._ui.actionSimulateSFG.trigger()
    dialog = widget._simulation_dialog
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.rejected):
        dialog.reject()

    assert not dialog.isVisible()
    assert not dialog.properties
    assert not hasattr(widget, "_thread")
    assert not widget._plot


def test_show_precedence_graph_with_one_sfg(loaded_sfg_window, qtbot, monkeypatch):
    widget = loaded_sfg_window
    graphs = []
    monkeypatch.setattr(Digraph, "view", lambda graph: graphs.append(graph.source))
    widget._ui.actionShowPC.trigger()
    dialog = widget._precedence_graph_dialog
    qtbot.addWidget(dialog)

    assert dialog.isVisible()
    assert dialog.windowTitle() == "Show precedence graph"
    assert len(dialog._check_box_dict) == 1
    check_box, name = next(iter(dialog._check_box_dict.items()))
    assert name == "twotapfir"
    assert check_box.isChecked()

    with qtbot.waitSignal(dialog.pc):
        qtbot.mouseClick(
            dialog._show_precedence_graph_button, Qt.MouseButton.LeftButton
        )

    assert graphs == [widget._sfg_dict[name].precedence_graph.source]
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert not dialog.isVisible()


@pytest.mark.parametrize(
    "selected_names", [[], ["twotapfir"], ["delay"], ["twotapfir", "delay"]]
)
def test_show_precedence_graph_for_selected_sfgs(
    loaded_sfg_window, sfg_delay, qtbot, monkeypatch, selected_names
):
    widget = loaded_sfg_window
    sfg_delay.name = "delay"
    widget._load_sfg(sfg_delay)
    graphs = []
    monkeypatch.setattr(Digraph, "view", lambda graph: graphs.append(graph.source))
    widget._ui.actionShowPC.trigger()
    dialog = widget._precedence_graph_dialog
    qtbot.addWidget(dialog)

    assert dialog.isVisible()
    assert set(dialog._check_box_dict.values()) == {"twotapfir", "delay"}
    for check_box, name in dialog._check_box_dict.items():
        assert not check_box.isChecked()
        check_box.setChecked(name in selected_names)

    with qtbot.waitSignal(dialog.pc):
        qtbot.mouseClick(
            dialog._show_precedence_graph_button, Qt.MouseButton.LeftButton
        )

    assert graphs == [
        widget._sfg_dict[name].precedence_graph.source for name in selected_names
    ]
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert not dialog.isVisible()


def test_cancel_precedence_graph(loaded_sfg_window, qtbot, monkeypatch):
    widget = loaded_sfg_window
    graphs = []
    monkeypatch.setattr(Digraph, "view", lambda graph: graphs.append(graph.source))
    widget._ui.actionShowPC.trigger()
    dialog = widget._precedence_graph_dialog
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.rejected):
        dialog.reject()

    assert not dialog.isVisible()
    assert not graphs
