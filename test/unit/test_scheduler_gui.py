import copy
import pickle

import pytest

from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.scheduler import ASAPScheduler

try:
    from b_asic.scheduler_gui import main_window
    from b_asic.scheduler_gui.main_window import ScheduleMainWindow
except ImportError:
    pytestmark = pytest.mark.skip("Qt not setup")


def test_start(qtbot):
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)

    widget.exit_app()


def test_load_schedule(qtbot, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type_name(ConstantMultiplication.type_name(), 4)

    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    schedule = Schedule(sfg_simple_filter, ASAPScheduler())
    widget.open(schedule)
    assert widget.statusbar.currentMessage() == "Schedule loaded successfully"


def test_close_schedule_then_open_new_schedule(qtbot, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type_name(ConstantMultiplication.type_name(), 4)
    first_schedule = Schedule(sfg_simple_filter, ASAPScheduler())
    second_schedule = copy.deepcopy(first_schedule)
    second_schedule.increase_time_resolution(2)

    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open(first_schedule)
    assert widget.schedule is not None
    assert widget._graph is not None

    widget.close_schedule()

    assert widget.schedule is None
    assert widget._graph is None
    assert not widget.menu_close_schedule.isEnabled()
    assert not widget.menu_save.isEnabled()
    assert not widget.menu_save_as.isEnabled()

    widget.open(second_schedule)

    assert widget.schedule is not None
    assert widget.schedule.schedule_time == second_schedule.schedule_time
    assert widget.schedule.schedule_time != first_schedule.schedule_time
    assert widget._graph is not None
    assert widget.statusbar.currentMessage() == "Schedule loaded successfully"


def test_rotate_forward(qtbot, precedence_sfg_delays):
    precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
    precedence_sfg_delays.set_latency_of_type_name(
        ConstantMultiplication.type_name(), 3
    )
    schedule = Schedule(precedence_sfg_delays, cyclic=True)
    original_start_times = schedule.start_times.copy()

    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open(schedule)

    widget._rotate_forward()

    assert widget.schedule is not None
    assert widget.schedule.start_times != original_start_times
    assert widget._graph is not None
    assert widget.statusbar.currentMessage() == "Scheduled rotated forward."


def test_rotate_backward(qtbot, precedence_sfg_delays):
    precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
    precedence_sfg_delays.set_latency_of_type_name(
        ConstantMultiplication.type_name(), 3
    )
    schedule = Schedule(precedence_sfg_delays, cyclic=True)
    original_start_times = schedule.start_times.copy()

    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open(schedule)

    widget._rotate_backward()

    assert widget.schedule is not None
    assert widget.schedule.start_times != original_start_times
    assert widget._graph is not None
    assert widget.statusbar.currentMessage() == "Scheduled rotated backward."


def test_increase_time_resolution(qtbot, monkeypatch, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type_name(ConstantMultiplication.type_name(), 4)
    schedule = Schedule(sfg_simple_filter, ASAPScheduler())
    original_schedule_time = schedule.schedule_time
    opened_schedules = []

    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget._schedule = schedule
    monkeypatch.setattr(widget, "open", opened_schedules.append)
    monkeypatch.setattr(main_window.QInputDialog, "getInt", lambda *args: (2, True))

    widget._increase_time_resolution()

    assert schedule.schedule_time == original_schedule_time * 2
    assert opened_schedules == [schedule]
    assert (
        widget.statusbar.currentMessage() == "Time resolution increased by a factor 2"
    )


def test_decrease_time_resolution(qtbot, monkeypatch, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type_name(ConstantMultiplication.type_name(), 4)
    schedule = Schedule(sfg_simple_filter, ASAPScheduler())
    schedule.increase_time_resolution(2)
    increased_schedule_time = schedule.schedule_time
    opened_schedules = []

    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget._schedule = schedule
    monkeypatch.setattr(widget, "open", opened_schedules.append)
    monkeypatch.setattr(
        main_window.QInputDialog,
        "getItem",
        lambda *args, **kwargs: ("2", True),
    )

    widget._decrease_time_resolution()

    assert schedule.schedule_time * 2 == increased_schedule_time
    assert opened_schedules == [schedule]
    assert (
        widget.statusbar.currentMessage() == "Time resolution decreased by a factor 2"
    )


def test_open_schedule_file(qtbot, monkeypatch, tmp_path, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type_name(ConstantMultiplication.type_name(), 4)
    schedule = Schedule(sfg_simple_filter, ASAPScheduler())
    schedule_path = tmp_path / "schedule.bsc"
    with schedule_path.open("wb") as schedule_file:
        pickle.dump(schedule, schedule_file)

    opened_schedules = []
    recent_files = []
    settings_values = []
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    monkeypatch.setattr(widget, "open", opened_schedules.append)
    monkeypatch.setattr(widget, "_add_recent_file", recent_files.append)
    monkeypatch.setattr(
        main_window.QSettings,
        "setValue",
        lambda settings, key, value: settings_values.append((key, value)),
    )

    widget._open_schedule_file(str(schedule_path))

    assert len(opened_schedules) == 1
    assert isinstance(opened_schedules[0], Schedule)
    assert widget._file_name == str(schedule_path)
    assert recent_files == [str(schedule_path)]
    assert settings_values == [("scheduler/last_opened_file", str(schedule_path))]
    assert widget.menu_save.isEnabled()
    assert widget.menu_save_as.isEnabled()
    assert widget.statusbar.currentMessage() == "Schedule loaded successfully"


def test_open_schedule_file_rejects_non_schedule(qtbot, monkeypatch, tmp_path):
    invalid_path = tmp_path / "not-a-schedule.bsc"
    with invalid_path.open("wb") as invalid_file:
        pickle.dump({"not": "a schedule"}, invalid_file)

    warnings = []
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    monkeypatch.setattr(
        main_window.QMessageBox,
        "warning",
        lambda *args: warnings.append(args),
    )

    widget._open_schedule_file(str(invalid_path))

    assert len(warnings) == 1
    assert widget._file_name is None
    assert widget.statusbar.currentMessage() == ""


def test_open_preferences_dialog(qtbot):
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open_preferences_dialog()
    widget._preferences_dialog.close()
    widget.exit_app()
