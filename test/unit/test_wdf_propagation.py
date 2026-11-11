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
VALUES = [[2.5, -3.75, 5], [-3.75, 0, 1], [1 + 2j, 3 - 4j, -2 + 0.5j]]


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
            for values in VALUES:
                assert simplified.evaluate_outputs(values[:ports]) == pytest.approx(
                    original.evaluate_outputs(values[:ports])
                )
            multiplier_bound = 2 if adaptor_type is SeriesThreeportAdaptor else 1
            assert (
                len(simplified.find_by_type(ConstantMultiplication)) <= multiplier_bound
            )


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
@pytest.mark.parametrize("explicit_sink", [False, True])
@pytest.mark.parametrize("decompose", [False, True])
def test_partial_outputs(adaptor_type, coefficient, ports, explicit_sink, decompose):
    for count in range(1, ports):
        for kept in combinations(range(ports), count):
            inputs = [Input(f"x{i}") for i in range(ports)]
            adaptor = adaptor_type(coefficient, *inputs)
            if explicit_sink:
                for i in range(ports):
                    if i not in kept:
                        Sink().input(0).connect(adaptor.output(i))
            original = SFG(inputs, [Output(adaptor.output(i), f"y{i}") for i in kept])
            simplified = original.sink_propagation(decompose=decompose)
            assert len(simplified.find_by_type(adaptor_type)) == (0 if decompose else 1)
            assert not simplified.find_by_type(DontCare)
            assert [op.name for op in simplified.output_operations] == [
                f"y{i}" for i in kept
            ]
            assert len(original.find_by_type(adaptor_type)) == 1
            for values in VALUES:
                assert simplified.evaluate_outputs(values[:ports]) == pytest.approx(
                    original.evaluate_outputs(values[:ports])
                )


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
def test_live_outputs_unchanged(adaptor_type, coefficient, ports):
    inputs = [Input() for _ in range(ports)]
    adaptor = adaptor_type(coefficient, *inputs)
    original = SFG(inputs, [Output(port) for port in adaptor.outputs])
    assert original.find_by_type(adaptor_type)[0]._sink_propagation() is None
    assert original.find_by_type(adaptor_type)[0]._constant_propagation() is None


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
@pytest.mark.parametrize("decompose", [False, True])
def test_all_unused_outputs(adaptor_type, coefficient, ports, decompose):
    inputs = [Input() for _ in range(ports)]
    adaptor = adaptor_type(coefficient, *inputs)
    for port in adaptor.outputs:
        Sink().input(0).connect(port)
    simplified = SFG(inputs, []).sink_propagation(adaptor_type, decompose=decompose)
    assert not simplified.find_by_type(adaptor_type)
    assert len(simplified.find_by_type(Sink)) == ports


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
def test_nonzero_constant_input_unchanged(adaptor_type, coefficient, ports):
    inputs = [Input() for _ in range(ports - 1)]
    adaptor = adaptor_type(coefficient, Constant(2), *inputs)
    original = SFG(inputs, [Output(port) for port in adaptor.outputs])
    assert original.find_by_type(adaptor_type)[0]._constant_propagation() is None


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
@pytest.mark.parametrize("zero", [False, True])
def test_all_constants(adaptor_type, coefficient, ports, zero):
    values = [0] * ports if zero else VALUES[-1][:ports]
    adaptor = adaptor_type(coefficient, *(Constant(value) for value in values))
    original = SFG([], [Output(port) for port in adaptor.outputs])
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(adaptor_type)
    assert simplified.evaluate_outputs([]) == pytest.approx(
        original.evaluate_outputs([])
    )
    assert len(simplified.find_by_type(Constant)) == ports


@pytest.mark.parametrize(
    ("adaptor_type", "coefficient", "ports"),
    [
        (SymmetricTwoportAdaptor, -1, 2),
        (SymmetricTwoportAdaptor, 0, 2),
        (SymmetricTwoportAdaptor, 1, 2),
        (SeriesTwoportAdaptor, 0, 2),
        (SeriesTwoportAdaptor, 1, 2),
        (SeriesTwoportAdaptor, 2, 2),
        (ParallelTwoportAdaptor, 0, 2),
        (ParallelTwoportAdaptor, 1, 2),
        (ParallelTwoportAdaptor, 2, 2),
        (SeriesThreeportAdaptor, (0, 0), 3),
        (SeriesThreeportAdaptor, (0, 2), 3),
        (SeriesThreeportAdaptor, (2, 0), 3),
        (ReflectionFreeSeriesThreeportAdaptor, 0, 3),
        (ReflectionFreeSeriesThreeportAdaptor, 1, 3),
    ],
)
def test_zero_input_boundary_coefficients(adaptor_type, coefficient, ports):
    test_zero_inputs(adaptor_type, coefficient, ports)


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
@pytest.mark.parametrize("propagation", ["constant_propagation", "sink_propagation"])
def test_restricted_target(adaptor_type, coefficient, ports, propagation):
    inputs = [Input() for _ in range(ports)]
    sources = [Constant(0), *inputs[1:]]
    adaptor = adaptor_type(coefficient, *sources)
    original = SFG(inputs, [Output(adaptor.output(0))])
    simplified = getattr(original, propagation)(adaptor_type)
    assert not simplified.find_by_type(adaptor_type)
    assert simplified.evaluate_outputs(VALUES[-1][:ports]) == pytest.approx(
        original.evaluate_outputs(VALUES[-1][:ports])
    )


def test_reflection_free_output_needs_no_multiplier():
    inputs = [Input() for _ in range(3)]
    adaptor = ReflectionFreeSeriesThreeportAdaptor(0.25, *inputs)
    simplified = SFG(inputs, [Output(adaptor.output(1))]).sink_propagation()
    assert not simplified.find_by_type(ConstantMultiplication)
    assert len(simplified.find_by_type(Sink)) == 1
    assert simplified.evaluate_outputs([2, 3, 4]) == [-6]


def test_dependent_series_output_needs_one_multiplier():
    inputs = [Input() for _ in range(3)]
    adaptor = SeriesThreeportAdaptor((0.25, 1.25), *inputs)
    simplified = SFG(inputs, [Output(adaptor.output(2))]).sink_propagation()
    assert len(simplified.find_by_type(ConstantMultiplication)) == 1
    assert simplified.evaluate_outputs([2, 3, 4]) == [-0.5]


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
def test_sink_does_not_discard_shared_live_output(adaptor_type, coefficient, ports):
    inputs = [Input() for _ in range(ports)]
    adaptor = adaptor_type(coefficient, *inputs)
    Sink().input(0).connect(adaptor.output(0))
    original = SFG(inputs, [Output(adaptor.output(0))])
    simplified = original.sink_propagation()
    assert simplified.evaluate_outputs(VALUES[-1][:ports]) == pytest.approx(
        original.evaluate_outputs(VALUES[-1][:ports])
    )
    assert not simplified.find_by_type(adaptor_type)


@pytest.mark.parametrize("kept", [0, 1])
def test_sink_without_decomposition_allows_direct_wiring(kept):
    first, second = Input("x0"), Input("x1")
    adaptor = SymmetricTwoportAdaptor(0, first, second)
    Sink(adaptor.output(1 - kept))
    original = SFG([first, second], [Output(adaptor.output(kept), "y")])
    simplified = original.sink_propagation(SymmetricTwoportAdaptor, decompose=False)
    assert not simplified.find_by_type(SymmetricTwoportAdaptor)
    assert not simplified.find_by_type(DontCare)
    assert len(simplified.find_by_type(Sink)) == 1
    assert [op.name for op in simplified.input_operations] == ["x0", "x1"]
    assert [op.name for op in simplified.output_operations] == ["y"]
    assert simplified.evaluate_outputs([2, 3]) == original.evaluate_outputs([2, 3])
