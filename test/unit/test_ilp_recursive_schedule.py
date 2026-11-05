"""Feedback and cyclic resource constraints for the recursive ILP scheduler."""

import pytest

from b_asic import (
    SFG,
    Addition,
    ConstantMultiplication,
    Delay,
    ILPRecursiveScheduler,
    ILPScheduler,
    Input,
    Output,
    Schedule,
)


def _feedback(latency=2, delays=1):
    source = Input()
    state = Delay()
    feedback = state
    for _ in range(delays - 1):
        feedback = Delay(feedback)
    op = Addition(source, feedback, latency=latency, execution_time=1)
    state.input(0).connect(op)
    return SFG(inputs=[source], outputs=[Output(op)])


def test_public_scheduler():
    assert isinstance(ILPRecursiveScheduler(), ILPScheduler)


@pytest.mark.parametrize("cyclic", [False, True])
def test_recursive_dependencies(sfg_direct_form_iir_lp_filter, cyclic):
    sfg = sfg_direct_form_iir_lp_filter
    sfg.set_latency_of_type(Addition, 2)
    sfg.set_latency_of_type(ConstantMultiplication, 3)
    sfg.set_execution_time_of_type(Addition, 1)
    sfg.set_execution_time_of_type(ConstantMultiplication, 1)
    schedule = Schedule(sfg, ILPRecursiveScheduler(), schedule_time=15, cyclic=cyclic)
    assert schedule.schedule_time == 15
    assert not schedule._sfg.find_by_type(Delay)
    assert any(schedule.laps.values())


def test_feedback_period_below_asap_length():
    # Four units of loop latency, two delays: period two is feasible even
    # though a single iteration's ASAP schedule takes four units.
    schedule = Schedule(
        _feedback(latency=4, delays=2),
        ILPRecursiveScheduler(max_time=4, input_times={"in0": 0}),
        schedule_time=2,
        cyclic=True,
    )
    assert schedule.schedule_time == 2
    assert all(lap >= 0 for lap in schedule.laps.values())


@pytest.mark.parametrize("cyclic", [False, True])
@pytest.mark.parametrize(("latency", "delays", "bound"), [(3, 1, "3"), (5, 2, "5/2")])
def test_infeasible_feedback_period(monkeypatch, cyclic, latency, delays, bound):
    import b_asic.scheduler as scheduler_module

    def unexpected_model(*args, **kwargs):
        pytest.fail("An infeasible period must be rejected before model construction")

    monkeypatch.setattr(scheduler_module.pulp, "LpProblem", unexpected_model)
    with pytest.raises(ValueError, match=f"iteration period bound: {bound}"):
        Schedule(
            _feedback(latency=latency, delays=delays),
            ILPRecursiveScheduler(),
            schedule_time=2,
            cyclic=cyclic,
        )


def test_parallel_connections_retain_delay_counts():
    source = Input()
    op = Addition(source, Delay(source), latency=2, execution_time=1)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        ILPRecursiveScheduler(input_times={"in0": 3}, output_times={"out0": 5}),
        schedule_time=8,
        cyclic=True,
    )
    assert schedule.start_times["add0"] == 3
    assert sorted(
        schedule.laps[port.signals[0].graph_id]
        for port in schedule._sfg.find_by_id("add0").inputs
    ) == [0, 1]


@pytest.mark.parametrize(("execution_time", "resources"), [(0, 0), (2, 1), (7, 3)])
def test_resource_occupancy(monkeypatch, execution_time, resources):
    import b_asic.scheduler as scheduler_module

    solve = scheduler_module._solve_ilp_problem
    objectives = []

    def capture(problem, solver):
        stats = solve(problem, solver)
        objectives.append(stats.objective)
        return stats

    monkeypatch.setattr(scheduler_module, "_solve_ilp_problem", capture)
    source = Input()
    op = ConstantMultiplication(2, source, latency=1, execution_time=execution_time)
    Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        ILPRecursiveScheduler(),
        schedule_time=3,
        cyclic=True,
    )
    assert objectives == [resources + 2]


def test_relative_output_times():
    source = Input()
    op = ConstantMultiplication(2, source, latency=2, execution_time=1)
    other = ConstantMultiplication(3, source, latency=2, execution_time=1)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op), Output(other)]),
        ILPRecursiveScheduler(output_delta_times={"out0": 0, "out1": 2}),
        schedule_time=8,
    )
    assert schedule.start_times["out1"] - schedule.start_times["out0"] == 2


def test_input_latency_offsets():
    source = Input()
    state = Delay()
    op = Addition(
        source,
        state,
        latency_offsets={"in0": 2, "in1": 1, "out0": 3},
        execution_time=1,
    )
    state.input(0).connect(op)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        ILPRecursiveScheduler(input_times={"in0": 2}, output_times={"out0": 3}),
        schedule_time=4,
        cyclic=True,
    )
    assert schedule.start_times["add0"] == 0


@pytest.mark.parametrize("cyclic", [False, True])
def test_utility_operations(cyclic):
    from b_asic.utility_operations import DontCare, Sink

    source = Input()
    op = Addition(source, DontCare(), latency=2, execution_time=1)
    sink = Sink()
    sink.input(0).connect(op)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        ILPRecursiveScheduler(),
        schedule_time=8,
        cyclic=cyclic,
    )
    assert {"dontcare0", "sink0"} <= schedule.start_times.keys()


def test_output_at_period_boundary():
    schedule = Schedule(
        _feedback(),
        ILPRecursiveScheduler(output_times={"out0": 4}),
        schedule_time=4,
        cyclic=True,
    )
    assert schedule.start_times["out0"] == 4


def test_default_period():
    schedule = Schedule(_feedback(), ILPRecursiveScheduler())
    assert schedule.schedule_time == 2


def test_empty_sfg(sfg_empty):
    with pytest.raises(ValueError, match="Empty signal flow graph"):
        Schedule(sfg_empty, ILPRecursiveScheduler())


@pytest.mark.parametrize("period", [0, -1, 1.5])
def test_invalid_period(period):
    with pytest.raises(ValueError, match="positive schedule time"):
        Schedule(_feedback(), ILPRecursiveScheduler(), schedule_time=period)


@pytest.mark.parametrize("horizon", [0, -1, 1.5])
def test_invalid_horizon(horizon):
    with pytest.raises(ValueError, match="max_time must be a positive integer"):
        Schedule(_feedback(), ILPRecursiveScheduler(max_time=horizon), cyclic=True)
