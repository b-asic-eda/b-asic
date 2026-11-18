"""Weighted resource and memory objectives for ILP and CP schedulers."""

import pytest

import b_asic.scheduler as scheduler_module
from b_asic import (
    SFG,
    Addition,
    ConstantMultiplication,
    CPScheduler,
    Delay,
    ILPScheduler,
    Input,
    Output,
    Schedule,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.utility_operations import DontCare, Sink
from test.unit.test_ilp_recursive_schedule import _feedback


def _chain():
    source = Input()
    op = ConstantMultiplication(1, source, latency=1, execution_time=0)
    return SFG(inputs=[source], outputs=[Output(op)])


@pytest.fixture(params=[ILPScheduler, CPScheduler])
def scheduler_type(request):
    if issubclass(request.param, CPScheduler):
        pytest.importorskip("cpmpy")
    return request.param


@pytest.fixture
def solved_models(monkeypatch, scheduler_type):
    models = []
    if issubclass(scheduler_type, CPScheduler):
        from cpmpy.transformations.get_variables import get_variables_model

        solve = scheduler_module._solve_cp_problem

        def capture(model, solver, **kwargs):
            names = {var.name for var in get_variables_model(model)}
            result = solve(model, solver, **kwargs)
            models.append((names, result.objective))
            return result

        monkeypatch.setattr(scheduler_module, "_solve_cp_problem", capture)
    else:
        solve = scheduler_module._solve_ilp_problem

        def capture(model, solver, **kwargs):
            names = {var.name for var in model.variables()}
            result = solve(model, solver, **kwargs)
            models.append((names, result.objective))
            return result

        monkeypatch.setattr(scheduler_module, "_solve_ilp_problem", capture)
    return models


@pytest.mark.parametrize("cyclic", [False, True])
def test_weighted_costs_match_memory_variables(scheduler_type, solved_models, cyclic):
    first, second = Input(), Input()
    first_ready, second_ready = Input(), Input()
    # One value has a direct transfer and a multicast memory read; the other
    # needs a separate read. Both stored values are written at time zero.
    sfg = SFG(
        inputs=[first, second, first_ready, second_ready],
        outputs=[
            Output(Addition(first, first_ready, latency=1, execution_time=0)),
            Output(Addition(first, first_ready, latency=1, execution_time=0)),
            Output(Addition(second, second_ready, latency=1, execution_time=0)),
            Output(ConstantMultiplication(1, first, latency=1, execution_time=0)),
        ],
    )
    schedule = Schedule(
        sfg,
        scheduler_type(
            input_times={
                op.graph_id: time
                for op, time in zip(sfg.input_operations, (0, 0, 2, 3), strict=True)
            },
            output_times={"out0": 3, "out1": 3, "out2": 4, "out3": 1},
            resource_weight=2,
            read_weight=3,
            write_weight=5,
            storage_weight=7,
        ),
        schedule_time=8,
        cyclic=cyclic,
    )
    _, memory = schedule.get_memory_variables().split_on_length()
    assert memory.read_ports_bound() == 1
    assert memory.write_ports_bound() == 2
    assert max(memory.total_execution_times().values()) == 2
    resources = sum(
        max(
            schedule.get_operations()
            .get_by_type_name(name)
            .total_execution_times()
            .values(),
            default=0,
        )
        for name in ("in", "out", "cmul", "add")
    )
    assert solved_models[0][1] == 2 * resources + 3 * 1 + 5 * 2 + 7 * 2


@pytest.mark.parametrize("weight", ["read_weight", "write_weight", "storage_weight"])
@pytest.mark.parametrize("cyclic", [False, True])
def test_memory_weights_change_the_optimum(
    scheduler_type, solved_models, weight, cyclic
):
    inputs = [Input(), Input()]
    ops = [
        ConstantMultiplication(1, source, latency=1, execution_time=0)
        for source in inputs
    ]
    schedule = Schedule(
        SFG(inputs=inputs, outputs=[Output(op) for op in ops]),
        scheduler_type(input_times={"in0": 0, "in1": 0}, **{weight: 10}),
        schedule_time=4,
        cyclic=cyclic,
    )
    # Sharing one output resource would require storing a value. The memory
    # penalty instead makes two simultaneous direct transfers optimal.
    assert schedule.start_times["out0"] == schedule.start_times["out1"] == 1
    assert solved_models[0][1] == 4


@pytest.mark.parametrize("delays", [1, 2, 3])
def test_cyclic_storage_counts_overlapping_values(
    scheduler_type, solved_models, delays
):
    source = Input()
    delayed = ConstantMultiplication(1, source, latency=1, execution_time=0)
    for _ in range(delays):
        delayed = Delay(delayed)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(delayed)]),
        scheduler_type(
            input_times={"in0": 2},
            output_times={"out0": 1},
            resource_weight=0,
            read_weight=3,
            write_weight=5,
            storage_weight=7,
        ),
        schedule_time=4,
        cyclic=True,
    )
    _, memory = schedule.get_memory_variables().split_on_length()
    assert max(memory.total_execution_times().values()) == delays
    assert solved_models[0][1] == 3 + 5 + 7 * delays


@pytest.mark.parametrize("enabled", [None, "resource", "read", "write", "storage"])
def test_zero_weights_omit_model_variables(scheduler_type, solved_models, enabled):
    weights = {
        f"{name}_weight": int(name == enabled)
        for name in ("resource", "read", "write", "storage")
    }
    Schedule(
        _chain(),
        scheduler_type(input_times={"in0": 0}, output_times={"out0": 2}, **weights),
        schedule_time=4,
    )
    names, objective = solved_models[0]
    for name, prefixes in (
        ("resource", ("R_used_", "resources_")),
        ("read", ("peak_reads", "memory_read_")),
        ("write", ("peak_writes", "memory_write_")),
        ("storage", ("total_storage", "memory_live_")),
    ):
        assert any(var.startswith(prefixes) for var in names) == (name == enabled)
    if enabled is None and issubclass(scheduler_type, CPScheduler):
        assert objective is None
    else:
        assert objective == {None: 0, "resource": 2}.get(enabled, 1)


def test_default_weights_skip_memory_model(scheduler_type, solved_models, monkeypatch):
    def unexpected_memory_groups(*args):
        pytest.fail("Disabled memory objectives must not build a memory model")

    monkeypatch.setattr(scheduler_type, "_memory_groups", unexpected_memory_groups)
    Schedule(
        _chain(),
        scheduler_type(),
        schedule_time=4,
    )
    assert solved_models[0][1] == 2


@pytest.mark.parametrize("weight", ["resource", "read", "write", "storage"])
@pytest.mark.parametrize("value", [-1, float("inf"), float("nan"), "1", None])
def test_invalid_weights(scheduler_type, weight, value):
    with pytest.raises(
        ValueError, match=f"{weight}_weight must be a finite non-negative"
    ):
        scheduler_type(**{f"{weight}_weight": value})


def test_fractional_weights(scheduler_type, solved_models):
    Schedule(
        _chain(),
        scheduler_type(
            input_times={"in0": 0},
            output_times={"out0": 2},
            resource_weight=0.5,
            read_weight=1.5,
            write_weight=0.25,
            storage_weight=0.75,
        ),
        schedule_time=4,
    )
    # CP scales the whole objective to integer coefficients, preserving ratios.
    scale = 4 if issubclass(scheduler_type, CPScheduler) else 1
    assert solved_models[0][1] == (0.5 * 2 + 1.5 + 0.25 + 0.75) * scale


def test_zero_latency_placement_can_reduce_storage(scheduler_type, solved_models):
    source = Input()
    ops = [
        ConstantMultiplication(value, source, latency=0, execution_time=0)
        for value in (1, 2)
    ]
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op) for op in ops]),
        scheduler_type(
            input_times={"in0": 0},
            output_times={"out0": 3, "out1": 3},
            resource_weight=0,
            read_weight=1,
            write_weight=10,
            storage_weight=1,
        ),
        schedule_time=4,
    )
    assert solved_models[0][1] == 12
    _, memory = schedule.get_memory_variables().split_on_length()
    assert len(memory) == 1
    assert schedule.start_times["cmul0"] == schedule.start_times["cmul1"] == 3


@pytest.mark.parametrize("cyclic", [False, True])
def test_offsets_and_output_ports_are_modeled_separately(
    scheduler_type, solved_models, cyclic
):
    first, second = Input(), Input()
    op = R2Butterfly(
        first,
        second,
        execution_time=1,
        latency_offsets={"in0": 2, "in1": 1, "out0": 3, "out1": 4},
    )
    schedule = Schedule(
        SFG(
            inputs=[first, second], outputs=[Output(op.output(0)), Output(op.output(1))]
        ),
        scheduler_type(
            input_times={"in0": 4, "in1": 3},
            output_times={"out0": 5, "out1": 6},
            resource_weight=0,
            read_weight=1,
            write_weight=1,
            storage_weight=1,
        ),
        schedule_time=8,
        cyclic=cyclic,
    )
    assert schedule.start_times["r2bfly0"] == 2
    assert solved_models[0][1] == 0


def test_utility_connections_do_not_require_memory(scheduler_type, solved_models):
    source = Input()
    op = Addition(source, DontCare(), latency=1, execution_time=1)
    sink = Sink()
    sink.input(0).connect(op)
    Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        scheduler_type(
            input_times={"in0": 0},
            output_times={"out0": 1},
            resource_weight=0,
            read_weight=1,
            write_weight=1,
            storage_weight=1,
        ),
        schedule_time=4,
    )
    assert solved_models[0][1] == 0


@pytest.mark.parametrize(("output_time", "cost"), [(1, 3), (2, 0)])
def test_memory_costs_survive_folding_a_long_horizon(
    scheduler_type, solved_models, output_time, cost
):
    source = Input()
    op = ConstantMultiplication(1, source, latency=5, execution_time=1)
    schedule = Schedule(
        SFG(inputs=[source], outputs=[Output(op)]),
        scheduler_type(
            input_times={"in0": 0},
            output_times={"out0": output_time},
            max_time=8,
            resource_weight=0,
            read_weight=1,
            write_weight=1,
            storage_weight=1,
        ),
        schedule_time=3,
        cyclic=True,
    )
    _, memory = schedule.get_memory_variables().split_on_length()
    actual_cost = (
        memory.read_ports_bound()
        + memory.write_ports_bound()
        + max(memory.total_execution_times().values(), default=0)
    )
    assert actual_cost == cost
    assert solved_models[0][1] == cost


def test_memory_costs_for_detected_feedback(scheduler_type, solved_models):
    graph = _feedback(latency=1, delays=2)
    assert graph.is_recursive
    schedule = Schedule(
        graph,
        scheduler_type(
            input_times={"in0": 0},
            output_times={"out0": 1},
            resource_weight=0,
            read_weight=3,
            write_weight=5,
            storage_weight=7,
        ),
        schedule_time=3,
        cyclic=True,
    )
    _, memory = schedule.get_memory_variables().split_on_length()
    assert memory.read_ports_bound() == 1
    assert memory.write_ports_bound() == 1
    assert max(memory.total_execution_times().values()) == 2
    assert solved_models[0][1] == 3 + 5 + 7 * 2
