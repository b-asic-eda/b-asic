"""Memory layouts and numerical results for matrix inverse generators."""

import numpy as np
import pytest

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
def test_matrix_inverse_memory_layout_and_values(generator, mode, pe, mem):
    size = 4
    graph = generator(size, mode=mode, pe=pe, mem=mem)
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
        if mem:
            assert read.address == write.address == address
            assert read.memory_name == write.memory_name == ""

    matrix = np.array([[2, 1, 0, 1], [1, 3, 1, 0], [0, 1, 4, 1], [1, 0, 1, 5]])
    matrix = matrix @ matrix.T + np.eye(size)
    actual = graph.evaluate_outputs(matrix[rows, cols])
    expected = np.linalg.inv(matrix)[rows, cols]
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-12)
