"""Algebraic WDF adaptor simplifications preserve their evaluated outputs."""

from itertools import combinations

import pytest

from b_asic.core_operations import Constant, ConstantMultiplication
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output
from b_asic.utility_operations import DontCare, Sink
from b_asic.wdf_operations import (
    ParallelTwoportAdaptor,
    ReflectionFreeSeriesThreeportAdaptor,
    SeriesThreeportAdaptor,
    SeriesTwoportAdaptor,
    SymmetricTwoportAdaptor,
)

ADAPTORS = [
    (SymmetricTwoportAdaptor, -0.25, 2),
    (SeriesTwoportAdaptor, 0.75, 2),
    (ParallelTwoportAdaptor, 0.75, 2),
    (SeriesThreeportAdaptor, (0.25, 1.25), 3),
    (ReflectionFreeSeriesThreeportAdaptor, 0.25, 3),
]
VALUES = [2.5, -3.75, 1 + 2j]


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
def test_zero_inputs(adaptor_type, coefficient, ports):
    for count in range(1, ports):
        for zeros in combinations(range(ports), count):
            inputs = [Input(f"x{i}") for i in range(ports)]
            sources = [
                Constant(0) if i in zeros else source for i, source in enumerate(inputs)
            ]
            adaptor = adaptor_type(coefficient, *sources)
            original = SFG(
                inputs,
                [Output(port, f"y{i}") for i, port in enumerate(adaptor.outputs)],
            )
            simplified = original.constant_propagation()
            assert not simplified.find_by_type(adaptor_type)
            assert len(original.find_by_type(adaptor_type)) == 1
            assert [op.name for op in simplified.input_operations] == [
                f"x{i}" for i in range(ports)
            ]
            assert [op.name for op in simplified.output_operations] == [
                f"y{i}" for i in range(ports)
            ]
            for value in VALUES:
                values = [value * (i + 1) for i in range(ports)]
                assert simplified.evaluate_outputs(values) == pytest.approx(
                    original.evaluate_outputs(values)
                )
            multiplier_bound = 2 if adaptor_type is SeriesThreeportAdaptor else 1
            assert (
                len(simplified.find_by_type(ConstantMultiplication)) <= multiplier_bound
            )


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
@pytest.mark.parametrize("explicit_sink", [False, True])
def test_partial_outputs(adaptor_type, coefficient, ports, explicit_sink):
    for count in range(1, ports):
        for kept in combinations(range(ports), count):
            inputs = [Input(f"x{i}") for i in range(ports)]
            adaptor = adaptor_type(coefficient, *inputs)
            if explicit_sink:
                for i in range(ports):
                    if i not in kept:
                        Sink().input(0).connect(adaptor.output(i))
            original = SFG(inputs, [Output(adaptor.output(i), f"y{i}") for i in kept])
            simplified = original.sink_propagation()
            assert not simplified.find_by_type(adaptor_type)
            assert not simplified.find_by_type(DontCare)
            assert [op.name for op in simplified.output_operations] == [
                f"y{i}" for i in kept
            ]
            assert len(original.find_by_type(adaptor_type)) == 1
            for value in VALUES:
                values = [value * (i + 1) for i in range(ports)]
                assert simplified.evaluate_outputs(values) == pytest.approx(
                    original.evaluate_outputs(values)
                )


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
def test_live_outputs_unchanged(adaptor_type, coefficient, ports):
    inputs = [Input() for _ in range(ports)]
    adaptor = adaptor_type(coefficient, *inputs)
    original = SFG(inputs, [Output(port) for port in adaptor.outputs])
    assert original.find_by_type(adaptor_type)[0]._sink_propagation() is None
    assert original.find_by_type(adaptor_type)[0]._constant_propagation() is None


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
def test_all_unused_outputs(adaptor_type, coefficient, ports):
    inputs = [Input() for _ in range(ports)]
    adaptor = adaptor_type(coefficient, *inputs)
    for port in adaptor.outputs:
        Sink().input(0).connect(port)
    simplified = SFG(inputs, []).sink_propagation()
    assert not simplified.find_by_type(adaptor_type)
    assert len(simplified.find_by_type(Sink)) == ports


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
def test_nonzero_constant_input_unchanged(adaptor_type, coefficient, ports):
    inputs = [Input() for _ in range(ports - 1)]
    adaptor = adaptor_type(coefficient, Constant(2), *inputs)
    original = SFG(inputs, [Output(port) for port in adaptor.outputs])
    assert original.find_by_type(adaptor_type)[0]._constant_propagation() is None
