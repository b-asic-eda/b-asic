"""Tests for matrix multiplication SFG generators."""

from copy import deepcopy

import numpy as np
import pytest

from b_asic.core_operations import Addition, Constant, Multiplication, Subtraction
from b_asic.sfg_generators import matrix_multiplication, strassen_matrix_multiplication
from b_asic.special_operations import Input, MemoryRead, MemoryWrite, Output


@pytest.mark.parametrize(
    "generator", [matrix_multiplication, strassen_matrix_multiplication]
)
@pytest.mark.parametrize("dimensions", [{}, {"n": None, "p": None}, {"n": 2}, {"p": 2}])
@pytest.mark.parametrize("mem", [False, True])
def test_optional_dimensions(generator, dimensions, mem):
    m = 3
    n = dimensions.get("n") or m
    p = dimensions.get("p") or m
    graph = generator(m, **dimensions, mem=mem)
    assert graph.input_count == m * n + n * p
    assert graph.output_count == m * p
    a = np.arange(m * n).reshape(m, n)
    b = np.arange(n * p).reshape(n, p)
    np.testing.assert_allclose(
        graph.evaluate_outputs([*a.ravel(), *b.ravel()]), (a @ b).ravel()
    )


@pytest.mark.parametrize(
    "generator", [matrix_multiplication, strassen_matrix_multiplication]
)
def test_options_are_keyword_only(generator):
    with pytest.raises(TypeError, match="positional"):
        generator(2, 2, 2, "product")


@pytest.mark.parametrize(
    "generator", [matrix_multiplication, strassen_matrix_multiplication]
)
@pytest.mark.parametrize(("m", "n", "p"), [(1, 1, 1), (2, 4, 2), (3, 5, 2)])
@pytest.mark.parametrize("mem", [False, True])
def test_matrix_memory_layout_and_values(generator, m, n, p, mem):
    graph = generator(m, n, p, mem=mem)
    assert len(graph.input_operations) == m * n + n * p
    assert len(graph.output_operations) == m * p
    for memory_name, rows, cols, operations, operation_type in (
        ("A", m, n, graph.input_operations[: m * n], MemoryRead if mem else Input),
        ("B", n, p, graph.input_operations[m * n :], MemoryRead if mem else Input),
        ("C", m, p, graph.output_operations, MemoryWrite if mem else Output),
    ):
        for i in range(rows):
            for j in range(cols):
                operation = operations[i * cols + j]
                assert type(operation) is operation_type
                assert operation.name == f"{memory_name}[{i},{j}]"
                if mem:
                    assert operation.address == i * cols + j
                    assert operation.memory_name == memory_name
    a = np.arange(m * n).reshape(m, n) + 1j
    b = np.arange(n * p).reshape(n, p) - 2j
    actual = graph.evaluate_outputs([*a.ravel(), *b.ravel()])
    np.testing.assert_allclose(np.array(actual).reshape(m, p), a @ b)


@pytest.mark.parametrize(
    ("m", "n", "p"),
    [
        (1, 1, 1),
        (2, 2, 2),
        (4, 4, 4),
        (8, 8, 8),
        (2, 4, 8),
        (8, 2, 4),
        (3, 3, 3),
        (3, 5, 2),
        (2, 3, 5),
        (5, 2, 3),
        (1, 5, 3),
        (5, 3, 1),
        (3, 1, 5),
    ],
)
@pytest.mark.parametrize("complex_values", [False, True])
def test_strassen_matches_numpy(m, n, p, complex_values):
    sfg = strassen_matrix_multiplication(m, n, p)
    assert sfg.input_count == m * n + n * p
    assert sfg.output_count == m * p
    rng = np.random.default_rng(42)
    for _ in range(3):
        a = rng.integers(-5, 6, size=(m, n))
        b = rng.integers(-5, 6, size=(n, p))
        if complex_values:
            a = a + 1j * rng.integers(-5, 6, size=a.shape)
            b = b + 1j * rng.integers(-5, 6, size=b.shape)
        inputs = [*a.ravel().tolist(), *b.ravel().tolist()]
        actual = np.array(sfg.evaluate_outputs(inputs)).reshape(m, p)
        np.testing.assert_allclose(actual, a @ b)


@pytest.mark.parametrize("size", [1, 2, 4, 8])
def test_strassen_operation_counts(size):
    sfg = strassen_matrix_multiplication(size, size, size)
    levels = size.bit_length() - 1
    assert len(sfg.find_by_type(Multiplication)) == 7**levels
    assert len(sfg.find_by_type(Addition)) + len(sfg.find_by_type(Subtraction)) == (
        6 * (7**levels - 4**levels)
    )
    assert not sfg.find_by_type(Constant)


def test_strassen_rectangular_seven_block_products():
    sfg = strassen_matrix_multiplication(2, 4, 8)
    assert len(sfg.find_by_type(Multiplication)) == 7 * (1 * 2 * 4)


def test_strassen_indexed_port_names():
    m, n, p = 3, 2, 4
    sfg = strassen_matrix_multiplication(m, n, p, name="product")
    assert sfg.name == "product"
    assert [op.name for op in sfg.input_operations] == [
        f"A[{i},{j}]" for i in range(m) for j in range(n)
    ] + [f"B[{i},{j}]" for i in range(n) for j in range(p)]
    assert [op.name for op in sfg.output_operations] == [
        f"C[{i},{j}]" for i in range(m) for j in range(p)
    ]
    assert (
        strassen_matrix_multiplication(1, 1, 1).name == "Strassen matrix-multiplication"
    )


@pytest.mark.parametrize("separate_sub_properties", [False, True])
def test_strassen_operator_properties(separate_sub_properties):
    mult_properties = {"latency": 5, "execution_time": 2}
    add_properties = {
        "latency_offsets": {"in0": 1, "in1": 0, "out0": 3},
        "execution_time": 1,
    }
    sub_properties = {"latency": 4, "execution_time": 2}
    original_properties = deepcopy((mult_properties, add_properties, sub_properties))
    sfg = strassen_matrix_multiplication(
        3,
        3,
        3,
        mult_properties=mult_properties,
        add_properties=add_properties,
        sub_properties=sub_properties if separate_sub_properties else None,
    )
    for operation_type, properties in (
        (Multiplication, mult_properties),
        (Addition, add_properties),
        (Subtraction, sub_properties if separate_sub_properties else add_properties),
    ):
        operations = sfg.find_by_type(operation_type)
        assert operations
        expected_offsets = properties.get("latency_offsets") or {
            "in0": 0,
            "in1": 0,
            "out0": properties["latency"],
        }
        for operation in operations:
            assert operation.latency_offsets == expected_offsets
            assert operation.execution_time == properties["execution_time"]
    assert (mult_properties, add_properties, sub_properties) == original_properties


@pytest.mark.parametrize("dimension", range(3))
@pytest.mark.parametrize("value", [0, -1])
def test_strassen_nonpositive_dimensions(dimension, value):
    dimensions = [2, 2, 2]
    dimensions[dimension] = value
    with pytest.raises(ValueError, match="must be positive"):
        strassen_matrix_multiplication(*dimensions)


@pytest.mark.parametrize("dimension", range(3))
@pytest.mark.parametrize("value", [2.5, "2", True])
def test_strassen_noninteger_dimensions(dimension, value):
    dimensions = [2, 2, 2]
    dimensions[dimension] = value
    with pytest.raises(TypeError, match="must be an integer"):
        strassen_matrix_multiplication(*dimensions)


def test_strassen_requires_m():
    with pytest.raises(TypeError, match="m must be an integer"):
        strassen_matrix_multiplication(None)
