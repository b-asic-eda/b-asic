"""Correctness and topology checks for comparator-based sorting SFGs."""

from functools import cache
from itertools import product
from random import Random

import pytest

from b_asic.core_operations import Comparator
from b_asic.sfg_generators import (
    bitonic_sort,
    bubble_sort,
    insertion_sort,
    odd_even_merge_sort,
    pairwise_sort,
    shell_sort,
)
from b_asic.special_operations import Input, Output

GENERATORS = (
    bubble_sort,
    insertion_sort,
    bitonic_sort,
    shell_sort,
    odd_even_merge_sort,
    pairwise_sort,
)


@pytest.mark.parametrize("generator", GENERATORS)
@pytest.mark.parametrize("size", range(1, 9))
def test_sorting_zero_one_principle(generator, size):
    # Exhaustive binary inputs prove the network sorts every totally ordered
    # input for this size, and cover duplicate values and pruned channels.
    sfg = generator(size)
    assert sfg.input_count == size
    assert sfg.output_count == size
    assert all(isinstance(op, (Input, Output, Comparator)) for op in sfg.operations)
    for inputs in product((0, 1), repeat=size):
        assert sfg.evaluate_outputs(inputs) == sorted(inputs)


@pytest.mark.parametrize("generator", GENERATORS)
@pytest.mark.parametrize("size", [9, 15, 16, 17, 31, 32])
def test_sorting_numeric_inputs(generator, size):
    sfg = generator(size)
    rng = Random(42)
    cases = [list(range(size)), list(reversed(range(size)))]
    cases.extend([rng.choices(range(-20, 20), k=size) for _ in range(4)])
    cases.append([rng.uniform(-10, 10) for _ in range(size)])
    for inputs in cases:
        assert sfg.evaluate_outputs(inputs) == sorted(inputs)


@pytest.mark.parametrize("size", [1, 2, 4, 8, 16])
@pytest.mark.parametrize("generator", GENERATORS)
def test_sorting_comparator_counts(generator, size):
    sfg = generator(size)
    count = len(sfg.find_by_type(Comparator))
    stages = size.bit_length() - 1

    @cache
    def depth(operation):
        previous = max(
            (depth(port.connected_source.operation) for port in operation.inputs),
            default=0,
        )
        return previous + isinstance(operation, Comparator)

    network_depth = max(depth(output) for output in sfg.output_operations)
    if generator in (bubble_sort, insertion_sort):
        assert count == size * (size - 1) // 2
        assert network_depth == max(0, 2 * size - 3)
    elif generator is bitonic_sort:
        assert count == size * stages * (stages + 1) // 4
        assert network_depth == stages * (stages + 1) // 2
    elif generator in (odd_even_merge_sort, pairwise_sort):
        assert count == size * stages * (stages - 1) // 4 + size - 1
        assert network_depth == stages * (stages + 1) // 2
    else:
        assert count == {1: 0, 2: 1, 4: 6, 8: 24, 16: 83}[size]
        assert network_depth <= stages * (stages + 1)


@pytest.mark.parametrize("generator", GENERATORS)
@pytest.mark.parametrize("size", [0, -1, -8])
def test_sorting_nonpositive_size(generator, size):
    with pytest.raises(ValueError, match="size must be positive"):
        generator(size)


@pytest.mark.parametrize("generator", GENERATORS)
@pytest.mark.parametrize("size", [2.5, "4", True, None])
def test_sorting_noninteger_size(generator, size):
    with pytest.raises(TypeError, match="size must be an integer"):
        generator(size)
