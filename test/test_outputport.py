"""
B-ASIC test suite for OutputPort.
"""
from b_asic import OutputPort, InputPort, Signal
import pytest

@pytest.fixture
def output_port():
    return OutputPort(0, None)

@pytest.fixture
def input_port():
    return InputPort(0, None)

@pytest.fixture
def list_of_input_ports():
    return [InputPort(_, None) for _ in range(0,3)]

class TestConnect:
    def test_multiple_ports(self, output_port, list_of_input_ports):
        """Can multiple ports connect to an output port?"""
        for port in list_of_input_ports:
            output_port.connect(port)

        assert output_port.signal_count() == len(list_of_input_ports)

    def test_same_port(self, output_port, list_of_input_ports):
        """Check error handing."""
        output_port.connect(list_of_input_ports[0])
        with pytest.raises(AssertionError):
            output_port.connect(list_of_input_ports[0])

        assert output_port.signal_count() == 2

class TestAddSignal:
    def test_dangling(self, output_port):
        s = Signal()
        output_port.add_signal(s)

        assert output_port.signal_count() == 1

    def test_with_destination(self, output_port, input_port):
        s = Signal(destination=input_port)
        output_port.add_signal(s)

        assert output_port.connected_ports == [s.destination]

class TestDisconnect:
    def test_multiple_ports(self, output_port, list_of_input_ports):
        """Can multiple ports disconnect from OutputPort?"""
        for port in list_of_input_ports:
            output_port.connect(port)

        for port in list_of_input_ports:
            output_port.disconnect(port)

        assert output_port.signal_count() == 3
        assert output_port.connected_ports == []

class TestRemoveSignal:
    def test_one_signal(self, output_port, input_port):
        s = output_port.connect(input_port)
        output_port.remove_signal(s)

        assert output_port.signal_count() == 0
        assert output_port.signals == []
        assert output_port.connected_ports == []

    def test_multiple_signals(self, output_port, list_of_input_ports):
        """Can multiple signals disconnect from OutputPort?"""
        sigs = []

        for port in list_of_input_ports:
            sigs.append(output_port.connect(port))

        for sig in sigs:
            output_port.remove_signal(sig)

        assert output_port.signal_count() == 0
        assert output_port.signals == []
