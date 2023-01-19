"""
B-ASIC test suit for the signal module which consists of the Signal class.
"""

import pytest

from b_asic import InputPort, OutputPort, Signal


def test_signal_creation_and_disconnction_and_connection_changing():
    in_port = InputPort(None, 0)
    out_port = OutputPort(None, 1)
    s = Signal(out_port, in_port)

    assert in_port.signals == [s]
    assert out_port.signals == [s]
    assert s.source is out_port
    assert s.destination is in_port

    in_port1 = InputPort(None, 0)
    s.set_destination(in_port1)

    assert in_port.signals == []
    assert in_port1.signals == [s]
    assert out_port.signals == [s]
    assert s.source is out_port
    assert s.destination is in_port1

    s.remove_source()

    assert out_port.signals == []
    assert in_port1.signals == [s]
    assert s.source is None
    assert s.destination is in_port1

    s.remove_destination()

    assert out_port.signals == []
    assert in_port1.signals == []
    assert s.source is None
    assert s.destination is None

    out_port1 = OutputPort(None, 0)
    s.set_source(out_port1)

    assert out_port1.signals == [s]
    assert s.source is out_port1
    assert s.destination is None

    s.set_source(out_port)

    assert out_port.signals == [s]
    assert out_port1.signals == []
    assert s.source is out_port
    assert s.destination is None

    s.set_destination(in_port)

    assert out_port.signals == [s]
    assert in_port.signals == [s]
    assert s.source is out_port
    assert s.destination is in_port


class TestBits:
    def test_pos_int(self, signal):
        signal.bits = 10
        assert signal.bits == 10

    def test_bits_zero(self, signal):
        signal.bits = 0
        assert signal.bits == 0

    def test_bits_neg_int(self, signal):
        with pytest.raises(ValueError):
            signal.bits = -10

    def test_bits_complex(self, signal):
        with pytest.raises(TypeError):
            signal.bits = 2 + 4j

    def test_bits_float(self, signal):
        with pytest.raises(TypeError):
            signal.bits = 3.2

    def test_bits_pos_then_none(self, signal):
        signal.bits = 10
        signal.bits = None
        assert signal.bits is None
