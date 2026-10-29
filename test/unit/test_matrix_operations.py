"""Tests for the Strassen matrix multiplication SFG generator."""

from copy import deepcopy

import numpy as np
import pytest

from b_asic.core_operations import Addition, Constant, Multiplication, Subtraction
from b_asic.sfg_generators import strassen_matrix_multiplication


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
@pytest.mark.parametrize("value", [2.5, "2", True, None])
def test_strassen_noninteger_dimensions(dimension, value):
    dimensions = [2, 2, 2]
    dimensions[dimension] = value
    with pytest.raises(TypeError, match="must be an integer"):
        strassen_matrix_multiplication(*dimensions)
