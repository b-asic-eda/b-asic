"""Verify mixed real/complex arithmetic costs during direct generation."""

import pytest

from b_asic.sfg_generators._matrix_arithmetic import _MatrixArithmetic


@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize("method", ["four", "three", "threealt"])
@pytest.mark.parametrize(
    ("left_real", "right_real"),
    [(True, True), (True, False), (False, True), (False, False)],
)
@pytest.mark.parametrize("is_add", [False, True])
@pytest.mark.parametrize("accumulate", [False, True])
def test_split_product_values_and_costs(
    pe, method, left_real, right_real, is_add, accumulate
):
    arithmetic = _MatrixArithmetic("split", method, pe)
    left = arithmetic.input(1, 1 if left_real else 0, False)
    right = arithmetic.input(2, 2 if right_real else 0, False)
    accumulator = arithmetic.input(3, 0, False) if accumulate else None
    result = arithmetic.mads(is_add, accumulator, left, right, accumulate)
    graph = arithmetic.graph([arithmetic.output(1, 0, result, False)], "product")
    inputs = [2, 3, -4, 5, 7, -11] if accumulate else [2, 3, -4, 5]
    expected = (2 if left_real else 2 + 3j) * (-4 if right_real else -4 + 5j)
    expected = expected if is_add else -expected
    if accumulate:
        expected += 7 - 11j
    assert graph.evaluate_outputs(inputs) == pytest.approx(
        [expected.real, expected.imag]
    )
    counts = graph.operation_counter()
    products = counts.get("mul", 0) + counts.get("mads", 0)
    expected_products = (
        1
        if left_real and right_real
        else 2
        if left_real or right_real
        else 4
        if method == "four"
        else 3
    )
    assert products == expected_products
    if pe == "mads":
        assert "mul" not in counts
    if pe == "addsub":
        assert "add" not in counts
        assert "sub" not in counts


@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize("method", ["four", "three", "threealt"])
@pytest.mark.parametrize("reverse", [False, True])
def test_split_conjugate_self_product_uses_two_squares(pe, method, reverse):
    arithmetic = _MatrixArithmetic("split", method, pe)
    value = arithmetic.input(1, 0, False)
    conjugate = arithmetic.conjugate(value)
    result = value * conjugate if reverse else conjugate * value
    graph = arithmetic.graph([arithmetic.output(1, 0, result, False)], "norm")
    assert graph.evaluate_outputs([3, -4]) == [25, 0]
    counts = graph.operation_counter()
    assert counts.get("mul", 0) + counts.get("mads", 0) == 2
    assert "neg" not in counts


@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize("method", ["four", "three", "threealt"])
def test_split_real_projection_only_emits_required_products(pe, method):
    arithmetic = _MatrixArithmetic("split", method, pe)
    left = arithmetic.input(1, 0, False)
    right = arithmetic.input(2, 0, False)
    result = left * right
    graph = arithmetic.graph([arithmetic.output(0, 0, result, False)], "real part")
    assert graph.evaluate_outputs([2, 3, -4, 5]) == [-23, 0]
    counts = graph.operation_counter()
    assert counts.get("mul", 0) + counts.get("mads", 0) == 2


@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize("method", ["four", "three", "threealt"])
@pytest.mark.parametrize(
    ("left_real", "right_real"),
    [(True, True), (True, False), (False, True), (False, False)],
)
@pytest.mark.parametrize(
    ("conjugate_left", "conjugate_right"),
    [(False, False), (True, False), (False, True), (True, True)],
)
@pytest.mark.parametrize("mode", ["multiply", "negative", "add", "subtract"])
def test_split_real_product_uses_scalar_products_and_sums(
    pe, method, left_real, right_real, conjugate_left, conjugate_right, mode
):
    arithmetic = _MatrixArithmetic("split", method, pe)
    left = arithmetic.input(1, 1 if left_real else 0, False)
    right = arithmetic.input(2, 2 if right_real else 0, False)
    if conjugate_left:
        left = arithmetic.conjugate(left)
    if conjugate_right:
        right = arithmetic.conjugate(right)
    inputs = [2, 3, -4, 5]
    accumulate = mode in ("add", "subtract")
    if accumulate:
        accumulator = arithmetic.input(0, 0, False)
        inputs += [9, 37]
    else:
        accumulator = None
    if mode == "multiply":
        result = arithmetic.multiplication(left, right, real_valued=True)
    else:
        result = arithmetic.mads(
            mode == "add", accumulator, left, right, accumulate, real_valued=True
        )
    assert result.im is None
    graph = arithmetic.graph([arithmetic.output(1, 0, result, False)], "real product")
    left_value = complex(2, 0 if left_real else 3)
    right_value = complex(-4, 0 if right_real else 5)
    if conjugate_left:
        left_value = left_value.conjugate()
    if conjugate_right:
        right_value = right_value.conjugate()
    expected = (left_value * right_value).real
    if mode in ("negative", "subtract"):
        expected = -expected
    if accumulate:
        expected += 9
    assert graph.evaluate_outputs(inputs) == pytest.approx([expected, 0])
    counts = graph.operation_counter()
    products = 2 if not left_real and not right_real else 1
    assert counts.get("mul", 0) + counts.get("mads", 0) == products
    additions = sum(counts.get(name, 0) for name in ("add", "sub", "addsub"))
    assert additions == (0 if pe == "mads" else products - 1 + accumulate)
    assert counts.get("neg", 0) == (pe != "mads" and mode == "negative")
