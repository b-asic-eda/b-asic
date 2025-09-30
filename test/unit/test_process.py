import re

import pytest

from b_asic.process import PlainMemoryVariable


def test_PlainMemoryVariable():
    mem = PlainMemoryVariable(3, 0, {4: 1, 5: 2})
    assert mem.write_port == 0
    assert mem.start_time == 3
    assert mem.execution_time == 2
    assert mem.life_times == [1, 2]
    assert mem.read_ports == [4, 5]
    assert repr(mem) == "PlainMemoryVariable(3, 0, {4: 1, 5: 2}, 'Var. 0')"

    mem2 = PlainMemoryVariable(2, 0, {4: 2, 5: 3}, "foo")
    assert repr(mem2) == "PlainMemoryVariable(2, 0, {4: 2, 5: 3}, 'foo')"

    assert mem2 < mem

    mem3 = PlainMemoryVariable(2, 0, {4: 1, 5: 2})
    assert mem2 < mem3


def test_MemoryVariables(secondorder_iir_schedule):
    pc = secondorder_iir_schedule.get_memory_variables()
    mem_vars = pc.collection
    pattern = re.compile(
        "MemoryVariable\\(3, <b_asic.port.OutputPort object at 0x[a-fA-F0-9]+>,"
        " {<b_asic.port.InputPort object at 0x[a-fA-F0-9]+>: 4}, 'cmul0.0'\\)"
    )
    mem_var = next(m for m in mem_vars if m.name == "cmul0.0")
    assert pattern.match(repr(mem_var))
    assert mem_var.execution_time == 4
    assert mem_var.start_time == 3


def test_OperatorProcess_error(secondorder_iir_schedule):
    with pytest.raises(ValueError, match=r"does not have an execution time specified"):
        _ = secondorder_iir_schedule.get_operations()


def test_MultiReadProcess():
    mv = PlainMemoryVariable(3, 0, {0: 1, 1: 2, 2: 5}, name="MV")

    with pytest.raises(KeyError, match=r"Process MV: 3 not in life_times: \[1, 2, 5\]"):
        mv._remove_life_time(3)

    assert mv.life_times == [1, 2, 5]
    assert mv.execution_time == 5
    mv._remove_life_time(5)
    assert mv.life_times == [1, 2]
    assert mv.execution_time == 2
    mv._add_life_time(4)
    assert mv.execution_time == 4
    assert mv.life_times == [1, 2, 4]
    mv._add_life_time(4)
    assert mv.life_times == [1, 2, 4]


def test_split_on_length():
    mv = PlainMemoryVariable(3, 0, {0: 1, 1: 2, 2: 5}, name="MV")
    short, long = mv.split_on_length(2)
    assert short is not None
    assert long is not None
    assert short.start_time == 3
    assert long.start_time == 3
    assert short.execution_time == 2
    assert long.execution_time == 5
    assert short.reads == {0: 1, 1: 2}
    assert long.reads == {2: 5}

    short, long = mv.split_on_length(0)
    assert short is None
    assert long is not None
