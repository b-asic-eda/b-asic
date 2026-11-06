"""Decomposition control and constant multiplier chain simplification."""

import pytest

from b_asic.core_operations import (
    MAD,
    Addition,
    Constant,
    ConstantMultiplication,
    Multiplication,
    Negation,
    Subtraction,
)
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output
from b_asic.utility_operations import Sink
from b_asic.wdf_operations import SymmetricTwoportAdaptor
from test.unit.test_wdf_propagation import ADAPTORS


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
@pytest.mark.parametrize("decompose", [False, True])
def test_partial_adaptor_decomposition(adaptor_type, coefficient, ports, decompose):
    inputs = [Input() for _ in range(ports - 1)]
    adaptor = adaptor_type(coefficient, Constant(0), *inputs)
    original = SFG(inputs, [Output(port) for port in adaptor.outputs])
    result = original.constant_propagation(decompose=decompose)
    assert bool(result.find_by_type(adaptor_type)) is not decompose
    assert result.evaluate_outputs([2 + 3j] * (ports - 1)) == pytest.approx(
        original.evaluate_outputs([2 + 3j] * (ports - 1))
    )


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
def test_all_constant_adaptor_removed_without_decomposition(
    adaptor_type, coefficient, ports
):
    adaptor = adaptor_type(coefficient, *(Constant(0) for _ in range(ports)))
    original = SFG([], [Output(port) for port in adaptor.outputs])
    result = original.constant_propagation(decompose=False)
    assert not result.find_by_type(adaptor_type)
    assert result.evaluate_outputs([]) == [0] * ports


def test_identity_adaptor_removed_without_decomposition():
    first, second = Input(), Input()
    adaptor = SymmetricTwoportAdaptor(0, first, second)
    result = SFG(
        [first, second], [Output(port) for port in adaptor.outputs]
    ).constant_propagation(decompose=False)
    assert not result.find_by_type(SymmetricTwoportAdaptor)
    assert result.evaluate_outputs([2, 3]) == [3, 2]


@pytest.mark.parametrize("decompose", [False, True])
def test_arithmetic_decomposition(decompose):
    first, second = Input(), Input()
    operation = MAD(first, second, Constant(0))
    original = SFG([first, second], [Output(operation)])
    result = original.constant_propagation(decompose=decompose)
    assert bool(result.find_by_type(MAD)) is not decompose
    assert bool(result.find_by_type(Multiplication)) is decompose
    assert result.evaluate_outputs([2, 3]) == [6]


def test_removal_and_negation_without_decomposition():
    source = Input()
    original = SFG(
        [source],
        [
            Output(Addition(source, Constant(0))),
            Output(Subtraction(Constant(0), source)),
        ],
    )
    result = original.constant_propagation(decompose=False)
    assert not result.find_by_type(Addition)
    assert len(result.find_by_type(Subtraction)) == 1
    assert not result.find_by_type(Negation)
    assert result.evaluate_outputs([3]) == [3, -3]


@pytest.mark.parametrize("decompose", [False, True])
@pytest.mark.parametrize(
    ("coefficients", "product"),
    [([2, 3, 4], 24), ([2, 0.5], 1), ([1], 1), ([0], 0), ([2j, -0.5j], 1)],
)
def test_merge_multipliers(decompose, coefficients, product):
    source = Input()
    result = source
    for value in coefficients:
        result = ConstantMultiplication(value, result)
    original = SFG([source], [Output(result)])
    simplified = original.constant_propagation(decompose=decompose)
    multipliers = simplified.find_by_type(ConstantMultiplication)
    assert len(multipliers) == int(product not in (0, 1))
    if multipliers:
        assert multipliers[0].value == product
    assert simplified.evaluate_outputs([2 + 3j]) == pytest.approx([product * (2 + 3j)])
    assert len(original.find_by_type(ConstantMultiplication)) == len(coefficients)


def test_merge_preserves_shared_producers_and_sinks():
    source = Input()
    parent = ConstantMultiplication(2, source)
    child = ConstantMultiplication(3, parent)
    Sink(parent, name="termination")
    original = SFG([source], [Output(parent), Output(child)])
    result = original.constant_propagation(decompose=False)
    assert sorted(op.value for op in result.find_by_type(ConstantMultiplication)) == [
        2,
        6,
    ]
    assert len(result.find_by_type(Sink)) == 1
    assert result.evaluate_outputs([3]) == [6, 18]


def test_targeted_merge():
    source = Input()
    original = SFG(
        [source],
        [
            Output(
                ConstantMultiplication(
                    0.5, ConstantMultiplication(2, source), name="child"
                )
            )
        ],
    )
    target = next(
        op.graph_id
        for op in original.find_by_type(ConstantMultiplication)
        if op.name == "child"
    )
    result = original.constant_propagation(target, decompose=False)
    assert not result.find_by_type(ConstantMultiplication)
    assert result.evaluate_outputs([3]) == [3]
