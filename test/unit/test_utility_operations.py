"""B-ASIC test suite for utility operations."""

import apytypes as apy
import pytest

from b_asic import (
    SFG,
    Addition,
    DontCare,
    Input,
    Output,
    R2Butterfly,
    Sink,
)
from b_asic.utility_operations import ComplexToReal, RealToComplex


@pytest.mark.parametrize("value", [0, 2.5, 3 + 4j, -2.5 - 1.25j])
def test_complex_interface_round_trip(value):
    parts = ComplexToReal().evaluate_outputs([value])
    assert parts == [value.real, value.imag]
    assert RealToComplex().evaluate(*parts) == value


def test_complex_interface_apyfixed():
    value = apy.APyCFixed.from_complex(2.5 - 1.25j, int_bits=4, frac_bits=4)
    real, imag = ComplexToReal().evaluate(value)
    assert isinstance(real, apy.APyFixed)
    assert isinstance(imag, apy.APyFixed)
    assert RealToComplex().evaluate(real, imag) == 2.5 - 1.25j


def test_complex_interface_conversion_hooks():
    assert ComplexToReal().to_sfg().evaluate(3 + 4j) == [3, 4]
    assert RealToComplex().to_sfg().evaluate(3, 4) == 3 + 4j
    splitter = ComplexToReal().complex_to_real()
    assert splitter.evaluate(3, 4) == [3, 0, 4, 0]
    joiner = RealToComplex().complex_to_real()
    assert joiner.evaluate(3, 0, 4, 0) == [3, 4]


class TestDontCare:
    def test_create_sfg_with_dontcare(self):
        i1 = Input()
        dc = DontCare()
        a = Addition(i1, dc)
        o = Output(a)
        sfg = SFG([i1], [o])

        assert sfg.output_count == 1
        assert sfg.input_count == 1

    def test_dontcare_latency_getter(self):
        test_operation = DontCare()
        assert test_operation.latency == 0

    def test_dontcare_repr(self):
        test_operation = DontCare()
        assert repr(test_operation) == "DontCare()"

    def test_dontcare_str(self):
        test_operation = DontCare()
        assert str(test_operation) == "dontcare"


class TestSink:
    def test_create_sfg_with_sink(self):
        bfly = R2Butterfly()
        sfg = bfly.to_sfg()
        s = Sink()
        with pytest.warns(UserWarning, match=r"Output port out0 has been removed"):
            sfg1 = sfg.replace("out0", s)

        assert sfg1.output_count == 1
        assert sfg1.input_count == 2

        assert sfg.evaluate_output(1, [0, 1]) == sfg1.evaluate_output(0, [0, 1])

    def test_sink_latency_getter(self):
        test_operation = Sink()
        assert test_operation.latency == 0

    def test_sink_repr(self):
        test_operation = Sink()
        assert repr(test_operation) == "Sink()"

    def test_sink_str(self):
        test_operation = Sink()
        assert str(test_operation) == "sink"
