"""Complex and split QR factors and all inverse recovery modes."""

import numpy as np
import pytest

from b_asic.core_operations import ComplexConjugate, Reciprocal, ReciprocalSquareRoot
from b_asic.sfg_generators import qr_decomposition, qr_matrix_inverse
from b_asic.special_operations import Input, MemoryRead, MemoryWrite, Output
from b_asic.utility_operations import ComplexToReal, RealToComplex


def _encode(values, data_type):
    values = np.asarray(values).ravel()
    if data_type == "split":
        return np.column_stack((values.real, values.imag)).ravel()
    return values


def _decode(values, data_type):
    values = np.asarray(values)
    return values[::2] + 1j * values[1::2] if data_type == "split" else values


def _check_arithmetic(graph, data_type, pe):
    counts = graph.operation_counter()
    assert "div" not in counts
    assert "sqrt" not in counts
    for operation_type in (Reciprocal, ReciprocalSquareRoot):
        assert all(op.real_valued for op in graph.find_by_type(operation_type))
    if data_type == "split":
        assert not graph.find_by_type(ComplexConjugate)
        assert not graph.find_by_type(ComplexToReal)
        assert not graph.find_by_type(RealToComplex)
        assert all(op.real_valued for op in graph.input_operations)
        assert all(op.real_valued for op in graph.output_operations)
    if pe == "mads":
        assert "mul" not in counts
    if pe == "addsub":
        assert "add" not in counts
        assert "sub" not in counts


@pytest.mark.parametrize("method", ["householder", "givens"])
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize(
    ("data_type", "multiplication_method"),
    [
        ("complex", "four"),
        ("split", "four"),
        ("split", "three"),
        ("split", "threealt"),
    ],
)
@pytest.mark.parametrize("mem", [False, True])
@pytest.mark.parametrize("size", [1, 3])
def test_complex_qr_factors(method, pe, data_type, multiplication_method, mem, size):
    graph = qr_decomposition(
        size,
        method=method,
        pe=pe,
        data_type=data_type,
        multiplication_method=multiplication_method,
        mem=mem,
    )
    rng = np.random.default_rng(71)
    random = rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size))
    deficient = random.copy()
    deficient[:, -1] = deficient[:, 0]
    samples = [
        random,
        deficient,
        np.zeros((size, size)),
        1j * np.eye(size),
        (1 + 2j) * np.eye(size)[::-1],
    ]
    if size > 1:
        zero_leading = random.copy()
        zero_leading[0, 0] = 0
        samples.append(zero_leading)
    rows, cols = np.triu_indices(size)
    for matrix in samples:
        values = _decode(graph.evaluate_outputs(_encode(matrix, data_type)), data_type)
        q = values[: size * size].reshape(size, size)
        r = np.zeros((size, size), dtype=complex)
        r[rows, cols] = values[size * size :]
        np.testing.assert_allclose(q @ r, matrix, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(q.conj().T @ q, np.eye(size), atol=1e-12)
    components = 2 if data_type == "split" else 1
    assert len(graph.input_operations) == size * size * components
    expected = [("Q", i, j, i * size + j) for i in range(size) for j in range(size)]
    expected += [
        ("R", i, j, index) for index, (i, j) in enumerate(zip(rows, cols, strict=True))
    ]
    assert len(graph.output_operations) == len(expected) * components
    for entry, (factor, i, j, address) in enumerate(expected):
        for part in range(components):
            operation = graph.output_operations[components * entry + part]
            assert type(operation) is (MemoryWrite if mem else Output)
            suffix = ("_real", "_imag")[part] if components == 2 else ""
            assert operation.name == f"{factor}[{i},{j}]" + suffix
            assert operation.real_valued is (components == 2)
            if mem:
                assert operation.memory_name == factor
                assert operation.address == components * address + part
    for address, operation in enumerate(graph.input_operations):
        assert type(operation) is (MemoryRead if mem else Input)
        assert operation.real_valued is (components == 2)
        if mem:
            assert operation.address == address
            assert operation.memory_name == "A"
    _check_arithmetic(graph, data_type, pe)


@pytest.mark.parametrize("method", ["householder", "givens"])
@pytest.mark.parametrize("mode", ["eqs", "mult", "implicitq"])
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize(
    ("data_type", "multiplication_method"),
    [
        ("complex", "four"),
        ("split", "four"),
        ("split", "three"),
        ("split", "threealt"),
    ],
)
@pytest.mark.parametrize("mem", [False, True])
@pytest.mark.parametrize("size", [1, 3])
def test_hermitian_qr_inverse(
    method, mode, pe, data_type, multiplication_method, mem, size
):
    graph = qr_matrix_inverse(
        size,
        method=method,
        mode=mode,
        pe=pe,
        data_type=data_type,
        multiplication_method=multiplication_method,
        mem=mem,
    )
    rng = np.random.default_rng(71)
    factor = rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size))
    samples = [
        factor @ factor.conj().T + np.eye(size),
        factor + factor.conj().T + np.diag(np.arange(size) + 1),
        -np.eye(size),
        np.eye(size)[::-1],
    ]
    if size > 1:
        # An imaginary off-diagonal pivot exercises conjugation and phase(0).
        sparse = np.eye(size, dtype=complex)
        sparse[:2, :2] = [[0, -2j], [2j, 0]]
        samples.append(sparse)
    rows, cols = np.tril_indices(size)
    for matrix in samples:
        inputs = _encode(matrix[rows, cols], data_type)
        if data_type == "split":
            inputs[2 * np.flatnonzero(rows == cols) + 1] = 13
        result = _decode(graph.evaluate_outputs(inputs), data_type)
        np.testing.assert_allclose(
            result, np.linalg.inv(matrix)[rows, cols], rtol=1e-10, atol=1e-12
        )
        np.testing.assert_allclose(result[rows == cols].imag, 0, atol=0)
    components = 2 if data_type == "split" else 1
    assert len(graph.input_operations) == len(rows) * components
    assert len(graph.output_operations) == len(rows) * components
    for entry, (i, j) in enumerate(zip(rows, cols, strict=True)):
        for part in range(components):
            address = components * entry + part
            read, write = (
                graph.input_operations[address],
                graph.output_operations[address],
            )
            assert type(read) is (MemoryRead if mem else Input)
            assert type(write) is (MemoryWrite if mem else Output)
            suffix = ("_real", "_imag")[part] if components == 2 else ""
            assert read.name == f"A[{i},{j}]" + suffix
            assert write.name == f"res[{i},{j}]" + suffix
            assert read.real_valued is (components == 2 or bool(i == j))
            assert write.real_valued is (components == 2 or bool(i == j))
            if mem:
                assert read.address == write.address == address
                assert read.memory_name == write.memory_name == ""
    _check_arithmetic(graph, data_type, pe)


@pytest.mark.parametrize("generator", [qr_matrix_inverse, qr_decomposition])
@pytest.mark.parametrize(
    "kwargs", [{"data_type": "unknown"}, {"multiplication_method": "unknown"}]
)
def test_invalid_complex_arguments(generator, kwargs):
    with pytest.raises(ValueError, match="must be"):
        generator(2, **kwargs)
