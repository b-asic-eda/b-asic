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
    args = []
    for _ in range(phase):
        args.append(zeros)
    args.append(a)
    for _ in range(factor - phase - 1):
        args.append(zeros)
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
