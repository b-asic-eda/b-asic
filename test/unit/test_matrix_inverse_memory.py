"""Memory layouts and numerical results for matrix inverse generators."""

import numpy as np
import pytest

from b_asic.core_operations import Reciprocal
from b_asic.sfg_generators import (
    analytical_block_matrix_inverse,
    block_cholesky_matrix_inverse,
    block_ldlt_matrix_inverse,
    cholesky_matrix_inverse,
    ldlt_matrix_inverse,
    tile_ldlt_matrix_inverse,
)
from b_asic.special_operations import Input, MemoryRead, MemoryWrite, Output

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
@pytest.mark.parametrize("cmplx", [False, True])
@pytest.mark.parametrize("size", [2, 4, 6])
def test_matrix_inverse_memory_layout_and_values(generator, mode, pe, mem, cmplx, size):
    graph = generator(size, mode=mode, pe=pe, mem=mem, cmplx=cmplx)
    assert all(op.real_valued is True for op in graph.find_by_type(Reciprocal))
    assert bool(graph.operation_counter().get("conj", 0)) == cmplx
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
    if cmplx:
        factor = factor + 1j * rng.normal(size=(size, size))
    matrix = factor @ factor.conj().T + np.eye(size)
    actual = graph.evaluate_outputs(matrix[rows, cols])
    expected = np.linalg.inv(matrix)[rows, cols]
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-12)
