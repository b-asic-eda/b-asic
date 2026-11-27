"""Memory layouts and numerical results for matrix inverse generators."""

import numpy as np
import pytest

from b_asic.core_operations import (
    ComplexConjugate,
    Constant,
    Multiplication,
    Reciprocal,
    ReciprocalSquareRoot,
)
from b_asic.sfg_generators import (
    analytical_block_matrix_inverse,
    block_cholesky_matrix_inverse,
    block_ldlt_matrix_inverse,
    cholesky_matrix_inverse,
    ldlt_matrix_inverse,
    tile_ldlt_matrix_inverse,
)
from b_asic.special_operations import Input, MemoryRead, MemoryWrite, Output
from b_asic.utility_operations import ComplexToReal, RealToComplex, Sink

_GENERATORS_AND_MODES = [
    (generator, mode)
    for generator in (
        ldlt_matrix_inverse,
        cholesky_matrix_inverse,
        block_ldlt_matrix_inverse,
        block_cholesky_matrix_inverse,
        tile_ldlt_matrix_inverse,
        analytical_block_matrix_inverse,
    )
    for mode in (
        ("top", "bot", "mid")
        if generator is analytical_block_matrix_inverse
        else ("eqs", "mult")
    )
]


@pytest.mark.parametrize(("generator", "mode"), _GENERATORS_AND_MODES)
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize("mem", [False, True])
@pytest.mark.parametrize("data_type", ["real", "complex"])
@pytest.mark.parametrize("size", [2, 4, 6])
def test_matrix_inverse_memory_layout_and_values(
    generator, mode, pe, mem, data_type, size
):
    graph = generator(size, mode=mode, pe=pe, mem=mem, data_type=data_type)
    assert all(op.real_valued is True for op in graph.find_by_type(Reciprocal))
    assert bool(graph.operation_counter().get("conj", 0)) == (data_type == "complex")
    rows, cols = np.tril_indices(size)
    assert len(graph.input_operations) == len(rows)
    assert len(graph.output_operations) == len(rows)
    for address, (row, col) in enumerate(zip(rows, cols, strict=True)):
        read = graph.input_operations[address]
        write = graph.output_operations[address]
        assert type(read) is (MemoryRead if mem else Input)
        assert type(write) is (MemoryWrite if mem else Output)
        assert read.name == f"A[{row},{col}]"
        assert write.name == f"res[{row},{col}]"
        assert read.real_valued is bool(row == col)
        assert write.real_valued is bool(row == col)
        if mem:
            assert read.address == write.address == address
            assert read.memory_name == write.memory_name == ""

    rng = np.random.default_rng(42)
    factor = rng.normal(size=(size, size))
    if data_type == "complex":
        factor = factor + 1j * rng.normal(size=(size, size))
    matrix = factor @ factor.conj().T + np.eye(size)
    actual = graph.evaluate_outputs(matrix[rows, cols])
    expected = np.linalg.inv(matrix)[rows, cols]
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize(("generator", "mode"), _GENERATORS_AND_MODES)
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize("mem", [False, True])
@pytest.mark.parametrize("method", ["four", "three", "threealt"])
@pytest.mark.parametrize("size", [2, 4, 6])
def test_matrix_inverse_split_layout_and_values(generator, mode, pe, mem, method, size):
    graph = generator(
        size,
        mode=mode,
        pe=pe,
        mem=mem,
        data_type="split",
        multiplication_method=method,
    )
    assert not graph.find_by_type(ComplexConjugate)
    assert not graph.find_by_type(ComplexToReal)
    assert not graph.find_by_type(RealToComplex)
    for operation_type in (Reciprocal, ReciprocalSquareRoot):
        assert all(op.real_valued for op in graph.find_by_type(operation_type))
    rows, cols = np.tril_indices(size)
    assert len(graph.input_operations) == len(graph.output_operations) == 2 * len(rows)
    for packed, (row, col) in enumerate(zip(rows, cols, strict=True)):
        for index, part in enumerate(("real", "imag")):
            address = 2 * packed + index
            read = graph.input_operations[address]
            write = graph.output_operations[address]
            assert type(read) is (MemoryRead if mem else Input)
            assert type(write) is (MemoryWrite if mem else Output)
            assert read.name == f"A[{row},{col}]_{part}"
            assert write.name == f"res[{row},{col}]_{part}"
            assert read.real_valued is write.real_valued is True
            if mem:
                assert read.address == write.address == address
                assert read.memory_name == write.memory_name == ""
            if row == col and part == "imag":
                assert all(
                    isinstance(signal.destination.operation, Sink)
                    for signal in read.output(0).signals
                )
                source = write.input(0).connected_source.operation
                assert isinstance(source, Constant)
                assert source.value == 0

    rng = np.random.default_rng(42)
    factor = rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size))
    matrix = factor @ factor.conj().T + np.eye(size)
    packed_input = matrix[rows, cols]
    inputs = np.column_stack((packed_input.real, packed_input.imag))
    # Hermitian diagonal entries are real, regardless of the unused input port.
    inputs[rows == cols, 1] = rng.normal(size=size)
    actual = graph.evaluate_outputs(inputs.ravel())
    expected = np.linalg.inv(matrix)[rows, cols]
    expected = np.column_stack((expected.real, expected.imag)).ravel()
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize(("generator", "mode"), _GENERATORS_AND_MODES)
@pytest.mark.parametrize("method", ["four", "three", "threealt"])
def test_matrix_inverse_split_avoids_redundant_products(generator, mode, method):
    direct = generator(4, mode=mode, data_type="split", multiplication_method=method)
    converted = generator(4, mode=mode, data_type="complex").complex_to_real(
        multiplication_method=method
    )
    assert len(direct.find_by_type(Multiplication)) < len(
        converted.find_by_type(Multiplication)
    )


@pytest.mark.parametrize(("generator", "mode"), _GENERATORS_AND_MODES)
@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("data_type", "invalid"),
        ("data_type", True),
        ("multiplication_method", "invalid"),
    ],
)
def test_matrix_inverse_rejects_unknown_arithmetic(generator, mode, argument, value):
    with pytest.raises(ValueError, match=argument):
        generator(2, mode=mode, **{argument: value})


@pytest.mark.parametrize(
    ("generator", "mode"),
    [
        pair
        for pair in _GENERATORS_AND_MODES
        if pair[0]
        in (
            ldlt_matrix_inverse,
            cholesky_matrix_inverse,
            analytical_block_matrix_inverse,
        )
    ],
)
@pytest.mark.parametrize("method", ["four", "three", "threealt"])
@pytest.mark.parametrize("size", [1, 3, 5])
def test_matrix_inverse_split_odd_dimensions(generator, mode, method, size):
    graph = generator(
        size, mode=mode, pe="mads", data_type="split", multiplication_method=method
    )
    rng = np.random.default_rng(123)
    factor = rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size))
    matrix = factor @ factor.conj().T + np.eye(size)
    lower = np.tril_indices(size)
    packed = matrix[lower]
    actual = np.asarray(
        graph.evaluate_outputs(np.column_stack((packed.real, packed.imag)).ravel())
    )
    np.testing.assert_allclose(
        actual[0::2] + 1j * actual[1::2], np.linalg.inv(matrix)[lower], atol=1e-12
    )
