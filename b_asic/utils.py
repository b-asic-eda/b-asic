"""B-ASIC Utils."""

from typing import List, Sequence

from b_asic.types import Num


def interleave(*args) -> List[Num]:
    """
    Interleave a number of arrays.

    For the input ``interleave([1, 2], [3, 4])``, return ``[1, 2, 3, 4]``.

    Parameters
    ----------
    *args : a number of arrays
        Arrays to interleave. Must be of the same length.

    Returns
    -------


    """
    return [val for tup in zip(*args) for val in tup]


def downsample(a: Sequence[Num], factor: int, phase: int = 0) -> List[Num]:
    """
    Downsample a sequence with an integer factor.

    Keeps every *factor* value, starting with *phase*.

    Parameters
    ----------
    a : array
        The array to downsample.
    factor : int
        The factor to downsample with.
    phase : int, default: 0
        The phase of the downsampling.

    Returns
    -------


    """
    return a[phase::factor]
