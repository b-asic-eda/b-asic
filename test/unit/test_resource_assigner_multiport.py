"""Joint min-mux assignment with multiple memory ports."""

from random import Random
from unittest.mock import Mock, patch

import pytest

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.process import MemoryOutputPort, MemoryVariable, OperatorProcess
from b_asic.resource_assigner import (
    _split_operations_and_variables,
    assign_processing_elements_and_memories,
)
from b_asic.resources import ProcessCollection
from b_asic.special_operations import Input, Output
from b_asic.types import TypeName


@pytest.fixture(params=["ilp_min_mux", "cp_min_mux", "greedy_min_mux"])
def strategy(request):
    if request.param == "cp_min_mux":
        pytest.importorskip("cpmpy", exc_type=ImportError)
    return request.param


def _schedule(write_times, read_times, source_types=None):
    sources = [kind() for kind in (source_types or [Input] * len(write_times))]
    outputs = [Output(source) for source in sources]
    for index, (source, output) in enumerate(zip(sources, outputs, strict=True)):
        source.graph_id = f"in{index}"
        output.graph_id = f"out{index}"
    variables = [
        MemoryVariable(
            write, source.output(0), {output.input(0): read - write}, name=f"v{index}"
        )
        for index, (source, output, write, read) in enumerate(
            zip(sources, outputs, write_times, read_times, strict=True)
        )
    ]
    schedule = Mock()
    schedule.get_memory_variables.return_value = ProcessCollection(variables, 8)
    schedule.get_operations.return_value = ProcessCollection(
        [
            *[
                OperatorProcess(time, source)
                for time, source in zip(write_times, sources, strict=True)
            ],
            *[
                OperatorProcess(time, output)
                for time, output in zip(read_times, outputs, strict=True)
            ],
        ],
        8,
    )
    return schedule


@pytest.mark.parametrize("explicit_bound", [False, True])
@pytest.mark.parametrize(
    ("writes", "reads", "ports", "expected"),
    [
        ((0, 1), (4, 4), (2, 1, 3), 1),
        ((6, 7), (9, 9), (2, 1, 3), 1),
        ((0, 1, 2), (4, 4, 4), (2, 1, 3), 2),
        ((0, 1, 4), (4, 4, 6), (2, 1, 2), 2),
        ((0, 1, 4), (4, 4, 6), (2, 1, 3), 1),
        ((0, 0, 1), (4, 4, 4), (3, 2, 5), 1),
    ],
)
def test_joint_multiport_capacities(
    strategy, explicit_bound, writes, reads, ports, expected, caplog
):
    schedule = _schedule(writes, reads)
    with (
        caplog.at_level("INFO", logger="b_asic.logger"),
        patch.object(
            ProcessCollection,
            "exclusion_graph_from_ports",
            side_effect=AssertionError(
                "Multiport models must not build single-port graphs"
            ),
        ),
    ):
        pes, memories, direct = assign_processing_elements_and_memories(
            schedule,
            strategy=strategy,
            resources={"in": len(writes), "out": len(reads)},
            max_mems=expected if explicit_bound else None,
            memory_read_ports=ports[0],
            memory_write_ports=ports[1],
            memory_total_ports=ports[2],
        )
    assert pes
    assert not direct
    assert len(memories) == expected
    assert sorted(var.name for memory in memories for var in memory) == [
        f"v{index}" for index in range(len(writes))
    ]
    architecture = Architecture(pes, memories, direct_interconnects=direct)
    cost = architecture.get_multiplexer_input_count()
    assert any(
        f"mux connection count: {cost}" in record.message for record in caplog.records
    )
    for memory in memories:
        assert memory.collection.read_ports_bound() <= ports[0]
        assert memory.collection.write_ports_bound() <= ports[1]
        assert memory.collection.total_ports_bound() <= ports[2]
        seen = set()
        selected = memory.port_assignment
        for variable in memory:
            for delay in (None, *set(variable.reads.values())):
                port = selected[variable, delay]
                assert 0 <= port < (ports[1] if delay is None else ports[0])
                endpoint = (
                    (variable.start_time + (delay or 0)) % memory.schedule_time,
                    delay is None,
                    port,
                )
                assert endpoint not in seen
                seen.add(endpoint)


def test_joint_multiport_infeasible_bound(strategy):
    with pytest.raises(
        ValueError,
        match=r"Solution could not be found|Insufficient|No feasible assignment",
    ):
        assign_processing_elements_and_memories(
            _schedule((0, 1, 2), (4, 4, 4)),
            strategy=strategy,
            resources={"in": 3, "out": 3},
            max_mems=1,
            memory_read_ports=2,
        )


@pytest.mark.parametrize("ports", [(2, 1, 3), (2, 2, 2), (3, 2, 4)])
def test_greedy_multiport_local_search_is_feasible_and_reproducible(ports):
    rng = Random(12)
    writes = tuple(range(8))
    reads = tuple(time + rng.randrange(1, 8) for time in writes)
    schedule = _schedule(writes, reads)
    options = {"restarts": 2, "max_passes": 4, "seed": 42}
    snapshots = []
    for _ in range(2):
        pes, memories, _ = assign_processing_elements_and_memories(
            schedule,
            strategy="greedy_min_mux",
            resources={"in": 8, "out": 8},
            max_mems=4,
            memory_read_ports=ports[0],
            memory_write_ports=ports[1],
            memory_total_ports=ports[2],
            strat_params=options,
        )
        for memory in memories:
            assert memory.collection.read_ports_bound() <= ports[0]
            assert memory.collection.write_ports_bound() <= ports[1]
            assert memory.collection.total_ports_bound() <= ports[2]
        assert sorted(var.name for memory in memories for var in memory) == [
            f"v{i}" for i in range(8)
        ]
        snapshots.append(
            (
                [sorted(process.name for process in pe) for pe in pes],
                [sorted(var.name for var in memory) for memory in memories],
            )
        )
    assert snapshots[0] == snapshots[1]
    assert options == {"restarts": 2, "max_passes": 4, "seed": 42}


class _OtherOutput(Output):
    @classmethod
    def type_name(cls):
        return TypeName("other_out")


def _read_mux_schedule():
    sources = [Input(), Input()]
    sink = _OtherOutput(sources[0])
    outputs = [Output(sources[1]), Output(sources[1])]
    operations = [*sources, sink, *outputs]
    for index, operation in enumerate(operations):
        operation.graph_id = f"op{index}"
    schedule = Mock()
    schedule.get_memory_variables.return_value = ProcessCollection(
        [
            MemoryVariable(0, sources[0].output(0), {sink.input(0): 4}, "v0"),
            MemoryVariable(
                1,
                sources[1].output(0),
                {outputs[0].input(0): 3, outputs[1].input(0): 4},
                "v1",
            ),
        ],
        8,
    )
    schedule.get_operations.return_value = ProcessCollection(
        [
            OperatorProcess(time, operation)
            for time, operation in zip((0, 1, 4, 4, 5), operations, strict=True)
        ],
        8,
    )
    return schedule


def test_read_ports_are_separate_mux_inputs(strategy, caplog):
    # Keeping v1 on the same port in cycles 4 and 5 avoids a PE input mux.
    # Consecutive port allocation would give it different ports and cost 4.
    with caplog.at_level("INFO", logger="b_asic.logger"):
        pes, memories, direct = assign_processing_elements_and_memories(
            _read_mux_schedule(),
            strategy=strategy,
            resources={"in": 1, "out": 1, "other_out": 1},
            max_mems=1,
            memory_read_ports=2,
        )
    architecture = Architecture(pes, memories, direct_interconnects=direct)
    assert architecture.get_multiplexer_input_count() == 3
    assert architecture.get_multiplexer_input_count(multiplexed_only=True) == 0
    assert any("mux connection count: 3" in record.message for record in caplog.records)
    ports = memories[0].port_assignment
    var = next(var for var in memories[0] if var.name == "v1")
    assert ports[var, 3] == ports[var, 4]
    ports[var, 3] = 100
    assert memories[0].port_assignment[var, 3] != 100
    # Rebuilding the architecture must retain the optimized access ports.
    assert (
        Architecture(
            pes, memories, direct_interconnects=direct
        ).get_multiplexer_input_count()
        == 3
    )
    pes, memories, direct = assign_processing_elements_and_memories(
        _read_mux_schedule(),
        strategy=strategy,
        resources={"in": 1, "out": 1, "other_out": 1},
        max_mems=1,
        memory_read_ports=2,
        max_mux_size=1,
    )
    assert (
        Architecture(
            pes, memories, direct_interconnects=direct
        ).get_multiplexer_input_count()
        == 3
    )


class _OtherInput(Input):
    @classmethod
    def type_name(cls):
        return TypeName("other_in")


def test_optimized_ports_keep_same_cycle_reads_as_a_broadcast(strategy):
    schedule = _schedule((0,), (4,))
    variable = next(iter(schedule.get_memory_variables()))
    source = variable.write_port.operation
    second_output = Output(source)
    second_output.graph_id = "extra_out"
    original_output = next(iter(variable.reads)).operation
    schedule.get_memory_variables.return_value = ProcessCollection(
        [
            MemoryVariable(
                0,
                variable.write_port,
                {original_output.input(0): 4, second_output.input(0): 4},
                "broadcast",
            ),
        ],
        8,
    )
    schedule.get_operations.return_value = ProcessCollection(
        [
            *schedule.get_operations(),
            OperatorProcess(4, second_output),
        ],
        8,
    )
    pes, memories, direct = assign_processing_elements_and_memories(
        schedule,
        strategy=strategy,
        resources={"in": 1, "out": 2},
        max_mems=1,
        memory_read_ports=2,
        memory_write_ports=2,
        max_mux_size=1,
    )
    memory = memories[0]
    assert len(memory.port_assignment) == 2  # One write and one broadcast read.
    architecture = Architecture(pes, memories, direct_interconnects=direct)
    assert architecture.get_multiplexer_input_count() == 3
    outputs = architecture.get_interconnects_for_memory(memory)[1]
    assert sorted(len(port) for port in outputs) == [0, 2]


def test_write_port_choices_reuse_sources_across_cycles(strategy, caplog):
    with caplog.at_level("INFO", logger="b_asic.logger"):
        pes, memories, direct = assign_processing_elements_and_memories(
            _schedule((0, 0, 1), (4, 4, 5), [Input, _OtherInput, _OtherInput]),
            strategy=strategy,
            resources={"in": 1, "other_in": 1, "out": 2},
            max_mems=1,
            memory_read_ports=2,
            memory_write_ports=2,
            max_mux_size=1,
        )
    architecture = Architecture(pes, memories, direct_interconnects=direct)
    assert architecture.get_multiplexer_input_count() == 4
    assert architecture.get_multiplexer_input_count(multiplexed_only=True) == 0
    ports = memories[0].port_assignment
    variables = {var.name: var for var in memories[0]}
    assert ports[variables["v1"], None] == ports[variables["v2"], None]
    assert ports[variables["v0"], None] != ports[variables["v1"], None]
    assert any("mux connection count: 4" in record.message for record in caplog.records)


def test_write_ports_have_independent_mux_limits(strategy, caplog):
    with caplog.at_level("INFO", logger="b_asic.logger"):
        pes, memories, direct = assign_processing_elements_and_memories(
            _schedule((0, 0), (4, 4)),
            strategy=strategy,
            resources={"in": 2, "out": 2},
            max_mems=1,
            memory_read_ports=2,
            memory_write_ports=2,
            max_mux_size=1,
        )
    architecture = Architecture(pes, memories, direct_interconnects=direct)
    memory = memories[0]
    inputs, outputs = architecture.get_interconnects_for_memory(memory)
    assert [len(port) for port in inputs] == [1, 1]
    assert [len(port) for port in outputs] == [1, 1]
    assert architecture.get_multiplexer_input_count() == 4
    assert architecture.get_multiplexer_input_count(multiplexed_only=True) == 0
    assert any("mux connection count: 4" in record.message for record in caplog.records)


def test_relay_ports_are_included_in_mux_cost(strategy, caplog):
    schedule = _schedule((0, 1, 4), (4, 6, 6))
    variables = schedule.get_memory_variables()
    early, long, stub = variables
    stub._name = "a_stub"
    chain = ProcessCollection([long], 8).split_into_chains(max_length=3)
    variables = ProcessCollection([early, stub, *chain], 8)
    with caplog.at_level("INFO", logger="b_asic.logger"):
        groups, collections = _split_operations_and_variables(
            schedule.get_operations().split_on_type_name(),
            variables,
            ProcessCollection([], 8),
            strategy=strategy,
            resources={"in": 1, "out": 2},
            max_mems=1,
            memory_read_ports=2,
            memory_write_ports=2,
        )
    pes = [
        ProcessingElement(group, f"{kind}{index}")
        for kind, assigned in groups.items()
        for index, group in enumerate(assigned)
    ]
    memories = [
        Memory(collection, entity_name=f"mem{index}")
        for index, collection in enumerate(collections)
    ]
    architecture = Architecture(pes, memories)
    memory = memories[0]
    assert any(isinstance(var.write_port, MemoryOutputPort) for var in memory)
    tail = next(var for var in memory if isinstance(var.write_port, MemoryOutputPort))
    root = tail.write_port.source_variable
    ports = memory.port_assignment
    write_port = ports[tail, None]
    read_port = ports[root, 3]
    assert (memory, read_port) in architecture.get_interconnects_for_memory(memory)[0][
        write_port
    ]
    cost = architecture.get_multiplexer_input_count()
    assert any(
        f"mux connection count: {cost}" in record.message for record in caplog.records
    )
