"""Tests for memory operations and their integration with SFG inputs and outputs."""

import pytest

from b_asic import SFG, Input, MemoryRead, MemoryWrite, Output
from b_asic.save_load_structure import sfg_to_python


@pytest.mark.parametrize("operation_type", [MemoryRead, MemoryWrite])
def test_memory_parameters_and_copy(operation_type):
    operation = operation_type(12, memory_name="samples", name="access")
    operation.address = 24
    operation.memory_name = "results"
    copied = operation.copy()
    assert type(copied) is operation_type
    assert copied.address == 24
    assert copied.memory_name == "results"
    assert copied.name == "access"
    operation.address = 48
    assert copied.address == 24
    assert operation_type().address == 0
    assert operation_type().memory_name == ""


def test_memory_port_behavior():
    read = MemoryRead(4)
    write = MemoryWrite(8, read)
    assert isinstance(read, Input)
    assert isinstance(write, Output)
    assert (read.input_count, read.output_count) == (0, 1)
    assert (write.input_count, write.output_count) == (1, 0)
    assert write.input(0).connected_source is read.output(0)
    assert read.latency == write.latency == 0
    assert read.execution_time == write.execution_time == 1
    assert read.type_name() != Input.type_name()
    assert write.type_name() != Output.type_name()
    read.value = 3 + 2j
    assert read.evaluate() == 3 + 2j


def test_memory_read_latency():
    read = MemoryRead(4, latency=3)
    assert read.latency == 3
    assert read.output(0).latency_offset == 3
    assert read.copy().latency == 3
    read.set_latency(5)
    assert read.latency == 5
    assert read.output(0).latency_offset == 5
    with pytest.raises(ValueError, match="Latency cannot be negative"):
        MemoryRead(latency=-1)


@pytest.mark.parametrize("address", [0, 12])
@pytest.mark.parametrize("memory_name", ["", "samples"])
@pytest.mark.parametrize("latency", [0, 3])
def test_memory_graph_copy_and_serialization(address, memory_name, latency):
    read = MemoryRead(address, memory_name=memory_name, latency=latency)
    write = MemoryWrite(address + 1, read + 2, memory_name="results")
    graph = SFG(read, write)
    namespace = {}
    exec(sfg_to_python(graph), namespace)
    for restored in (graph, graph(), namespace["sfg"]):
        restored_read = restored.input_operations[0]
        restored_write = restored.output_operations[0]
        assert isinstance(restored_read, MemoryRead)
        assert isinstance(restored_write, MemoryWrite)
        assert restored_read.address == address
        assert restored_read.memory_name == memory_name
        assert restored_read.latency == latency
        assert restored_write.address == address + 1
        assert restored_write.memory_name == "results"
        assert restored.evaluate(5) == 7


def test_multiple_memories():
    left = MemoryRead(3, memory_name="left")
    right = MemoryRead(3, memory_name="right")
    graph = SFG(
        [left, right],
        [
            MemoryWrite(3, left + right, memory_name="sum"),
            MemoryWrite(3, left - right, memory_name="difference"),
        ],
    )
    assert graph.evaluate_outputs([10, 4]) == [14, 6]
    assert [op.memory_name for op in graph.input_operations] == ["left", "right"]
    assert [op.memory_name for op in graph.output_operations] == ["sum", "difference"]
