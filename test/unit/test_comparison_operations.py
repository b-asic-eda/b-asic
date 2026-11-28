"""Tests for conditional replacement operations and QR zero guards."""

import math

import apytypes as apy
import pytest

from b_asic import ReplaceZero, ops
from b_asic.core_operations import CopySign
from b_asic.data_type import DataType
from b_asic.save_load_structure import sfg_to_python
from b_asic.sfg import SFG
from b_asic.sfg_generators import qr_decomposition, qr_matrix_inverse
from b_asic.sfg_generators._matrix_arithmetic import _MatrixArithmetic
from b_asic.sfg_generators.matrix_decomposition import _qr_safe_norm
from b_asic.special_operations import Input, Output


@pytest.mark.parametrize("replacement", [0, 1, -3.25, 2 + 3j])
@pytest.mark.parametrize(
    "value", [0, 0.0, -0.0, 0j, 2, -4.5, 1e-300, 1j, -2 + 3j, float("inf")]
)
def test_values(replacement, value):
    assert ReplaceZero(replacement).evaluate(value) == (
        replacement if value == 0 else value
    )


def test_nan_is_not_zero():
    assert math.isnan(ReplaceZero(1).evaluate(float("nan")))


def test_nonfinite_replacement():
    source = Input()
    operation = ReplaceZero(float("inf"), source)
    assert operation.evaluate(0) == float("inf")
    assert operation.evaluate(3) == 3
    with pytest.raises(NotImplementedError, match="finite replacement"):
        SFG([source], [Output(operation)]).complex_to_real()


def test_real_valued_and_parameter():
    operation = ReplaceZero(2, real_valued=True)
    assert operation.evaluate(3j) == 2
    assert operation.evaluate(4 + 3j) == 4
    operation.value = -7
    assert operation.evaluate(0) == -7
    with pytest.raises(ValueError, match="real replacement"):
        operation.value = 1j


@pytest.mark.parametrize("value", [0, 1.5, -2.5])
def test_fixed_point(value):
    result = ReplaceZero(3.25).evaluate(
        apy.fx(value, 4, 4), data_type=DataType(wl=(4, 4))
    )
    assert isinstance(result, apy.APyFixed)
    assert float(result) == (3.25 if value == 0 else value)


def test_copy_and_serialization():
    source = Input()
    operation = ReplaceZero(
        3, source, name="guard", latency=2, execution_time=1, real_valued=True
    )
    assert operation.input_count == operation.output_count == 1
    assert not operation.is_linear
    assert ops.ReplaceZero is ReplaceZero
    copied = operation.copy()
    assert copied.value == 3
    assert copied.name == "guard"
    assert copied.latency == 2
    assert copied.execution_time == 1
    assert copied.real_valued is True
    graph = SFG([source], [Output(operation)])
    namespace = {}
    exec(sfg_to_python(graph), namespace)
    restored = next(value for value in namespace.values() if isinstance(value, SFG))
    assert restored.evaluate_outputs([0]) == [3]
    assert restored.evaluate_outputs([-2]) == [-2]


@pytest.mark.parametrize("real_valued", [None, True])
def test_complex_conversion(real_valued):
    source = Input()
    replacement = -2 if real_valued else -2 + 3j
    graph = SFG(
        [source], [Output(ReplaceZero(replacement, source, real_valued=real_valued))]
    )
    converted = graph.complex_to_real()
    for value in (0j, 1j, 2, 2 - 3j, 1e-300 + 0j, float("inf") + 0j):
        expected = graph.evaluate_outputs([value])[0]
        assert converted.evaluate_outputs([value.real, value.imag]) == pytest.approx(
            [expected.real, expected.imag]
        )


@pytest.mark.parametrize("parts", [(float("nan"), 0), (0, float("nan"))])
def test_complex_conversion_preserves_nan_components(parts):
    source = Input()
    graph = SFG([source], [Output(ReplaceZero(2 + 3j, source))]).complex_to_real()
    result = graph.evaluate_outputs(parts)
    for actual, expected in zip(result, parts, strict=True):
        if math.isnan(expected):
            assert math.isnan(actual)
        else:
            assert actual == expected


@pytest.mark.parametrize("data_type", ["real", "complex", "split"])
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
def test_qr_norm_guard_uses_replace_zero(data_type, pe):
    arithmetic = _MatrixArithmetic(data_type, "four", pe)
    norm = arithmetic.input(0, 0, False)
    norm = arithmetic.real_part(norm)
    safe, is_zero = _qr_safe_norm(arithmetic, norm)
    graph = arithmetic.graph(
        [
            arithmetic.output(0, 0, safe, False),
            arithmetic.output(0, 0, is_zero, False),
        ],
        "guard",
    )
    assert len(graph.find_by_type(ReplaceZero)) == 1
    assert not graph.find_by_type(CopySign)
    for value in (0, 1e-300, 0.5, 5):
        inputs = [value, 0] if data_type == "split" else [value]
        expected = [1 if value == 0 else value, int(value == 0)]
        if data_type == "split":
            expected = [expected[0], 0, expected[1], 0]
        assert graph.evaluate_outputs(inputs) == expected


@pytest.mark.parametrize("method", ["householder", "givens"])
@pytest.mark.parametrize("generator", [qr_matrix_inverse, qr_decomposition])
def test_qr_graph_uses_comparison_primitive(generator, method):
    graph = generator(3, method=method)
    assert graph.find_by_type(ReplaceZero)
    # CopySign remains only for the actual Householder sign choice.
    assert len(graph.find_by_type(CopySign)) == (2 if method == "householder" else 0)
