"""Numerical, partition, and interface checks for Schur inversion."""

import numpy as np
import pytest

from b_asic.core_operations import Reciprocal, ReciprocalSquareRoot
from b_asic.sfg_generators import (
    Leaf,
    analytical_block_matrix_inverse,
    schur_matrix_inverse,
)
from b_asic.special_operations import Input, MemoryRead, MemoryWrite, Output


def _matrix(size, structure, data_type):
    rng = np.random.default_rng(830)
    values = rng.normal(size=(size, size))
    if data_type != "real":
        values = values + 1j * rng.normal(size=(size, size))
    if structure == "hermitian":
        return values @ values.conj().T + np.eye(size)
    if structure == "symmetric":
        values = values + values.T
    return values + (4 * size) * np.eye(size)


def _check(graph, matrix, structure, data_type):
    indices = (
        np.indices(matrix.shape).reshape(2, -1)
        if structure == "general"
        else np.tril_indices(len(matrix))
    )
    inputs = matrix[tuple(indices)]
    expected = np.linalg.inv(matrix)[tuple(indices)]
    if data_type == "split":
        inputs = np.column_stack((inputs.real, inputs.imag)).ravel()
        actual = np.asarray(graph.evaluate_outputs(inputs))
        actual = actual[::2] + 1j * actual[1::2]
    else:
        actual = graph.evaluate_outputs(inputs)
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-12)
    counts = graph.operation_counter()
    assert "div" not in counts
    assert "sqrt" not in counts
    assert graph.find_by_type(Reciprocal) or graph.find_by_type(ReciprocalSquareRoot)
    assert all(
        op.real_valued
        for cls in (Reciprocal, ReciprocalSquareRoot)
        for op in graph.find_by_type(cls)
    )


@pytest.mark.parametrize(
    "partition", ["balanced", "top", "bot", [1, 2, 2], (2, (1, 2)), ((1, 2), 2)]
)
@pytest.mark.parametrize("structure", ["general", "symmetric", "hermitian"])
@pytest.mark.parametrize("data_type", ["real", "complex", "split"])
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
def test_partitions(partition, structure, data_type, pe):
    graph = schur_matrix_inverse(
        5, partition=partition, structure=structure, data_type=data_type, pe=pe
    )
    _check(graph, _matrix(5, structure, data_type), structure, data_type)
    counts = graph.operation_counter()
    if pe == "mads":
        assert "mul" not in counts
    if pe == "addsub":
        assert "add" not in counts
        assert "sub" not in counts


@pytest.mark.parametrize("mode", ["eqs", "mult", "implicitq", "implicitq_eqs"])
@pytest.mark.parametrize("method", ["householder", "givens"])
@pytest.mark.parametrize("structure", ["general", "symmetric", "hermitian"])
@pytest.mark.parametrize("data_type", ["real", "complex", "split"])
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
def test_qr_leaves(mode, method, structure, data_type, pe):
    graph = schur_matrix_inverse(
        5,
        partition=(3, 2),
        leaf_method="qr",
        leaf_options={"method": method, "mode": mode},
        structure=structure,
        data_type=data_type,
        pe=pe,
    )
    _check(graph, _matrix(5, structure, data_type), structure, data_type)


@pytest.mark.parametrize("method", ["ldlt", "cholesky"])
@pytest.mark.parametrize("mode", ["eqs", "mult"])
@pytest.mark.parametrize(
    ("structure", "data_type"),
    [
        ("hermitian", "real"),
        ("hermitian", "complex"),
        ("hermitian", "split"),
        ("symmetric", "real"),
        ("symmetric", "complex"),
        ("symmetric", "split"),
    ],
)
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
def test_factorization_leaves(method, mode, structure, data_type, pe):
    if method == "cholesky" and structure == "symmetric" and data_type != "real":
        pytest.skip("Complex symmetric Cholesky is deliberately unsupported")
    graph = schur_matrix_inverse(
        7,
        partition="top",
        block_size=3,
        leaf_method=method,
        leaf_options={"mode": mode},
        structure=structure,
        data_type=data_type,
        pe=pe,
    )
    _check(graph, _matrix(7, structure, data_type), structure, data_type)


@pytest.mark.parametrize("structure", ["general", "symmetric", "hermitian"])
@pytest.mark.parametrize("multiplication_method", ["four", "three", "threealt"])
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
def test_split_multiplication_methods(structure, multiplication_method, pe):
    graph = schur_matrix_inverse(
        5,
        partition=(2, 3),
        leaf_method="qr",
        data_type="split",
        structure=structure,
        multiplication_method=multiplication_method,
        pe=pe,
    )
    _check(graph, _matrix(5, structure, "split"), structure, "split")


@pytest.mark.parametrize("structure", ["general", "symmetric", "hermitian"])
@pytest.mark.parametrize("data_type", ["real", "complex", "split"])
@pytest.mark.parametrize("mem", [False, True])
def test_interfaces(structure, data_type, mem):
    graph = schur_matrix_inverse(
        3, structure=structure, data_type=data_type, mem=mem, name="Schur test"
    )
    assert graph.name == "Schur test"
    indices = [
        (i, j) for i in range(3) for j in range(3 if structure == "general" else i + 1)
    ]
    components = 2 if data_type == "split" else 1
    assert (
        len(graph.input_operations)
        == len(graph.output_operations)
        == components * len(indices)
    )
    for index, (i, j) in enumerate(indices):
        for component in range(components):
            address = components * index + component
            read, write = (
                graph.input_operations[address],
                graph.output_operations[address],
            )
            assert type(read) is (MemoryRead if mem else Input)
            assert type(write) is (MemoryWrite if mem else Output)
            expected_real = data_type in ("real", "split") or (
                structure == "hermitian" and i == j
            )
            assert read.real_valued == write.real_valued == expected_real
            if mem:
                assert read.address == write.address == address
                assert read.memory_name == write.memory_name == ""
    _check(graph, _matrix(3, structure, data_type), structure, data_type)


def test_leaf_option_inheritance(monkeypatch):
    from b_asic.sfg_generators import matrix_inversion as module

    original = module._qr_inverse
    calls = []

    def record(matrix, arithmetic, method, mode, **kwargs):
        calls.append((len(matrix), method, mode))
        return original(matrix, arithmetic, method, mode, **kwargs)

    monkeypatch.setattr(module, "_qr_inverse", record)
    options = {"method": "givens", "mode": "implicitq"}
    graph = schur_matrix_inverse(
        8,
        partition=(
            (2, Leaf(1, options={"mode": "mult"})),
            (
                Leaf(2, method="qr"),
                Leaf(3, method="cholesky", options={"mode": "mult"}),
            ),
        ),
        leaf_method="qr",
        leaf_options=options,
    )
    assert calls == [
        (2, "givens", "implicitq"),
        (1, "givens", "mult"),
        (2, "householder", "eqs"),
    ]
    assert options == {"method": "givens", "mode": "implicitq"}
    _check(graph, _matrix(8, "hermitian", "real"), "hermitian", "real")


@pytest.mark.parametrize("size", [1, 2, 3])
@pytest.mark.parametrize("structure", ["general", "symmetric", "hermitian"])
@pytest.mark.parametrize("data_type", ["real", "complex", "split"])
def test_terminal_and_remainder_blocks(size, structure, data_type):
    graph = schur_matrix_inverse(size, structure=structure, data_type=data_type)
    _check(graph, _matrix(size, structure, data_type), structure, data_type)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"N": 0},
        {"N": True},
        {"N": 2.5},
        {"structure": "unknown"},
        {"block_size": 0},
        {"block_size": True},
        {"block_size": 1.5},
        {"partition": "mid"},
        {"partition": []},
        {"partition": [2, 0, 3]},
        {"partition": [2, 2]},
        {"partition": (1, 2, 2)},
        {"partition": (1, "bad")},
        {"partition": Leaf(True)},
        {"partition": Leaf(5, method="unknown")},
        {"leaf_method": "unknown"},
        {"block_size": 3},
        {"leaf_options": {"mem": True}},
        {"leaf_options": []},
        {"leaf_method": "qr", "leaf_options": {"method": "unknown"}},
        {"leaf_method": "qr", "leaf_options": {"mode": "unknown"}},
        {"leaf_method": "ldlt", "leaf_options": {"mode": "implicitq"}},
        {"leaf_method": "cholesky", "structure": "general"},
        {"leaf_method": "ldlt", "structure": "general"},
        {"leaf_method": "cholesky", "structure": "symmetric", "data_type": "complex"},
        {"partition": Leaf(5, options=[])},
        {"pe": "unknown"},
        {"data_type": "unknown"},
        {"multiplication_method": "unknown"},
    ],
)
def test_invalid_arguments(kwargs):
    with pytest.raises(ValueError, match=r"must|require|Unsupported"):
        schur_matrix_inverse(**({"N": 5} | kwargs))


@pytest.mark.parametrize("mode", ["top", "bot", "mid"])
@pytest.mark.parametrize("size", [1, 3, 5, 8])
def test_legacy_values(mode, size):
    graph = analytical_block_matrix_inverse(size, mode=mode)
    assert graph.name == "Analytical block matrix-inversion"
    _check(graph, _matrix(size, "hermitian", "real"), "hermitian", "real")


def test_analytical_leaf_handles_zero_scalar_pivot():
    graph = schur_matrix_inverse(2)
    assert graph.evaluate_outputs([0, 1, 0]) == [0, 1, 0]


@pytest.mark.parametrize(
    ("preset", "expected"),
    [
        ("balanced", ((2, 3), (2, 3))),
        ("top", (3, (3, (3, 1)))),
        ("bot", (((1, 3), 3), 3)),
    ],
)
def test_preset_partition_shapes(preset, expected):
    from b_asic.sfg_generators.matrix_inversion import _schur_partition

    def shape(tree):
        return tree.size if isinstance(tree, Leaf) else (shape(tree[0]), shape(tree[1]))

    tree = _schur_partition(10, preset, 3, "qr", None, "hermitian", "real")
    assert shape(tree) == expected


@pytest.mark.parametrize("multiplication_method", ["four", "three", "threealt"])
@pytest.mark.parametrize("mode", ["eqs", "mult"])
def test_complex_symmetric_ldlt_multiplication_methods(multiplication_method, mode):
    graph = schur_matrix_inverse(
        3,
        partition=Leaf(3, method="ldlt", options={"mode": mode}),
        data_type="split",
        structure="symmetric",
        pe="mads",
        multiplication_method=multiplication_method,
    )
    _check(graph, _matrix(3, "symmetric", "split"), "symmetric", "split")


@pytest.mark.parametrize("structure", ["general", "symmetric"])
def test_unpartitioned_complex_scalar(structure):
    graph = schur_matrix_inverse(1, partition=1, data_type="split", structure=structure)
    np.testing.assert_allclose(graph.evaluate_outputs([2, 3]), [2 / 13, -3 / 13])
