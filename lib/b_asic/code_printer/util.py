"""Utility functions for the code printers."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from b_asic.architecture import ProcessingElement


def time_bin_str(time: int, pe: "ProcessingElement"):
    return bin(time)[2:].zfill(pe.schedule_time.bit_length())


def bin_str(num: int, bits: int) -> str:
    """
    Return binary representation of integer.

    If *int* is negatine, the two's complement representation it used.

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
    return bin(num + 2**bits)[2:].zfill(bits) if num < 0 else bin(num)[2:].zfill(bits)
