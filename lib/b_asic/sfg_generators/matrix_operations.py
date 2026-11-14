"""
B-ASIC signal flow graph generators.

This module contains a number of functions generating SFGs for matrix operations.

With ``mem=True``, matrices A, B, and C use separate named memories, each stored
in row-major order starting at address zero. A has :math:`mn` locations with
address :math:`in + j`; B has :math:`np` locations with address :math:`ip + j`;
C has :math:`mp` locations with address :math:`ip + j`. Indices are zero-based.
The input order is all of A followed by all of B; outputs follow C's row order.
"""

from b_asic.core_operations import (
    MAD,
    Addition,
    Constant,
    Multiplication,
    Subtraction,
)
from b_asic.sfg import SFG
from b_asic.special_operations import Input, MemoryRead, MemoryWrite, Output
from b_asic.utility_operations import DontCare


def matrix_multiplication(
    m: int,
    n: int | None = None,
    p: int | None = None,
    *,
    name: str | None = None,
    mad_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
    mem: bool = False,
) -> SFG:
    r"""
    Generate a structure for the multiplication of matrices A and B.
    Where A is of size :math:`m \times n` and B :math:`n \times p`.

    Parameters
    ----------
    m : int
        Number of rows in A.
    n : int, optional
        Number of columns in A (and rows in B). If None, use m.
    p : int, optional
        Number of columns in B. If None, use m.
    name : :data:`~b_asic.types.Name`, optional
        The name of the SFG. If None, "Matrix-multiplication".
    mad_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.MAD`.
    mem : bool, default: False
        Use :class:`~b_asic.special_operations.MemoryRead` and
        :class:`~b_asic.special_operations.MemoryWrite` instead of
        :class:`~b_asic.special_operations.Input` and
        :class:`~b_asic.special_operations.Output`. Matrices use separate
        memories named ``A``, ``B``, and ``C``, in row-major order starting at
        address zero. Entry :math:`A_{i,j}` has address :math:`in + j`; entries
        :math:`B_{i,j}` and :math:`C_{i,j}` have address :math:`ip + j`. Memory
        sizes are :math:`mn`, :math:`np`, and :math:`mp`, respectively.

    Returns
    -------
    :class:`~b_asic.sfg.SFG`
        Signal Flow Graph
    """
    n = m if n is None else n
    p = m if p is None else p
    if name is None:
        name = "Matrix-multiplication"
    if mad_properties is None:
        mad_properties = {}

    A = [
        [
            MemoryRead(i * n + j, memory_name="A", name=f"A[{i},{j}]")
            if mem
            else Input(f"A[{i},{j}]")
            for j in range(n)
        ]
        for i in range(m)
    ]
    B = [
        [
            MemoryRead(i * p + j, memory_name="B", name=f"B[{i},{j}]")
            if mem
            else Input(f"B[{i},{j}]")
            for j in range(p)
        ]
        for i in range(n)
    ]

    C = []
    for i in range(m):
        for j in range(p):
            tmp = DontCare()
            for k in range(n):
                tmp = MAD(A[i][k], B[k][j], tmp, do_add=(k != 0), **mad_properties)
            C.append(
                MemoryWrite(i * p + j, tmp, memory_name="C", name=f"C[{i},{j}]")
                if mem
                else Output(tmp, f"C[{i},{j}]")
            )

    inputs = [elem for row in A for elem in row] + [elem for row in B for elem in row]
    outputs = C

    return SFG(inputs, outputs, name=name)


def strassen_matrix_multiplication(
    m: int,
    n: int | None = None,
    p: int | None = None,
    *,
    name: str | None = None,
    mult_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
    add_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
    sub_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
    mem: bool = False,
) -> SFG:
    r"""
    Generate a Strassen matrix multiplication SFG for A of size :math:`m \times n`
    and B of size :math:`n \times p`.

    Parameters
    ----------
    m : int
        Positive number of rows in A.
    n : int, optional
        Positive number of columns in A and rows in B. If None, use m.
    p : int, optional
        Positive number of columns in B. If None, use m.
    name : str, optional
        SFG name. Defaults to "Strassen matrix-multiplication".
    mult_properties : dictionary, optional
        Properties passed to every :class:`~b_asic.core_operations.Multiplication`,
        such as ``latency``, ``latency_offsets``, and ``execution_time``.
    add_properties : dictionary, optional
        Properties passed to every :class:`~b_asic.core_operations.Addition`.
    sub_properties : dictionary, optional
        Properties passed to every :class:`~b_asic.core_operations.Subtraction`.
        If omitted, use ``add_properties`` for subtractions as well.
    mem : bool, default: False
        Use :class:`~b_asic.special_operations.MemoryRead` and
        :class:`~b_asic.special_operations.MemoryWrite` instead of
        :class:`~b_asic.special_operations.Input` and
        :class:`~b_asic.special_operations.Output`. Matrices use separate
        memories named ``A``, ``B``, and ``C``, in row-major order starting at
        address zero. Entry :math:`A_{i,j}` has address :math:`in + j`; entries
        :math:`B_{i,j}` and :math:`C_{i,j}` have address :math:`ip + j`. Memory
        sizes are :math:`mn`, :math:`np`, and :math:`mp`, respectively. Padding is internal
        and occupies no memory locations.

    Returns
    -------
    :class:`~b_asic.sfg.SFG`
        Inputs are the elements of A followed by B, each in row-major order,
        named ``A[i,j]`` and ``B[i,j]`` with zero-based row and column indices.
        Outputs are the elements of :math:`C = AB` in row-major order, named ``C[i,j]``.

    Notes
    -----
    Each dimension is independently zero-padded to the next power of two.
    Padding uses internal constants and adds no external inputs or outputs.
    Recursion uses seven block products until a block dimension is one, when
    conventional multiplication is used. Padding may add arithmetic operations;
    the graph is not guaranteed to be smaller than conventional multiplication.

    References
    ----------
    .. [1] V. Strassen, "Gaussian elimination is not optimal", Numerische
       Mathematik, 13, 354-356, 1969. https://doi.org/10.1007/BF02165411
    """
    n = m if n is None else n
    p = m if p is None else p
    for dimension, value in (("m", m), ("n", n), ("p", p)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{dimension} must be an integer")
        if value < 1:
            raise ValueError(f"{dimension} must be positive")
    mult_properties = {} if mult_properties is None else mult_properties
    add_properties = {} if add_properties is None else add_properties
    sub_properties = add_properties if sub_properties is None else sub_properties

    a = [
        [
            MemoryRead(i * n + j, memory_name="A", name=f"A[{i},{j}]")
            if mem
            else Input(f"A[{i},{j}]")
            for j in range(n)
        ]
        for i in range(m)
    ]
    b = [
        [
            MemoryRead(i * p + j, memory_name="B", name=f"B[{i},{j}]")
            if mem
            else Input(f"B[{i},{j}]")
            for j in range(p)
        ]
        for i in range(n)
    ]
    padded_m, padded_n, padded_p = (
        1 << (value - 1).bit_length() for value in (m, n, p)
    )
    zero = Constant(0)
    padded_a = [
        [a[i][j] if i < m and j < n else zero for j in range(padded_n)]
        for i in range(padded_m)
    ]
    padded_b = [
        [b[i][j] if i < n and j < p else zero for j in range(padded_p)]
        for i in range(padded_n)
    ]

    def combine(left, right, *, subtract=False):
        operation = Subtraction if subtract else Addition
        properties = sub_properties if subtract else add_properties
        return [
            [operation(x, y, **properties) for x, y in zip(lrow, rrow, strict=True)]
            for lrow, rrow in zip(left, right, strict=True)
        ]

    def split(matrix):
        rows, cols = len(matrix) // 2, len(matrix[0]) // 2
        return (
            [row[:cols] for row in matrix[:rows]],
            [row[cols:] for row in matrix[:rows]],
            [row[:cols] for row in matrix[rows:]],
            [row[cols:] for row in matrix[rows:]],
        )

    def multiply(left, right):
        rows, inner, cols = len(left), len(right), len(right[0])
        if min(rows, inner, cols) == 1:
            result = []
            for row in left:
                result_row = []
                for col in range(cols):
                    products = [
                        Multiplication(row[k], right[k][col], **mult_properties)
                        for k in range(inner)
                    ]
                    total = products[0]
                    for product in products[1:]:
                        total = Addition(total, product, **add_properties)
                    result_row.append(total)
                result.append(result_row)
            return result

        a11, a12, a21, a22 = split(left)
        b11, b12, b21, b22 = split(right)
        product1 = multiply(combine(a11, a22), combine(b11, b22))
        product2 = multiply(combine(a21, a22), b11)
        product3 = multiply(a11, combine(b12, b22, subtract=True))
        product4 = multiply(a22, combine(b21, b11, subtract=True))
        product5 = multiply(combine(a11, a12), b22)
        product6 = multiply(combine(a21, a11, subtract=True), combine(b11, b12))
        product7 = multiply(combine(a12, a22, subtract=True), combine(b21, b22))

        c11 = combine(
            combine(combine(product1, product4), product5, subtract=True), product7
        )
        c12 = combine(product3, product5)
        c21 = combine(product2, product4)
        c22 = combine(
            combine(combine(product1, product2, subtract=True), product3), product6
        )
        return [lrow + rrow for lrow, rrow in zip(c11, c12, strict=True)] + [
            lrow + rrow for lrow, rrow in zip(c21, c22, strict=True)
        ]

    result = multiply(padded_a, padded_b)
    inputs = [elem for row in a for elem in row] + [elem for row in b for elem in row]
    outputs = [
        MemoryWrite(i * p + j, result[i][j], memory_name="C", name=f"C[{i},{j}]")
        if mem
        else Output(result[i][j], f"C[{i},{j}]")
        for i in range(m)
        for j in range(p)
    ]
    return SFG(
        inputs,
        outputs,
        name="Strassen matrix-multiplication" if name is None else name,
    )
