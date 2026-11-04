"""Recursive CP scheduling, including periods below the ASAP schedule length."""

import pytest

from b_asic import (
    SFG,
    Addition,
    ConstantMultiplication,
    CPRecursiveScheduler,
    CPScheduler,
    Delay,
    Input,
    Output,
    Schedule,
)
from test.unit.test_ilp_recursive_schedule import _feedback

cp = pytest.importorskip("cpmpy")


def test_public_scheduler():
    assert isinstance(CPRecursiveScheduler(), CPScheduler)


@pytest.mark.parametrize("cyclic", [False, True])
def test_recursive_dependencies(sfg_direct_form_iir_lp_filter, cyclic):
    sfg = sfg_direct_form_iir_lp_filter
    sfg.set_latency_of_type(Addition, 2)
    sfg.set_latency_of_type(ConstantMultiplication, 3)
    sfg.set_execution_time_of_type(Addition, 1)
    sfg.set_execution_time_of_type(ConstantMultiplication, 1)
    schedule = Schedule(sfg, CPRecursiveScheduler(), schedule_time=15, cyclic=cyclic)
    assert not schedule._sfg.find_by_type(Delay)
    assert any(schedule.laps.values())


def test_period_below_asap_length():
    schedule = Schedule(
        _feedback(latency=4, delays=2),
        CPRecursiveScheduler(max_time=4, input_times={"in0": 0}),
        schedule_time=2,
        cyclic=True,
    )
    assert schedule.schedule_time == 2
    assert all(lap >= 0 for lap in schedule.laps.values())


@pytest.mark.parametrize("cyclic", [False, True])
@pytest.mark.parametrize(("latency", "delays", "bound"), [(3, 1, "3"), (5, 2, "5/2")])
def test_infeasible_feedback(monkeypatch, cyclic, latency, delays, bound):
    def unexpected_model(*args, **kwargs):
        pytest.fail("An infeasible period must be rejected before model construction")

    monkeypatch.setattr(cp, "Model", unexpected_model)
    with pytest.raises(ValueError, match=f"iteration period bound: {bound}"):
        Schedule(
            _feedback(latency=latency, delays=delays),
            CPRecursiveScheduler(),
            schedule_time=2,
            cyclic=cyclic,
        )


def test_parallel_connections_and_offsets():
    source = Input()
    op = Addition(
        source,
        Delay(source),
        latency_offsets={"in0": 2, "in1": 1, "out0": 3},
        execution_time=1,
    )
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        CPRecursiveScheduler(input_times={"in0": 2}, output_times={"out0": 3}),
        schedule_time=4,
        cyclic=True,
    )
    assert schedule.start_times["add0"] == 0
    assert sorted(
        schedule.laps[port.signals[0].graph_id]
        for port in schedule._sfg.find_by_id("add0").inputs
    ) == [0, 1]


@pytest.mark.parametrize(("duration", "resources"), [(0, 0), (2, 1), (7, 3)])
def test_resource_occupancy(duration, resources):
    source = Input()
    op = ConstantMultiplication(2, source, latency=1, execution_time=duration)
    solver = cp.SolverLookup.get("ortools")
    Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        CPRecursiveScheduler(solver=solver),
        schedule_time=3,
        cyclic=True,
    )
    assert solver.objective_value() == resources + 2


def test_relative_output_times_and_solver_options():
    source = Input()
    first = ConstantMultiplication(2, source, latency=2, execution_time=1)
    second = ConstantMultiplication(3, source, latency=2, execution_time=1)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(first), Output(second)]),
        CPRecursiveScheduler(
            output_delta_times={"out0": 0, "out1": 2},
            time_limit=10,
            num_search_workers=1,
        ),
        schedule_time=8,
    )
    assert schedule.start_times["out1"] - schedule.start_times["out0"] == 2


def test_output_boundary():
    schedule = Schedule(
        _feedback(),
        CPRecursiveScheduler(output_times={"out0": 4}),
        schedule_time=4,
        cyclic=True,
    )
    assert schedule.start_times["out0"] == 4


def test_default_period():
    assert Schedule(_feedback(), CPRecursiveScheduler()).schedule_time == 2


def test_empty_sfg(sfg_empty):
    with pytest.raises(ValueError, match="Empty signal flow graph"):
        Schedule(sfg_empty, CPRecursiveScheduler())


@pytest.mark.parametrize("period", [0, -1, 1.5])
def test_invalid_period(period):
    with pytest.raises(ValueError, match="positive schedule time"):
        Schedule(_feedback(), CPRecursiveScheduler(), schedule_time=period)


@pytest.mark.parametrize("horizon", [0, -1, 1.5])
def test_invalid_horizon(horizon):
    with pytest.raises(ValueError, match="max_time must be a positive integer"):
        CPRecursiveScheduler(max_time=horizon)


def test_noncyclic_horizon():
    with pytest.raises(ValueError, match="only supported for cyclic scheduling"):
        Schedule(_feedback(), CPRecursiveScheduler(max_time=8), schedule_time=4)
