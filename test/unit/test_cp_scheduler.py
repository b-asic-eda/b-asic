import pytest

from b_asic import SFG, Addition, ConstantMultiplication, Delay, Input, Output
from b_asic.schedule import Schedule
from b_asic.scheduler import CPScheduler
from b_asic.sfg_generators import direct_form_1_iir
from b_asic.utility_operations import DontCare, Sink

cp = pytest.importorskip("cpmpy")


def _chain(latency=2, execution_time=1):
    source = Input()
    op = ConstantMultiplication(
        2, source, latency=latency, execution_time=execution_time
    )
    return SFG(inputs=[source], outputs=[Output(op)])


def test_empty_sfg(sfg_empty):
    with pytest.raises(ValueError, match="Empty signal flow graph"):
        Schedule(sfg_empty, CPScheduler())


@pytest.mark.parametrize("period", [11, 50])
def test_direct_form_1_iir(period):
    sfg = direct_form_1_iir([0.1, 0.2, 0.3], [1, 2, 3])
    sfg.set_latency_of_type(ConstantMultiplication, 2)
    sfg.set_latency_of_type(Addition, 3)
    sfg.set_execution_time_of_type(ConstantMultiplication, 1)
    sfg.set_execution_time_of_type(Addition, 1)
    schedule = Schedule(sfg, CPScheduler(), schedule_time=period)
    assert schedule.schedule_time == period
    if period == 50:
        operations = schedule.get_operations()
        for name in ("add", "cmul", "in", "out"):
            assert operations.get_by_type_name(name).processing_element_bound() == 1


def test_inferred_schedule_time():
    schedule = Schedule(_chain(), CPScheduler())
    assert schedule.schedule_time == 2


@pytest.mark.parametrize("solver", ["ortools", "instance"])
def test_fixed_io_times(solver):
    if solver == "instance":
        solver = cp.SolverLookup.get("ortools")
        solver.ort_solver.parameters.num_search_workers = 1
    schedule = Schedule(
        _chain(),
        CPScheduler(solver=solver, input_times={"in0": 2}, output_times={"out0": 8}),
        schedule_time=10,
    )
    assert schedule.start_times["in0"] == 2
    assert schedule.start_times["out0"] == 8
    if not isinstance(solver, str):
        assert solver.ort_solver.parameters.num_search_workers == 1


def test_infeasible_io_times():
    with pytest.raises(ValueError, match="Solution could not be found via CP"):
        Schedule(
            _chain(),
            CPScheduler(input_times={"in0": 2}, output_times={"out0": 1}),
            schedule_time=10,
        )


def test_short_schedule_time():
    with pytest.raises(ValueError, match="Shortest possible schedule time"):
        Schedule(_chain(), CPScheduler(), schedule_time=1)


def test_output_delta_times():
    source = Input()
    op = ConstantMultiplication(2, source, latency=2, execution_time=1)
    other = ConstantMultiplication(3, source, latency=2, execution_time=1)
    sfg = SFG(inputs=[source], outputs=[Output(op), Output(other)])
    schedule = Schedule(
        sfg,
        CPScheduler(output_delta_times={"out0": 0, "out1": 2}),
        schedule_time=10,
    )
    assert schedule.start_times["out1"] - schedule.start_times["out0"] == 2


def test_latency_offsets():
    source = Input()
    op = ConstantMultiplication(
        2,
        source,
        latency_offsets={"in0": 2, "out0": 3},
        execution_time=1,
    )
    sfg = SFG(inputs=[source], outputs=[Output(op)])
    schedule = Schedule(
        sfg,
        CPScheduler(input_times={"in0": 4}, output_times={"out0": 5}),
        schedule_time=8,
    )
    assert schedule.start_times["cmul0"] == 2


def test_cyclic_horizon():
    schedule = Schedule(
        _chain(latency=5),
        CPScheduler(input_times={"in0": 0}, output_times={"out0": 2}, max_time=8),
        schedule_time=3,
        cyclic=True,
    )
    assert schedule.schedule_time == 3
    assert schedule.start_times["out0"] == 2
    assert all(lap >= 0 for lap in schedule.laps.values())


def test_recursive_dependencies(sfg_direct_form_iir_lp_filter):
    sfg = sfg_direct_form_iir_lp_filter
    sfg.set_latency_of_type(Addition, 2)
    sfg.set_latency_of_type(ConstantMultiplication, 3)
    sfg.set_execution_time_of_type(Addition, 1)
    sfg.set_execution_time_of_type(ConstantMultiplication, 1)
    schedule = Schedule(sfg, CPScheduler(), schedule_time=15, cyclic=True)
    assert not schedule._sfg.find_by_type(Delay)
    assert any(schedule.laps.values())


@pytest.mark.parametrize(
    ("execution_time", "expected_resources"), [(0, 0), (2, 1), (7, 3)]
)
def test_cyclic_resource_usage(execution_time, expected_resources):
    solver = cp.SolverLookup.get("ortools")
    Schedule(
        _chain(latency=1, execution_time=execution_time),
        CPScheduler(solver=solver, input_times={"in0": 0}),
        schedule_time=3,
        cyclic=True,
    )
    # The input and output each need one resource in addition to the multiplier.
    assert solver.objective_value() == expected_resources + 2


@pytest.mark.parametrize(("duration", "resources"), [(2, 1), (3, 2)])
def test_cyclic_execution_wraps(duration, resources):
    source = Input()
    first = ConstantMultiplication(2, source, latency=1, execution_time=duration)
    second = ConstantMultiplication(3, source, latency=1, execution_time=duration)
    sfg = SFG(inputs=[source], outputs=[Output(first), Output(second)])
    solver = cp.SolverLookup.get("ortools")
    schedule = Schedule(
        sfg,
        CPScheduler(
            solver=solver,
            input_times={"in0": 0},
            output_times={"out0": 3, "out1": 1},
        ),
        schedule_time=4,
        cyclic=True,
    )
    assert (
        schedule.get_operations().get_by_type_name("cmul").processing_element_bound()
        == resources
    )
    assert solver.objective_value() == resources + 2


@pytest.mark.parametrize("cyclic", [False, True])
def test_utility_operations(cyclic):
    source = Input()
    op = Addition(source, DontCare(), latency=2, execution_time=1)
    sink = Sink()
    sink.input(0).connect(op)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        CPScheduler(),
        schedule_time=8,
        cyclic=cyclic,
    )
    assert {"dontcare0", "sink0"} <= schedule.start_times.keys()
    assert all(value >= 0 for value in schedule.laps.values())


def test_parallel_edges_with_different_delays():
    source = Input()
    op = Addition(source, Delay(source), latency=2, execution_time=1)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        CPScheduler(input_times={"in0": 3}, output_times={"out0": 5}),
        schedule_time=8,
        cyclic=True,
    )
    assert schedule.start_times["add0"] == 3
    assert sorted(
        schedule.laps[port.signals[0].graph_id]
        for port in schedule._sfg.find_by_id("add0").inputs
    ) == [0, 1]


def test_output_at_period_boundary():
    schedule = Schedule(
        _chain(),
        CPScheduler(output_times={"out0": 4}),
        schedule_time=4,
        cyclic=True,
    )
    assert schedule.start_times["out0"] == 4


def test_missing_cp_dependency(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def without_cpmpy(name, *args, **kwargs):
        if name == "cpmpy":
            raise ImportError("CPMpy unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_cpmpy)
    with pytest.raises(ImportError, match=r"install b-asic\[cp\]"):
        Schedule(_chain(), CPScheduler(), schedule_time=5)


@pytest.mark.parametrize("max_time", [0, -1, 1.5])
def test_invalid_max_time(max_time):
    with pytest.raises(ValueError, match="max_time must be a positive integer"):
        CPScheduler(max_time=max_time)


def test_invalid_solver():
    with pytest.raises(TypeError, match="CPMpy solver name or instance"):
        Schedule(_chain(), CPScheduler(solver=object()), schedule_time=5)
