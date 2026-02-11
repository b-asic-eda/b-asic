"""Utility functions for the code printers."""

import math


def time_bin_str(time: int, schedule_time: int) -> str:
    """Return the binary string representation of time for the given schedule_time."""
    return f"{time:0{(schedule_time - 1).bit_length()}b}"


def selector_bits(num_sources: int) -> int:
    """
    Return the number of bits needed to select between *num_sources*.

    Parameters
    ----------
    num_sources : int
        Number of sources to select from.
    """
    return max(1, math.ceil(math.log2(num_sources)))


def bin_str(num: int, bits: int) -> str:
    """
    Return binary representation of integer.

    If *num* is negative, the two's complement representation it used.

    .. note:: This does not check that *num* fits in *bits* bits.

    Parameters
    ----------
    num : int
        Number to convert.
    bits : int
        Number of bits to use.

    Returns
    -------
    str
        The resulting binary string.
    """
    return f"{(num + 2**bits):0{bits}b}" if num < 0 else f"{num:0{bits}b}"
