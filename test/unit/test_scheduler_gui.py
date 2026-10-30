import copy
import itertools
import pickle

import pytest

from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.scheduler import ASAPScheduler
from b_asic.sfg import SFG
from b_asic.special_operations import Delay, Input, Output
from b_asic.utility_operations import Sink

try:
    from qtpy.QtCore import QEvent, QPoint, QPointF, Qt
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtWidgets import QApplication, QGraphicsScene, QGraphicsView

    from b_asic.scheduler_gui import main_window
    from b_asic.scheduler_gui.io_latency_window import IOLatencyWindow
    from b_asic.scheduler_gui.main_window import ScheduleMainWindow
    from b_asic.scheduler_gui.scheduler_item import SchedulerItem
except ImportError:
    pytestmark = pytest.mark.skip("Qt not setup")


def test_start(qtbot):
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)

    widget.exit_app()


@pytest.mark.parametrize(("delay_count", "expected_valid"), [(1, False), (2, True)])
def test_timeline_drag_wraps_only_with_nonnegative_forward_slack(
    qtbot, delay_count, expected_valid
):
    input_item = Input()
    delays = [Delay() for _ in range(delay_count)]
    accumulator = (input_item + delays[0]) * 0.5
    for current_delay, next_delay in itertools.pairwise(delays):
        current_delay <<= next_delay
    delays[-1] <<= accumulator
    sfg = SFG([input_item], [Output(delays[0])])
    sfg.set_latency_of_type_name(Addition.type_name(), 1)
    sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 1)
    schedule = Schedule(sfg, cyclic=True)
    scheduler_item = SchedulerItem(schedule)

    assert scheduler_item.is_valid_delta_time(-1) is expected_valid
    assert not scheduler_item.is_valid_delta_time(-2)
    if expected_valid:
        scheduler_item.change_schedule_time(-1)
        assert schedule.schedule_time == 1
        assert schedule.forward_slack("cmul0") == 0
    else:
        with pytest.raises(ValueError, match="invalidate the cyclic schedule"):
            schedule.set_schedule_time(1, allow_cyclic_wrap=True)


@pytest.mark.parametrize("boundary", [1, 4])
def test_timeline_drop_wraps_operations_that_remain_movable(qtbot, boundary):
    input_item = Input()
    first_delay = Delay()
    second_delay = Delay()
    third_delay = Delay()
    accumulator = (input_item + first_delay) * 0.5
    first_delay <<= second_delay
    second_delay <<= third_delay
    third_delay <<= accumulator
    sfg = SFG([input_item], [Output(first_delay)])
    sfg.set_latency_of_type_name(Addition.type_name(), 1)
    sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 1)
    schedule = Schedule(sfg, cyclic=True)
    schedule.set_schedule_time(boundary + 1)
    schedule.move_operation("cmul0", boundary - 1)
    graph = SchedulerItem(schedule)
    scene = QGraphicsScene()
    scene.addItem(graph)
    graph.installSceneEventFilters(graph.event_items)
    view = QGraphicsView(scene)
    qtbot.addWidget(view)
    view.resize(900, 600)
    view.scale(75, 75)
    view.show()

    def drag(start, end):
        qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QApplication.sendEvent(
            view.viewport(),
            QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(end),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)

    timeline = graph.axes.event_items[0]
    timeline_pos = view.mapFromScene(timeline.mapToScene(timeline.line().center()))
    drag(timeline_pos, timeline_pos - QPoint(75, 0))

    operation = graph._operation_items["cmul0"]
    assert schedule.schedule_time == boundary
    assert schedule.start_times["cmul0"] == 0
    assert operation.x() == pytest.approx(graph._x_axis_indent)
    assert schedule.forward_slack("cmul0") > 0

    graph.change_schedule_time(1)
    assert schedule.start_times["cmul0"] == 0
    assert operation.x() == pytest.approx(graph._x_axis_indent)
    graph.change_schedule_time(-1)

    start_times = schedule.start_times.copy()
    laps = schedule._laps.copy()
    operation_pos = view.mapFromScene(
        operation.mapToScene(operation._latency_item.boundingRect().center())
    )
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=operation_pos)
    assert schedule.start_times == start_times
    assert schedule._laps == laps

    drag(operation_pos, operation_pos + QPoint(75, 0))
    assert schedule.start_times["cmul0"] == 1 % boundary
    assert operation.x() == pytest.approx(graph._x_axis_indent + 1 % boundary)


@pytest.mark.parametrize(
    ("source_start", "middle_laps", "dragged_id", "dx", "wrapped"),
    [
        (0, 0, "cmul0", -1, True),
        (0, 0, "cmul1", 1, True),
        (2, 1, "cmul0", 1, False),
    ],
)
def test_signal_wraps_during_drag_before_drop(
    qtbot, source_start, middle_laps, dragged_id, dx, wrapped
):
    input_item = Input()
    source = ConstantMultiplication(0.5, input_item, latency=1)
    destination = ConstantMultiplication(0.25, source, latency=0)
    sfg = SFG([input_item], [Output(destination)])
    schedule = Schedule(
        sfg,
        cyclic=True,
        schedule_time=3,
        start_times={"in0": 0, "cmul0": source_start, "cmul1": 2, "out0": 2},
        laps={"s0": 1, "s1": 1, "s2": middle_laps},
    )
    graph = SchedulerItem(schedule)
    scene = QGraphicsScene()
    scene.addItem(graph)
    graph.installSceneEventFilters(graph.event_items)
    view = QGraphicsView(scene)
    qtbot.addWidget(view)
    view.resize(900, 600)
    view.scale(75, 75)
    view.show()
    operation = graph._operation_items[dragged_id]
    signal = next(
        signal
        for signal in graph._get_all_signals()
        if signal._src_operation.graph_id == "cmul0"
        and signal._dest_operation.graph_id == "cmul1"
    )
    original_start_times = schedule.start_times.copy()
    original_laps = schedule.laps.copy()
    start = view.mapFromScene(
        operation.mapToScene(operation._latency_item.boundingRect().center())
    )
    end = start + QPoint(75 * dx, 0)
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QApplication.sendEvent(
        view.viewport(),
        QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(end),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )

    def assert_wrapped():
        path = signal.path()
        has_curve = any(
            path.elementAt(index).isCurveTo() for index in range(path.elementCount())
        )
        assert has_curve is not wrapped

    assert operation.x() == pytest.approx(
        graph._x_axis_indent + original_start_times[dragged_id] + dx
    )
    assert_wrapped()
    assert schedule.start_times == original_start_times
    assert schedule.laps == original_laps
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert_wrapped()


@pytest.mark.parametrize("cyclic", [False, True])
def test_timeline_drop_keeps_output_and_sink_at_right_boundary(qtbot, cyclic):
    input_item = Input()
    operation = ConstantMultiplication(0.5, input_item, latency=1)
    sink = Sink()
    sink <<= operation
    sfg = SFG([input_item], [Output(operation)])
    schedule = Schedule(sfg, cyclic=cyclic)
    schedule.set_schedule_time(2)
    graph = SchedulerItem(schedule)

    graph.change_schedule_time(-1)

    for graph_id in ("out0", "sink0"):
        item = graph._operation_items[graph_id]
        assert schedule.start_times[graph_id] == schedule.schedule_time
        assert item.x() == pytest.approx(graph._x_axis_indent + schedule.schedule_time)
        graph.set_new_start_time(item)
        assert schedule.start_times[graph_id] == schedule.schedule_time


@pytest.mark.parametrize("warnings", [False, True])
def test_timeline_change_refreshes_warning_colors(qtbot, warnings):
    input_item = Input()
    feedback = Delay()
    accumulator = (input_item + feedback) * 0.5
    feedback <<= Delay(Delay(accumulator))
    sfg = SFG([input_item], [Output(feedback)])
    sfg.set_latency_of_type_name(Addition.type_name(), 1)
    sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 1)
    schedule = Schedule(sfg, cyclic=True)
    graph = SchedulerItem(schedule, warnings=warnings)
    feedback_signal = next(
        signal
        for signal in graph._get_all_signals()
        if signal._dest_operation.graph_id == "add0"
        and signal._src_operation.graph_id == "cmul0"
    )

    def assert_colors(warning):
        assert feedback_signal.pen() == (
            feedback_signal._warning_pen if warning else feedback_signal._inactive_pen
        )
        for operation, key in (
            (feedback_signal._src_operation, feedback_signal._src_key),
            (feedback_signal._dest_operation, feedback_signal._dest_key),
        ):
            assert operation._ports[key]["item"].brush() == (
                operation._port_filling_brush_warning
                if warning
                else operation._port_filling_brush
            )

    assert_colors(warnings)
    graph.change_schedule_time(-1)
    assert_colors(False)
    graph.change_schedule_time(1)
    assert_colors(warnings)


def test_load_schedule(qtbot, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type_name(ConstantMultiplication.type_name(), 4)

    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    schedule = Schedule(sfg_simple_filter, ASAPScheduler())
    widget.open(schedule)
    assert widget.statusbar.currentMessage() == "Schedule loaded successfully"


def test_view_io_latency(qtbot, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type_name(ConstantMultiplication.type_name(), 4)
    schedule = Schedule(sfg_simple_filter, ASAPScheduler())

    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    assert not widget.action_view_io_latency.isEnabled()

    widget.open(schedule)
    assert widget.action_view_io_latency.isEnabled()

    widget.action_view_io_latency.trigger()

    assert widget._io_latency_window is not None
    table = widget._io_latency_window.table
    assert [table.horizontalHeaderItem(i).text() for i in range(2)] == [
        "Input",
        "out0",
    ]
    assert [table.item(0, i).text() for i in range(2)] == ["in0", "9"]

    widget.close_schedule()
    assert widget._io_latency_window is None


@pytest.mark.parametrize(
    "output_latencies",
    [{"out10": 110, "out2": 12}, {"out2": 12, "out10": 110}],
)
def test_io_latency_columns_are_naturally_sorted(qtbot, output_latencies):
    widget = IOLatencyWindow()
    qtbot.addWidget(widget)
    widget.set_io_latency({"in0": output_latencies, "in1": {"out1": 21, "out10": 210}})

    table = widget.table
    assert [
        table.horizontalHeaderItem(column).text()
        for column in range(table.columnCount())
    ] == ["Input", "out1", "out2", "out10"]
    assert [table.item(0, column).text() for column in range(4)] == [
        "in0",
        "-",
        "12",
        "110",
    ]
    assert [table.item(1, column).text() for column in range(4)] == [
        "in1",
        "21",
        "-",
        "210",
    ]


@pytest.mark.parametrize("user_resized", [False, True])
def test_io_latency_updates_preserve_window_size(qtbot, user_resized):
    widget = IOLatencyWindow()
    qtbot.addWidget(widget)
    widget.set_io_latency({"in0": {"out0": 9, "out1": 10}})
    widget.show()
    QApplication.processEvents()
    if user_resized:
        widget.resize(600, 300)
        QApplication.processEvents()
    initial_size = widget.size()

    for latency in range(10, 15):
        widget.set_io_latency({"in0": {"out0": latency, "out1": latency + 1}})
        QApplication.processEvents()
        assert widget.size() == initial_size
        assert widget.table.item(0, 1).text() == str(latency)
        assert widget.table.item(0, 2).text() == str(latency + 1)


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
