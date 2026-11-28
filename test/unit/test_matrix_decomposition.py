"""Factor reconstruction, arithmetic choices, and decomposition interfaces."""

import numpy as np
import pytest

from b_asic.sfg_generators import (
    cholesky_decomposition,
    ldlt_decomposition,
    qr_decomposition,
)
from b_asic.special_operations import Input, MemoryRead, MemoryWrite, Output


@pytest.mark.parametrize("generator", [cholesky_decomposition, ldlt_decomposition])
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize("mem", [False, True])
@pytest.mark.parametrize("data_type", ["real", "complex", "split"])
@pytest.mark.parametrize("method", ["four", "three", "threealt"])
@pytest.mark.parametrize("size", [1, 3])
def test_hermitian_factors(generator, pe, mem, data_type, method, size):
    graph = generator(
        size,
        name="factor test",
        pe=pe,
        mem=mem,
        data_type=data_type,
        multiplication_method=method,
    )
    assert graph.name == "factor test"
    rng = np.random.default_rng(45)
    factor = rng.normal(size=(size, size))
    if data_type != "real":
        factor = factor + 1j * rng.normal(size=(size, size))
    matrix = factor @ factor.conj().T + np.eye(size)
    rows, cols = np.tril_indices(size)
    values = matrix[rows, cols]
    split = data_type == "split"
    components = 2 if split else 1
    if split:
        values = np.column_stack((values.real, values.imag)).ravel()
        # Hermitian diagonal imaginary inputs are deliberately unused.
        values[2 * np.flatnonzero(rows == cols) + 1] = 17

    result = np.asarray(graph.evaluate_outputs(values))
    if split:
        assert np.all(result[1::2][np.flatnonzero(rows == cols)] == 0)
        result = result[::2] + 1j * result[1::2]
    length = len(rows)
    lower = np.zeros((size, size), dtype=result.dtype)
    lower[rows, cols] = result[:length]
    if generator is cholesky_decomposition:
        np.testing.assert_allclose(lower, np.linalg.cholesky(matrix), atol=1e-12)
        reconstructed = lower @ lower.conj().T
    else:
        np.testing.assert_allclose(np.diag(lower), 1, atol=1e-12)
        diagonal = result[length:]
        np.testing.assert_allclose(diagonal.imag, 0, atol=1e-12)
        reconstructed = lower @ np.diag(diagonal) @ lower.conj().T
    np.testing.assert_allclose(reconstructed, matrix, rtol=1e-11, atol=1e-12)
    assert len(graph.input_operations) == length * components
    assert (
        len(graph.output_operations)
        == (length + (size if generator is ldlt_decomposition else 0)) * components
    )
    for index, read in enumerate(graph.input_operations):
        assert type(read) is (MemoryRead if mem else Input)
        if mem:
            assert read.address == index
            assert read.memory_name == ""
    expected_entries = [
        (f"L[{i},{j}]", "L", address, i == j)
        for address, (i, j) in enumerate(zip(rows, cols, strict=True))
    ]
    if generator is ldlt_decomposition:
        expected_entries += [(f"D[{i}]", "D", i, True) for i in range(size)]
    for entry, (name, memory, address, diagonal) in enumerate(expected_entries):
        for part in range(components):
            write = graph.output_operations[components * entry + part]
            assert type(write) is (MemoryWrite if mem else Output)
            suffix = ("_real", "_imag")[part] if split else ""
            assert write.name == name + suffix
            assert write.real_valued is (data_type != "complex" or bool(diagonal))
            if mem:
                assert write.memory_name == memory
                assert write.address == components * address + part
    _assert_arithmetic(graph, pe)


@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize("data_type", ["real", "complex", "split"])
def test_ldlt_indefinite(pe, data_type):
    lower = np.array([[1, 0, 0], [2, 1, 0], [-3, 2, 1]], dtype=complex)
    if data_type != "real":
        lower[1, 0] += 1j
    diagonal = np.array([2, -3, 4])
    matrix = lower @ np.diag(diagonal) @ lower.conj().T
    values = matrix[np.tril_indices(3)]
    if data_type == "real":
        values = values.real
    if data_type == "split":
        values = np.column_stack((values.real, values.imag)).ravel()
    result = np.asarray(
        ldlt_decomposition(3, pe=pe, data_type=data_type).evaluate_outputs(values)
    )
    if data_type == "split":
        result = result[::2] + 1j * result[1::2]
    np.testing.assert_allclose(result[:6], lower[np.tril_indices(3)], atol=1e-12)
    np.testing.assert_allclose(result[6:], diagonal, atol=1e-12)


@pytest.mark.parametrize("method", ["householder", "givens"])
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize("mem", [False, True])
@pytest.mark.parametrize("size", [1, 3, 4])
def test_qr_factors_and_layout(method, pe, mem, size):
    graph = qr_decomposition(size, method=method, pe=pe, mem=mem, name="QR factors")
    assert graph.name == "QR factors"
    rng = np.random.default_rng(34)
    random = rng.normal(size=(size, size))
    rank_deficient = random.copy()
    rank_deficient[:, -1] = rank_deficient[:, 0]
    rows, cols = np.triu_indices(size)
    for matrix in (random, rank_deficient, np.zeros((size, size)), np.eye(size)[::-1]):
        result = np.asarray(graph.evaluate_outputs(matrix.ravel()))
        q = result[: size * size].reshape(size, size)
        r = np.zeros((size, size))
        r[rows, cols] = result[size * size :]
        np.testing.assert_allclose(q @ r, matrix, atol=1e-12)
        np.testing.assert_allclose(q.T @ q, np.eye(size), atol=1e-12)
    assert len(graph.input_operations) == size * size
    for address, read in enumerate(graph.input_operations):
        assert type(read) is (MemoryRead if mem else Input)
        assert read.name == f"A[{address // size},{address % size}]"
        assert read.real_valued
        if mem:
            assert read.memory_name == "A"
            assert read.address == address
    expected_entries = [
        ("Q", i, j, i * size + j) for i in range(size) for j in range(size)
    ] + [
        ("R", i, j, index) for index, (i, j) in enumerate(zip(rows, cols, strict=True))
    ]
    assert len(graph.output_operations) == len(expected_entries)
    for write, (factor, i, j, address) in zip(
        graph.output_operations, expected_entries, strict=True
    ):
        assert type(write) is (MemoryWrite if mem else Output)
        assert write.name == f"{factor}[{i},{j}]"
        assert write.real_valued
        if mem:
            assert write.address == address
            assert write.memory_name == factor
    _assert_arithmetic(graph, pe)


def _assert_arithmetic(graph, pe):
    counts = graph.operation_counter()
    assert "div" not in counts
    assert "sqrt" not in counts
    if pe == "mads":
        assert "mul" not in counts
    if pe == "addsub":
        assert "add" not in counts
        assert "sub" not in counts


@pytest.mark.parametrize(
    "generator", [cholesky_decomposition, ldlt_decomposition, qr_decomposition]
)
@pytest.mark.parametrize("size", [0, -1, 1.5, True])
def test_invalid_size(generator, size):
    with pytest.raises(ValueError, match="positive integer"):
        generator(size)


@pytest.mark.parametrize(
    "generator", [cholesky_decomposition, ldlt_decomposition, qr_decomposition]
)
def test_invalid_pe(generator):
    with pytest.raises(ValueError, match="pe must be"):
        generator(2, pe="unknown")


@pytest.mark.parametrize("generator", [cholesky_decomposition, ldlt_decomposition])
@pytest.mark.parametrize(
    "kwargs", [{"data_type": "unknown"}, {"multiplication_method": "unknown"}]
)
def test_invalid_arithmetic(generator, kwargs):
    with pytest.raises(ValueError, match="must be"):
        generator(2, **kwargs)


def test_invalid_qr_method():
    with pytest.raises(ValueError, match="method must be"):
        qr_decomposition(2, method="unknown")
