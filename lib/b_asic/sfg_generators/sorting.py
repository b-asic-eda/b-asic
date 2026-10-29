"""
Generate sorting networks from two-input, two-output comparators.

Inputs are real-valued, and outputs are ordered from smallest at index zero to
largest at the last index. Every network has fixed, data-independent wiring.
"""

from collections.abc import Iterable, Iterator

from b_asic.core_operations import Comparator
from b_asic.port import OutputPort
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output


def bubble_sort(size: int) -> SFG:
    """
    Generate a bubble/insertion sorting network with ascending outputs.

    Parameters
    ----------
    size : int
        Positive number of inputs and outputs.

    Returns
    -------
    SFG
        Sorting network with ``size * (size - 1) / 2`` comparators.

    See Also
    --------
    insertion_sort
    """
    _validate_size(size)
    pairs = (
        (index - 1, index) for end in range(1, size) for index in range(end, 0, -1)
    )
    return _sorting_network(size, pairs)


def insertion_sort(size: int) -> SFG:
    """
    Generate an insertion sorting network with ascending outputs.

    Parameters
    ----------
    size : int
        Positive number of inputs and outputs.

    Returns
    -------
    SFG
        The same comparator network as :func:`bubble_sort`.
    """
    return bubble_sort(size)


def bitonic_sort(size: int) -> SFG:
    """
    Generate a Batcher bitonic sorting network with ascending outputs.

    Parameters
    ----------
    size : int
        Positive number of inputs and outputs. Sizes other than powers of two
        are supported by pruning a network for the next power of two.

    Returns
    -------
    SFG
        Sorting network built from :class:`~b_asic.core_operations.Comparator`.
    """
    width = _validate_size(size)
    return _sorting_network(size, _bitonic_pairs(width))


def shell_sort(size: int) -> SFG:
    """
    Generate a Shell sorting network using Pratt's gaps, with ascending outputs.

    Parameters
    ----------
    size : int
        Positive number of inputs and outputs.

    Returns
    -------
    SFG
        Sorting network using descending gaps of the form ``2**p * 3**q``.
        Each gap uses two stages of disjoint compare-exchanges, giving
        ``O(size * log(size)**2)`` comparators and ``O(log(size)**2)`` depth.

    References
    ----------
    .. [1] Vaughan R. Pratt, "Shellsort and Sorting Networks", Stanford
       University Computer Science Department, report STAN-CS-72-260, 1972.
    """
    _validate_size(size)
    gaps = []
    power_of_two = 1
    while power_of_two < size:
        gap = power_of_two
        while gap < size:
            gaps.append(gap)
            gap *= 3
        power_of_two *= 2
    # Processing all larger Pratt gaps makes each gap subsequence both
    # 2-sorted and 3-sorted. Any inversions are disjoint adjacent pairs,
    # so even and odd subsequence positions can be processed in two stages.
    pairs = (
        (index, index + gap)
        for gap in sorted(gaps, reverse=True)
        for parity in (0, 1)
        for index in range(size - gap)
        if (index // gap) % 2 == parity
    )
    return _sorting_network(size, pairs)


def odd_even_merge_sort(size: int) -> SFG:
    """
    Generate a Batcher odd-even merge sorting network with ascending outputs.

    Parameters
    ----------
    size : int
        Positive number of inputs and outputs. Sizes other than powers of two
        are supported by pruning a network for the next power of two.

    Returns
    -------
    SFG
        Sorting network built from :class:`~b_asic.core_operations.Comparator`.
        This uses recursive odd-even merging, rather than odd-even transposition.
    """
    width = _validate_size(size)
    return _sorting_network(size, _odd_even_sort_pairs(0, width))


def pairwise_sort(size: int) -> SFG:
    """
    Generate a Parberry pairwise sorting network with ascending outputs.

    Parameters
    ----------
    size : int
        Positive number of inputs and outputs. Sizes other than powers of two
        are supported by pruning a network for the next power of two.

    Returns
    -------
    SFG
        Sorting network built from :class:`~b_asic.core_operations.Comparator`.

    References
    ----------
    .. [1] Ian Parberry, "The Pairwise Sorting Network", Parallel Processing
       Letters, 2(2,3), 205-211, 1992. https://ianparberry.com/pubs/pairwise.pdf
    """
    width = _validate_size(size)
    return _sorting_network(size, _pairwise_pairs(list(range(width))))


def _validate_size(size: int) -> int:
    """Validate the channel count and return the next power of two."""
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeError("size must be an integer")
    if size < 1:
        raise ValueError("size must be positive")
    return 1 << (size - 1).bit_length()


def _sorting_network(size: int, pairs: Iterable[tuple[int, int]]) -> SFG:
    """Wire compare-exchanges, eliminating virtual positive-infinity inputs."""
    inputs = [Input() for _ in range(size)]
    ports: list[OutputPort | None] = [source.output(0) for source in inputs]
    ports.extend([None] * ((1 << (size - 1).bit_length()) - size))
    for low, high in pairs:
        # None denotes a virtual +infinity. It may move during descending
        # bitonic stages, so track its location rather than dropping indices.
        if ports[low] is None:
            ports[low], ports[high] = ports[high], None
        elif ports[high] is not None:
            comparator = Comparator(ports[low], ports[high])
            ports[low], ports[high] = comparator.outputs
    outputs = [Output(port) for port in ports[:size]]
    return SFG(inputs=inputs, outputs=outputs)


def _bitonic_pairs(width: int) -> Iterator[tuple[int, int]]:
    block = 2
    while block <= width:
        distance = block // 2
        while distance:
            for index in range(width):
                other = index ^ distance
                if other > index:
                    yield (index, other) if index & block == 0 else (other, index)
            distance //= 2
        block *= 2


def _odd_even_sort_pairs(start: int, width: int) -> Iterator[tuple[int, int]]:
    if width > 1:
        half = width // 2
        yield from _odd_even_sort_pairs(start, half)
        yield from _odd_even_sort_pairs(start + half, half)
        yield from _odd_even_merge_pairs(start, width, 1)


def _odd_even_merge_pairs(
    start: int, width: int, stride: int
) -> Iterator[tuple[int, int]]:
    step = 2 * stride
    if step < width:
        yield from _odd_even_merge_pairs(start, width, step)
        yield from _odd_even_merge_pairs(start + stride, width, step)
        for index in range(start + stride, start + width - stride, step):
            yield index, index + stride
    else:
        yield start, start + stride


def _pairwise_pairs(indices: list[int]) -> Iterator[tuple[int, int]]:
    if len(indices) < 2:
        return
    for index in range(0, len(indices), 2):
        yield indices[index], indices[index + 1]
    yield from _pairwise_pairs(indices[::2])
    yield from _pairwise_pairs(indices[1::2])
    # Merge sorted pairs by repeatedly halving their maximum separation.
    distance = len(indices) // 4
    while distance:
        for index in range(len(indices) // 2 - distance):
            yield indices[2 * index + 1], indices[2 * (index + distance)]
        distance //= 2
