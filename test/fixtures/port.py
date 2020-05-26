import pytest

from b_asic import InputPort, OutputPort


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
