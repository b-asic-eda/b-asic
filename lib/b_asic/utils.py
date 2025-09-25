"""B-ASIC Utilities."""

from collections.abc import Sequence

from b_asic.types import Num


def interleave(*args) -> list[Num]:
    """
    Interleave a number of arrays.

    Parameters
    ----------
    *args : a number of arrays
        Arrays to interleave. Must be of the same length.

    Examples
    --------
    >>> from b_asic.utils import interleave
    ...
    ... a = [1, 2]
    ... b = [3, 4]
    ... interleave(a, b)
    [1, 3, 2, 4]
    >>> c = [-1, 0]
    ... interleave(a, b, c)
    [1, 3, -1, 2, 4, 0]
    """
    return [val for tup in zip(*args, strict=True) for val in tup]


def downsample(a: Sequence[Num], factor: int, phase: int = 0) -> list[Num]:
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

    Examples
    --------
    >>> from b_asic.utils import downsample
    ...
    ... a = list(range(6))
    ... downsample(a, 3)
    [0, 3]
    >>> downsample(a, 3, 1)
    [1, 4]
    """
    return a[phase::factor]


def upsample(a: Sequence[Num], factor: int, phase: int = 0) -> list[Num]:
    """
    Upsample a sequence with an integer factor.

    Insert *factor* - 1 zeros between every value, starting with *phase* zeros.

    Parameters
    ----------
    a : array
        The array to upsample.
    factor : int
        The factor to upsample with.
    phase : int, default: 0
        The phase of the upsampling.

    Examples
    --------
    >>> from b_asic.utils import upsample
    ...
    ... a = list(range(1, 4))
    ... upsample(a, 3)
    [1, 0, 0, 2, 0, 0, 3, 0, 0]
    >>> upsample(a, 3, 1)
    [0, 1, 0, 0, 2, 0, 0, 3, 0]
    """
    length = len(a)
    zeros = [0] * length
    args = [zeros for _ in range(phase)]
    args.append(a)
    args.extend(zeros for _ in range(factor - phase - 1))
    return interleave(*args)


def decompose(a: Sequence[Num], factor: int) -> list[list[Num]]:
    """
    Polyphase decompose signal *a* into *factor* parts.

    Return *factor* lists, each with every *factor* value.

    Parameters
    ----------
    a : array
        The array to polyphase decompose.
    factor : int
        The number of polyphase components with.

    Examples
    --------
    >>> from b_asic.utils import decompose
    ...
    ... a = list(range(6))
    ... decompose(a, 2)
    [[0, 2, 4], [1, 3, 5]]
    >>> decompose(a, 3)
    [[0, 3], [1, 4], [2, 5]]
    """
    return [downsample(a, factor, phase) for phase in range(factor)]


def int_to_csd(n: int) -> list[int]:
    """
    Return the Canonical Signed Digit (CSD) representation of an integer with MSB first.

    Parameters
    ----------
    n : int
        The integer to convert.
    """
    csd = []
    while n != 0:
        if n % 2 == 0:
            csd.append(0)
            n //= 2
        else:
            r = n % 4
            if r == 1:
                csd.append(1)
            else:
                csd.append(-1)
            n = (n - csd[-1]) // 2
    return csd[::-1]


def float_to_csd(n: float | int) -> tuple[list[int], int]:
    """
    Convert a number (int or float) to its Canonical Signed Digit (CSD)
    representation with MSB first.

    Returns (csd, frac_bits) where `csd` is a list of digits (LSB first) in {-1, 0, 1}
    and `frac_bits` is the number of fractional bits (can be negative).

    Parameters
    ----------
    n : float or int
        The number to convert.
    """
    if n == 0:
        return ([], 0)

    # calculate frac_bits
    abs_n = abs(n)
    k = 0
    while True:
        val = abs_n * (1 << k)
        m = round(val)
        if abs(val - m) == 0:
            frac_bits = k
            int_val = int(m)
            break
        k += 1

    csd_digits = int_to_csd(int_val)

    # apply sign
    if n < 0:
        csd_digits = [-d for d in csd_digits]

    # trim zeros from the LSB side and update frac_bits accordingly
    while csd_digits and csd_digits[-1] == 0:
        csd_digits.pop()
        frac_bits -= 1

    return csd_digits, frac_bits
