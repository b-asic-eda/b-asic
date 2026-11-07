"""Algebraic graph joins and operation expansion, including shared consumers."""

from itertools import product

import pytest

from b_asic.core_operations import (
    MAD,
    MADS,
    Addition,
    AddSub,
    Comparator,
    Constant,
    ConstantMultiplication,
    ImaginaryMultiplication,
    LeftShift,
    Max,
    Min,
    Multiplication,
    Negation,
    RightShift,
    Shift,
    Subtraction,
)
from b_asic.fft_operations import (
    R2Butterfly,
    R2DIFButterfly,
    R2DITButterfly,
    R2TFButterfly,
)
from b_asic.sfg import SFG
from b_asic.signal import Signal
from b_asic.special_operations import Input, Output

VALUES = [-8, 0, 3.5, 2 + 3j]
SCALARS = [
    (ConstantMultiplication, (3 - 2j,)),
    (Negation, ()),
    (ImaginaryMultiplication, ()),
    (RightShift, (2,)),
    (LeftShift, (1,)),
    (Shift, (-2,)),
]


def equivalent(original, transformed, real=False):
    assert transformed.name == original.name
    assert [op.name for op in transformed.input_operations] == [
        op.name for op in original.input_operations
    ]
    assert [op.name for op in transformed.output_operations] == [
        op.name for op in original.output_operations
    ]
    values = VALUES[:3] if real else VALUES
    for inputs in product(values, repeat=original.input_count):
        assert transformed.evaluate_outputs(inputs) == pytest.approx(
            original.evaluate_outputs(inputs)
        )


def graph(inputs, results):
    return SFG(
        inputs,
        [Output(result, name=f"result{i}") for i, result in enumerate(results)],
        name="patterns",
    )


@pytest.mark.parametrize("first", SCALARS)
@pytest.mark.parametrize("second", SCALARS)
@pytest.mark.parametrize("direction", ["forward", "backward"])
def test_scalar_chains(first, second, direction):
    x = Input("x")
    left = first[0](*first[1], x, name="first")
    right = second[0](*second[1], left, name="second")
    original = graph([x], [right, left])
    target = original.find_by_name("first" if direction == "forward" else "second")[0]
    joined = original.join(target.graph_id, direction)
    equivalent(original, joined)
    # Keep the externally visible intermediate value.
    assert len(original.operations) == 5
    assert joined.find_by_name("first")


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("value", [0, 1, -1, 1j, 3 - 2j])
def test_constant_multiplication_join(index, value):
    x = Input("x")
    constant = Constant(value)
    args = [x, x]
    args[index] = constant
    original = graph([x], [Multiplication(*args)])
    joined = original.join(original.find_by_type(Constant)[0].graph_id, "forward")
    assert not joined.find_by_type(Multiplication)
    equivalent(original, joined)


@pytest.mark.parametrize("operation_type", [Addition, Subtraction, AddSub])
@pytest.mark.parametrize("index", [0, 1, "both"])
@pytest.mark.parametrize("scalar", SCALARS[1:])
@pytest.mark.parametrize("mul_j", [False, True])
def test_scalar_arithmetic_inputs(operation_type, index, scalar, mul_j):
    x, y = Input("x"), Input("y")
    scaled = scalar[0](*scalar[1], x, name="factor")
    args = [x, y]
    if index == "both":
        args = [scaled, scaled]
    else:
        args[index] = scaled
    operation = operation_type(
        in0=args[0], in1=args[1], mul_j=mul_j, in0_scale=3, in1_scale=4, out0_scale=1
    )
    original = graph([x, y], [operation, scaled])
    joined = original.join(original.find_by_name("factor")[0].graph_id, "forward")
    equivalent(original, joined)
    assert len(joined.find_by_type(operation_type)) <= 1


@pytest.mark.parametrize("operation_type", [Addition, Subtraction, AddSub])
@pytest.mark.parametrize("scalar", [(RightShift, (2,)), (Shift, (-1,))])
def test_output_shift_join(operation_type, scalar):
    x, y = Input("x"), Input("y")
    operation = operation_type(in0=x, in1=y, out0_scale=2, mul_j=True)
    original = graph([x, y], [scalar[0](*scalar[1], operation), operation])
    target = original.find_by_type(operation_type)[0]
    joined = original.join(target.graph_id, "forward")
    equivalent(original, joined)
    assert not joined.find_by_type(scalar[0])


@pytest.mark.parametrize("operation_type", [Addition, Subtraction, AddSub])
@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("direction", ["forward", "backward"])
def test_multiply_arithmetic_fusion(operation_type, index, direction):
    x, y, z = Input("x"), Input("y"), Input("z")
    multiplication = Multiplication(x, y, name="product")
    args = [z, z]
    args[index] = multiplication
    operation = operation_type(in0=args[0], in1=args[1], name="arithmetic")
    original = graph([x, y, z], [operation, multiplication])
    target = original.find_by_name(
        "product" if direction == "forward" else "arithmetic"
    )[0]
    joined = original.join(target.graph_id, direction)
    equivalent(original, joined)
    assert not joined.find_by_type(operation_type)
    assert len(joined.find_by_type(MAD)) + len(joined.find_by_type(MADS)) == 1
    assert len(joined.find_by_type(Multiplication)) == 1


@pytest.mark.parametrize("is_add", [False, True])
@pytest.mark.parametrize("mul_j", [False, True])
@pytest.mark.parametrize(
    "substitute", [Addition, Subtraction, Shift, ImaginaryMultiplication]
)
def test_addsub_parameter_extraction(is_add, mul_j, substitute):
    x, y = Input("x"), Input("y")
    operation = AddSub(
        is_add, x, y, mul_j=mul_j, in0_scale=2, in1_scale=1, out0_scale=3
    )
    original = graph([x, y], [operation])
    expanded = original.rewrite(substitute, AddSub)
    equivalent(original, expanded)
    assert len(expanded.find_by_type(RightShift)) == 3
    for arithmetic in expanded.find_by_type(AddSub):
        assert not any(
            (
                arithmetic.in0_scale,
                arithmetic.in1_scale,
                arithmetic.out0_scale,
                arithmetic.mul_j,
            )
        )


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("substitute", [Multiplication, Addition, AddSub, MADS])
def test_mad_expansion(enabled, substitute):
    inputs = [Input(str(i)) for i in range(3)]
    original = graph(inputs, [MAD(*inputs, do_add=enabled)])
    expanded = original.rewrite(substitute, MAD)
    equivalent(original, expanded)
    assert not expanded.find_by_type(MAD)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("is_add", [False, True])
@pytest.mark.parametrize(
    "substitute", [Multiplication, Addition, Subtraction, AddSub, MAD]
)
def test_mads_expansion(enabled, is_add, substitute):
    inputs = [Input(str(i)) for i in range(3)]
    original = graph(inputs, [MADS(is_add, *inputs, do_addsub=enabled)])
    expanded = original.rewrite(substitute, MADS)
    equivalent(original, expanded)
    assert not expanded.find_by_type(MADS)


@pytest.mark.parametrize("twiddle", [None, 1j, 0.5 - 0.5j])
@pytest.mark.parametrize("target_is_add", [False, True])
@pytest.mark.parametrize("swap_add", [False, True])
def test_butterfly_recognition(twiddle, target_is_add, swap_add):
    x, y = Input("x"), Input("y")
    b = y if twiddle is None else ConstantMultiplication(twiddle, y)
    addition = Addition(b, x) if swap_add else Addition(x, b)
    subtraction = Subtraction(x, b)
    original = graph([x, y], [addition, subtraction, b])
    target = original.find_by_type(Addition if target_is_add else Subtraction)[0]
    joined = original.join(target.graph_id, "forward")
    equivalent(original, joined)
    assert not joined.find_by_type(Addition)
    assert not joined.find_by_type(Subtraction)
    assert (
        len(joined.find_by_type(R2Butterfly if twiddle is None else R2DITButterfly))
        == 1
    )


@pytest.mark.parametrize("factors", [(1, 1j), (2, 3j)])
@pytest.mark.parametrize("direction", ["forward", "backward"])
def test_butterfly_output_fusion(factors, direction):
    x, y = Input("x"), Input("y")
    butterfly = R2Butterfly(x, y)
    outputs = [
        ConstantMultiplication(factor, butterfly.output(i))
        for i, factor in enumerate(factors)
    ]
    original = graph([x, y], outputs)
    target = original.find_by_type(
        R2Butterfly if direction == "forward" else ConstantMultiplication
    )[0]
    joined = original.join(target.graph_id, direction)
    equivalent(original, joined)
    assert not joined.find_by_type(ConstantMultiplication)
    assert (
        len(joined.find_by_type(R2DIFButterfly if factors[0] == 1 else R2TFButterfly))
        == 1
    )


@pytest.mark.parametrize(
    ("operation_type", "parameters"),
    [
        (R2Butterfly, ()),
        (R2DITButterfly, (0.5 + 1j,)),
        (R2DIFButterfly, (2 - 1j,)),
        (R2TFButterfly, (0.5, 1j)),
    ],
)
@pytest.mark.parametrize("substitute", [Addition, Subtraction, AddSub])
def test_butterfly_expansion(operation_type, parameters, substitute):
    x, y = Input("x"), Input("y")
    operation = operation_type(*parameters, x, y)
    original = graph(
        [x, y], [operation.output(1), operation.output(0), operation.output(1)]
    )
    expanded = original.rewrite(substitute, operation_type)
    equivalent(original, expanded)
    assert not expanded.find_by_type(operation_type)


@pytest.mark.parametrize("target_type", [Min, Max])
@pytest.mark.parametrize("swap_max", [False, True])
def test_comparator_join(target_type, swap_max):
    x, y = Input("x"), Input("y")
    minimum = Min(x, y)
    maximum = Max(y, x) if swap_max else Max(x, y)
    original = graph([x, y], [maximum, minimum, maximum])
    target = original.find_by_type(target_type)[0]
    joined = original.join(target.graph_id, "backward")
    equivalent(original, joined, real=True)
    assert len(joined.find_by_type(Comparator)) == 1
    assert not joined.find_by_type(Min)
    assert not joined.find_by_type(Max)


def test_mixed_supported_and_unsupported_consumers():
    x, y = Input("x"), Input("y")
    negated = Negation(x)
    supported = ConstantMultiplication(3, negated)
    unsupported = Multiplication(negated, y)
    original = graph([x, y], [supported, unsupported])
    joined = original.join(original.find_by_type(Negation)[0].graph_id, "forward")
    equivalent(original, joined)
    assert len(joined.find_by_type(Negation)) == 1
    assert len(joined.find_by_type(Multiplication)) == 1


def test_join_preserves_signal_metadata_and_original():
    x = Input("x")
    first = ConstantMultiplication(2, x)
    second = Negation(first)
    output = Output(name="answer")
    Signal(second, output, bits=12, name="kept")
    original = SFG([x], [output])
    before = str(original)
    joined = original.join(
        original.find_by_type(ConstantMultiplication)[0].graph_id, "forward"
    )
    signal = joined.output_operations[0].input(0).signals[0]
    assert signal.name == "kept"
    assert signal.bits == 12
    assert str(original) == before
    equivalent(original, joined)


def test_unsupported_join_and_validation():
    x, y = Input("x"), Input("y")
    original = graph([x, y], [Multiplication(x, y)])
    unchanged = original.join(
        original.find_by_type(Multiplication)[0].graph_id, "forward"
    )
    equivalent(original, unchanged)
    with pytest.raises(ValueError, match="not found"):
        original.join("missing", "forward")
    with pytest.raises(ValueError, match="Direction"):
        original.join("mul0", "sideways")


@pytest.mark.parametrize(
    ("operation_type", "parameters"),
    [
        (R2DITButterfly, (0.5 + 1j,)),
        (R2DIFButterfly, (2 - 1j,)),
        (R2TFButterfly, (0.5, 1j)),
    ],
)
def test_weighted_butterfly_expansion(operation_type, parameters):
    x, y = Input("x"), Input("y")
    operation = operation_type(*parameters, x, y)
    original = graph([x, y], [operation.output(0), operation.output(1)])
    expanded = original.rewrite(R2Butterfly, operation_type)
    equivalent(original, expanded)
    assert len(expanded.find_by_type(R2Butterfly)) == 1
    assert not expanded.find_by_type(operation_type)


@pytest.mark.parametrize("direction", ["forward", "backward"])
@pytest.mark.parametrize("existing_weight", [None, 0.5 + 1j])
def test_butterfly_input_fusion(direction, existing_weight):
    x, y = Input("x"), Input("y")
    scaled = ConstantMultiplication(2 - 3j, y, name="coefficient")
    operation = (
        R2Butterfly(x, scaled, name="butterfly")
        if existing_weight is None
        else R2DITButterfly(existing_weight, x, scaled, name="butterfly")
    )
    original = graph([x, y], [operation.output(0), operation.output(1), scaled])
    target = original.find_by_name(
        "coefficient" if direction == "forward" else "butterfly"
    )[0]
    joined = original.join(target.graph_id, direction)
    equivalent(original, joined)
    assert len(joined.find_by_type(R2DITButterfly)) == 1
    assert len(joined.find_by_type(ConstantMultiplication)) == 1


@pytest.mark.parametrize("weights", [None, (0.5, 2j)])
def test_butterfly_recognition_with_output_coefficients(weights):
    x, y = Input("x"), Input("y")
    addition, subtraction = Addition(x, y), Subtraction(x, y)
    outputs = (
        [addition, ConstantMultiplication(3j, subtraction)]
        if weights is None
        else [
            ConstantMultiplication(weights[0], addition),
            ConstantMultiplication(weights[1], subtraction),
        ]
    )
    original = graph([x, y], outputs)
    joined = original.join(original.find_by_type(Addition)[0].graph_id, "forward")
    equivalent(original, joined)
    assert (
        len(joined.find_by_type(R2DIFButterfly if weights is None else R2TFButterfly))
        == 1
    )
    assert not joined.find_by_type(ConstantMultiplication)
