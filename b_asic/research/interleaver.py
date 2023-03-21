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
    inputorders = list(range(size))
    outputorders = inputorders[:]
    random.shuffle(outputorders)
    inputorders, outputorders = _insert_delays(
        inputorders, outputorders, min_lifetime, cyclic
    )
    return ProcessCollection(
        {
            PlainMemoryVariable(inputorder, 0, {0: outputorders[i] - inputorder})
            for i, inputorder in enumerate(inputorders)
        },
        len(inputorders),
        cyclic,
    )


def generate_matrix_transposer(
    rows: int,
    cols: Optional[int] = None,
    min_lifetime: int = 0,
    cyclic: bool = True,
) -> ProcessCollection:
    r"""
    Generate a ProcessCollection with memory variable corresponding to transposing a
    matrix of size *rows* :math:`\times` *cols*. If *cols* is not provided, a
    square matrix of size *rows* :math:`\times` *rows* is used.

    Parameters
    ----------
    rows : int
        Number of rows in input matrix.
    cols : int, optional
        Number of columns in input matrix. If not provided assumed to be equal
        to *rows*, i.e., a square matrix.
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
    if cols is None:
        cols = rows

    inputorder = []
    for col in range(cols):
        for row in range(rows):
            inputorder.append(row + rows * col)

    outputorder = []
    for row in range(rows):
        for col in range(cols):
            outputorder.append(col * rows + row)

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
