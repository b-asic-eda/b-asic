import copy
import itertools
import pickle

import pytest

from b_asic.core_operations import Addition, ConstantMultiplication, Subtraction
from b_asic.schedule import Schedule
from b_asic.scheduler import ASAPScheduler
from b_asic.sfg import SFG
from b_asic.special_operations import Delay, Input, Output
from b_asic.utility_operations import DontCare, Sink

try:
    from qtpy.QtCore import QEvent, QPoint, QPointF, Qt
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtWidgets import QApplication, QGraphicsScene, QGraphicsView

    from b_asic.scheduler_gui import main_window
    from b_asic.scheduler_gui.axes_item import AxesItem
    from b_asic.scheduler_gui.io_latency_window import IOLatencyWindow
    from b_asic.scheduler_gui.main_window import ScheduleMainWindow
    from b_asic.scheduler_gui.operation_item import OperationItem
    from b_asic.scheduler_gui.scheduler_item import SchedulerItem
except ImportError:
    pytestmark = pytest.mark.skip("Qt not setup")


def _mouse_move_with_left_button(view, pos):
    viewport = view.viewport()
    QApplication.sendEvent(
        viewport,
        QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(pos),
            QPointF(viewport.mapToGlobal(pos)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )


def test_start(qtbot):
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)

    widget.exit_app()


@pytest.mark.parametrize("cyclic", [False, True])
def test_unused_ports_are_marked_without_placeholder_operations(qtbot, cyclic):
    source = Input()
    operation = Addition(source, DontCare(), latency=1)
    Sink(operation)
    schedule = Schedule(SFG([source], [Output(operation)]), cyclic=cyclic)
    start_times = schedule.start_times.copy()
    laps = schedule.laps.copy()
    graph = SchedulerItem(schedule)

    assert set(graph._operation_items) == {"in0", "add0", "out0"}
    assert len(graph._get_all_signals()) == 2
    item = graph._operation_items["add0"]
    assert item._ports["in1"]["item"].toolTip() == "DontCare"
    assert item._ports["out0"]["item"].toolTip() == "Sink"
    assert not item._ports["in0"]["item"].toolTip()
    assert len(item._ports["in1"]["item"].childItems()) == 1
    assert len(item._ports["out0"]["item"].childItems()) == 1
    assert not item._ports["in0"]["item"].childItems()
    assert set(schedule._y_locations) == set(graph._operation_items)
    assert set(schedule._y_locations.values()) == {0, 1, 2}
    assert schedule.start_times == start_times
    assert schedule.laps == laps

    graph._redraw_from_start()
    graph.refresh()
    assert set(schedule._y_locations) == set(graph._operation_items)
    assert item._ports["in1"]["item"].toolTip() == "DontCare"
    assert item._ports["out0"]["item"].toolTip() == "Sink"
    assert schedule.start_times == start_times
    assert schedule.laps == laps

    schedule.swap_io_of_operation("add0")
    graph.refresh()
    assert item._ports["in0"]["item"].toolTip() == "DontCare"
    assert not item._ports["in1"]["item"].toolTip()
    assert item._ports["out0"]["item"].toolTip() == "Sink"


@pytest.mark.parametrize("cyclic", [False, True])
def test_operation_with_sink_can_move_into_available_slack(qtbot, monkeypatch, cyclic):
    monkeypatch.setattr(OperationItem, "_scale", 75)
    monkeypatch.setattr(AxesItem, "_scale", 75)
    source = Input()
    unused = Subtraction(source, source, latency=1)
    Sink(unused)
    used = ConstantMultiplication(0.5, source, latency=4)
    schedule = Schedule(SFG([source], [Output(used)]), cyclic=cyclic)
    graph = SchedulerItem(schedule)
    scene = QGraphicsScene()
    scene.addItem(graph)
    graph.installSceneEventFilters(graph.event_items)
    view = QGraphicsView(scene)
    qtbot.addWidget(view)
    view.resize(900, 600)
    view.scale(75, 75)
    view.show()
    item = graph._operation_items["sub0"]

    assert graph.is_component_valid_pos(item, item.x() + 2)
    start = view.mapFromScene(
        item.mapToScene(item._latency_item.boundingRect().center())
    )
    end = start + QPoint(150, 0)
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    _mouse_move_with_left_button(view, end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert schedule.start_times["sub0"] == 2
    schedule._validate_slacks()
    schedule._validate_laps()


def test_dontcare_input_allows_cyclic_backward_drag(qtbot, monkeypatch):
    monkeypatch.setattr(OperationItem, "_scale", 75)
    monkeypatch.setattr(AxesItem, "_scale", 75)
    operation = ConstantMultiplication(0.5, DontCare(), latency=1)
    schedule = Schedule(SFG([], [Output(operation)]), cyclic=True, schedule_time=4)
    graph = SchedulerItem(schedule)
    scene = QGraphicsScene()
    scene.addItem(graph)
    graph.installSceneEventFilters(graph.event_items)
    view = QGraphicsView(scene)
    qtbot.addWidget(view)
    view.resize(900, 600)
    view.scale(75, 75)
    view.show()
    item = graph._operation_items["cmul0"]
    start = view.mapFromScene(
        item.mapToScene(item._latency_item.boundingRect().center())
    )
    end = start - QPoint(75, 0)
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    _mouse_move_with_left_button(view, end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)

    assert schedule.start_times["cmul0"] == 3
    schedule._validate_slacks()
    schedule._validate_laps()


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
        _mouse_move_with_left_button(view, end)
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
    ("start_time", "latency", "expected_start"), [(3, 1, 0), (2, 2, 2)]
)
def test_timeline_drag_wraps_sink_terminated_operation(
    qtbot, monkeypatch, start_time, latency, expected_start
):
    monkeypatch.setattr(OperationItem, "_scale", 75)
    monkeypatch.setattr(AxesItem, "_scale", 75)
    source = Input()
    unused = Subtraction(source, source, latency=latency)
    Sink(unused)
    used = ConstantMultiplication(0.5, source, latency=1)
    schedule = Schedule(SFG([source], [Output(used)]), cyclic=True, schedule_time=4)
    schedule.move_operation("sub0", start_time)
    graph = SchedulerItem(schedule)
    scene = QGraphicsScene()
    scene.addItem(graph)
    graph.installSceneEventFilters(graph.event_items)
    view = QGraphicsView(scene)
    qtbot.addWidget(view)
    view.resize(900, 600)
    view.scale(75, 75)
    view.show()
    start_times = schedule.start_times.copy()
    laps = schedule.laps.copy()

    assert graph.is_valid_delta_time(-1)
    assert schedule.start_times == start_times
    assert schedule.laps == laps
    timeline = graph.axes.event_items[0]
    start = view.mapFromScene(timeline.mapToScene(timeline.line().center()))
    end = start - QPoint(75, 0)
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    _mouse_move_with_left_button(view, end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)

    assert schedule.schedule_time == 3
    assert schedule.start_times["sub0"] == expected_start
    assert schedule.start_times["sink0"] == 1
    schedule._validate()
    graph.change_schedule_time(1)
    schedule._validate()
    graph.change_schedule_time(-1)
    schedule._validate()


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
    _mouse_move_with_left_button(view, end)

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


@pytest.mark.parametrize("fragment", ["left", "right"])
@pytest.mark.parametrize("initially_wrapped", [False, True])
def test_drag_wrapped_operation_fragment(
    qtbot, monkeypatch, fragment, initially_wrapped
):
    monkeypatch.setattr(OperationItem, "_scale", 75)
    monkeypatch.setattr(AxesItem, "_scale", 75)
    source = Input()
    operation = ConstantMultiplication(0.5, source, latency=3)
    schedule = Schedule(
        SFG([source], [Output(operation)]),
        cyclic=True,
        schedule_time=5,
        start_times={"in0": 0, "cmul0": 3 if initially_wrapped else 2, "out0": 3},
        laps={"s0": 0, "s1": int(not initially_wrapped)},
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
    if not initially_wrapped:
        schedule.move_operation("cmul0", 1)
        graph._set_position("cmul0")
        graph._redraw_all_lines()
    item = graph._operation_items["cmul0"]
    output_signal = next(
        signal for signal in graph._signal_dict[item] if signal._src_operation is item
    )

    def assert_direct():
        path = output_signal.path()
        assert any(path.elementAt(i).isCurveTo() for i in range(path.elementCount()))

    assert_direct()
    polygons = item._latency_item.path().toSubpathPolygons()
    polygons = sorted(polygons, key=lambda polygon: polygon.boundingRect().left())
    point = polygons[0 if fragment == "left" else -1].boundingRect().center()
    start = view.mapFromScene(item.mapToScene(point))
    end = start + QPoint(75, 0)

    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    assert scene.mouseGrabberItem() is item
    _mouse_move_with_left_button(view, end)
    assert item.x() == pytest.approx(graph._x_axis_indent + 4)
    assert_direct()
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)

    assert schedule.start_times["cmul0"] == 4
    assert_direct()


@pytest.mark.parametrize(
    ("source_start", "source_latency", "dest_start", "dest_offset", "laps"),
    [(3, 3, 3, 0, 0), (2, 0, 3, 3, 0), (3, 3, 3, 0, 1), (2, 3, 0, 0, 1)],
)
def test_signal_routing_matches_matplotlib(
    qtbot, source_start, source_latency, dest_start, dest_offset, laps
):
    from matplotlib.figure import Figure
    from matplotlib.patches import PathPatch

    source = Input()
    producer = ConstantMultiplication(0.5, source, latency=source_latency)
    consumer = ConstantMultiplication(
        0.25, producer, latency_offsets={"in0": dest_offset, "out0": dest_offset}
    )
    schedule = Schedule(
        SFG([source], [Output(consumer)]),
        cyclic=True,
        schedule_time=5,
        start_times={"in0": 0, "cmul0": source_start, "cmul1": dest_start, "out0": 4},
        laps={"s0": 0, "s1": 0, "s2": laps},
    )
    graph = SchedulerItem(schedule)
    signal = next(
        signal
        for signal in graph._get_all_signals()
        if signal._src_operation.graph_id == "cmul0"
        and signal._dest_operation.graph_id == "cmul1"
    )
    ax = Figure().subplots()
    schedule.plot(ax)
    # Every direct interconnect is a PathPatch in the matplotlib drawing.
    expected_direct_count = sum(isinstance(patch, PathPatch) for patch in ax.patches)

    def direct_count():
        return sum(
            any(
                line.path().elementAt(i).isCurveTo()
                for i in range(line.path().elementCount())
            )
            for line in graph._get_all_signals()
        )

    assert direct_count() == expected_direct_count
    # Drag previews and the redraw after dropping must use the same routing.
    graph._redraw_lines(signal._src_operation)
    assert direct_count() == expected_direct_count
    graph._redraw_all_lines()
    assert direct_count() == expected_direct_count


@pytest.mark.parametrize(
    ("cyclic", "input_time", "output_time"),
    [(False, 0, 5), (True, 0, 0), (True, 0, 5), (True, 5, 0), (True, 5, 5)],
)
def test_io_boundary_positions_and_connections(qtbot, cyclic, input_time, output_time):
    source = Input()
    operation = ConstantMultiplication(0.5, source, latency=1)
    schedule = Schedule(
        SFG([source], [Output(operation)]),
        cyclic=cyclic,
        schedule_time=5,
        start_times={"in0": input_time, "cmul0": 1, "out0": output_time},
        laps={"s0": int(input_time == 5), "s1": int(output_time == 0)},
    )
    graph = SchedulerItem(schedule)
    assert graph._operation_items["in0"].x() == pytest.approx(graph._x_axis_indent)
    assert graph._operation_items["out0"].x() == pytest.approx(graph._x_axis_indent + 5)
    for line in graph._get_all_signals():
        path = line.path()
        assert any(path.elementAt(i).isCurveTo() for i in range(path.elementCount()))
        assert path.elementAt(0).x == pytest.approx(
            line._src_operation.get_port_location(line._src_key).x()
        )
        assert path.elementAt(path.elementCount() - 1).x == pytest.approx(
            line._dest_operation.get_port_location(line._dest_key).x()
        )


@pytest.mark.parametrize("input_time", [0, 5])
@pytest.mark.parametrize("output_time", [0, 5])
@pytest.mark.parametrize("dragged_id", ["in0", "cmul0", "cmul1", "out0"])
@pytest.mark.parametrize("dx", [-2, -1, 1, 2])
def test_drag_paths_match_drop_at_cycle_boundaries(
    qtbot, monkeypatch, input_time, output_time, dragged_id, dx
):
    monkeypatch.setattr(OperationItem, "_scale", 75)
    monkeypatch.setattr(AxesItem, "_scale", 75)
    source = Input()
    producer = ConstantMultiplication(0.5, source, latency=3)
    consumer = ConstantMultiplication(0.25, producer, latency=0)
    schedule = Schedule(
        SFG([source], [Output(consumer)]),
        cyclic=True,
        schedule_time=5,
        start_times={"in0": input_time, "cmul0": 3, "cmul1": 3, "out0": output_time},
        laps={"s0": int(input_time == 5), "s1": int(output_time == 0), "s2": 0},
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
    item = graph._operation_items[dragged_id]
    point = item._label_item.mapToScene(item._label_item.boundingRect().center())
    start = view.mapFromScene(point)
    end = start + QPoint(75 * dx, 0)
    original_times = schedule.start_times.copy()
    original_laps = schedule.laps.copy()
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    assert scene.mouseGrabberItem() is item
    original_x = item.x()
    _mouse_move_with_left_button(view, end)
    expected_dx = max(dx, -1) if dragged_id == "in0" else dx
    assert item.x() == pytest.approx(original_x + expected_dx)
    assert schedule.start_times == original_times
    assert schedule.laps == original_laps

    def path_elements(line):
        path = line.path()
        return [path.elementAt(i) for i in range(path.elementCount())]

    def outline_coordinates():
        path = item._latency_item.mapToItem(graph, item._latency_item.path())
        return [
            value
            for i in range(path.elementCount())
            for value in (path.elementAt(i).x, path.elementAt(i).y)
        ]

    preview_outline = outline_coordinates()
    preview = {line: path_elements(line) for line in graph._get_all_signals()}
    for line, elements in preview.items():
        source_x = line._src_operation.get_port_location(line._src_key).x()
        if source_x == pytest.approx(graph._x_axis_indent + 5) and not any(
            element.isCurveTo() for element in elements
        ):
            # Qt omits the zero-length outgoing stub at the right boundary.
            assert elements[0].x == pytest.approx(graph._x_axis_indent)
        else:
            assert elements[0].x == pytest.approx(source_x)
        assert elements[-1].x == pytest.approx(
            line._dest_operation.get_port_location(line._dest_key).x()
        )
        for element in (elements[0], elements[-1]):
            assert (
                graph._x_axis_indent - 1e-9
                <= element.x
                <= graph._x_axis_indent + 5 + 1e-9
            )
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert outline_coordinates() == pytest.approx(preview_outline)
    for line, before in preview.items():
        after = path_elements(line)
        assert [element.type for element in before] == [
            element.type for element in after
        ]
        assert [
            value for element in before for value in (element.x, element.y)
        ] == pytest.approx(
            [value for element in after for value in (element.x, element.y)]
        )


@pytest.fixture
def drag_view(qtbot, monkeypatch):
    monkeypatch.setattr(OperationItem, "_scale", 75)
    monkeypatch.setattr(AxesItem, "_scale", 75)
    source = Input()
    operation = ConstantMultiplication(0.5, source, latency=1)
    schedule = Schedule(
        SFG([source], [Output(operation)]),
        schedule_time=10,
        start_times={"in0": 0, "cmul0": 3, "out0": 8},
        laps={"s0": 0, "s1": 0},
    )
    graph = SchedulerItem(schedule)
    scene = QGraphicsScene()
    scene.addItem(graph)
    graph.installSceneEventFilters(graph.event_items)
    view = QGraphicsView(scene)
    # QGraphicsView does not own its scene. Keep it alive after this fixture returns.
    scene.setParent(view)
    qtbot.addWidget(view)
    view.resize(1200, 600)
    view.scale(75, 75)
    view.show()
    return graph, view


@pytest.mark.parametrize(
    ("dx", "dy", "expected_start"),
    [(-3, 0, 0), (3, 0, 6), (-8, 0, 0), (8, 0, 7), (8, 1, 7)],
)
def test_fast_operation_drag_stops_at_slack_limits(
    qtbot, drag_view, dx, dy, expected_start
):
    graph, view = drag_view
    item = graph._operation_items["cmul0"]
    old_row = graph.schedule.get_y_location(item.graph_id)
    start = view.mapFromScene(
        item._label_item.mapToScene(item._label_item.boundingRect().center())
    )
    end = start + QPoint(75 * dx, 75 * dy)
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    assert view.scene().mouseGrabberItem() is item
    _mouse_move_with_left_button(view, end)
    assert item.x() == pytest.approx(graph._x_axis_indent + expected_start)
    assert graph.schedule.start_times[item.graph_id] == 3
    assert graph.schedule.get_y_location(item.graph_id) == old_row + dy
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert graph.schedule.start_times[item.graph_id] == expected_start


@pytest.mark.parametrize(("dx", "expected_time"), [(-5, 8), (-2, 8), (3, 13)])
def test_fast_timeline_drag_stops_at_minimum_time(qtbot, drag_view, dx, expected_time):
    graph, view = drag_view
    item = graph.axes.event_items[0]
    original_x = item.x()
    start = view.mapFromScene(item.mapToScene(item.line().center()))
    end = start + QPoint(75 * dx, 0)
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    assert view.scene().mouseGrabberItem() is item
    _mouse_move_with_left_button(view, end)
    assert item.x() == pytest.approx(original_x + expected_time - 10)
    assert graph.schedule.schedule_time == 10
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert graph.schedule.schedule_time == expected_time


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

    assert schedule.start_times["sink0"] == schedule.schedule_time
    item = graph._operation_items["out0"]
    assert schedule.start_times["out0"] == schedule.schedule_time
    assert item.x() == pytest.approx(graph._x_axis_indent + schedule.schedule_time)
    graph.set_new_start_time(item)
    assert schedule.start_times["out0"] == schedule.schedule_time


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
    assert table.horizontalHeaderItem(0).text() == "OUT"
    assert table.verticalHeaderItem(0).text() == "IN"
    assert table.item(0, 0).text() == "9"

    widget.close_schedule()
    assert widget._io_latency_window is None


def test_io_latency_shortcut(qtbot, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type_name(ConstantMultiplication.type_name(), 4)
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.activateWindow()
    qtbot.waitActive(widget)

    qtbot.keyClick(widget, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)
    assert widget._io_latency_window is None

    widget.open(Schedule(sfg_simple_filter, ASAPScheduler()))
    QApplication.processEvents()
    qtbot.keyClick(widget, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)
    assert widget._io_latency_window is not None
    assert widget._io_latency_window.isVisible()


def test_plot_schedule_shortcut(qtbot, monkeypatch, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type_name(ConstantMultiplication.type_name(), 4)
    plotted = []

    def record_plot(schedule):
        plotted.append(schedule)

    monkeypatch.setattr(Schedule, "show", record_plot)
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.activateWindow()
    qtbot.waitActive(widget)
    qtbot.keyClick(widget, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier)
    assert not plotted

    widget.open(Schedule(sfg_simple_filter, ASAPScheduler()))
    QApplication.processEvents()
    qtbot.keyClick(widget, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier)
    assert plotted == [widget.schedule]


@pytest.mark.parametrize(
    ("action_name", "key_name", "control", "shift"),
    [
        ("actionZoom_to_fit", "F", True, False),
        ("actionZoom_to_fit_ignore_aspect_ratio", "F", True, True),
        ("actionRestore_aspect_ratio", "0", True, False),
        ("actionRotateForward", "Right", True, False),
        ("actionRotateBackward", "Left", True, False),
        ("actionIncrease_time_resolution", "Up", True, True),
        ("actionDecrease_time_resolution", "Down", True, True),
        ("action_show_port_numbers", "N", True, True),
        ("action_view_port_accesses", "A", True, True),
        ("action_view_variables", "E", True, False),
        ("action_total_execution_times_of_variables", "E", True, True),
        ("actionDocumentation", "F1", False, False),
    ],
)
def test_scheduler_action_shortcuts(qtbot, action_name, key_name, control, shift):
    source = Input()
    operation = ConstantMultiplication(0.5, source, latency=1)
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.activateWindow()
    qtbot.waitActive(widget)
    widget.open(Schedule(SFG([source], [Output(operation)])))
    QApplication.processEvents()

    action = getattr(widget, action_name)
    action.triggered.disconnect()
    modifiers = Qt.KeyboardModifier.NoModifier
    if control:
        modifiers |= Qt.KeyboardModifier.ControlModifier
    if shift:
        modifiers |= Qt.KeyboardModifier.ShiftModifier
    with qtbot.waitSignal(action.triggered):
        qtbot.keyClick(widget, getattr(Qt.Key, f"Key_{key_name}"), modifiers)


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
    ] == ["out1", "out2", "out10"]
    assert [table.verticalHeaderItem(row).text() for row in range(2)] == ["in0", "in1"]
    assert [table.item(0, column).text() for column in range(3)] == [
        "-",
        "12",
        "110",
    ]
    assert [table.item(1, column).text() for column in range(3)] == [
        "21",
        "-",
        "210",
    ]


def test_io_latency_rows_are_naturally_sorted(qtbot):
    widget = IOLatencyWindow()
    qtbot.addWidget(widget)
    widget.set_io_latency(
        {
            "in10": {"out1": 101},
            "in2": {"out2": 22},
            "in11": {"out2": 112},
            "in1": {"out1": 11},
            "in0": {"out1": 1},
        }
    )

    table = widget.table
    assert [
        table.verticalHeaderItem(row).text() for row in range(table.rowCount())
    ] == ["in0", "in1", "in2", "in10", "in11"]
    assert [
        [table.item(row, column).text() for column in range(2)]
        for row in range(table.rowCount())
    ] == [
        ["1", "-"],
        ["11", "-"],
        ["-", "22"],
        ["101", "-"],
        ["-", "112"],
    ]


def test_io_latency_uses_names_without_merging_duplicate_names(qtbot):
    widget = IOLatencyWindow()
    qtbot.addWidget(widget)
    widget.set_io_latency(
        {"in0": {"out0": 1}, "in1": {"out1": 2}, "in2": {"out2": 3}},
        {"in0": "A[0,10]", "in1": "A[0,2]", "out0": "result", "out1": "result"},
    )
    table = widget.table
    assert [table.horizontalHeaderItem(i).text() for i in range(3)] == [
        "out2",
        "result",
        "result",
    ]
    assert [
        table.verticalHeaderItem(row).text() for row in range(table.rowCount())
    ] == ["A[0,2]", "A[0,10]", "in2"]
    assert [
        [table.item(row, column).text() for column in range(3)]
        for row in range(table.rowCount())
    ] == [
        ["-", "-", "2"],
        ["-", "1", "-"],
        ["3", "-", "-"],
    ]


def test_view_io_latency_uses_and_refreshes_operation_names(qtbot):
    source = Input(name="A[0,0]")
    operation = ConstantMultiplication(0.5, source, latency=1)
    output = Output(operation, name="result")
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open(Schedule(SFG([source], [output])))
    widget.action_view_io_latency.trigger()

    table = widget._io_latency_window.table
    assert table.verticalHeaderItem(0).text() == "A[0,0]"
    assert table.horizontalHeaderItem(0).text() == "result"
    widget.schedule._sfg.find_by_id("in0").name = "A[0,1]"
    widget._schedule_changed()
    assert table.verticalHeaderItem(0).text() == "A[0,1]"


def test_io_latency_input_header_stays_visible_when_scrolling(qtbot):
    widget = IOLatencyWindow()
    qtbot.addWidget(widget)
    widget.set_io_latency({"in0": {f"out{index}": index for index in range(20)}})
    widget.resize(300, 200)
    widget.show()
    QApplication.processEvents()
    table = widget.table
    header = table.verticalHeader()
    scrollbar = table.horizontalScrollBar()
    assert header.isVisible()
    assert scrollbar.maximum() > 0
    position = header.pos()
    scrollbar.setValue(scrollbar.maximum())
    QApplication.processEvents()
    assert header.pos() == position
    assert table.verticalHeaderItem(0).text() == "in0"


def test_io_latency_selects_rows_and_columns_from_headers(qtbot):
    widget = IOLatencyWindow()
    qtbot.addWidget(widget)
    widget.set_io_latency(
        {"in0": {"out0": 1, "out1": 2}, "in1": {"out0": 3, "out1": 4}}
    )
    widget.show()
    QApplication.processEvents()
    table = widget.table

    def selected_cells():
        return {(item.row(), item.column()) for item in table.selectedItems()}

    row_header = table.verticalHeader()
    row_pos = QPoint(
        row_header.viewport().width() // 2,
        row_header.sectionViewportPosition(1) + row_header.sectionSize(1) // 2,
    )
    qtbot.mouseClick(row_header.viewport(), Qt.MouseButton.LeftButton, pos=row_pos)
    assert selected_cells() == {(1, 0), (1, 1)}

    column_header = table.horizontalHeader()
    column_pos = QPoint(
        column_header.sectionViewportPosition(0) + column_header.sectionSize(0) // 2,
        column_header.viewport().height() // 2,
    )
    qtbot.mouseClick(
        column_header.viewport(), Qt.MouseButton.LeftButton, pos=column_pos
    )
    assert selected_cells() == {(0, 0), (1, 0)}

    qtbot.mouseClick(
        table.viewport(),
        Qt.MouseButton.LeftButton,
        pos=table.visualItemRect(table.item(0, 1)).center(),
    )
    assert selected_cells() == {(0, 1)}


@pytest.mark.parametrize("empty_latency", [{}, {"in0": {}}])
def test_io_latency_empty_table_can_be_refreshed(qtbot, empty_latency):
    widget = IOLatencyWindow()
    qtbot.addWidget(widget)
    widget.set_io_latency({"in0": {"out0": 1}})
    widget.set_io_latency(empty_latency)
    assert widget.table.item(0, 0).text() == "No input/output paths"
    assert widget.table.verticalHeaderItem(0).text() == ""
    widget.set_io_latency({"in1": {"out1": 2}})
    assert widget.table.verticalHeaderItem(0).text() == "in1"
    assert widget.table.horizontalHeaderItem(0).text() == "out1"
    assert widget.table.item(0, 0).text() == "2"


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
        assert widget.table.item(0, 0).text() == str(latency)
        assert widget.table.item(0, 1).text() == str(latency + 1)


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


def test_undo_redo_rotation(qtbot, precedence_sfg_delays):
    precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
    precedence_sfg_delays.set_latency_of_type_name(
        ConstantMultiplication.type_name(), 3
    )
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open(Schedule(precedence_sfg_delays, cyclic=True))
    original = widget.schedule.start_times.copy()

    assert not widget.actionUndo.isEnabled()
    assert not widget.actionRedo.isEnabled()
    widget.actionRotateForward.trigger()
    rotated = widget.schedule.start_times.copy()
    assert rotated != original
    assert widget.actionUndo.isEnabled()
    assert not widget.actionRedo.isEnabled()

    widget.actionUndo.trigger()
    assert widget.schedule.start_times == original
    assert not widget.actionUndo.isEnabled()
    assert widget.actionRedo.isEnabled()
    widget.actionRedo.trigger()
    assert widget.schedule.start_times == rotated
    assert widget.actionUndo.isEnabled()
    assert not widget.actionRedo.isEnabled()


def test_undo_redo_drag_and_shortcuts(qtbot):
    source = Input()
    product = ConstantMultiplication(0.5, source, latency=1)
    schedule = Schedule(SFG([source], [Output(product)]), schedule_time=5)
    schedule.move_operation("out0", 3)
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.resize(1000, 700)
    widget.show()
    qtbot.waitExposed(widget)
    widget.activateWindow()
    qtbot.waitActive(widget)
    widget.open(schedule)
    widget.action_view_io_latency.trigger()
    latency_window = widget._io_latency_window
    graph = widget._graph
    item = graph._operation_items["cmul0"]
    viewport = widget.view.viewport()
    start = widget.view.mapFromScene(
        item.mapToScene(item._latency_item.boundingRect().center())
    )
    end = start + QPoint(75, 0)
    qtbot.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=start)
    assert not widget.actionUndo.isEnabled()
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    _mouse_move_with_left_button(widget.view, end)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
    assert widget.schedule.start_times["cmul0"] == 1
    assert widget.actionUndo.isEnabled()

    QApplication.setActiveWindow(widget)
    qtbot.waitActive(widget)
    widget.view.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is widget.view)
    qtbot.keyClick(widget.view, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert widget.schedule.start_times["cmul0"] == 0
    assert widget._io_latency_window is latency_window
    assert widget._graph._operation_items["cmul0"].x() == pytest.approx(
        widget._graph._x_axis_indent
    )
    qtbot.keyClick(
        widget.view,
        Qt.Key.Key_Z,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    assert widget.schedule.start_times["cmul0"] == 1
    assert widget._io_latency_window is latency_window
    qtbot.keyClick(widget.view, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    widget._graph._operation_items["cmul0"]._move_asap()
    assert widget.actionRedo.isEnabled()
    qtbot.keyClick(widget.view, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert widget.schedule.start_times["cmul0"] == 1


def test_undo_redo_timeline_and_branch(qtbot):
    source = Input()
    product = ConstantMultiplication(0.5, source, latency=1)
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.resize(1000, 700)
    widget.show()
    qtbot.waitExposed(widget)
    widget.open(Schedule(SFG([source], [Output(product)]), schedule_time=5))
    graph = widget._graph
    timeline = graph.axes.event_items[0]
    start = widget.view.mapFromScene(timeline.mapToScene(timeline.line().center()))
    end = start + QPoint(75, 0)
    viewport = widget.view.viewport()
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    _mouse_move_with_left_button(widget.view, end)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
    assert widget.schedule.schedule_time == 6
    widget.actionUndo.trigger()
    assert widget.schedule.schedule_time == 5
    assert widget._graph.axes.width == 5
    widget.actionRedo.trigger()
    assert widget.schedule.schedule_time == 6
    widget.actionUndo.trigger()
    widget._graph._operation_items["out0"]._move_alap()
    assert not widget.actionRedo.isEnabled()
    widget.actionUndo.trigger()
    assert widget.schedule.start_times["out0"] == 1
    widget.close_schedule()
    assert not widget.actionUndo.isEnabled()
    assert not widget.actionRedo.isEnabled()


def test_undo_redo_swap_and_resolution(qtbot, monkeypatch):
    left, right = Input(), Input()
    addition = Addition(left, right, latency=2)
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open(Schedule(SFG([left, right], [Output(addition)])))
    widget.info_table_update_component("add0")

    def input_signals():
        operation = widget.schedule._sfg.find_by_id("add0")
        return tuple(port.signals[0].graph_id for port in operation.inputs)

    initial_inputs = input_signals()
    widget._graph._swap_io_of_operation("add0")
    swapped_inputs = input_signals()
    assert swapped_inputs == initial_inputs[::-1]
    monkeypatch.setattr(main_window.QInputDialog, "getInt", lambda *args: (2, True))
    widget._increase_time_resolution()
    assert widget.schedule.schedule_time == 4
    widget.actionUndo.trigger()
    assert widget.schedule.schedule_time == 2
    assert input_signals() == swapped_inputs
    assert widget._selected_graph_id == "add0"
    widget.actionUndo.trigger()
    assert input_signals() == initial_inputs
    widget.actionRedo.trigger()
    assert input_signals() == swapped_inputs
    widget.actionRedo.trigger()
    assert widget.schedule.schedule_time == 4


def test_undo_redo_vertical_drag_and_reorder(qtbot):
    source = Input()
    product = ConstantMultiplication(0.5, source, latency=1)
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.resize(1000, 700)
    widget.show()
    qtbot.waitExposed(widget)
    widget.open(Schedule(SFG([source], [Output(product)]), schedule_time=5))
    graph = widget._graph
    initial = dict(widget.schedule._y_locations)
    item = graph._operation_items["cmul0"]
    start = widget.view.mapFromScene(
        item.mapToScene(item._latency_item.boundingRect().center())
    )
    end = start + QPoint(0, 100)
    viewport = widget.view.viewport()
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    _mouse_move_with_left_button(widget.view, end)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
    moved = dict(widget.schedule._y_locations)
    assert moved != initial
    widget._action_reorder()
    reordered = dict(widget.schedule._y_locations)
    assert reordered != moved
    widget.actionUndo.trigger()
    assert dict(widget.schedule._y_locations) == moved
    widget.actionUndo.trigger()
    assert dict(widget.schedule._y_locations) == initial
    widget.actionRedo.trigger()
    assert dict(widget.schedule._y_locations) == moved


def test_undo_redo_cyclic_wrap(qtbot):
    source = Input()
    first = ConstantMultiplication(0.5, source, latency=1)
    second = ConstantMultiplication(0.25, first, latency=0)
    schedule = Schedule(
        SFG([source], [Output(second)]),
        cyclic=True,
        schedule_time=3,
        start_times={"in0": 0, "cmul0": 0, "cmul1": 2, "out0": 2},
        laps={"s0": 1, "s1": 1, "s2": 0},
    )
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.resize(1000, 700)
    widget.show()
    qtbot.waitExposed(widget)
    widget.open(schedule)
    initial_times = dict(widget.schedule.start_times)
    initial_laps = dict(widget.schedule.laps)
    item = widget._graph._operation_items["cmul0"]
    start = widget.view.mapFromScene(
        item.mapToScene(item._latency_item.boundingRect().center())
    )
    end = start - QPoint(75, 0)
    viewport = widget.view.viewport()
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    _mouse_move_with_left_button(widget.view, end)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
    moved_times = dict(widget.schedule.start_times)
    moved_laps = dict(widget.schedule.laps)
    assert moved_times != initial_times
    assert moved_laps != initial_laps
    widget.actionUndo.trigger()
    assert widget.schedule.start_times == initial_times
    assert widget.schedule.laps == initial_laps
    widget.actionRedo.trigger()
    assert widget.schedule.start_times == moved_times
    assert widget.schedule.laps == moved_laps


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


@pytest.mark.parametrize("direction", ["forward", "backward"])
def test_invalid_noncyclic_rotation_does_nothing(qtbot, monkeypatch, direction):
    source = Input()
    operation = ConstantMultiplication(2, source, latency=2)
    schedule = Schedule(SFG([source], [Output(operation)]), schedule_time=2)
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open(schedule)
    original_times = widget.schedule.start_times.copy()
    original_laps = widget.schedule.laps.copy()
    history_index = widget._history_index
    original_message = widget.statusbar.currentMessage()
    warnings = []
    monkeypatch.setattr(
        main_window.QMessageBox, "warning", lambda *args: warnings.append(args)
    )

    getattr(widget, f"_rotate_{direction}")()

    assert not warnings
    assert widget.schedule.start_times == original_times
    assert widget.schedule.laps == original_laps
    assert widget._history_index == history_index
    assert widget.statusbar.currentMessage() == original_message


def test_noncyclic_rotation_undo_redo(qtbot):
    source = Input()
    operation = ConstantMultiplication(2, source, latency=1)
    schedule = Schedule(SFG([source], [Output(operation)]), schedule_time=5)
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open(schedule)
    original_times = widget.schedule.start_times.copy()

    widget.actionRotateForward.trigger()
    rotated_times = widget.schedule.start_times.copy()
    assert rotated_times != original_times
    widget.actionUndo.trigger()
    assert widget.schedule.start_times == original_times
    widget.actionRedo.trigger()
    assert widget.schedule.start_times == rotated_times


def test_cyclic_operation_item_drawing_wraps_at_end(qtbot, precedence_sfg_delays):
    precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
    precedence_sfg_delays.set_latency_of_type_name(
        ConstantMultiplication.type_name(), 3
    )
    schedule = Schedule(precedence_sfg_delays, cyclic=True)
    scheduler_item = SchedulerItem(schedule)
    operation_item = max(
        scheduler_item.components,
        key=lambda item: item._latency_path.boundingRect().width(),
    )
    original_bounds = operation_item._latency_path.boundingRect()
    period = schedule.schedule_time
    for right_fraction in (0.25, 0.5):
        start_time = (
            period - original_bounds.left() - right_fraction * original_bounds.width()
        )
        operation_item.setX(scheduler_item._x_axis_indent + start_time)

        wrapped_path = operation_item._latency_item.path()
        wrapped_bounds = wrapped_path.boundingRect()
        assert len(wrapped_path.toSubpathPolygons()) >= 2
        assert wrapped_bounds.left() >= -start_time - 1e-6
        assert wrapped_bounds.right() <= period - start_time + 1e-6

        label_center = operation_item._label_item.mapToParent(
            operation_item._label_item.boundingRect().center()
        )
        label_time = start_time + label_center.x()
        left_width = (1 - right_fraction) * original_bounds.width()
        right_width = right_fraction * original_bounds.width()
        expected_label_time = (
            left_width / 2 if left_width >= right_width else period - right_width / 2
        )
        assert label_time == pytest.approx(expected_label_time)


@pytest.mark.parametrize(
    "operation_type", [ConstantMultiplication, Input, Output, Sink]
)
def test_cyclic_operation_at_schedule_time_draws_on_expected_side(
    qtbot, operation_type
):
    source = Input()
    operation = ConstantMultiplication(0.5, source, latency=2, execution_time=1)
    sink = Sink()
    sink <<= operation
    schedule = Schedule(SFG([source], [Output(operation)]), cyclic=True)
    schedule.set_schedule_time(4)
    graph = SchedulerItem(schedule)
    if operation_type is Sink:
        item = OperationItem(schedule._sfg.find_by_id("sink0"), graph)
    else:
        item = next(
            item
            for item in graph.components
            if isinstance(item.operation, operation_type)
        )
    period = schedule.schedule_time
    item.setX(graph._x_axis_indent + period)
    offset = 0 if operation_type in (Output, Sink) else -period

    assert item._latency_item.path() == item._latency_path.translated(offset, 0)
    if item._execution_time_path is not None:
        assert item._execution_time_item.path() == item._execution_time_path.translated(
            offset, 0
        )
    for key, port in item._ports.items():
        assert item.get_port_location(key).x() == pytest.approx(
            graph._x_axis_indent + period + port["pos"].x() + offset
        )
    label_center = item._label_item.mapToParent(
        item._label_item.boundingRect().center()
    )
    expected_center = item._latency_item.path().boundingRect().center()
    assert label_center.x() == pytest.approx(expected_center.x())
    assert label_center.y() == pytest.approx(expected_center.y())


def test_cyclic_operation_item_label_centered_on_initial_wrapped_part(
    qtbot, precedence_sfg_delays
):
    precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
    precedence_sfg_delays.set_latency_of_type_name(
        ConstantMultiplication.type_name(), 3
    )
    schedule = Schedule(precedence_sfg_delays, cyclic=True)
    operation = schedule._sfg.find_by_name("C0")[0]
    start_times = schedule.start_times.copy()
    start_times[operation.graph_id] = schedule.schedule_time - 1
    schedule.start_times = start_times

    scheduler_item = SchedulerItem(schedule)
    operation_item = scheduler_item._operation_items[operation.graph_id]
    polygons = operation_item._latency_item.path().toSubpathPolygons()
    largest_polygon = max(polygons, key=lambda polygon: polygon.boundingRect().width())
    expected_center = largest_polygon.boundingRect().center()
    label_center = operation_item._label_item.mapToParent(
        operation_item._label_item.boundingRect().center()
    )

    assert len(polygons) >= 2
    assert label_center.x() == pytest.approx(expected_center.x())
    assert label_center.y() == pytest.approx(expected_center.y())


@pytest.mark.parametrize("source_type", [Input, DontCare])
@pytest.mark.parametrize("start_time", [0, 5])
def test_input_like_boundary_shapes(qtbot, source_type, start_time):
    source = source_type()
    operation = ConstantMultiplication(0.5, source, latency=1)
    source_id = f"{source_type.type_name()}0"
    sfg = SFG([source] if source_type is Input else [], [Output(operation)])
    signal_id = sfg.find_by_id(source_id).output(0).signals[0].graph_id
    schedule = Schedule(
        sfg,
        cyclic=True,
        schedule_time=5,
        start_times={source_id: start_time, "cmul0": 1, "out0": 2},
        laps={signal_id: int(start_time == 5)},
    )
    graph = SchedulerItem(schedule)
    if source_type is DontCare:
        item = OperationItem(schedule._sfg.find_by_id(source_id), graph)
        item.setX(graph._x_axis_indent)
    else:
        item = graph._operation_items[source_id]
    assert item.x() == pytest.approx(graph._x_axis_indent)

    for drag_time in (0, 5):
        item.setX(graph._x_axis_indent + drag_time)
        expected = item._latency_path.translated(-drag_time, 0)
        assert item._latency_item.path() == expected
        assert item._execution_time_item.path() == expected
        assert item.get_port_location("out0").x() == pytest.approx(graph._x_axis_indent)
        label_center = item._label_item.mapToItem(
            graph, item._label_item.boundingRect().center()
        )
        assert label_center.x() < graph._x_axis_indent


def test_cyclic_io_operation_shapes_stay_outside_cycle(qtbot, precedence_sfg_delays):
    precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
    precedence_sfg_delays.set_latency_of_type_name(
        ConstantMultiplication.type_name(), 3
    )
    schedule = Schedule(precedence_sfg_delays, cyclic=True)
    scheduler_item = SchedulerItem(schedule)
    input_item = next(
        item for item in scheduler_item.components if isinstance(item.operation, Input)
    )
    output_item = next(
        item for item in scheduler_item.components if isinstance(item.operation, Output)
    )
    period = schedule.schedule_time
    indent = scheduler_item._x_axis_indent

    input_item.setX(indent)
    output_item.setX(indent + period)

    input_bounds = input_item._latency_item.path().boundingRect()
    output_bounds = output_item._latency_item.path().boundingRect()
    assert input_bounds.left() < 0
    assert input_bounds.right() == pytest.approx(0)
    assert output_bounds.left() == pytest.approx(0)
    assert output_bounds.right() > 0

    input_label_center = input_item._label_item.mapToParent(
        input_item._label_item.boundingRect().center()
    )
    output_label_center = output_item._label_item.mapToParent(
        output_item._label_item.boundingRect().center()
    )
    assert input_label_center.x() < 0
    assert output_item.x() - indent + output_label_center.x() > period


def test_cyclic_io_signal_endpoints_use_wrapped_ports(qtbot, precedence_sfg_delays):
    precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
    precedence_sfg_delays.set_latency_of_type_name(
        ConstantMultiplication.type_name(), 3
    )
    schedule = Schedule(precedence_sfg_delays, cyclic=True)
    scheduler_item = SchedulerItem(schedule)
    input_item = next(
        item for item in scheduler_item.components if isinstance(item.operation, Input)
    )
    output_item = next(
        item for item in scheduler_item.components if isinstance(item.operation, Output)
    )
    period = schedule.schedule_time
    indent = scheduler_item._x_axis_indent

    input_item.setX(indent - 1)
    output_item.setX(indent + period + 1)

    input_bounds = input_item._latency_item.path().boundingRect()
    output_bounds = output_item._latency_item.path().boundingRect()
    assert input_bounds.left() > 0
    assert output_bounds.right() < 0
    assert input_item.x() - indent + input_bounds.left() >= -1e-6
    assert input_item.x() - indent + input_bounds.right() <= period + 1e-6
    assert output_item.x() - indent + output_bounds.left() >= -1e-6
    assert output_item.x() - indent + output_bounds.right() <= period + 1e-6

    input_signal = input_item.operation.output(0).signals[0]
    output_signal = output_item.operation.input(0).signals[0]
    input_line = next(
        line
        for line in scheduler_item._signal_dict[input_item]
        if line._signal is input_signal
    )
    output_line = next(
        line
        for line in scheduler_item._signal_dict[output_item]
        if line._signal is output_signal
    )
    input_line.update_path()
    output_line.update_path()

    assert input_item.get_port_location("out0").x() == pytest.approx(
        indent + period - 1
    )
    assert output_item.get_port_location("in0").x() == pytest.approx(indent + 1)
    assert input_line.path().elementAt(0).x == pytest.approx(indent + period - 1)
    assert output_line.path().elementAt(
        output_line.path().elementCount() - 1
    ).x == pytest.approx(indent + 1)


def test_signal_wraps_port_immediately_after_schedule_time(
    qtbot, precedence_sfg_delays
):
    precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
    precedence_sfg_delays.set_latency_of_type_name(
        ConstantMultiplication.type_name(), 3
    )
    schedule = Schedule(precedence_sfg_delays, cyclic=True)
    scheduler_item = SchedulerItem(schedule)
    source_item = next(item for item in scheduler_item.components if item.name == "C0")
    signal = source_item.operation.output(0).signals[0]
    signal_item = next(
        item
        for item in scheduler_item._signal_dict[source_item]
        if item._signal is signal
    )
    period = schedule.schedule_time
    indent = scheduler_item._x_axis_indent
    output_time = source_item._ports["out0"]["pos"].x()

    source_item.setX(indent + period + 1 - output_time)
    signal_item.update_path()
    assert signal_item.path().elementAt(0).x == pytest.approx(indent + 1)

    source_item.setX(indent + period + 0.5 - output_time)
    signal_item.update_path()
    assert signal_item.path().elementAt(0).x == pytest.approx(indent + 0.5)


def test_open_long_chain(qtbot):
    source = Input()
    end = source
    for _ in range(250):
        end = ConstantMultiplication(0.5, end, latency=1)
    original = Schedule(SFG([source], [Output(end)]))
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)

    widget.open(original)

    assert widget.schedule is not original
    assert widget.schedule.start_times == original.start_times
    assert len(widget._graph.components) == 252


@pytest.mark.parametrize(
    "action", ["asap", "alap", "swap", "rotate_forward", "rotate_backward"]
)
def test_internal_edits_preserve_schedule_and_items(qtbot, action):
    left, right = Input(), Input()
    addition = Addition(left, right, latency=1)
    product = ConstantMultiplication(0.5, addition, latency=2)
    original = Schedule(SFG([left, right], [Output(product)]), cyclic=True)
    original.set_schedule_time(8)
    original.move_operation("out0", 8 - original.start_times["out0"])
    original.move_operation("cmul0", 1)
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open(original)
    schedule, graph = widget.schedule, widget._graph
    items = graph.components.copy()
    signals = graph._get_all_signals()
    item = graph._operation_items["cmul0"]
    widget.info_table_update_component("cmul0")
    scene_item_count = len(widget._scene.items())

    if action == "asap":
        item._move_asap()
        assert schedule.start_times["cmul0"] == 1
    elif action == "alap":
        item._move_alap()
        assert schedule.start_times["cmul0"] == 6
    elif action == "swap":
        graph._swap_io_of_operation("add0")
    else:
        getattr(widget, f"_{action}")()

    assert widget.schedule is schedule
    assert widget._graph is graph
    assert graph.components == items
    assert graph._get_all_signals() == signals
    assert widget._selected_graph_id == "cmul0"
    assert len(widget._scene.items()) == scene_item_count
    for signal in signals:
        assert signal._src_key == f"out{signal._signal.source.index}"
        assert signal._dest_key == f"in{signal._signal.destination.index}"
        assert (
            signal.path().currentPosition()
            == signal._dest_operation.get_port_location(signal._dest_key)
        )


def test_increase_time_resolution(qtbot, monkeypatch, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type_name(ConstantMultiplication.type_name(), 4)
    schedule = Schedule(sfg_simple_filter, ASAPScheduler())
    original_schedule_time = schedule.schedule_time
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open(schedule)
    graph = widget._graph
    gui_schedule = widget.schedule
    operation = graph._operation_items["cmul0"]
    old_width = operation._latency_path.boundingRect().width()
    child_count = len(operation.childItems())
    top_level_items = {
        item for item in widget._scene.items() if item.parentItem() is None
    }
    monkeypatch.setattr(main_window.QInputDialog, "getInt", lambda *args: (2, True))

    widget._increase_time_resolution()

    assert gui_schedule.schedule_time == original_schedule_time * 2
    assert widget.schedule is gui_schedule
    assert widget._graph is graph
    assert graph._operation_items["cmul0"] is operation
    assert operation._latency_path.boundingRect().width() == pytest.approx(
        old_width * 2
    )
    assert graph.axes.width == gui_schedule.schedule_time
    assert len(operation.childItems()) == child_count
    assert {
        item for item in widget._scene.items() if item.parentItem() is None
    } == top_level_items
    assert graph.axes.event_items[0].x() == pytest.approx(
        graph._x_axis_indent + gui_schedule.schedule_time
    )
    assert schedule.schedule_time == original_schedule_time
    assert (
        widget.statusbar.currentMessage() == "Time resolution increased by a factor 2"
    )


def test_decrease_time_resolution(qtbot, monkeypatch, sfg_simple_filter):
    sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
    sfg_simple_filter.set_latency_of_type_name(ConstantMultiplication.type_name(), 4)
    schedule = Schedule(sfg_simple_filter, ASAPScheduler())
    schedule.increase_time_resolution(2)
    increased_schedule_time = schedule.schedule_time
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open(schedule)
    graph = widget._graph
    gui_schedule = widget.schedule
    operation = graph._operation_items["cmul0"]
    old_width = operation._latency_path.boundingRect().width()
    child_count = len(operation.childItems())
    top_level_items = {
        item for item in widget._scene.items() if item.parentItem() is None
    }
    monkeypatch.setattr(
        main_window.QInputDialog,
        "getItem",
        lambda *args, **kwargs: ("2", True),
    )

    widget._decrease_time_resolution()

    assert gui_schedule.schedule_time * 2 == increased_schedule_time
    assert widget.schedule is gui_schedule
    assert widget._graph is graph
    assert graph._operation_items["cmul0"] is operation
    assert operation._latency_path.boundingRect().width() == pytest.approx(
        old_width / 2
    )
    assert graph.axes.width == gui_schedule.schedule_time
    assert len(operation.childItems()) == child_count
    assert {
        item for item in widget._scene.items() if item.parentItem() is None
    } == top_level_items
    assert graph.axes.event_items[0].x() == pytest.approx(
        graph._x_axis_indent + gui_schedule.schedule_time
    )
    assert schedule.schedule_time == increased_schedule_time
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


def test_execution_time_plot_font(qtbot, secondorder_iir_schedule):
    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open(secondorder_iir_schedule)
    widget._show_execution_times_for_variables()
    axes = widget._execution_time_for_variables.axes
    assert axes.xaxis.label.get_fontfamily() == ["DejaVu Serif"]
    assert all(text.get_fontfamily() == ["DejaVu Serif"] for text in axes.texts)
    widget._update_execution_times_for_variables()
    assert axes.xaxis.label.get_fontfamily() == ["DejaVu Serif"]
    widget._execution_time_for_variables.close()
    widget.exit_app()


def test_reset_font_uses_default(qtbot, monkeypatch):
    from b_asic.scheduler_gui._preferences import FONT

    widget = ScheduleMainWindow()
    qtbot.addWidget(widget)
    widget.open_preferences_dialog()
    dialog = widget._preferences_dialog
    for attribute in ("current_font", "changed", "color", "size", "bold", "italic"):
        monkeypatch.setattr(FONT, attribute, getattr(FONT, attribute))
    monkeypatch.setattr(dialog, "update_font", lambda: None)
    monkeypatch.setattr(widget, "load_preferences", lambda: None)
    monkeypatch.setattr(dialog, "match_dialog_font", lambda: None)
    dialog.reset_font_clicked()
    assert FONT.current_font.family() == "DejaVu Serif"
    assert not FONT.changed
    dialog.close()
    widget.exit_app()
