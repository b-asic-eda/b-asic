"""Scheduler window actions, dialogs, plots, and schedule persistence."""

import pickle
import sys
from types import ModuleType

import pytest

pytest.importorskip("qtpy.QtWidgets", exc_type=ImportError)

from qtpy.QtCore import QSettings, Qt
from qtpy.QtWidgets import QMessageBox

from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.scheduler_gui import main_window
from b_asic.scheduler_gui.main_window import ScheduleMainWindow
from b_asic.sfg import SFG
from b_asic.special_operations import Delay, Input, Output


@pytest.fixture
def scheduler_window(qtbot, monkeypatch, tmp_path):
    settings_path = str(tmp_path / "scheduler.ini")
    monkeypatch.setattr(
        main_window,
        "QSettings",
        lambda: QSettings(settings_path, QSettings.Format.IniFormat),
    )
    main_window.QSettings().setValue("scheduler/hide_exit_dialog", True)
    widget = ScheduleMainWindow()
    qtbot.addWidget(
        widget, before_close_func=lambda window: window.hide_exit_dialog(True)
    )
    return widget


def _assert_bar_values(axes, values):
    assert [bar.get_x() + bar.get_width() / 2 for bar in axes.patches] == (
        pytest.approx(list(values))
    )
    assert [bar.get_height() for bar in axes.patches] == pytest.approx(
        list(values.values())
    )


@pytest.mark.parametrize("restore_minimum", [False, True])
def test_info_table_can_be_hidden_and_restored(
    scheduler_window, qtbot, restore_minimum
):
    widget = scheduler_window
    widget.resize(1000, 600)
    widget.show()
    qtbot.waitExposed(widget)
    _, maximum = widget.splitter.getRange(1)
    widget.splitter.moveSplitter(maximum - 250, 1)
    width = widget.splitter.sizes()[1]
    assert width > 0

    widget.menu_node_info.trigger()
    assert not widget.menu_node_info.isChecked()
    assert widget.splitter.sizes()[1] == 0

    if restore_minimum:
        widget._splitter_pos = 0
    widget.menu_node_info.trigger()
    assert widget.menu_node_info.isChecked()
    if restore_minimum:
        assert widget.splitter.sizes()[1] >= widget._splitter_min
    else:
        assert widget.splitter.sizes()[1] == width


def test_moving_splitter_updates_info_table_action(scheduler_window, qtbot):
    widget = scheduler_window
    widget.resize(1000, 600)
    widget.show()
    qtbot.waitExposed(widget)
    _, maximum = widget.splitter.getRange(1)

    widget.splitter.moveSplitter(maximum, 1)
    assert not widget.menu_node_info.isChecked()
    assert widget.splitter.sizes()[1] == 0

    widget.splitter.moveSplitter(maximum - 250, 1)
    assert widget.menu_node_info.isChecked()
    assert widget._splitter_pos == widget.splitter.sizes()[1] == 250


def test_info_table_updates_selected_operation(scheduler_window):
    source = Input()
    gain = ConstantMultiplication(0.5, source, name="Gain", latency=2)
    widget = scheduler_window
    widget.open(Schedule(SFG([source], [Output(gain)])))
    assert widget.info_table.item(1, 1).text() == "2"
    assert widget.info_table.item(2, 1).text() == "False"

    widget._graph._signals.component_selected.emit("cmul0")
    rows = {
        widget.info_table.item(row, 0).text(): widget.info_table.item(row, 1).text()
        for row in range(widget.info_table.rowCount())
        if widget.info_table.item(row, 1) is not None
    }
    assert rows["ID"] == "cmul0"
    assert rows["Name"] == "Gain"
    assert rows["value"] == "0.5"
    assert rows["Forward slack"] == "0"
    assert rows["Backward slack"] == "0"

    widget._graph._signals.component_selected.emit("in0")
    assert not widget.info_table.findItems("Gain", Qt.MatchFlag.MatchExactly)
    assert not widget.info_table.findItems("value", Qt.MatchFlag.MatchExactly)
    assert widget.info_table.findItems("in0", Qt.MatchFlag.MatchExactly)


@pytest.mark.parametrize("answer", ["Yes", "No"])
@pytest.mark.parametrize("do_not_ask_again", [False, True])
def test_exit_confirmation_and_do_not_ask_again(
    scheduler_window, qtbot, monkeypatch, answer, do_not_ask_again
):
    widget = scheduler_window
    widget.menu_exit_dialog.trigger()
    prompts = []

    def answer_dialog(box):
        prompts.append(box)
        # QMessageBox ignores window titles on macOS.
        assert "Confirm Exit" in box.text()
        assert "Are you sure you want to exit?" in box.text()
        assert box.standardButtons() == QMessageBox.Yes | QMessageBox.No
        assert box.checkBox().text() == "Do not ask again"
        assert not box.checkBox().isChecked()
        box.checkBox().setChecked(do_not_ask_again)
        return getattr(QMessageBox.StandardButton, answer)

    monkeypatch.setattr(QMessageBox, "exec_", answer_dialog)
    widget.show()
    qtbot.waitExposed(widget)
    accepted = answer == "Yes"
    assert widget.close() == accepted
    assert widget.isVisible() != accepted
    assert len(prompts) == 1
    settings = main_window.QSettings()
    hidden = accepted and do_not_ask_again
    assert settings.value("scheduler/hide_exit_dialog", type=bool) == hidden
    assert settings.contains("scheduler/size") == accepted

    widget._read_settings()
    assert widget.menu_exit_dialog.isChecked() == hidden
    widget.show()
    assert widget.close() == accepted
    assert len(prompts) == (1 if hidden else 2)


def test_hide_exit_dialog_menu_persists_both_states(scheduler_window):
    widget = scheduler_window
    for checked in (False, True):
        widget.menu_exit_dialog.trigger()
        assert widget.menu_exit_dialog.isChecked() == checked
        assert (
            main_window.QSettings().value("scheduler/hide_exit_dialog", type=bool)
            == checked
        )
        widget._read_settings()
        assert widget.menu_exit_dialog.isChecked() == checked


def test_exit_with_confirmation_disabled_does_not_show_dialog(
    scheduler_window, monkeypatch
):
    def unexpected_dialog(_box):
        pytest.fail("The exit dialog must stay hidden")

    monkeypatch.setattr(QMessageBox, "exec_", unexpected_dialog)
    assert scheduler_window.close()
    assert main_window.QSettings().contains("scheduler/size")


@pytest.mark.parametrize(
    ("action_name", "dialog_name", "title"),
    [
        (
            "action_view_variables",
            "_execution_time_for_variables",
            "Execution times for variables",
        ),
        (
            "action_total_execution_times_of_variables",
            "_total_execution_time_for_variables",
            "Total execution times for variables",
        ),
        (
            "action_view_port_accesses",
            "_ports_accesses_for_storage",
            "Port accesses for storage",
        ),
    ],
)
def test_variable_plots_display_refresh_and_close(
    scheduler_window,
    qtbot,
    secondorder_iir_schedule_with_execution_times,
    action_name,
    dialog_name,
    title,
):
    widget = scheduler_window
    action = getattr(widget, action_name)
    assert not action.isEnabled()
    widget.open(secondorder_iir_schedule_with_execution_times)
    assert action.isEnabled()
    action.trigger()
    dialog = getattr(widget, dialog_name)
    qtbot.addWidget(dialog)
    assert dialog.isVisible()
    assert dialog.windowTitle() == title

    for refresh in (False, True):
        if refresh:
            widget._graph.change_schedule_time(1)
            widget._graph._signals.schedule_time_changed.emit()
        assert getattr(widget, dialog_name) is dialog
        variables = widget.schedule.get_memory_variables()
        if action_name == "action_view_variables":
            assert {text.get_text() for text in dialog.axes.texts} == {
                str(variable) for variable in variables
            }
            assert len(dialog.axes.texts) == len(variables)
            assert dialog.axes.get_xlim() == (0, widget.schedule.schedule_time)
        elif action_name == "action_total_execution_times_of_variables":
            _assert_bar_values(dialog.axes, variables.total_execution_times())
            assert dialog.axes.get_xlim() == (
                -0.5,
                widget.schedule.schedule_time - 0.5,
            )
        else:
            _, stored_variables = variables.split_on_length()
            assert [axes.get_title() for axes in dialog.axes] == [
                "Read port accesses",
                "Write port accesses",
                "Total port accesses",
            ]
            for axes, values in zip(
                dialog.axes,
                (
                    stored_variables.read_port_accesses(),
                    stored_variables.write_port_accesses(),
                    stored_variables.total_port_accesses(),
                ),
                strict=True,
            ):
                _assert_bar_values(axes, values)
                assert axes.get_xlim() == (-0.5, widget.schedule.schedule_time - 0.5)

    dialog.close()
    assert getattr(widget, dialog_name) is None
    action.trigger()
    reopened = getattr(widget, dialog_name)
    qtbot.addWidget(reopened)
    assert reopened is not dialog
    assert reopened.isVisible()
    reopened.close()


@pytest.mark.parametrize("type_name", ["add", "cmul"])
@pytest.mark.parametrize("total", [False, True])
def test_operation_type_plots_display_refresh_and_close(
    scheduler_window,
    qtbot,
    secondorder_iir_schedule_with_execution_times,
    type_name,
    total,
):
    widget = scheduler_window
    widget.open(secondorder_iir_schedule_with_execution_times)
    if total:
        menu = widget.menu_view_total_execution_times_of_type
        dialogs = widget._total_execution_time_plot_dialogs
        title = f"Total execution times for {type_name}"
    else:
        menu = widget.menu_view_execution_times
        dialogs = widget._execution_time_plot_dialogs
        title = f"Execution times for {type_name}"
    action = next(action for action in menu.actions() if action.text() == type_name)
    action.trigger()
    dialog = dialogs[type_name]
    qtbot.addWidget(dialog)
    assert dialog.isVisible()
    assert dialog.windowTitle() == title

    for refresh in (False, True):
        if refresh:
            widget._graph.change_schedule_time(1)
            widget._graph._signals.schedule_time_changed.emit()
        assert dialogs[type_name] is dialog
        operations = widget.schedule.get_operations().get_by_type_name(type_name)
        if total:
            _assert_bar_values(dialog.axes, operations.total_execution_times())
            assert dialog.axes.get_xlim() == (
                -0.5,
                widget.schedule.schedule_time - 0.5,
            )
        else:
            assert {text.get_text() for text in dialog.axes.texts} == {
                str(operation) for operation in operations
            }
            assert len(dialog.axes.texts) == len(operations)
            assert dialog.axes.get_xlim() == (0, widget.schedule.schedule_time)

    dialog.close()
    assert dialogs[type_name] is None


def test_exit_closes_all_plot_windows(
    scheduler_window, qtbot, secondorder_iir_schedule_with_execution_times
):
    widget = scheduler_window
    widget.open(secondorder_iir_schedule_with_execution_times)
    widget.action_view_variables.trigger()
    widget.action_total_execution_times_of_variables.trigger()
    widget.action_view_port_accesses.trigger()
    for menu in (
        widget.menu_view_execution_times,
        widget.menu_view_total_execution_times_of_type,
    ):
        next(action for action in menu.actions() if action.text() == "add").trigger()
    dialogs = [
        widget._execution_time_for_variables,
        widget._total_execution_time_for_variables,
        widget._ports_accesses_for_storage,
        widget._execution_time_plot_dialogs["add"],
        widget._total_execution_time_plot_dialogs["add"],
    ]
    for dialog in dialogs:
        qtbot.addWidget(dialog)
        assert dialog.isVisible()

    assert widget.close()
    assert all(not dialog.isVisible() for dialog in dialogs)
    assert widget._execution_time_for_variables is None
    assert widget._total_execution_time_for_variables is None
    assert widget._ports_accesses_for_storage is None
    assert widget._execution_time_plot_dialogs["add"] is None
    assert widget._total_execution_time_plot_dialogs["add"] is None


def test_status_bar_can_be_toggled(scheduler_window, qtbot):
    widget = scheduler_window
    widget.show()
    qtbot.waitExposed(widget)
    for visible in (False, True):
        widget.actionStatus_bar.trigger()
        assert widget.actionStatus_bar.isChecked() == visible
        assert widget.statusbar.isVisible() == visible


def test_full_screen_can_be_toggled(scheduler_window, qtbot):
    widget = scheduler_window
    widget.show()
    qtbot.waitExposed(widget)
    assert not widget.isFullScreen()
    widget.actionToggle_full_screen.trigger()
    qtbot.waitUntil(widget.isFullScreen)
    widget.actionToggle_full_screen.trigger()
    qtbot.waitUntil(lambda: not widget.isFullScreen())
    assert widget.isVisible()


def test_port_numbers_can_be_toggled(scheduler_window, secondorder_iir_schedule):
    widget = scheduler_window
    assert not widget.action_show_port_numbers.isEnabled()
    widget.open(secondorder_iir_schedule)
    numbers = [
        port["number"]
        for operation in widget._graph._operation_items.values()
        for port in operation._ports.values()
    ]
    assert numbers
    for visible in (True, False):
        widget.action_show_port_numbers.trigger()
        assert widget.action_show_port_numbers.isChecked() == visible
        assert all(number.isVisible() == visible for number in numbers)
    widget.close_schedule()
    assert not widget.action_show_port_numbers.isEnabled()


def test_execution_time_warnings_can_be_toggled(scheduler_window):
    source, feedback = Input(), Delay()
    accumulator = (source + feedback) * 0.5
    feedback <<= Delay(Delay(accumulator))
    sfg = SFG([source], [Output(feedback)])
    sfg.set_latency_of_type_name(Addition.type_name(), 1)
    sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 1)
    widget = scheduler_window
    widget.open(Schedule(sfg, cyclic=True))
    signal = next(
        signal
        for signal in widget._graph._get_all_signals()
        if signal._dest_operation.graph_id == "add0"
        and signal._src_operation.graph_id == "cmul0"
    )
    assert signal.pen() == signal._warning_pen
    for enabled in (False, True):
        widget.action_incorrect_execution_time.trigger()
        assert widget.action_incorrect_execution_time.isChecked() == enabled
        assert signal.pen() == (
            signal._warning_pen if enabled else signal._inactive_pen
        )
        for operation, key in (
            (signal._src_operation, signal._src_key),
            (signal._dest_operation, signal._dest_key),
        ):
            assert operation._ports[key]["item"].brush() == (
                operation._port_filling_brush_warning
                if enabled
                else operation._port_filling_brush
            )


@pytest.mark.parametrize("filename", ["schedule", "schedule.bsc"])
def test_save_and_open_schedule_round_trip(
    scheduler_window, monkeypatch, tmp_path, secondorder_iir_schedule, filename
):
    widget = scheduler_window
    widget.open(secondorder_iir_schedule)
    prompts = []

    def choose_save_file(*_args, **_kwargs):
        prompts.append(filename)
        return str(tmp_path / filename), "B-ASIC schedule (*.bsc)"

    monkeypatch.setattr(main_window.QFileDialog, "getSaveFileName", choose_save_file)
    widget.menu_save.trigger()
    path = tmp_path / "schedule.bsc"
    assert path.is_file()
    assert widget._file_name == str(path)
    assert widget.statusbar.currentMessage() == "Schedule saved successfully"

    widget._graph.change_schedule_time(1)
    widget._graph._signals.schedule_time_changed.emit()
    expected_time = widget.schedule.schedule_time
    expected_starts = dict(widget.schedule.start_times)
    expected_laps = dict(widget.schedule.laps)
    widget.menu_save.trigger()
    assert prompts == [filename]
    with path.open("rb") as saved_file:
        saved = pickle.load(saved_file)
    assert isinstance(saved, Schedule)
    assert saved.schedule_time == expected_time
    assert saved.start_times == expected_starts
    assert saved.laps == expected_laps

    widget.close_schedule()
    assert widget.schedule is None
    monkeypatch.setattr(
        main_window.QFileDialog,
        "getOpenFileName",
        lambda *_args: (str(path), "B-ASIC schedule (*.bsc)"),
    )
    widget.menu_open.trigger()
    assert widget.schedule.schedule_time == expected_time
    assert widget.schedule.start_times == expected_starts
    assert widget.schedule.laps == expected_laps
    assert widget.schedule.cyclic == saved.cyclic
    assert widget._graph is not None
    assert widget._file_name == str(path)
    assert widget.info_table.item(1, 1).text() == str(expected_time)
    assert widget.menu_save.isEnabled()
    assert widget.menu_save_as.isEnabled()
    assert widget.statusbar.currentMessage() == "Schedule loaded successfully"
    settings = main_window.QSettings()
    assert settings.value("scheduler/last_opened_file") == str(path)
    assert str(path) in settings.value("scheduler/recentFiles")


def test_save_as_preserves_original_schedule_file(
    scheduler_window, monkeypatch, tmp_path, secondorder_iir_schedule
):
    widget = scheduler_window
    widget.open(secondorder_iir_schedule)
    original = tmp_path / "original.bsc"
    renamed = tmp_path / "renamed.bsc"
    filenames = iter((str(original), str(renamed)))
    monkeypatch.setattr(
        main_window.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (next(filenames), "B-ASIC schedule (*.bsc)"),
    )
    widget.menu_save_as.trigger()
    original_bytes = original.read_bytes()
    widget._graph.change_schedule_time(1)
    widget._graph._signals.schedule_time_changed.emit()
    widget.menu_save_as.trigger()
    assert widget._file_name == str(renamed)
    assert original.read_bytes() == original_bytes
    with renamed.open("rb") as saved_file:
        assert pickle.load(saved_file).schedule_time == widget.schedule.schedule_time


@pytest.mark.parametrize("action_name", ["menu_save", "menu_save_as"])
def test_cancel_save_leaves_schedule_unchanged(
    scheduler_window, monkeypatch, tmp_path, secondorder_iir_schedule, action_name
):
    widget = scheduler_window
    widget.open(secondorder_iir_schedule)
    schedule = widget.schedule
    monkeypatch.setattr(
        main_window.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: ("", ""),
    )
    getattr(widget, action_name).trigger()
    assert widget.schedule is schedule
    assert widget._file_name is None
    assert not list(tmp_path.glob("*.bsc"))
    assert main_window.QSettings().value("scheduler/recentFiles") is None
    assert widget.statusbar.currentMessage() == "Schedule loaded successfully"


@pytest.mark.parametrize("action_name", ["menu_open", "menu_load_from_file"])
@pytest.mark.parametrize("filename", ["", "unused.bsc"])
def test_cancel_open_leaves_schedule_unchanged(
    scheduler_window, monkeypatch, secondorder_iir_schedule, action_name, filename
):
    widget = scheduler_window
    widget.open(secondorder_iir_schedule)
    schedule, graph = widget.schedule, widget._graph
    monkeypatch.setattr(
        main_window.QFileDialog, "getOpenFileName", lambda *_args: (filename, "")
    )
    getattr(widget, action_name).trigger()
    assert widget.schedule is schedule
    assert widget._graph is graph
    assert widget._file_name is None
    assert main_window.QSettings().value("scheduler/last_opened_file") is None


@pytest.mark.parametrize("contents", [None, b"invalid pickle", pickle.dumps({})])
def test_open_invalid_schedule_preserves_current_schedule(
    scheduler_window, monkeypatch, tmp_path, secondorder_iir_schedule, contents
):
    path = tmp_path / "invalid.bsc"
    if contents is not None:
        path.write_bytes(contents)
    widget = scheduler_window
    widget.open(secondorder_iir_schedule)
    schedule, graph = widget.schedule, widget._graph
    warnings = []
    monkeypatch.setattr(
        main_window.QFileDialog,
        "getOpenFileName",
        lambda *_args: (str(path), "B-ASIC schedule (*.bsc)"),
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    widget.menu_open.trigger()
    assert len(warnings) == 1
    assert warnings[0][1] == "Could not open schedule"
    assert path.name in warnings[0][2]
    assert widget.schedule is schedule
    assert widget._graph is graph
    assert widget._file_name is None
    assert main_window.QSettings().value("scheduler/last_opened_file") is None
    assert main_window.QSettings().value("scheduler/recentFiles") is None


@pytest.mark.filterwarnings("error::DeprecationWarning")
@pytest.mark.parametrize(
    ("multiple", "accepted"), [(False, True), (True, True), (True, False)]
)
def test_load_schedule_from_python_file(
    scheduler_window, monkeypatch, tmp_path, multiple, accepted
):
    path = tmp_path / f"python_schedules_{multiple}_{accepted}.py"
    source = (
        "from b_asic import ConstantMultiplication, Input, Output, SFG, Schedule\n"
        "source = Input()\n"
        "operation = ConstantMultiplication(0.5, source, latency=2)\n"
        "first = Schedule(SFG([source], [Output(operation)]))\n"
    )
    if multiple:
        source += "second = first.increase_time_resolution(2)\n"
    path.write_text(source)
    selections = []

    def choose_schedule(_parent, _title, _label, names, _index, _editable):
        selections.append(list(names))
        return "second", accepted

    monkeypatch.setattr(
        main_window.QFileDialog,
        "getOpenFileName",
        lambda *_args: (str(path), "Python Files (*.py *.py3)"),
    )
    monkeypatch.setattr(main_window.QInputDialog, "getItem", choose_schedule)
    widget = scheduler_window
    widget.menu_load_from_file.trigger()
    assert selections == ([["first", "second"]] if multiple else [])
    if accepted:
        assert widget.schedule.schedule_time == (4 if multiple else 2)
        assert widget._file_name == str(path)
        assert main_window.QSettings().value("scheduler/last_opened_file") == str(path)
        assert widget.statusbar.currentMessage() == "Schedule loaded successfully"
    else:
        assert widget.schedule is None
        assert widget._graph is None
        assert widget._file_name is None
        assert not widget.menu_save.isEnabled()


def test_load_python_schedule_with_dataclass(scheduler_window, tmp_path):
    path = tmp_path / "schedule_with_dataclass.py"
    path.write_text(
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "from b_asic import ConstantMultiplication, Input, Output, SFG, Schedule\n"
        "@dataclass\n"
        "class Configuration:\n"
        "    coefficient: float = 0.5\n"
        "source = Input()\n"
        "operation = ConstantMultiplication(Configuration().coefficient, source, latency=2)\n"
        "schedule = Schedule(SFG([source], [Output(operation)]))\n"
    )

    scheduler_window._load_from_file(str(path))

    assert scheduler_window.schedule.schedule_time == 2
    assert scheduler_window._file_name == str(path)


@pytest.mark.parametrize("cached", [False, True])
def test_failed_python_import_preserves_current_schedule_and_module(
    scheduler_window, monkeypatch, tmp_path, secondorder_iir_schedule, cached
):
    path = tmp_path / "broken_python_schedule.py"
    path.write_text("raise RuntimeError('Cannot create schedule')\n")
    previous_module = ModuleType(path.stem)
    if cached:
        monkeypatch.setitem(sys.modules, path.stem, previous_module)
    widget = scheduler_window
    widget.open(secondorder_iir_schedule)
    schedule, graph = widget.schedule, widget._graph

    widget._load_from_file(str(path))

    assert widget.schedule is schedule
    assert widget._graph is graph
    assert widget._file_name is None
    assert main_window.QSettings().value("scheduler/recentFiles") is None
    if cached:
        assert sys.modules[path.stem] is previous_module
    else:
        assert path.stem not in sys.modules
