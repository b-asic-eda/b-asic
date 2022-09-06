import pytest

from b_asic import InputPort, OutputPort, Signal


@pytest.fixture
def input_port():
    return InputPort(None, 0)


@pytest.fixture
def output_port():
    return OutputPort(None, 0)


@pytest.fixture
def list_of_input_ports():
    return [InputPort(None, i) for i in range(0, 3)]


@pytest.fixture
def list_of_output_ports():
    return [OutputPort(None, i) for i in range(0, 3)]


@pytest.fixture
def output_port2():
    return OutputPort(None, 1)


@pytest.fixture
def dangling_sig():
    return Signal()


@pytest.fixture
def s_w_source(output_port):
    return Signal(source=output_port)


@pytest.fixture
def sig_with_dest(inp_port):
    return Signal(destination=inp_port)


@pytest.fixture
def connected_sig(inp_port, output_port):
    return Signal(source=output_port, destination=inp_port)
