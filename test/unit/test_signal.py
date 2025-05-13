"""
B-ASIC test suit for the signal module which consists of the Signal class.
"""

import pytest

from b_asic.core_operations import (
    Addition,
    Constant,
    ConstantMultiplication,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.port import InputPort, OutputPort
from b_asic.signal import Signal
from b_asic.special_operations import Input


def test_signal_creation_and_disconnection_and_connection_changing():
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
        with pytest.raises(ValueError, match="Bits cannot be negative"):
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


def test_create_from_single_input_single_output():
    cm1 = ConstantMultiplication(0.5, name="Foo")
    cm2 = ConstantMultiplication(1.5, name="Bar")
    signal = Signal(cm1, cm2)
    assert signal.destination.operation.name == "Bar"
    assert signal.source.operation.name == "Foo"

    add1 = Addition(name="Zig")

    signal.set_source(add1)

    assert signal.source.operation.name == "Zig"


def test_signal_is_constant():
    c = Constant(0.5, name="Foo")
    signal = Signal(c)
    assert signal.is_constant

    i = Input()
    signal = Signal(i)
    assert not signal.is_constant


def test_signal_errors():
    cm1 = ConstantMultiplication(0.5, name="Foo")
    add1 = Addition(name="Zig")
    with pytest.raises(
        TypeError,
        match=(
            "Addition cannot be used as an output destination because it has"
            " more than one input"
        ),
    ):
        _ = Signal(cm1, add1)

    bf = R2Butterfly()
    with pytest.raises(
        TypeError,
        match=(
            "R2Butterfly cannot be used as an input source because it has more"
            " than one output"
        ),
    ):
        _ = Signal(bf, cm1)

    cm2 = ConstantMultiplication(1.5, name="Bar")
    signal = Signal(cm1, cm2)
    with pytest.raises(
        TypeError,
        match=(
            "Addition cannot be used as an output destination because it has"
            " more than one input"
        ),
    ):
        signal.set_destination(add1)

    with pytest.raises(
        TypeError,
        match=(
            "R2Butterfly cannot be used as an input source because it has more"
            " than one output"
        ),
    ):
        signal.set_source(bf)

    signal = Signal()
    with pytest.raises(ValueError, match="Signal source not set"):
        _ = signal.is_constant
