"""
B-ASIC signal flow graph generators.

This module contains a number of functions generating SFGs for matrix operations.
"""

from b_asic.core_operations import (
    MAD,
)
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output
from b_asic.utility_operations import DontCare


def matrix_multiplication(
    m: int,
    n: int,
    p: int,
    name: str | None = None,
    mad_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
) -> SFG:
    r"""
    Generate a structure for the multiplication of matrices A and B.
    Where A is of size :math:`m \times n` and B :math:`n \times p`.

    Parameters
    ----------
    m : int
        Number of rows in A.
    n : int
        Number of columns in A (and rows in B).
    p : int
        Number of columns in B.
    name : Name, optional
        The name of the SFG. If None, "Matrix-multiplication".
    mad_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.MAD`.

    Returns
    -------
    SFG
        Signal Flow Graph
    """
    if name is None:
        name = "Matrix-multiplication"
    if mad_properties is None:
        mad_properties = {}

    A = [[Input(f"A[{i},{j}]") for i in range(n)] for j in range(m)]
    B = [[Input(f"B[{i},{j}]") for i in range(p)] for j in range(n)]

    C = []
    for i in range(m):
        for j in range(p):
            tmp = DontCare()
            for k in range(n):
                tmp = MAD(A[i][k], B[k][j], tmp, do_add=(k != 0), **mad_properties)
            C.append(Output(tmp, f"C[{i},{j}]"))

    inputs = [elem for row in A for elem in row] + [elem for row in B for elem in row]
    outputs = C

    return SFG(inputs, outputs, name=name)
