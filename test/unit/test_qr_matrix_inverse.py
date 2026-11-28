"""Numerical and structural checks for QR-based inversion."""

import math

import numpy as np
import pytest

from b_asic.core_operations import CopySign
from b_asic.sfg import SFG
from b_asic.sfg_generators import qr_matrix_inverse
from b_asic.sfg_generators._matrix_arithmetic import _MatrixArithmetic
from b_asic.sfg_generators.matrix_decomposition import _qr_decomposition
from b_asic.special_operations import Input, MemoryRead, MemoryWrite, Output


@pytest.mark.parametrize("method", ["householder", "givens"])
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize("mem", [False, True])
@pytest.mark.parametrize("size", [1, 2, 3, 5])
def test_qr_inverse_values_and_layout(method, pe, mem, size):
    graph = qr_matrix_inverse(size, method=method, pe=pe, mem=mem, name="QR test")
    assert graph.name == "QR test"
    rows, cols = np.tril_indices(size)
    for index, (row, col) in enumerate(zip(rows, cols, strict=True)):
        read, write = graph.input_operations[index], graph.output_operations[index]
        assert type(read) is (MemoryRead if mem else Input)
        assert type(write) is (MemoryWrite if mem else Output)
        assert read.name == f"A[{row},{col}]"
        assert write.name == f"res[{row},{col}]"
        assert read.real_valued
        assert write.real_valued
        if mem:
            assert read.address == write.address == index
            assert read.memory_name == write.memory_name == ""

    rng = np.random.default_rng(2026)
    matrix = rng.normal(size=(size, size))
    matrix = matrix + matrix.T
    # QR inversion also works for indefinite matrices and negative pivots.
    matrix += np.diag(np.arange(1, size + 1) * (-1.0) ** np.arange(size))
    actual = graph.evaluate_outputs(matrix[rows, cols])
    np.testing.assert_allclose(
        actual, np.linalg.inv(matrix)[rows, cols], rtol=1e-10, atol=1e-12
    )
    counts = graph.operation_counter()
    assert "div" not in counts
    assert "sqrt" not in counts
    if pe == "mads":
        assert "mul" not in counts
    if pe == "addsub":
        assert "add" not in counts
        assert "sub" not in counts


@pytest.mark.parametrize("method", ["householder", "givens"])
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize(
    "matrix",
    [
        np.eye(4),
        -np.eye(4),
        np.eye(4)[::-1],
        np.diag([1.0, -2.0, 3.0, -4.0]),
        np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 2.0]]),
        np.array([[1.0, 1e-10], [1e-10, -2.0]]),
    ],
)
def test_sparse_inputs_and_small_householder_tails(method, pe, matrix):
    rows, cols = np.tril_indices(len(matrix))
    graph = qr_matrix_inverse(len(matrix), method=method, pe=pe)
    np.testing.assert_allclose(
        graph.evaluate_outputs(matrix[rows, cols]),
        np.linalg.inv(matrix)[rows, cols],
        rtol=1e-10,
        atol=1e-12,
    )


@pytest.mark.parametrize("method", ["householder", "givens"])
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
def test_qr_factors(method, pe):
    size = 4
    arithmetic = _MatrixArithmetic("real", "four", pe)
    inputs = [Input(real_valued=True) for _ in range(size * size)]
    matrix_sources = [inputs[i * size : (i + 1) * size] for i in range(size)]
    r, qt = _qr_decomposition(matrix_sources, arithmetic, method)
    graph = SFG(
        inputs, [Output(value) for matrix in (r, qt) for row in matrix for value in row]
    )
    rng = np.random.default_rng(42)
    for matrix in (rng.normal(size=(size, size)), np.zeros((size, size))):
        result = np.asarray(graph.evaluate_outputs(matrix.ravel()))
        r_result, qt_result = result.reshape(2, size, size)
        np.testing.assert_allclose(qt_result.T @ r_result, matrix, atol=1e-12)
        np.testing.assert_allclose(qt_result.T @ qt_result, np.eye(size), atol=1e-12)
        np.testing.assert_allclose(np.tril(r_result, -1), 0, atol=1e-12)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"N": 0},
        {"N": -1},
        {"N": 1.5},
        {"N": True},
        {"N": 2, "method": "unknown"},
        {"N": 2, "pe": "unknown"},
    ],
)
def test_invalid_arguments(kwargs):
    with pytest.raises(ValueError, match="must be"):
        qr_matrix_inverse(**kwargs)


@pytest.mark.parametrize("magnitude", [-3.0, 3.0, -0.0, 0.0])
@pytest.mark.parametrize("sign", [-2.0, 2.0, -0.0, 0.0])
def test_copy_sign(magnitude, sign):
    operation = CopySign()
    result = operation.evaluate(magnitude, sign)
    assert result == math.copysign(magnitude, sign)
    assert math.copysign(1, result) == math.copysign(1, sign)
    assert not operation.is_swappable


def test_copy_sign_graph_copy_and_conversion():
    inputs = [Input(), Input()]
    operation = CopySign(*inputs, name="sign", latency=3, execution_time=1)
    graph = SFG(inputs, [Output(operation)])
    assert graph.evaluate_outputs([-3, -2]) == [-3]
    assert graph().evaluate_outputs([-3, 2]) == [3]
    converted = graph.complex_to_real()
    assert converted.evaluate_outputs([-3, 0, -2, 0]) == [-3, 0]
    copied = operation.copy()
    assert copied.name == "sign"
    assert copied.latency == 3
    assert copied.execution_time == 1


@pytest.mark.parametrize("inputs", [(1j, 1), (1, 1j)])
def test_copy_sign_rejects_complex(inputs):
    with pytest.raises(ValueError, match="does not support complex"):
        CopySign().evaluate(*inputs)
