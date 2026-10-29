"""CP mux assignment tests, including physical interconnect costs."""

import pytest

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.process import MemoryVariable, OperatorProcess
from b_asic.resource_assigner import (
    _cp_min_mux,
    _get_assignment_from_coloring,
    assign_processing_elements_and_memories,
)
from b_asic.resources import ProcessCollection
from b_asic.special_operations import Input, Output


@pytest.fixture
def cp_solver():
    """Skip CP cases if CPMpy or its default native solver cannot be imported."""
    pytest.importorskip("cpmpy", exc_type=ImportError)
    pytest.importorskip("ortools.sat.python.cp_model", exc_type=ImportError)
    return "ortools"


def _problem(read_times=(1, 2)):
    sources = [Input(), Input()]
    outputs = [Output(source) for source in sources]
    for idx, (source, output) in enumerate(zip(sources, outputs, strict=True)):
        source.graph_id = f"in{idx}"
        output.graph_id = f"out{idx}"
    groups = {
        "in": ProcessCollection(
            [OperatorProcess(t, op) for t, op in enumerate(sources)], 4
        ),
        "out": ProcessCollection(
            [OperatorProcess(t, op) for t, op in zip(read_times, outputs, strict=True)],
            4,
        ),
    }
    variables = ProcessCollection(
        [
            MemoryVariable(t, src.output(0), {dst.input(0): rt - t}, name=f"v{t}")
            for t, (src, dst, rt) in enumerate(
                zip(sources, outputs, read_times, strict=True)
            )
        ],
        4,
    )
    direct, memories = variables.split_on_length()
    return groups, memories, direct


def _architecture(groups, memories, direct, pe_x, mem_x, max_pes, max_mems):
    pes = []
    for op_type, group in groups.items():
        assigned = _get_assignment_from_coloring(
            group, pe_x[op_type], max_pes[op_type], 4
        )
        pes.extend(
            ProcessingElement(collection, entity_name=f"{op_type}{idx}")
            for idx, collection in assigned.items()
        )
    assigned = _get_assignment_from_coloring(memories, mem_x, max_mems, 4)
    mems = [
        Memory(collection, entity_name=f"memory{idx}", assign=True)
        for idx, collection in assigned.items()
    ]
    return Architecture(pes, mems, direct_interconnects=direct)


@pytest.mark.parametrize(
    ("total_ports", "expected_cost", "expected_memories"), [(1, 4, 2), (2, 2, 1)]
)
@pytest.mark.usefixtures("cp_solver")
def test_cp_memory_port_capacity(total_ports, expected_cost, expected_memories):
    groups, memories, direct = _problem()
    max_pes = {"in": 1, "out": 1}
    pe_x, mem_x = _cp_min_mux(
        groups, memories, max_pes, 2, direct, memory_total_ports=total_ports
    )
    arch = _architecture(groups, memories, direct, pe_x, mem_x, max_pes, 2)
    assert len(arch.memories) == expected_memories
    assert arch.get_multiplexer_input_count() == expected_cost


@pytest.mark.usefixtures("cp_solver")
def test_cp_single_port_insufficient_memories():
    groups, memories, direct = _problem()
    with pytest.raises(ValueError, match="Insufficient resources"):
        _cp_min_mux(
            groups, memories, {"in": 1, "out": 1}, 1, direct, memory_total_ports=1
        )


@pytest.mark.usefixtures("cp_solver")
def test_cp_mux_bound_combines_direct_and_memory_sources():
    groups, memories, direct = _problem(read_times=(2, 1))
    max_pes = {"in": 1, "out": 1}
    with pytest.raises(ValueError, match="Solution could not be found"):
        _cp_min_mux(groups, memories, max_pes, 1, direct, max_mux_size=1)
    pe_x, mem_x = _cp_min_mux(groups, memories, max_pes, 1, direct, max_mux_size=2)
    arch = _architecture(groups, memories, direct, pe_x, mem_x, max_pes, 1)
    assert arch.get_multiplexer_input_count() == 3


@pytest.mark.usefixtures("cp_solver")
def test_cp_direct_only_and_empty_memories():
    groups, memories, direct = _problem(read_times=(0, 1))
    max_pes = {"in": 1, "out": 1}
    pe_x, mem_x = _cp_min_mux(groups, memories, max_pes, 0, direct, max_mux_size=1)
    arch = _architecture(groups, memories, direct, pe_x, mem_x, max_pes, 0)
    assert not mem_x
    assert arch.get_multiplexer_input_count() == 1


@pytest.mark.usefixtures("cp_solver")
def test_cp_chained_memory_connections():
    groups, _, _ = _problem()
    source = next(iter(groups["in"]))
    dest = next(iter(groups["out"]))
    groups = {
        "in": ProcessCollection([source], 4),
        "out": ProcessCollection([dest], 4),
    }
    memories = ProcessCollection(
        [
            MemoryVariable(
                0, source.operation.output(0), {dest.operation.input(0): 5}, "long"
            )
        ],
        4,
    ).split_into_chains()
    direct = ProcessCollection([], 4)
    max_pes = {"in": 1, "out": 1}
    pe_x, mem_x = _cp_min_mux(groups, memories, max_pes, 2, direct)
    arch = _architecture(groups, memories, direct, pe_x, mem_x, max_pes, 2)
    assert arch.get_multiplexer_input_count() == 3


def test_cp_rejects_pulp_solver_before_building_model():
    from pulp import HiGHS

    with pytest.raises(TypeError, match="CPMpy solver name"):
        assign_processing_elements_and_memories(
            None, strategy="cp_min_mux", solver=HiGHS()
        )


@pytest.mark.parametrize("strategy", ["ilp_min_mux", "cp_min_mux"])
def test_public_mux_strategy_optimum(strategy, request):
    if strategy == "cp_min_mux":
        request.getfixturevalue("cp_solver")

    from b_asic.list_schedulers import HybridScheduler
    from b_asic.schedule import Schedule
    from b_asic.sfg_generators import radix_2_dif_fft

    sfg = radix_2_dif_fft(8)
    for op_type in ("r2bfly", "cmul"):
        sfg.set_latency_of_type_name(op_type, 1)
        sfg.set_execution_time_of_type_name(op_type, 1)
    resources = {"r2bfly": 1, "cmul": 1, "in": 2, "out": 1}
    schedule = Schedule(
        sfg,
        scheduler=HybridScheduler(
            resources, max_concurrent_reads=3, max_concurrent_writes=3
        ),
    )
    pes, mems, direct = assign_processing_elements_and_memories(
        schedule,
        strategy=strategy,
        resources=resources,
        max_mems=3,
        memory_read_ports=1,
        memory_write_ports=1,
        memory_total_ports=2,
    )
    arch = Architecture(pes, mems, direct_interconnects=direct)
    assert arch.get_multiplexer_input_count() == 18


@pytest.mark.usefixtures("cp_solver")
def test_cp_zero_duration_isolated_processes():
    sources = [Input(), Input()]
    for source in sources:
        source.execution_time = 0
    group = ProcessCollection([OperatorProcess(0, source) for source in sources], 4)
    empty = ProcessCollection([], 4)
    pe_x, mem_x = _cp_min_mux({"in": group}, empty, {"in": 2}, 0, empty)
    assert all(sum(colors.values()) == 1 for colors in pe_x["in"].values())
    assert not mem_x
