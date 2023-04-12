import re

import pytest

from b_asic.process import PlainMemoryVariable


def test_PlainMemoryVariable():
    mem = PlainMemoryVariable(3, 0, {4: 1, 5: 2})
    assert mem.write_port == 0
    assert mem.start_time == 3
    assert mem.execution_time == 2
    assert mem.life_times == (1, 2)
    assert mem.read_ports == (4, 5)
    assert repr(mem) == "PlainMemoryVariable(3, 0, {4: 1, 5: 2}, 'Proc. 0')"

    mem2 = PlainMemoryVariable(2, 0, {4: 2, 5: 3}, 'foo')
    assert repr(mem2) == "PlainMemoryVariable(2, 0, {4: 2, 5: 3}, 'foo')"

    assert mem2 < mem

    mem3 = PlainMemoryVariable(2, 0, {4: 1, 5: 2})
    assert mem2 < mem3


def test_MemoryVariables(secondorder_iir_schedule):
    pc = secondorder_iir_schedule.get_memory_variables()
    mem_vars = pc.collection
    pattern = re.compile(
        "MemoryVariable\\(3, <b_asic.port.OutputPort object at 0x[a-fA-F0-9]+>,"
        " {<b_asic.port.InputPort object at 0x[a-fA-F0-9]+>: 4}, 'cmul1.0'\\)"
    )
    mem_var = [m for m in mem_vars if m.name == 'cmul1.0'][0]
    assert pattern.match(repr(mem_var))
    assert mem_var.execution_time == 4
    assert mem_var.start_time == 3


def test_OperatorProcess_error(secondorder_iir_schedule):
    with pytest.raises(ValueError, match="does not have an execution time specified"):
        _ = secondorder_iir_schedule.get_operations()
