"""Logical operation ports sharing physical PE interfaces."""

import io
from unittest.mock import Mock

import pytest

from b_asic import SFG, Addition, Input, Output, R2Butterfly
from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.code_printer.vhdl import control, processing_element, top_level
from b_asic.code_printer.vhdl.vhdl_printer import VhdlPrinter
from b_asic.data_type import DataType
from b_asic.process import MemoryVariable, OperatorProcess
from b_asic.resource_assigner import (
    _mux_problem,
    assign_processing_elements_and_memories,
)
from b_asic.resources import ProcessCollection
from b_asic.save_load_structure import sfg_to_python


def mapped_butterfly(*sources):
    op = R2Butterfly(
        *sources,
        latency_offsets={"in0": 0, "in1": 1, "out0": 3, "out1": 4},
        execution_time=1,
    )
    op.set_port_mapping({"in0": 0, "in1": 0, "out0": 0, "out1": 0})
    return op


def test_mapping_defaults_copy_and_reset():
    op = R2Butterfly()
    assert op.port_mapping == {"in0": 0, "in1": 1, "out0": 0, "out1": 1}
    assert op.physical_input_count == op.physical_output_count == 2
    op.set_port_mapping({"in0": 0, "in1": 0})
    assert op.input_count == op.output_count == 2
    assert op.input_port_mapping == (0, 0)
    assert op.output_port_mapping == (0, 1)
    assert op.physical_input_count == 1
    copied = op.copy()
    assert copied.port_mapping == op.port_mapping
    copied.set_port_mapping(None)
    assert copied.input_port_mapping == (0, 1)
    assert op.input_port_mapping == (0, 0)
    mapping = op.port_mapping
    mapping["in1"] = 1
    assert op.input_port_mapping == (0, 0)
    op.set_port_mapping({"out0": 1, "out1": 0})
    assert op.input_port_mapping == (0, 0)
    assert op.output_port_mapping == (1, 0)
    assert Input().physical_input_count == Output().physical_output_count == 0


@pytest.mark.parametrize(
    "mapping",
    [
        {"in2": 0},
        {"in0": 0},
        {"out1": 0},
        {"in0": -1, "in1": 0},
        {"in0": True, "in1": 0},
        {"in0": 0.0, "in1": 0},
        {"in0": 0, "in1": 2},
    ],
)
def test_invalid_mapping_is_atomic(mapping):
    op = mapped_butterfly()
    original = op.port_mapping
    with pytest.raises(ValueError, match=r"port|indices"):
        op.set_port_mapping(mapping)
    assert op.port_mapping == original


@pytest.mark.parametrize("by_name", [False, True])
def test_mapping_of_type_survives_sfg_copy(by_name):
    sources = [Input(), Input()]
    op = Addition(*sources)
    sfg = SFG(sources, [Output(op)])
    if by_name:
        sfg.set_port_mapping_of_type_name(Addition.type_name(), {"in0": 0, "in1": 0})
    else:
        sfg.set_port_mapping_of_type(Addition, {"in0": 0, "in1": 0})
    copied = sfg.copy()
    assert copied.find_by_type(Addition)[0].input_port_mapping == (0, 0)
    sfg.set_port_mapping_of_type(Addition, None)
    assert sfg.find_by_type(Addition)[0].input_port_mapping == (0, 1)


def test_mapping_survives_serialization():
    sources = [Input(), Input()]
    op = mapped_butterfly(*sources)
    sfg = SFG(sources, [Output(port) for port in op.outputs])
    namespace = {}
    exec(sfg_to_python(sfg), namespace)
    restored = namespace["prop"]["name"].find_by_type(R2Butterfly)[0]
    assert restored.port_mapping == op.port_mapping
    assert restored.latency_offsets == op.latency_offsets


@pytest.mark.parametrize("strategy", ["left_edge", "greedy_graph_color"])
@pytest.mark.parametrize("starts", [(0, 1), (0, 7)])
def test_assignment_rejects_port_overlap(strategy, starts):
    processes = [OperatorProcess(t, mapped_butterfly()) for t in starts]
    collection = ProcessCollection(processes, 8)
    assert len(collection.split_on_execution_time(strategy)) == 2
    with pytest.raises(ValueError, match="Physical port collision"):
        ProcessingElement(collection)


def test_nonoverlapping_invocations_can_share_pe():
    processes = [OperatorProcess(t, mapped_butterfly()) for t in (0, 2)]
    collection = ProcessCollection(processes, 8)
    assert len(collection.split_on_execution_time()) == 1
    pe = ProcessingElement(collection)
    assert pe.input_count == pe.output_count == 1


@pytest.mark.parametrize("offset", [0, 8])
def test_single_invocation_collision(offset):
    op = mapped_butterfly()
    op.input(1).latency_offset = offset
    collection = ProcessCollection([OperatorProcess(0, op)], 8)
    with pytest.raises(ValueError, match="Physical port collision"):
        ProcessingElement(collection, assign=False)
    with pytest.raises(ValueError, match="Physical port collision"):
        collection.split_on_execution_time()


@pytest.mark.parametrize("change_timing", [False, True])
def test_incompatible_interfaces_are_split(change_timing):
    first, second = mapped_butterfly(), mapped_butterfly()
    if change_timing:
        second.input(1).latency_offset = 2
    else:
        second.set_port_mapping(None)
    collection = ProcessCollection(
        [OperatorProcess(0, first), OperatorProcess(4, second)], 16
    )
    assert len(collection.split_on_execution_time()) == 2
    with pytest.raises(ValueError, match="incompatible port mappings or timing"):
        ProcessingElement(collection)


def make_architecture(stored):
    gap = int(stored)
    sources = [Input(), Input()]
    op = mapped_butterfly(*sources)
    sinks = [Output(port) for port in op.outputs]
    for i, source in enumerate(sources):
        source.graph_id = f"in{i}"
    op.graph_id = "bf0"
    for i, sink in enumerate(sinks):
        sink.graph_id = f"out{i}"
    pes = [
        ProcessingElement(ProcessCollection([OperatorProcess(i, source)], 8), f"src{i}")
        for i, source in enumerate(sources)
    ]
    pe = ProcessingElement(ProcessCollection([OperatorProcess(gap, op)], 8), "bf")
    pes.append(pe)
    pes.extend(
        ProcessingElement(
            ProcessCollection([OperatorProcess(2 * gap + 3 + i, sink)], 8), f"dst{i}"
        )
        for i, sink in enumerate(sinks)
    )
    variables = [
        MemoryVariable(i, source.output(0), {op.input(i): gap}, f"input{i}")
        for i, source in enumerate(sources)
    ] + [
        MemoryVariable(gap + 3 + i, op.output(i), {sink.input(0): gap}, f"output{i}")
        for i, sink in enumerate(sinks)
    ]
    collection = ProcessCollection(variables, 8)
    memories = [Memory(collection, entity_name="mem")] if stored else []
    arch = Architecture(
        pes, memories, direct_interconnects=None if stored else collection
    )
    return arch, pe


@pytest.mark.parametrize("stored", [False, True])
@pytest.mark.parametrize("registered", [False, True])
def test_physical_routing_and_vhdl_interfaces(stored, registered):
    arch, pe = make_architecture(stored)
    inputs, outputs = arch.get_interconnects_for_pe(pe)
    assert len(inputs) == len(outputs) == 1
    assert sum(inputs[0].values()) == sum(outputs[0].values()) == 2
    pe_muxes, memory_muxes = top_level._collect_mux_info(arch)
    bf_assignments = next(items for resource, port, items in pe_muxes if resource is pe)
    if stored:
        assert bf_assignments == [(1, "mem_0_out"), (2, "mem_0_out")]
        assert memory_muxes[0][2][-2:] == [(4, "bf_0_out"), (5, "bf_0_out")]
        memory_inputs, memory_outputs = arch.get_interconnects_for_memory(
            arch.memories[0]
        )
        assert memory_inputs[0][pe, 0] == memory_outputs[0][pe, 0] == 2
    else:
        assert bf_assignments == [(0, "src0_0_out"), (1, "src1_0_out")]
        for resource, _, assignments in pe_muxes:
            if resource.entity_name.startswith("dst"):
                assert assignments[0][1] == "bf_0_out"
        controls = control.mux_controls(8, pe_muxes, memory_muxes, registered)
        selector = next(item for item in controls if item.name == "bf_0_sel")
        assert selector.values[-int(registered) % 8] == "0"
        assert selector.values[(1 - int(registered)) % 8] == "1"
    printer = VhdlPrinter(DataType(8))
    interface = io.StringIO()
    processing_element.entity(interface, pe, printer._dt)
    assert "p_0_in : in" in interface.getvalue()
    assert "p_0_out : out" in interface.getvalue()
    assert "p_1_in" not in interface.getvalue()
    assert "p_1_out" not in interface.getvalue()
    for centralized in (False, True):
        code = printer.print_Architecture(
            arch,
            centralize_control=centralized,
            multiplexer_control_registered=registered,
        )
        assert "bf_0_in" in code
        assert "bf_0_out" in code
        assert "bf_1_in" not in code
        assert "bf_1_out" not in code


@pytest.mark.parametrize("stored", [False, True])
def test_memory_mux_objectives_use_physical_pe_endpoints(stored):
    arch, _ = make_architecture(stored)
    variables = arch.memories[0].collection if stored else arch.direct_interconnects
    groups = variables._port_connection_groups(
        "ilp_graph_color_min_mux", arch.processing_elements
    )
    assert sorted(map(len, groups)) == [1, 1, 1, 1, 2, 2]


@pytest.mark.parametrize("stored", [False, True])
def test_joint_mux_problem_uses_physical_pe_endpoints(stored):
    arch, pe = make_architecture(stored)
    groups = {
        resource.operation_type.type_name(): resource.collection
        for resource in arch.processing_elements
    }
    # Collect all operations of each type, including sources and sinks.
    for type_name in groups:
        groups[type_name] = ProcessCollection(
            [
                p
                for resource in arch.processing_elements
                for p in resource
                if p.operation.type_name() == type_name
            ],
            8,
        )
    variables = arch.memories[0].collection if stored else ProcessCollection([], 8)
    direct = ProcessCollection([], 8) if stored else arch.direct_interconnects
    _, _, links = _mux_problem(
        groups,
        variables,
        {name: len(group) for name, group in groups.items()},
        1,
        direct,
        2,
    )
    for source, destination, source_port, destination_port in links:
        if source[0] == "pe" and source[-1].operation is pe.processes[0].operation:
            assert source_port == 0
        if (
            destination[0] == "pe"
            and destination[-1].operation is pe.processes[0].operation
        ):
            assert destination_port == 0


def test_joint_mux_problem_contains_physical_port_conflicts():
    first, second = [OperatorProcess(t, mapped_butterfly()) for t in (0, 1)]
    type_name = R2Butterfly.type_name()
    groups = {type_name: ProcessCollection([first, second], 8)}
    empty = ProcessCollection([], 8)
    _, families, _ = _mux_problem(groups, empty, {type_name: 2}, 1, empty, 2)
    assert (
        frozenset({("pe", type_name, first), ("pe", type_name, second)})
        in families[0][1]
    )


@pytest.mark.parametrize(
    "strategy",
    ["left_edge", "greedy_graph_color", "greedy_min_mux", "ilp_min_mux", "cp_min_mux"],
)
@pytest.mark.parametrize("stored", [False, True])
def test_joint_assignment_preserves_shared_interfaces(strategy, stored):
    if strategy == "cp_min_mux":
        pytest.importorskip("cpmpy", exc_type=ImportError)
    arch, _ = make_architecture(stored)
    schedule = Mock()
    schedule.get_operations.return_value = ProcessCollection(
        [process for pe in arch.processing_elements for process in pe], 8
    )
    schedule.get_memory_variables.return_value = (
        arch.memories[0].collection if stored else arch.direct_interconnects
    )
    pes, memories, direct = assign_processing_elements_and_memories(
        schedule, strategy=strategy
    )
    mapped = next(pe for pe in pes if pe.operation_type is R2Butterfly)
    assert mapped.input_count == mapped.output_count == 1
    assigned = Architecture(pes, memories, direct_interconnects=direct)
    inputs, outputs = assigned.get_interconnects_for_pe(mapped)
    assert {port for _, port in inputs[0]} == {0}
    assert {port for _, port in outputs[0]} == {0}
    if not stored:
        assert assigned.get_multiplexer_input_count() == 2
