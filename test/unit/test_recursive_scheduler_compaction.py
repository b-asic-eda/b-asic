"""I/O compaction shared by the recursive optimizing schedulers."""

import pytest

from b_asic import (
    SFG,
    Addition,
    Constant,
    ConstantMultiplication,
    CPRecursiveScheduler,
    ILPRecursiveScheduler,
    Input,
    Output,
    Schedule,
)


@pytest.fixture(params=[ILPRecursiveScheduler, CPRecursiveScheduler])
def scheduler_type(request):
    if request.param is CPRecursiveScheduler:
        pytest.importorskip("cpmpy")
    return request.param


@pytest.mark.parametrize("cyclic", [False, True])
@pytest.mark.parametrize("input_time", [None, 3])
def test_compact_input_and_output(scheduler_type, cyclic, input_time):
    source = Input()
    first = ConstantMultiplication(2, source, latency=2, execution_time=1)
    second = ConstantMultiplication(3, first, latency=2, execution_time=1)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(second)]),
        scheduler_type(input_times=None if input_time is None else {"in0": input_time}),
        schedule_time=12,
        cyclic=cyclic,
    )
    assert schedule.start_times["in0"] == (input_time or 0)
    assert schedule.forward_slack("in0") == 0
    assert schedule.backward_slack("out0") == 0


@pytest.mark.parametrize("cyclic", [False, True])
def test_multiple_free_inputs_start_at_zero(scheduler_type, cyclic):
    first, second = Input(), Input()
    op = Addition(first, second, latency=2, execution_time=1)
    schedule = Schedule(
        SFG(inputs=[first, second], outputs=[Output(op)]),
        scheduler_type(),
        schedule_time=10,
        cyclic=cyclic,
    )
    assert schedule.start_times["in0"] == schedule.start_times["in1"] == 0
    assert schedule.forward_slack("in0") == 0
    assert schedule.backward_slack("out0") == 0


@pytest.mark.parametrize("cyclic", [False, True])
def test_output_delta_group_and_unspecified_output(scheduler_type, cyclic):
    source = Input()
    first = ConstantMultiplication(2, source, latency=2, execution_time=1)
    second = ConstantMultiplication(3, source, latency=2, execution_time=1)
    third = ConstantMultiplication(4, source, latency=2, execution_time=1)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(first), Output(second), Output(third)]),
        scheduler_type(output_delta_times={"out0": 1, "out1": 4}),
        schedule_time=12,
        cyclic=cyclic,
    )
    assert (schedule.start_times["out1"] - schedule.start_times["out0"]) % 12 == 3
    assert min(schedule.backward_slack("out0"), schedule.backward_slack("out1")) == 0
    assert schedule.backward_slack("out2") == 0


@pytest.mark.parametrize("cyclic", [False, True])
def test_explicit_output_time_bypasses_compaction(scheduler_type, cyclic, monkeypatch):
    source = Input()
    op = ConstantMultiplication(2, source, latency=2, execution_time=1)
    before = {}
    compact = scheduler_type._compact_recursive_io

    def capture(self, schedule, period):
        before.update(schedule.start_times)
        compact(self, schedule, period)
        assert schedule.start_times == before

    monkeypatch.setattr(scheduler_type, "_compact_recursive_io", capture)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        scheduler_type(input_times={"in0": 2}, output_times={"out0": 10}),
        schedule_time=12,
        cyclic=cyclic,
    )
    assert schedule.start_times["in0"] == 2
    assert schedule.start_times["out0"] == 10


def test_rotation_wraps_other_operations_and_preserves_dependencies(scheduler_type):
    source = Input()
    first = ConstantMultiplication(2, source, latency=2, execution_time=1)
    constant = Constant(1)
    second = Addition(first, constant, latency=2, execution_time=1)

    class SeededScheduler(scheduler_type):
        def apply_scheduling(self, schedule):
            self._schedule = schedule
            schedule.start_times.update(in0=2, cmul0=5, c0=0, add0=7, out0=12)
            self._compact_recursive_io(schedule, 16)
            self._finish_cyclic_schedule(schedule, 16, 16)

    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(second)]),
        SeededScheduler(input_times={"in0": 2}),
        schedule_time=16,
        cyclic=True,
    )
    assert schedule.start_times == {
        "in0": 2,
        "cmul0": 2,
        "c0": 13,
        "add0": 4,
        "out0": 6,
    }
    assert schedule.forward_slack("in0") == schedule.backward_slack("out0") == 0
    assert any(schedule.laps.values())


def test_rotation_respects_port_offsets(scheduler_type):
    source = Input()
    first = ConstantMultiplication(2, source, latency=3, execution_time=1)
    second = Addition(
        first,
        Constant(1),
        latency_offsets={"in0": 3, "in1": 0, "out0": 3},
        execution_time=1,
    )

    class SeededScheduler(scheduler_type):
        def apply_scheduling(self, schedule):
            self._schedule = schedule
            schedule.start_times.update(in0=2, cmul0=4, c0=0, add0=4, out0=8)
            self._compact_recursive_io(schedule, 4)
            self._finish_cyclic_schedule(schedule, 4, 8)

    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(second)]),
        SeededScheduler(input_times={"in0": 2}),
        schedule_time=4,
        cyclic=True,
    )
    # Rotating by either one or two cycles would create a negative lap
    # between the multiplier and the adder because of the adder's input offset.
    assert schedule.start_times["cmul0"] == schedule.start_times["add0"] == 0
    assert schedule.backward_slack("out0") == 0
    assert all(lap >= 0 for lap in schedule.laps.values())
