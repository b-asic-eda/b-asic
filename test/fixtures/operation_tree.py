from b_asic.core_operations import Addition, Constant
from b_asic.signal import Signal

import pytest

@pytest.fixture
def operation():
    return Constant(2)

def create_operation(_type, dest_oper, index, **kwargs):
    oper = _type(**kwargs)
    oper_signal = Signal()
    oper._output_ports[0].add_signal(oper_signal)

    dest_oper._input_ports[index].add_signal(oper_signal)
    return oper

@pytest.fixture
def operation_tree():
    """Return a addition operation connected with 2 constants.
    ---C---+
           ---A
    ---C---+
    """
    add_oper = Addition()
    create_operation(Constant, add_oper, 0, value=2)
    create_operation(Constant, add_oper, 1, value=3)
    return add_oper

@pytest.fixture
def large_operation_tree():
    """Return a constant operation connected with a large operation tree with 3 other constants and 3 additions.
    ---C---+
           ---A---+
    ---C---+      |
                  +---A
    ---C---+      |
           ---A---+
    ---C---+
    """
    add_oper = Addition()
    add_oper_2 = Addition()

    const_oper = create_operation(Constant, add_oper, 0, value=2)
    create_operation(Constant, add_oper, 1, value=3)

    create_operation(Constant, add_oper_2, 0, value=4)
    create_operation(Constant, add_oper_2, 1, value=5)

    add_oper_3 = Addition()
    add_oper_signal = Signal(add_oper.output(0), add_oper_3.output(0))
    add_oper._output_ports[0].add_signal(add_oper_signal)
    add_oper_3._input_ports[0].add_signal(add_oper_signal)

    add_oper_2_signal = Signal(add_oper_2.output(0), add_oper_3.output(0))
    add_oper_2._output_ports[0].add_signal(add_oper_2_signal)
    add_oper_3._input_ports[1].add_signal(add_oper_2_signal)
    return const_oper
