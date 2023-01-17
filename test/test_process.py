import pytest

from b_asic.process import PlainMemoryVariable


def test_PlainMemoryVariable():
    mem = PlainMemoryVariable(3, 0, {4: 1, 5: 2})
    assert mem.write_port == 0
    assert mem.start_time == 3
    assert mem.execution_time == 2
    assert mem.life_times == (1, 2)
    assert mem.read_ports == (4, 5)
