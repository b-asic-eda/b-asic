"""
B-ASIC test suite for OutputPort.
"""
import pytest

from b_asic import Signal


class TestConnect:
    def test_multiple_ports(self, output_port, list_of_input_ports):
        """Multiple connections to an output port should be possible."""
        for port in list_of_input_ports:
            port.connect(output_port)

        assert output_port.signal_count == len(list_of_input_ports)

    def test_same_port(self, output_port, input_port):
        """Check error handing."""
        input_port.connect(output_port)
        with pytest.raises(Exception):
            input_port.connect(output_port)

        assert output_port.signal_count == 1


class TestAddSignal:
    def test_dangling(self, output_port):
        s = Signal()
        output_port.add_signal(s)

        assert output_port.signal_count == 1
        assert output_port.signals == [s]


class TestClear:
    def test_others_clear(self, output_port, list_of_input_ports):
        for port in list_of_input_ports:
            port.connect(output_port)

        for port in list_of_input_ports:
            port.clear()

        assert output_port.signal_count == 3
        assert all(s.dangling() for s in output_port.signals)

    def test_self_clear(self, output_port, list_of_input_ports):
        for port in list_of_input_ports:
            port.connect(output_port)

        output_port.clear()

        assert output_port.signal_count == 0
        assert output_port.signals == []


class TestRemoveSignal:
    def test_one_signal(self, output_port, input_port):
        s = input_port.connect(output_port)
        output_port.remove_signal(s)

        assert output_port.signal_count == 0
        assert output_port.signals == []

    def test_multiple_signals(self, output_port, list_of_input_ports):
        sigs = []

        for port in list_of_input_ports:
            sigs.append(port.connect(output_port))

        for s in sigs:
            output_port.remove_signal(s)

        assert output_port.signal_count == 0
        assert output_port.signals == []
