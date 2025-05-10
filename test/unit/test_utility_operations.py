"""B-ASIC test suite for utility operations."""

import pytest

from b_asic import (
    SFG,
    Addition,
    Butterfly,
    DontCare,
    Input,
    Output,
    Sink,
)


class TestDontCare:
    def test_create_sfg_with_dontcare(self):
        i1 = Input()
        dc = DontCare()
        a = Addition(i1, dc)
        o = Output(a)
        sfg = SFG([i1], [o])

        assert sfg.output_count == 1
        assert sfg.input_count == 1

        assert sfg.evaluate_output(0, [0]) == 0
        assert sfg.evaluate_output(0, [1]) == 1

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
        bfly = Butterfly()
        sfg = bfly.to_sfg()
        s = Sink()
        with pytest.warns(UserWarning, match="Output port out0 has been removed"):
            sfg1 = sfg.replace_operation(s, "out0")

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
