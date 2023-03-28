"""
Functions to generate memory-variable test data that are used for research.
"""

import random
from itertools import product
from typing import List, Optional, Tuple

from b_asic.process import PlainMemoryVariable
from b_asic.resources import ProcessCollection


def _insert_delays(
    inputorder: List[Tuple[int, int]],
    outputorder: List[Tuple[int, int]],
    min_lifetime: int,
    cyclic: bool,
    time: int,
) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    size = len(inputorder)
    maxdiff = min(outputorder[i][0] - inputorder[i][0] for i in range(size))
    outputorder = [(o[0] - maxdiff + min_lifetime, o[1]) for o in outputorder]
    maxdelay = max(outputorder[i][0] - inputorder[i][0] for i in range(size))
    if cyclic:
        if maxdelay >= time:
            inputorder = inputorder + [(i[0] + time, i[1]) for i in inputorder]
            outputorder = outputorder + [(o[0] + time, o[1]) for o in outputorder]
    return inputorder, outputorder


def generate_random_interleaver(
    size: int, min_lifetime: int = 0, cyclic: bool = True, parallelism: int = 1
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
    parallelism : int, default: 1
        Number of values to input and output every cycle.

    Returns
    -------
    ProcessCollection

    """
    inputorders = list(product(range(size), range(parallelism)))
    outputorders = inputorders[:]
    random.shuffle(outputorders)
    inputorders, outputorders = _insert_delays(
        inputorders, outputorders, min_lifetime, cyclic, size
    )
    return ProcessCollection(
        {
            PlainMemoryVariable(
                *inputorder, {outputorders[i][1]: outputorders[i][0] - inputorder[0]}
            )
            for i, inputorder in enumerate(inputorders)
        },
        len(inputorders) // parallelism,
        cyclic,
    )


def generate_matrix_transposer(
    rows: int,
    cols: Optional[int] = None,
    min_lifetime: int = 0,
    cyclic: bool = True,
    parallelism: int = 1,
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
    parallelism : int, default: 1
        Number of values to input and output every cycle.

    Returns
    -------
    ProcessCollection
    """
    if cols is None:
        cols = rows

    if (rows * cols // parallelism) * parallelism != rows * cols:
        raise ValueError(
            f"parallelism ({parallelism}) must be an integer multiple of rows*cols"
            f" ({rows}*{cols} = {rows*cols})"
        )

    inputorders = []
    for col in range(cols):
        for row in range(rows):
            inputorders.append(((row + rows * col) // parallelism, row % parallelism))

    outputorders = []
    for row in range(rows):
        for col in range(cols):
            outputorders.append(((col * rows + row) // parallelism, col % parallelism))

    inputorders, outputorders = _insert_delays(
        inputorders, outputorders, min_lifetime, cyclic, rows * cols // parallelism
    )
    return ProcessCollection(
        {
            PlainMemoryVariable(
                *inputorder,
                {outputorders[i][1]: outputorders[i][0] - inputorder[0]},
                name=f"{inputorders[i][0]*parallelism + inputorders[i][1]}",
            )
            for i, inputorder in enumerate(inputorders)
        },
        len(inputorders) // parallelism,
        cyclic,
    )
