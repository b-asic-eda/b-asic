"""
Functions to generate memory-variable test data that are used for research.
"""

import random
from typing import List, Optional, Tuple

from b_asic.process import PlainMemoryVariable
from b_asic.resources import ProcessCollection


def _insert_delays(
    inputorder: List[int], outputorder: List[int], min_lifetime: int, cyclic: bool
) -> Tuple[List[int], List[int]]:
    size = len(inputorder)
    maxdiff = min(outputorder[i] - inputorder[i] for i in range(size))
    outputorder = [o - maxdiff + min_lifetime for o in outputorder]
    maxdelay = max(outputorder[i] - inputorder[i] for i in range(size))
    if cyclic:
        if maxdelay >= size:
            inputorder = inputorder + [i + size for i in inputorder]
            outputorder = outputorder + [o + size for o in outputorder]
    return inputorder, outputorder


def generate_random_interleaver(
    size: int, min_lifetime: int = 0, cyclic: bool = True
) -> ProcessCollection:
    """
    Generate a ProcessCollection with memory variable corresponding to a random
    interleaver with length *size*.

    Parameters
    ----------
    size : int
        The size of the random interleaver sequence.
    min_lifetime : int, default: 0
        The minimum lifetime for a memory variable. Default is 0 meaning that at least
        one variable is passed from the input to the output directly,
    cyclic : bool, default: True
        If the interleaver should operate continuously in a cyclic manner. That is,
        start a new interleaving operation directly after the previous.

    Returns
    -------
    ProcessCollection

    """
    inputorder = list(range(size))
    outputorder = inputorder[:]
    random.shuffle(outputorder)
    inputorder, outputorder = _insert_delays(
        inputorder, outputorder, min_lifetime, cyclic
    )
    return ProcessCollection(
        {
            PlainMemoryVariable(inputorder[i], 0, {0: outputorder[i] - inputorder[i]})
            for i in range(len(inputorder))
        },
        len(inputorder),
        cyclic,
    )


def generate_matrix_transposer(
    height: int,
    width: Optional[int] = None,
    min_lifetime: int = 0,
    cyclic: bool = True,
) -> ProcessCollection:
    r"""
    Generate a ProcessCollection with memory variable corresponding to transposing a
    matrix of size *height* :math:`\times` *width*. If *width* is not provided, a
    square matrix of size *height* :math:`\times` *height* is used.

    Parameters
    ----------
    height : int
        Matrix height.
    width : int, optional
        Matrix width. If not provided assumed to be equal to height, i.e., a square
        matrix.
    min_lifetime : int, default: 0
        The minimum lifetime for a memory variable. Default is 0 meaning that at
        least one variable is passed from the input to the output directly,
    cyclic : bool, default: True
        If the interleaver should operate continuously in a cyclic manner. That is,
        start a new interleaving operation directly after the previous.

    Returns
    -------
    ProcessCollection
    """
    if width is None:
        width = height

    inputorder = []
    for row in range(height):
        for col in range(width):
            inputorder.append(col + width * row)

    outputorder = []
    for row in range(width):
        for col in range(height):
            outputorder.append(col * width + row)

    inputorder, outputorder = _insert_delays(
        inputorder, outputorder, min_lifetime, cyclic
    )
    return ProcessCollection(
        {
            PlainMemoryVariable(
                inputorder[i],
                0,
                {0: outputorder[i] - inputorder[i]},
                name=f"{inputorder[i]}",
            )
            for i in range(len(inputorder))
        },
        len(inputorder),
        cyclic,
    )
