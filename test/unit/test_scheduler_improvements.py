"""Regressions for scheduling constraints, reuse, and model construction."""

from collections import Counter

import pytest

import b_asic.scheduler as scheduler_module
from b_asic import SFG, Addition, ConstantMultiplication, Delay, Input, Output
from b_asic._scheduler_utils import _get_connections
from b_asic.fft_operations import R2Butterfly
from b_asic.schedule import Schedule
from b_asic.scheduler import (
    ALAPScheduler,
    ASAPScheduler,
    CPScheduler,
    ILPScheduler,
    ListScheduler,
    RecursiveListScheduler,
)


def _chain(latency=2, execution_time=1):
    source = Input()
    op = ConstantMultiplication(
        2, source, latency=latency, execution_time=execution_time
    )
    return SFG(inputs=[source], outputs=[Output(op)])


def _scheduler(scheduler_type, **kwargs):
    if issubclass(scheduler_type, ListScheduler):
        return scheduler_type(((1, True),), **kwargs)
    return scheduler_type(**kwargs)


@pytest.mark.parametrize("scheduler_type", [ListScheduler, RecursiveListScheduler])
@pytest.mark.parametrize("amount", [0, -1])
def test_nonpositive_resource_limits(scheduler_type, amount):
    with pytest.raises(ValueError, match="must be positive"):
        _scheduler(scheduler_type, max_resources={ConstantMultiplication: amount})


def test_cyclic_resource_demand_includes_overlapping_instances():
    sources = [Input(), Input()]
    ops = [
        ConstantMultiplication(2, source, latency=1, execution_time=4)
        for source in sources
    ]
    schedule = Schedule(
        SFG(inputs=sources, outputs=[Output(op) for op in ops]),
        ListScheduler(((1, True),), max_resources={"in": 2, "out": 2, "cmul": 3}),
        schedule_time=3,
        cyclic=True,
    )
    occupancy = Counter(
        (schedule.start_times[op.graph_id] + offset) % 3
        for op in schedule.sfg.operations
        if isinstance(op, ConstantMultiplication)
        for offset in range(op.execution_time)
    )
    assert max(occupancy.values()) == 3
    assert all(
        schedule._execution_times_in_time(ConstantMultiplication, time)
        == occupancy[time]
        for time in range(3)
    )


def test_cyclic_resource_validation_rejects_invalid_provided_placement():
    scheduler = ListScheduler(((1, True),), max_resources={"cmul": 1})
    schedule = Schedule(_chain(latency=1), scheduler, schedule_time=3, cyclic=True)
    schedule._sfg.set_execution_time_of_type(ConstantMultiplication, 4)
    with pytest.raises(ValueError, match="breaches resource constraints"):
        scheduler._validate_constraints()


def test_resource_count_wraps_across_period_boundary():
    schedule = Schedule(
        _chain(latency=1, execution_time=2),
        ListScheduler(((1, True),), input_times={"in0": 2}),
        schedule_time=3,
        cyclic=True,
    )
    assert [
        schedule._execution_times_in_time(ConstantMultiplication, time)
        for time in range(3)
    ] == [1, 0, 1]


def test_fixed_inputs_count_towards_resource_limits():
    sources = [Input(), Input()]
    ops = [
        ConstantMultiplication(2, source, latency=1, execution_time=1)
        for source in sources
    ]
    with pytest.raises(ValueError, match="breaches resource constraints"):
        Schedule(
            SFG(inputs=sources, outputs=[Output(op) for op in ops]),
            ListScheduler(((1, True),), input_times={"in0": 0, "in1": 0}),
            schedule_time=10,
        )


def test_memory_constraints_build_memory_variables_once(monkeypatch):
    original = Schedule.get_memory_variables
    calls = []

    def track(schedule):
        calls.append(schedule)
        return original(schedule)

    monkeypatch.setattr(Schedule, "get_memory_variables", track)
    Schedule(
        _chain(),
        ListScheduler(((1, True),), max_concurrent_reads=2, max_concurrent_writes=2),
        schedule_time=100,
    )
    assert len(calls) == 1


@pytest.mark.parametrize("scheduler_type", [ListScheduler, RecursiveListScheduler])
def test_scheduler_reuse_on_different_operation_types(scheduler_type):
    scheduler = _scheduler(scheduler_type)
    first = Schedule(_chain(), scheduler)
    first_starts = first.start_times.copy()
    sources = [Input(), Input()]
    op = Addition(*sources, latency=1, execution_time=1)
    second = Schedule(SFG(inputs=sources, outputs=[Output(op)]), scheduler)
    assert "add0" in second.start_times
    assert first.start_times == first_starts
    assert scheduler._max_resources == {}


@pytest.mark.parametrize(
    "scheduler_type",
    [ASAPScheduler, ALAPScheduler, ListScheduler, RecursiveListScheduler],
)
def test_timing_configuration_is_copied(scheduler_type):
    inputs = {"in0": 2}
    outputs = {"out0": 8}
    scheduler = _scheduler(scheduler_type, input_times=inputs, output_times=outputs)
    inputs["in0"] = 99
    outputs["out0"] = 99
    schedule = Schedule(_chain(), scheduler, schedule_time=10)
    assert schedule.start_times["in0"] == 2
    assert schedule.start_times["out0"] == 8


@pytest.mark.parametrize(
    "scheduler_type",
    [ASAPScheduler, ALAPScheduler, ListScheduler, RecursiveListScheduler],
)
@pytest.mark.parametrize("period", [None, 10])
def test_fixed_output_times(scheduler_type, period):
    schedule = Schedule(
        _chain(),
        _scheduler(scheduler_type, output_times={"out0": 8}),
        schedule_time=period,
    )
    assert schedule.start_times["out0"] == 8
    assert schedule.schedule_time == (period or 8)


@pytest.mark.parametrize("scheduler_type", [ListScheduler, RecursiveListScheduler])
@pytest.mark.parametrize("output_time", [0, 2, 5])
def test_fixed_output_phase_after_data_crosses_period(scheduler_type, output_time):
    schedule = Schedule(
        _chain(latency=7),
        _scheduler(scheduler_type, output_times={"out0": output_time}),
        schedule_time=5,
        cyclic=True,
    )
    assert schedule.start_times["out0"] % 5 == output_time % 5
    assert schedule.backward_slack("out0") == (output_time - 7) % 5
    assert all(lap >= 0 for lap in schedule.laps.values())


@pytest.mark.parametrize(
    "scheduler_type",
    [ASAPScheduler, ALAPScheduler, ListScheduler, RecursiveListScheduler],
)
@pytest.mark.filterwarnings(
    "ignore:^Two signals connected to the same output port$:UserWarning"
)
def test_fixed_output_relative_group_crosses_period(scheduler_type):
    source = Input()
    op = ConstantMultiplication(2, source, latency=2, execution_time=1)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op), Output(op)]),
        _scheduler(
            scheduler_type,
            output_times={"out0": 4},
            output_delta_times={"out0": 0, "out1": 3},
        ),
        schedule_time=5,
        cyclic=True,
    )
    assert schedule.start_times["out0"] == 4
    assert schedule.start_times["out1"] == 2
    assert all(lap >= 0 for lap in schedule.laps.values())


@pytest.mark.parametrize(
    "scheduler_type",
    [ASAPScheduler, ALAPScheduler, ListScheduler, RecursiveListScheduler],
)
def test_impossible_fixed_output_time(scheduler_type):
    with pytest.raises(ValueError, match="Cannot place output"):
        Schedule(
            _chain(),
            _scheduler(scheduler_type, output_times={"out0": 1}),
            schedule_time=10,
        )


@pytest.mark.parametrize(
    "scheduler_type",
    [ASAPScheduler, ALAPScheduler, ListScheduler, RecursiveListScheduler],
)
@pytest.mark.filterwarnings(
    "ignore:^Two signals connected to the same output port$:UserWarning"
)
def test_fixed_output_preserves_relative_output_group(scheduler_type):
    source = Input()
    op = ConstantMultiplication(2, source, latency=2, execution_time=1)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op), Output(op)]),
        _scheduler(
            scheduler_type,
            output_times={"out0": 8},
            output_delta_times={"out0": 0, "out1": 2},
        ),
        schedule_time=12,
    )
    assert schedule.start_times["out0"] == 8
    assert schedule.start_times["out1"] == 10


@pytest.mark.parametrize(
    "scheduler_type",
    [ASAPScheduler, ALAPScheduler, ListScheduler, RecursiveListScheduler],
)
@pytest.mark.filterwarnings(
    "ignore:^Two signals connected to the same output port$:UserWarning"
)
def test_conflicting_output_timing_constraints(scheduler_type):
    source = Input()
    op = ConstantMultiplication(2, source, latency=2, execution_time=1)
    with pytest.raises(ValueError, match="conflict"):
        Schedule(
            SFG(inputs=[source], outputs=[Output(op), Output(op)]),
            _scheduler(
                scheduler_type,
                output_times={"out0": 8, "out1": 9},
                output_delta_times={"out0": 0, "out1": 2},
            ),
            schedule_time=12,
        )


def test_idle_scheduler_jumps_to_data_release(monkeypatch):
    original = ListScheduler._get_priority_table
    calls = []

    def track(self, candidate_ids):
        calls.append(self._current_time)
        return original(self, candidate_ids)

    monkeypatch.setattr(ListScheduler, "_get_priority_table", track)
    schedule = Schedule(_chain(latency=10000), ListScheduler(((1, True),)))
    assert schedule.start_times["out0"] == 10000
    assert len(calls) < 10


def test_idle_scheduler_jumps_to_resource_release(monkeypatch):
    original = ListScheduler._get_priority_table
    calls = []

    def track(self, candidate_ids):
        calls.append(self._current_time)
        return original(self, candidate_ids)

    monkeypatch.setattr(ListScheduler, "_get_priority_table", track)
    sources = [Input(), Input()]
    ops = [
        ConstantMultiplication(2, source, latency=1, execution_time=1000)
        for source in sources
    ]
    schedule = Schedule(
        SFG(inputs=sources, outputs=[Output(op) for op in ops]),
        ListScheduler(((1, True),), max_resources={"in": 2, "out": 2}),
    )
    assert sorted(
        schedule.start_times[op.graph_id]
        for op in schedule.sfg.operations
        if isinstance(op, ConstantMultiplication)
    ) == [0, 1000]
    assert len(calls) < 16


@pytest.mark.parametrize("cyclic", [False, True])
def test_impossible_write_limit_fails_without_looping(monkeypatch, cyclic):
    original = ListScheduler._get_priority_table
    calls = 0

    def guard(self, candidate_ids):
        nonlocal calls
        calls += 1
        assert calls < 30, "Scheduling did not detect impossible constraints"
        return original(self, candidate_ids)

    monkeypatch.setattr(ListScheduler, "_get_priority_table", guard)
    sources = [Input(), Input()]
    op = R2Butterfly(*sources, latency=1, execution_time=1)
    with pytest.raises(ValueError, match="cannot satisfy scheduling constraints"):
        Schedule(
            SFG(inputs=sources, outputs=[Output(op.output(0)), Output(op.output(1))]),
            ListScheduler(((1, True),), max_concurrent_writes=1),
            schedule_time=5 if cyclic else None,
            cyclic=cyclic,
        )


def test_unused_memory_priority_is_not_calculated(monkeypatch):
    def unexpected(*args):
        pytest.fail("Unused memory-read priorities were calculated")

    monkeypatch.setattr(ListScheduler, "_calculate_memory_reads", unexpected)
    Schedule(_chain(), ListScheduler(((1, True),)))


def test_descending_graph_id_priority():
    sources = [Input(), Input()]
    ops = [
        ConstantMultiplication(2, source, latency=1, execution_time=1)
        for source in sources
    ]
    schedule = Schedule(
        SFG(inputs=sources, outputs=[Output(op) for op in ops]),
        ListScheduler(((0, False),)),
    )
    assert schedule.start_times["in1"] == 0
    assert schedule.start_times["in0"] == 1


def test_ilp_creates_only_feasible_start_variables(monkeypatch):
    source = Input()
    op = source
    for _ in range(20):
        op = ConstantMultiplication(2, op, latency=1, execution_time=1)
    solve = scheduler_module._solve_ilp_problem
    counts = []

    def inspect(problem, solver, **kwargs):
        starts = [var for var in problem.variables() if var.name.startswith("X_")]
        counts.append(len(starts))
        assert all(var.upBound != 0 for var in starts)
        return solve(problem, solver, **kwargs)

    monkeypatch.setattr(scheduler_module, "_solve_ilp_problem", inspect)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op)]), ILPScheduler(), schedule_time=20
    )
    assert counts == [22]
    assert schedule.start_times["out0"] == 20


@pytest.mark.parametrize("scheduler_type", [ILPScheduler, CPScheduler])
def test_parallel_connections_keep_their_individual_delays(scheduler_type):
    if scheduler_type is CPScheduler:
        pytest.importorskip("cpmpy")
    source = Input()
    op = Addition(source, Delay(source), latency=2, execution_time=1)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        scheduler_type(input_times={"in0": 3}, output_times={"out0": 5}),
        schedule_time=10,
    )
    assert schedule.start_times["add0"] == 3
    assert all(schedule.backward_slack(op_id) >= 0 for op_id in schedule.start_times)


def test_recursive_list_retiming_preserves_fixed_io():
    source = Input()
    op = Addition(source, None, latency=1, execution_time=1)
    op.input(1).connect(Delay(op))
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        RecursiveListScheduler(
            ((1, True),), input_times={"in0": 2}, output_times={"out0": 8}
        ),
    )
    assert schedule.start_times["in0"] == 2
    assert schedule.start_times["out0"] == 8


@pytest.mark.parametrize("scheduler_type", [ILPScheduler, CPScheduler])
def test_optimization_respects_input_port_offset(scheduler_type):
    if scheduler_type is CPScheduler:
        pytest.importorskip("cpmpy")
    source = Input()
    op = ConstantMultiplication(
        2, source, latency_offsets={"in0": 2, "out0": 3}, execution_time=1
    )
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        scheduler_type(input_times={"in0": 4}, output_times={"out0": 5}),
        schedule_time=8,
    )
    assert schedule.start_times["cmul0"] == 2


def test_connection_preprocessing_rejects_delay_only_feedback():
    delay = Delay()
    delay.input(0).connect(delay)
    with pytest.raises(ValueError, match="delay-only feedback loop"):
        _get_connections([Output(delay)])
