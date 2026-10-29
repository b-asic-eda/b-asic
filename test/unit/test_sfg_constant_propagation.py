"""Zero propagation and graph reconnection tests."""

from collections import Counter

import numpy as np
import pytest

from b_asic.core_operations import (
    Addition,
    AddSub,
    Constant,
    ConstantMultiplication,
    ImaginaryMultiplication,
    LeftShift,
    Multiplication,
    Negation,
    RightShift,
    Subtraction,
)
from b_asic.sfg import SFG
from b_asic.sfg_generators import strassen_matrix_multiplication
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay, Input, Output

ARITHMETIC = [
    (Addition, {}),
    (Subtraction, {}),
    (AddSub, {"is_add": True}),
    (AddSub, {"is_add": False}),
]


def _arithmetic_sfg(operation_type, zero_index, **properties):
    source = Input("x")
    inputs = [source, source]
    inputs[zero_index] = Constant(0)
    operation = operation_type(
        in0=inputs[0], in1=inputs[1], name="arithmetic", **properties
    )
    return SFG([source], [Output(operation, "result")], name="zero propagation")


@pytest.mark.parametrize(("operation_type", "properties"), ARITHMETIC)
@pytest.mark.parametrize("zero_index", [0, 1])
def test_add_sub_zero(operation_type, properties, zero_index):
    original = _arithmetic_sfg(operation_type, zero_index, **properties)
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(operation_type)
    assert not simplified.find_by_type(Constant)
    subtract = operation_type is Subtraction or properties.get("is_add") is False
    assert len(simplified.find_by_type(Negation)) == int(subtract and zero_index == 0)
    for value in [-7, 0, 4, 2 + 3j]:
        assert simplified.evaluate_outputs([value]) == original.evaluate_outputs(
            [value]
        )
    assert simplified.name == original.name
    assert [op.name for op in simplified.input_operations] == ["x"]
    assert [op.name for op in simplified.output_operations] == ["result"]
    assert len(original.find_by_type(operation_type)) == 1


@pytest.mark.parametrize(("operation_type", "properties"), ARITHMETIC)
@pytest.mark.parametrize("zero_index", [0, 1])
@pytest.mark.parametrize(
    ("in0_scale", "in1_scale", "out0_scale"),
    [(1, 2, 1), (0, 2, 0), (2, 0, 2), (0, 0, 0)],
)
@pytest.mark.parametrize("mul_j", [False, True])
def test_scaled_add_sub_zero(
    operation_type, properties, zero_index, in0_scale, in1_scale, out0_scale, mul_j
):
    original = _arithmetic_sfg(
        operation_type,
        zero_index,
        in0_scale=in0_scale,
        in1_scale=in1_scale,
        out0_scale=out0_scale,
        mul_j=mul_j,
        **properties,
    )
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(operation_type)
    surviving_scale = in1_scale if zero_index == 0 else in0_scale
    assert len(simplified.find_by_type(RightShift)) == sum(
        scale > 0 for scale in (surviving_scale, out0_scale)
    )
    assert len(simplified.find_by_type(LeftShift)) == sum(
        scale < 0 for scale in (surviving_scale, out0_scale)
    )
    assert len(simplified.find_by_type(ImaginaryMultiplication)) == int(
        mul_j and zero_index == 0
    )
    for value in [-11.25, 9, 3.5 + 2j]:
        assert simplified.evaluate_outputs([value]) == pytest.approx(
            original.evaluate_outputs([value])
        )


def test_scaled_subtraction_preserves_unary_order():
    original = _arithmetic_sfg(Subtraction, 0, in1_scale=1, mul_j=True)
    # Generic operation parameters can encode a leftward output scale.
    original.find_by_type(Subtraction)[0].set_param("out0_scale", -2)
    simplified = original.constant_propagation()
    operation = simplified.output_operations[0].input(0).connected_source.operation
    for operation_type in (
        LeftShift,
        Negation,
        ImaginaryMultiplication,
        RightShift,
        Input,
    ):
        assert isinstance(operation, operation_type)
        if operation.input_count:
            operation = operation.input(0).connected_source.operation


@pytest.mark.parametrize(("operation_type", "properties"), ARITHMETIC)
def test_both_inputs_zero(operation_type, properties):
    original = SFG(
        outputs=[Output(operation_type(in0=Constant(0), in1=Constant(0), **properties))]
    )
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(operation_type)
    assert simplified.evaluate_outputs([]) == [0]


@pytest.mark.parametrize("zero_index", [0, 1])
def test_multiplication_by_zero(zero_index):
    original = _arithmetic_sfg(Multiplication, zero_index)
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(Multiplication)
    assert simplified.input_count == 1
    assert simplified.evaluate_outputs([7]) == [0]


@pytest.mark.parametrize("zero_coefficient", [False, True])
def test_constant_multiplication_by_zero(zero_coefficient):
    source = Input("x")
    operation = ConstantMultiplication(
        0 if zero_coefficient else 7,
        source if zero_coefficient else Constant(0),
    )
    original = SFG([source], [Output(operation)])
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(ConstantMultiplication)
    assert simplified.input_count == 1
    assert simplified.evaluate_outputs([7]) == [0]


def test_chained_propagation_and_dead_branches():
    x, y, z = Input("x"), Input("y"), Input("z")
    zero = Constant(0)
    dead = Addition(x, Constant(5))
    product = Multiplication(dead, zero)
    result = Addition(Multiplication(Addition(product, y), zero), Subtraction(z, zero))
    original = SFG([x, y, z], [Output(result, "result")])
    simplified = original.constant_propagation()
    assert [op.name for op in simplified.input_operations] == ["x", "y", "z"]
    assert not any(
        isinstance(op, (Addition, Subtraction, Multiplication, Constant))
        for op in simplified.operations
    )
    assert simplified.evaluate_outputs([3, 4, 5]) == [5]
    assert original.evaluate_outputs([3, 4, 5]) == [5]
    assert original.find_by_type(Multiplication)


def test_shared_producer_and_multiple_consumers():
    x, y = Input("x"), Input("y")
    shared = Addition(x, y)
    result = Addition(shared, Constant(0))
    original = SFG(
        [x, y],
        [Output(result), Output(Negation(result)), Output(Multiplication(shared, y))],
    )
    simplified = original.constant_propagation()
    assert len(simplified.find_by_type(Addition)) == 1
    assert len(simplified.find_by_type(Multiplication)) == 1
    assert simplified.evaluate_outputs([2, 3]) == [5, -5, 15]


def test_general_constant_value_propagated():
    original = SFG(outputs=[Output(Addition(Constant(0), Constant(7)))])
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(Addition)
    (constant,) = simplified.find_by_type(Constant)
    assert constant.value == 7
    assert simplified.evaluate_outputs([]) == [7]


def test_preserves_delay_initial_state():
    delay = Delay(Constant(0), initial_value=7)
    original = SFG(outputs=[Output(Addition(delay, Constant(0)))])
    simplified = original.constant_propagation()
    assert len(simplified.find_by_type(Delay)) == 1
    simulation = Simulation(simplified)
    simulation.run_for(3)
    np.testing.assert_array_equal(simulation.results["out0"], [7, 0, 0])


def test_propagation_with_feedback():
    source = Input()
    delay = Delay(initial_value=7)
    add = Addition(source, delay)
    delay <<= add
    original = SFG([source], [Output(Addition(add, Constant(0)))])
    simplified = original.constant_propagation()
    assert len(simplified.find_by_type(Addition)) == 1
    simulation = Simulation(simplified, [[1, 2, 3]])
    simulation.run_for(3)
    np.testing.assert_array_equal(simulation.results["out0"], [8, 10, 13])


def test_padded_strassen_and_idempotence():
    original = strassen_matrix_multiplication(3, 5, 2)
    simplified = original.constant_propagation()
    again = simplified.constant_propagation()
    assert len(simplified.find_by_type(Multiplication)) < len(
        original.find_by_type(Multiplication)
    )
    assert Counter(type(op) for op in simplified.operations) == Counter(
        type(op) for op in again.operations
    )
    a = np.arange(15).reshape(3, 5) - 4
    b = np.arange(10).reshape(5, 2) - 3
    inputs = [*a.ravel().tolist(), *b.ravel().tolist()]
    np.testing.assert_allclose(
        np.array(simplified.evaluate_outputs(inputs)).reshape(3, 2), a @ b
    )
    assert [op.name for op in simplified.input_operations] == [
        op.name for op in original.input_operations
    ]
    assert [op.name for op in simplified.output_operations] == [
        op.name for op in original.output_operations
    ]


def test_zero_initialized_delay_propagates_zero():
    original = SFG(outputs=[Output(Delay(Constant(0)))])
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(Delay)
    assert simplified.evaluate_outputs([]) == [0]


def test_outgoing_signal_metadata_preserved():
    from b_asic.signal import Signal

    source = Input()
    addition = Addition(source, Constant(0))
    output = Output()
    Signal(addition, output, bits=12, name="result_signal")
    simplified = SFG([source], [output]).constant_propagation()
    signal = simplified.output_operations[0].input(0).signals[0]
    assert signal.name == "result_signal"
    assert signal.bits == 12
    assert signal.source.operation is simplified.input_operations[0]


def test_nonzero_arithmetic_unchanged():
    source = Input()
    original = SFG([source], [Output(Addition(source, Constant(1e-20)))])
    simplified = original.constant_propagation()
    assert len(simplified.find_by_type(Addition)) == 1
    assert simplified.evaluate_outputs([0]) == [1e-20]
