"""Utility functions for the code printers."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from b_asic.architecture import ProcessingElement


def time_bin_str(time: int, pe: "ProcessingElement"):
    return f"{time:0{pe.schedule_time.bit_length()}b}"


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
    return f"{(num + 2**bits):0{bits}b}" if num < 0 else f"{num:0{bits}b}"
