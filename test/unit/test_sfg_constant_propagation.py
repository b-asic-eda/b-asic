"""Zero propagation and graph reconnection tests."""

from collections import Counter
from itertools import product

import numpy as np
import pytest

from b_asic.core_operations import (
    MAD,
    MADS,
    Addition,
    AddSub,
    Constant,
    ConstantMultiplication,
    Division,
    ImaginaryMultiplication,
    LeftShift,
    Max,
    Min,
    Multiplication,
    Negation,
    Reciprocal,
    RightShift,
    Shift,
    Subtraction,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.operation import Operation
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


@pytest.mark.parametrize(
    ("operation_type", "properties"),
    [
        (MAD, {"do_add": True}),
        (MAD, {"do_add": False}),
        (MADS, {"is_add": True, "do_addsub": True}),
        (MADS, {"is_add": False, "do_addsub": True}),
        (MADS, {"is_add": True, "do_addsub": False}),
        (MADS, {"is_add": False, "do_addsub": False}),
    ],
)
@pytest.mark.parametrize("zeros", list(product((False, True), repeat=3)))
def test_mad_mads_rules(operation_type, properties, zeros):
    inputs = [Input(f"x{i}") for i in range(3)]
    sources = [
        Constant(0) if zero else source
        for source, zero in zip(inputs, zeros, strict=True)
    ]
    operation = operation_type(
        in0=sources[0], in1=sources[1], in2=sources[2], **properties
    )
    original = SFG(inputs, [Output(operation)])
    simplified = original.constant_propagation()
    enabled = properties.get("do_add", properties.get("do_addsub"))
    assert len(simplified.find_by_type(operation_type)) == int(
        not any(zeros) and enabled
    )
    assert simplified.input_count == 3
    for values in ([2, 3, 5], [-2, 4, -3], [2 + 1j, -3 + 2j, 4 - 2j]):
        assert simplified.evaluate_outputs(values) == pytest.approx(
            original.evaluate_outputs(values)
        )
    # Private hooks return independent graphs with the original port ordering.
    (original_op,) = original.find_by_type(operation_type)
    replacement = original_op._constant_propagation()
    if replacement is not None:
        assert replacement.input_count == 3
        assert replacement.output_count == 1
        arguments = [
            0 if zero else value for value, zero in zip([2, 3, 5], zeros, strict=True)
        ]
        assert replacement.evaluate_outputs(arguments) == original.evaluate_outputs(
            [2, 3, 5]
        )
    assert len(original.find_by_type(operation_type)) == 1


def _target_sfg():
    source = Input("x")
    zero = Constant(0)
    first = Addition(source, zero, name="first")
    second = Addition(first, zero, name="second")
    third = Subtraction(second, zero, name="third")
    return SFG([source], [Output(third)])


@pytest.mark.parametrize("kind", ["type", "id", "list", "iterator", "empty"])
def test_target_selection(kind):
    original = _target_sfg()
    first_id = original.find_by_name("first")[0].graph_id
    second_id = original.find_by_name("second")[0].graph_id
    targets = {
        "type": Addition,
        "id": first_id,
        "list": [first_id, second_id],
        "iterator": (graph_id for graph_id in (first_id, second_id)),
        "empty": iter(()),
    }
    simplified = original.constant_propagation(target=targets[kind])
    remaining = {op.name for op in simplified.find_by_type(Addition)}
    assert remaining == (
        {"first", "second"}
        if kind == "empty"
        else {"second"}
        if kind == "id"
        else set()
    )
    assert len(simplified.find_by_type(Subtraction)) == 1
    assert simplified.evaluate_outputs([7]) == [7]
    assert len(original.find_by_type(Addition)) == 2


def test_selection_controls_cascaded_propagation():
    source = Input()
    zero_product = Multiplication(source, Constant(0))
    original = SFG([source], [Output(Addition(zero_product, Constant(7)))])
    partial = original.constant_propagation(Multiplication)
    assert not partial.find_by_type(Multiplication)
    assert len(partial.find_by_type(Addition)) == 1
    assert partial.evaluate_outputs([3]) == [7]
    assert not original.constant_propagation(Operation).find_by_type(Addition)


@pytest.mark.parametrize("target", [42, str, [Addition], ["add0", 42]])
def test_invalid_target_type(target):
    with pytest.raises(TypeError, match="target"):
        _target_sfg().constant_propagation(target)


def test_unknown_target_graph_id():
    with pytest.raises(ValueError, match="missing"):
        _target_sfg().constant_propagation(iter(["missing"]))


def test_signal_target_graph_id():
    original = _target_sfg()
    signal_id = original.output_operations[0].input(0).signals[0].graph_id
    with pytest.raises(TypeError, match="does not identify an operation"):
        original.constant_propagation(signal_id)


def test_custom_operation_hook():
    class IdentityNegation(Negation):
        # This operation is deliberately an identity, demonstrating that the
        # driver dispatches to operation hooks without knowing their types.
        def evaluate(self, a, data_type=None):
            return a

        def _constant_propagation(self):
            source = Input()
            return SFG([source], [Output(source)])

    source = Input()
    original = SFG([source], [Output(IdentityNegation(source))])
    simplified = original.constant_propagation(IdentityNegation)
    assert not simplified.find_by_type(IdentityNegation)
    assert simplified.evaluate_outputs([3]) == original.evaluate_outputs([3])


def test_default_operation_hook_returns_none():
    assert Input()._constant_propagation() is None
    source = Input()
    assert Multiplication(source, source)._constant_propagation() is None
    assert Addition(source, source)._constant_propagation() is None


@pytest.mark.parametrize(
    "operation_type", [Negation, ImaginaryMultiplication, LeftShift, RightShift, Shift]
)
def test_zero_propagates_through_unary_replacements(operation_type):
    source = Input()
    product = Multiplication(source, Constant(0))
    unary = operation_type(in0=product)
    original = SFG([source], [Output(Addition(unary, Constant(7)))])
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(operation_type)
    assert not simplified.find_by_type(Addition)
    assert simplified.evaluate_outputs([3]) == [7]


@pytest.mark.parametrize(
    ("operation_type", "values", "properties"),
    [
        (Addition, [2, 3], {}),
        (
            Addition,
            [12, 8],
            {"in0_scale": 1, "in1_scale": 2, "out0_scale": 1, "mul_j": True},
        ),
        (Subtraction, [2, 3], {}),
        (AddSub, [2, 3], {"is_add": False}),
        (Multiplication, [2 + 1j, 3 - 2j], {}),
        (Division, [6, 2], {}),
        (Division, [1, 0], {}),
        (Reciprocal, [4], {}),
        (Negation, [7], {}),
        (ConstantMultiplication, [7], {"value": 3}),
        (RightShift, [8], {"value": 2}),
        (LeftShift, [3], {"value": 2}),
        (Shift, [3], {"value": -2}),
        (ImaginaryMultiplication, [2], {}),
        (Min, [2, 3], {}),
        (Max, [2, 3], {}),
        (MAD, [2, 3, 4], {}),
        (MAD, [2, 3, 4], {"do_add": False}),
        (MADS, [2, 3, 4], {"is_add": True}),
        (MADS, [2, 3, 4], {"is_add": False}),
        (MADS, [2, 3, 4], {"is_add": False, "do_addsub": False}),
        (R2Butterfly, [2 + 1j, 3 - 2j], {}),
    ],
)
def test_all_constant_inputs(operation_type, values, properties):
    operation = operation_type(
        **{f"in{i}": Constant(value) for i, value in enumerate(values)},
        **properties,
    )
    expected = operation.evaluate_outputs(values)
    original = SFG(outputs=[Output(port) for port in operation.outputs])
    simplified = original.constant_propagation()
    assert simplified.evaluate_outputs([]) == pytest.approx(expected)
    assert not simplified.find_by_type(operation_type)
    assert len(simplified.find_by_type(Constant)) == operation.output_count
    assert len(original.find_by_type(operation_type)) == 1
    # The private hook itself returns a full replacement, including every port.
    replacement = operation._constant_propagation()
    assert replacement.input_count == operation.input_count
    assert replacement.output_count == operation.output_count
    assert replacement.evaluate_outputs(values) == pytest.approx(expected)


def test_all_constant_chain_and_partial_selection():
    add = Addition(Constant(2), Constant(3), name="add")
    mul = Multiplication(add, Constant(4), name="mul")
    original = SFG(outputs=[Output(mul)])
    partial = original.constant_propagation(Addition)
    assert not partial.find_by_type(Addition)
    assert len(partial.find_by_type(Multiplication)) == 1
    for target in (
        None,
        (
            op.graph_id
            for op in original.find_by_type(Addition)
            + original.find_by_type(Multiplication)
        ),
    ):
        simplified = original.constant_propagation(target)
        (constant,) = simplified.find_by_type(Constant)
        assert constant.value == 20
        assert not simplified.find_by_type(Addition)
        assert not simplified.find_by_type(Multiplication)
        assert simplified.evaluate_outputs([]) == [20]


@pytest.mark.parametrize("value", [5, 2 + 3j])
def test_constant_delay_output(value):
    original = SFG(outputs=[Output(Delay(Constant(value), initial_value=value))])
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(Delay)
    assert simplified.evaluate_outputs([]) == [value]


def test_delay_with_nonzero_constant_input_and_transient():
    original = SFG(outputs=[Output(Delay(Constant(5), initial_value=0))])
    simplified = original.constant_propagation()
    assert len(simplified.find_by_type(Delay)) == 1
    simulation = Simulation(simplified)
    simulation.run_for(3)
    np.testing.assert_array_equal(simulation.results["out0"], [0, 5, 5])


def test_all_constant_nested_sfg():
    first, second = Input(), Input()
    inner = SFG([first, second], [Output(Addition(first, second))])
    nested = inner(Constant(2), Constant(3))
    original = SFG(outputs=[Output(nested)])
    (original_nested,) = original.find_by_type(SFG)
    before = [op.value for op in original_nested.input_operations]
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(SFG)
    assert simplified.evaluate_outputs([]) == [5]
    assert [op.value for op in original_nested.input_operations] == before


def test_constant_inputs_do_not_erase_nested_delay_transient():
    source = Input()
    inner = SFG([source], [Output(Delay(source, initial_value=0))])
    original = SFG(outputs=[Output(inner(Constant(5)))])
    simplified = original.constant_propagation()
    assert len(simplified.find_by_type(SFG)) == 1


def test_invalid_constant_expression_is_retained():
    original = SFG(outputs=[Output(Min(Constant(1j), Constant(2)))])
    simplified = original.constant_propagation()
    assert len(simplified.find_by_type(Min)) == 1
