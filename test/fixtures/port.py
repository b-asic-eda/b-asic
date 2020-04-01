import pytest
from b_asic.port import InputPort, OutputPort

@pytest.fixture
def input_port():
    return InputPort(0, None)

@pytest.fixture
def output_port():
    return OutputPort(0, None)
