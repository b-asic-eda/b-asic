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


@pytest.mark.parametrize("execution_time", [0, 1, 11])
@pytest.mark.parametrize("cyclic", [False, True])
@pytest.mark.parametrize("complete", [False, True])
@pytest.mark.parametrize(
    "timing_kind", ["input_times", "output_times", "output_delta_times"]
)
def test_io_resource_bounds(monkeypatch, execution_time, cyclic, complete, timing_kind):
    inputs = [Input() for _ in range(3)]
    ops = [
        ConstantMultiplication(value, source, latency=1, execution_time=1)
        for value, source in enumerate(inputs, start=2)
    ]
    sfg = SFG(inputs=inputs, outputs=[Output(op) for op in ops])
    io_type = Input if timing_kind == "input_times" else Output
    prefix = "in" if io_type is Input else "out"
    sfg.set_execution_time_of_type(io_type, execution_time)
    first_time = 5 if timing_kind == "output_times" else 0
    timings = {f"{prefix}0": first_time, f"{prefix}1": first_time}
    if complete:
        timings[f"{prefix}2"] = first_time + 1
    bounds = []
    intvar = cp.intvar

    def capture_capacity(*args, **kwargs):
        var = intvar(*args, **kwargs)
        if kwargs.get("name") == f"resources_{prefix}":
            bounds.append((var.lb, var.ub))
        return var

    monkeypatch.setattr(cp, "intvar", capture_capacity)
    Schedule(
        sfg,
        CPScheduler(**{timing_kind: timings}),
        schedule_time=10,
        cyclic=cyclic,
    )
    occupancy = {}
    for start in timings.values():
        for offset in range(execution_time):
            time = (start + offset) % 10 if cyclic else start + offset
            occupancy[time] = occupancy.get(time, 0) + 1
    required = max(occupancy.values(), default=0)
    assert bounds[0][0] == required
    if complete:
        assert bounds[0][1] == required


@pytest.mark.parametrize("solver_kind", ["ortools", "instance"])
@pytest.mark.parametrize("cyclic", [False, True])
@pytest.mark.parametrize("fixed_output_time", [None, 3])
def test_feasible_warm_start(monkeypatch, solver_kind, cyclic, fixed_output_time):
    source = Input()
    ops = [
        ConstantMultiplication(value, source, latency=1, execution_time=7)
        for value in (2, 3)
    ]
    sfg = SFG(inputs=[source], outputs=[Output(op) for op in ops])
    solver = cp.SolverLookup.get("ortools")
    hints = []
    solution_hint = type(solver).solution_hint

    def capture_hint(instance, variables, values):
        hints.append(
            {var.name: value for var, value in zip(variables, values, strict=True)}
        )
        assert all(var.value() is None for var in variables)
        solution_hint(instance, variables, values)

    monkeypatch.setattr(type(solver), "solution_hint", capture_hint)
    schedule = Schedule(
        sfg,
        CPScheduler(
            solver=solver if solver_kind == "instance" else "ortools",
            input_times={"in0": 0},
            output_delta_times={"out0": 0, "out1": 1},
            output_times={"out0": fixed_output_time}
            if fixed_output_time is not None
            else None,
        ),
        schedule_time=5,
        cyclic=cyclic,
    )
    assert len(hints) == int(fixed_output_time is None)
    if hints:
        assert hints[0]["resources_cmul"] == (4 if cyclic else 2)
        assert hints[0]["output_base"] == (1 if cyclic else 4)
    if fixed_output_time is not None:
        assert schedule.start_times["out0"] == fixed_output_time


def test_warm_start_preserves_unspecified_output_spacing(monkeypatch):
    source = Input()
    ops = [
        ConstantMultiplication(value, source, latency=latency, execution_time=1)
        for value, latency in ((2, 3), (3, 3), (4, 1))
    ]
    solver = cp.SolverLookup.get("ortools")
    hints = []
    solution_hint = solver.solution_hint

    def capture_hint(variables, values):
        hints.append(
            {var.name: value for var, value in zip(variables, values, strict=True)}
        )
        solution_hint(variables, values)

    monkeypatch.setattr(solver, "solution_hint", capture_hint)
    Schedule(
        SFG(inputs=[source], outputs=[Output(op) for op in ops]),
        CPScheduler(
            solver=solver,
            input_times={"in0": 0},
            output_delta_times={"out0": 0, "out1": 1},
        ),
        schedule_time=10,
    )
    assert len(hints) == 1
    assert hints[0]["output_base"] == 9
    assert hints[0]["out2"] == 7
    assert hints[0]["resources_out"] == 1


def test_solver_without_solution_hints(monkeypatch):
    from cpmpy.exceptions import NotSupportedError

    solver = cp.SolverLookup.get("ortools")
    attempts = []

    def unsupported_hint(variables, values):
        attempts.append(True)
        raise NotSupportedError("Solution hints unavailable")

    monkeypatch.setattr(solver, "solution_hint", unsupported_hint)
    schedule = Schedule(_chain(), CPScheduler(solver=solver), schedule_time=5)
    assert attempts == [True]
    assert schedule.schedule_time == 5


@pytest.mark.parametrize(("period", "resources"), [(3, 2), (10, 1)])
def test_relative_outputs_allow_resource_sharing(period, resources):
    source = Input()
    ops = [
        ConstantMultiplication(value, source, latency=2, execution_time=1)
        for value in range(2, 6)
    ]
    deltas = {"out0": 0, "out1": 0, "out2": 1, "out3": 1}
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op) for op in ops]),
        CPScheduler(input_times={"in0": 0}, output_delta_times=deltas),
        schedule_time=period,
    )
    origin = schedule.start_times["out0"]
    assert {key: schedule.start_times[key] - origin for key in deltas} == deltas
    assert (
        schedule.get_operations().get_by_type_name("cmul").processing_element_bound()
        == resources
    )


@pytest.mark.parametrize("period", [5, 60])
def test_fold_schedule_crossing_period(period):
    source = Input()
    first = ConstantMultiplication(2, source, latency=2, execution_time=1)
    second = ConstantMultiplication(3, first, latency=1, execution_time=1)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(second)]),
        CPScheduler(
            input_times={"in0": period - 1},
            output_times={"out0": 2},
            output_delta_times={"out0": 0},
            max_time=2 * period,
        ),
        schedule_time=period,
        cyclic=True,
    )
    assert schedule.start_times == {
        "in0": period - 1,
        "cmul0": period - 1,
        "cmul1": 1,
        "out0": 2,
    }
    assert all(lap == 0 for lap in schedule.laps.values())
    for graph_id in schedule.start_times:
        assert schedule.backward_slack(graph_id) >= 0
        assert schedule.forward_slack(graph_id) >= 0


@pytest.mark.parametrize("scheduler_kind", ["cp", "ilp"])
@pytest.mark.parametrize("cyclic", [False, True])
@pytest.mark.parametrize(
    ("execution_time", "cyclic_resources", "noncyclic_resources"),
    [(0, 0, 0), (1, 1, 1), (2, 1, 1), (3, 2, 2), (10, 3, 2), (17, 5, 2)],
)
def test_resource_usage_covers_whole_execution(
    monkeypatch,
    scheduler_kind,
    cyclic,
    execution_time,
    cyclic_resources,
    noncyclic_resources,
):
    import pulp

    import b_asic.scheduler as scheduler_module

    inputs = [Input(), Input()]
    ops = [
        ConstantMultiplication(2, source, latency=1, execution_time=execution_time)
        for source in inputs
    ]
    sfg = SFG(inputs=inputs, outputs=[Output(op) for op in ops])
    timings = {
        "input_times": {"in0": 1, "in1": 3},
        "output_times": {"out0": 2, "out1": 4},
    }
    capacities = []
    if scheduler_kind == "cp":
        solver = cp.SolverLookup.get("ortools")
        scheduler = CPScheduler(solver=solver, **timings)
    else:
        solve = scheduler_module._solve_ilp_problem

        def capture_capacity(problem, solver, **kwargs):
            result = solve(problem, solver, **kwargs)
            capacities.append(pulp.value(problem.variablesDict()["R_used_cmul"]))
            return result

        monkeypatch.setattr(scheduler_module, "_solve_ilp_problem", capture_capacity)
        scheduler = scheduler_module.ILPScheduler(**timings)
    schedule = Schedule(sfg, scheduler, schedule_time=8, cyclic=cyclic)
    assert [schedule.start_times[f"cmul{i}"] for i in range(2)] == [1, 3]
    # Starts never coincide. Duration 2 just touches; duration 3 overlaps.
    # Durations 10 and 17 additionally overlap successive cyclic iterations.
    expected = cyclic_resources if cyclic else noncyclic_resources
    if scheduler_kind == "cp":
        # Distinct input and output times each require one additional resource.
        assert solver.objective_value() == expected + 2
    else:
        assert capacities == [expected]
