r"""
B-ASIC signal flow graph generators.

This module contains a number of functions generating SFGs for matrix inversion.

With ``data_type="complex"`` or ``data_type="split"``, the generators invert
Hermitian input matrices. The default ``data_type="real"`` uses symmetric
matrices. Cholesky algorithms require positive definite input matrices.
Scalar inverses use explicit :class:`~b_asic.core_operations.Reciprocal`
operations marked real-valued: diagonal pivots and Hermitian block determinants
are real. Real matrices have real-valued input and output interfaces; Hermitian
matrices have real-valued diagonal interfaces, including memory interfaces.
When only the real part of a product is needed, including diagonal inverse
updates, it is generated directly in split mode regardless of the selected
complex multiplication method.

When ``mem=True``, the input matrix and its inverse use the same packed
lower-triangular layout in the default unnamed memory. For zero-based row and
column indices :math:`i \ge j`, the address is :math:`\frac{i(i+1)}{2} + j`. Thus addresses
0, 1, 2, 3, 4, 5 correspond to entries (0, 0), (1, 0), (1, 1), (2, 0), (2, 1),
(2, 2), respectively. Each matrix occupies :math:`\frac{N(N+1)}{2}` locations;
upper-triangular entries follow by symmetry, or conjugate symmetry when
``data_type="complex"`` or ``data_type="split"``. Split graphs store each real
component at twice the packed address and its imaginary component at the next
address, occupying :math:`N(N+1)` real locations. Block and tile algorithms use
this same external layout regardless of their internal partitioning.

For example, generate a Hermitian inverse directly in real arithmetic with
three real multiplications per general complex product using::

    sfg = ldlt_matrix_inverse(4, data_type="split", multiplication_method="three")
"""

from typing import Literal

from b_asic.sfg import SFG
from b_asic.sfg_generators._matrix_arithmetic import _MatrixArithmetic


def ldlt_matrix_inverse(
    N: int,
    name: str | None = None,
    mode: Literal["eqs", "mult"] = "eqs",
    pe: Literal["addsub", "mads"] | None = None,
    mem: bool = False,
    data_type: Literal["real", "complex", "split"] = "real",
    multiplication_method: Literal["four", "three", "threealt"] = "four",
) -> SFG:
    r"""
    Generate an SFG for the LDLT matrix inverse algorithm.

    Parameters
    ----------
    N : int
        Dimension of the square input matrix.
    name : str, optional
        The name of the SFG. If None, "LDLT matrix-inversion".
    mode : {"eqs", "mult"}, default: "eqs"
        The mode of operation, either "mult" or "eqs".
    pe : {"addsub", "mads", None}, optional
        Processing element to use. None means separate Addition and Subtraction.
    mem : bool, default: False
        Use :class:`~b_asic.special_operations.MemoryRead` and
        :class:`~b_asic.special_operations.MemoryWrite` instead of
        :class:`~b_asic.special_operations.Input` and
        :class:`~b_asic.special_operations.Output`. Input and inverse entries
        use packed lower-triangular row order in the default unnamed memory:
        entry :math:`(i, j)` has address :math:`\frac{i(i+1)}{2} + j` for :math:`i \ge j`.
        Each matrix occupies :math:`\frac{N(N+1)}{2}` locations.
    data_type : {"real", "complex", "split"}, default: "real"
        Generate scalar real arithmetic for symmetric matrices, native complex
        arithmetic for Hermitian matrices, or real arithmetic with separate
        real and imaginary components for Hermitian matrices. Split interfaces
        are ordered ``real0, imag0, real1, imag1, ...``. Diagonal imaginary inputs
        are unused and diagonal imaginary outputs are zero. With ``mem=True``,
        components of packed entry address ``p`` use addresses ``2*p`` and
        ``2*p + 1`` in the same memory.
    multiplication_method : {"four", "three", "threealt"}, default: "four"
        Complex product implementation for ``data_type="split"``, matching
        :meth:`~b_asic.sfg.SFG.complex_to_real` and :meth:`~b_asic.sfg.SFG.transform`.
        General complex products use four real multiplications or three with
        extra additions. Real-real and real-complex products use only one and
        two real multiplications, respectively, regardless of this setting.
        Conjugate self-products use two squares and produce a real result.

    Returns
    -------
    :class:`~b_asic.sfg.SFG`
        Signal Flow Graph
    """
    arithmetic = _MatrixArithmetic(data_type, multiplication_method, pe)
    if name is None:
        name = "LDLT matrix-inversion"

    def ldl_decomposition(A):
        N_local = len(A)
        L = [[None for _ in range(N_local)] for _ in range(N_local)]
        D = [None for _ in range(N_local)]
        D_inv = [None for _ in range(N_local)]
        M = [[None for _ in range(N_local)] for _ in range(N_local)]

        for j in range(N_local):
            D[j] = A[j][j]
            for k in range(j):
                l_conj = arithmetic.conjugate(L[j][k])
                if pe == "mads":
                    D[j] = arithmetic.mads(
                        is_add=False,
                        in0=D[j],
                        in1=M[j][k],
                        in2=l_conj,
                        do_addsub=True,
                        real_valued=True,
                    )
                elif pe == "addsub":
                    D[j] = arithmetic.addsub(
                        is_add=False,
                        in0=D[j],
                        in1=arithmetic.multiplication(
                            M[j][k], l_conj, real_valued=True
                        ),
                    )
                else:
                    D[j] = D[j] - arithmetic.multiplication(
                        M[j][k], l_conj, real_valued=True
                    )

            D_inv[j] = arithmetic.reciprocal(D[j], name=f"D_inv[{j}]", real_valued=True)

            for i in range(j + 1, N_local):
                M[i][j] = A[i][j]
                for k in range(j):
                    l_conj = arithmetic.conjugate(L[j][k])
                    if pe == "mads":
                        M[i][j] = arithmetic.mads(
                            is_add=False,
                            in0=M[i][j],
                            in1=M[i][k],
                            in2=l_conj,
                            do_addsub=True,
                        )
                    elif pe == "addsub":
                        M[i][j] = arithmetic.addsub(
                            is_add=False,
                            in0=M[i][j],
                            in1=M[i][k] * l_conj,
                        )
                    else:
                        M[i][j] = M[i][j] - M[i][k] * l_conj

                if pe == "mads":
                    L[i][j] = arithmetic.mads(
                        is_add=True,
                        in0=None,
                        in1=M[i][j],
                        in2=D_inv[j],
                        do_addsub=False,
                    )
                else:
                    L[i][j] = M[i][j] * D_inv[j]

        return L, D, D_inv

    def ldl_l_inv(L):
        N_local = len(L)
        L_inv = [[None for _ in range(N_local)] for _ in range(N_local)]
        for i in range(1, N_local):
            for j in range(i - 1, -1, -1):
                if pe == "mads":
                    acc = L[i][j]
                    for k in range(j + 1, i):
                        acc = arithmetic.mads(
                            is_add=True,
                            in0=acc,
                            in1=L[i][k],
                            in2=L_inv[k][j],
                            do_addsub=True,
                        )
                    L_inv[i][j] = -acc
                elif pe == "addsub":
                    acc = L[i][j]
                    for k in range(j + 1, i):
                        acc = arithmetic.addsub(
                            is_add=True,
                            in0=acc,
                            in1=L[i][k] * L_inv[k][j],
                        )
                    L_inv[i][j] = -acc
                else:
                    acc = L[i][j]
                    for k in range(j + 1, i):
                        acc = acc + L[i][k] * L_inv[k][j]
                    L_inv[i][j] = -acc

        return L_inv

    def ldl_matmul(L_inv, D_inv):
        n = len(L_inv)
        res = [[None for _ in range(n)] for _ in range(n)]
        for i in range(n - 1, -1, -1):
            for j in range(i, -1, -1):
                if i == j:
                    res[i][j] = D_inv[i]
                elif pe == "mads":
                    res[i][j] = arithmetic.mads(
                        is_add=True,
                        in0=None,
                        in1=D_inv[i],
                        in2=L_inv[i][j],
                        do_addsub=False,
                    )
                else:
                    res[i][j] = D_inv[i] * L_inv[i][j]

                for k in range(i + 1, n):
                    l_inv_conj = arithmetic.conjugate(L_inv[k][i])
                    if pe == "mads":
                        t0 = arithmetic.mads(
                            is_add=True,
                            in0=None,
                            in1=l_inv_conj,
                            in2=D_inv[k],
                            do_addsub=False,
                        )
                        res[i][j] = arithmetic.mads(
                            is_add=True,
                            in0=res[i][j],
                            in1=t0,
                            in2=L_inv[k][j],
                            do_addsub=True,
                            real_valued=i == j,
                        )
                    elif pe == "addsub":
                        t0 = l_inv_conj * D_inv[k]
                        res[i][j] = arithmetic.addsub(
                            is_add=True,
                            in0=res[i][j],
                            in1=arithmetic.multiplication(
                                t0, L_inv[k][j], real_valued=i == j
                            ),
                        )
                    else:
                        t0 = l_inv_conj * D_inv[k]
                        res[i][j] = res[i][j] + arithmetic.multiplication(
                            t0, L_inv[k][j], real_valued=i == j
                        )

        return res

    def ldl_eqs(L, D_inv):
        n = len(L)
        res = [[None for _ in range(n)] for _ in range(n)]

        for s in range(2 * (n - 1), -1, -1):
            i_min = (s + 1) // 2
            i_max = min(s, n - 1)
            for i in range(i_max, i_min - 1, -1):
                j = s - i
                if i == j:
                    val = D_inv[i]
                    for k in range(n - 1, i, -1):
                        l_conj = arithmetic.conjugate(L[k][i])
                        if pe == "mads":
                            val = arithmetic.mads(
                                is_add=False,
                                in0=val,
                                in1=l_conj,
                                in2=res[k][i],
                                do_addsub=True,
                                real_valued=True,
                            )
                        elif pe == "addsub":
                            val = arithmetic.addsub(
                                is_add=False,
                                in0=val,
                                in1=arithmetic.multiplication(
                                    l_conj, res[k][i], real_valued=True
                                ),
                            )
                        else:
                            val = val - arithmetic.multiplication(
                                l_conj, res[k][i], real_valued=True
                            )
                else:
                    for k in range(n - 1, j, -1):
                        res_ik = arithmetic.matrix_entry(res, i, k)
                        if pe == "mads":
                            if k == n - 1:
                                val = arithmetic.mads(
                                    is_add=False,
                                    in0=None,
                                    in1=L[k][j],
                                    in2=res_ik,
                                    do_addsub=False,
                                )
                            else:
                                val = arithmetic.mads(
                                    is_add=False,
                                    in0=val,
                                    in1=L[k][j],
                                    in2=res_ik,
                                    do_addsub=True,
                                )
                        elif pe == "addsub":
                            if k == n - 1:
                                val = -(L[k][j] * res_ik)
                            else:
                                val = arithmetic.addsub(
                                    is_add=False,
                                    in0=val,
                                    in1=L[k][j] * res_ik,
                                )
                        else:
                            if k == n - 1:
                                val = -L[k][j] * res_ik
                            else:
                                val = val - L[k][j] * res_ik
                res[i][j] = arithmetic.real(val) if i == j else val

        return res

    A = [[None for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(i + 1):
            in_op = arithmetic.input(i, j, mem)
            A[i][j] = in_op

    L, _, D_inv = ldl_decomposition(A)

    if mode == "mult":
        L_inv = ldl_l_inv(L)
        res = ldl_matmul(L_inv, D_inv)
        outputs = [
            arithmetic.output(i, j, res[i][j], mem)
            for i in range(N)
            for j in range(i + 1)
        ]
    else:
        res = ldl_eqs(L, D_inv)
        outputs = [
            arithmetic.output(i, j, res[i][j], mem)
            for i in range(N)
            for j in range(i + 1)
        ]

    return arithmetic.graph(outputs, name)


def cholesky_matrix_inverse(
    N: int,
    name: str | None = None,
    mode: Literal["eqs", "mult"] = "eqs",
    pe: Literal["addsub", "mads"] | None = None,
    mem: bool = False,
    data_type: Literal["real", "complex", "split"] = "real",
    multiplication_method: Literal["four", "three", "threealt"] = "four",
) -> SFG:
    r"""
    Generate an SFG for the Cholesky matrix inverse algorithm.

    Parameters
    ----------
    N : int
        Dimension of the square input matrix.
    name : str, optional
        The name of the SFG. If None, "Cholesky matrix-inversion".
    mode : {"eqs", "mult"}, default: "eqs"
        The mode of operation, either "mult" or "eqs".
    pe : {"addsub", "mads", None}, optional
        Processing element to use. None means separate Addition and Subtraction.
    mem : bool, default: False
        Use :class:`~b_asic.special_operations.MemoryRead` and
        :class:`~b_asic.special_operations.MemoryWrite` instead of
        :class:`~b_asic.special_operations.Input` and
        :class:`~b_asic.special_operations.Output`. Input and inverse entries
        use packed lower-triangular row order in the default unnamed memory:
        entry :math:`(i, j)` has address :math:`\frac{i(i+1)}{2} + j` for :math:`i \ge j`.
        Each matrix occupies :math:`\frac{N(N+1)}{2}` locations.
    data_type : {"real", "complex", "split"}, default: "real"
        Generate scalar real arithmetic for symmetric matrices, native complex
        arithmetic for Hermitian matrices, or real arithmetic with separate
        real and imaginary components for Hermitian matrices. Split interfaces
        are ordered ``real0, imag0, real1, imag1, ...``. Diagonal imaginary inputs
        are unused and diagonal imaginary outputs are zero. With ``mem=True``,
        components of packed entry address ``p`` use addresses ``2*p`` and
        ``2*p + 1`` in the same memory.
    multiplication_method : {"four", "three", "threealt"}, default: "four"
        Complex product implementation for ``data_type="split"``, matching
        :meth:`~b_asic.sfg.SFG.complex_to_real` and :meth:`~b_asic.sfg.SFG.transform`.
        General complex products use four real multiplications or three with
        extra additions. Real-real and real-complex products use only one and
        two real multiplications, respectively, regardless of this setting.
        Conjugate self-products use two squares and produce a real result.

    Returns
    -------
    :class:`~b_asic.sfg.SFG`
        Signal Flow Graph
    """
    arithmetic = _MatrixArithmetic(data_type, multiplication_method, pe)
    if name is None:
        name = "Cholesky matrix-inversion"

    def chol_decomposition(A):
        N_local = len(A)
        L = [[None for _ in range(N_local)] for _ in range(N_local)]
        L_inv = [[None for _ in range(N_local)] for _ in range(N_local)]

        for j in range(N_local):
            acc = A[j][j]
            for k in range(j):
                l_conj = arithmetic.conjugate(L[j][k])
                if pe == "mads":
                    acc = arithmetic.mads(
                        is_add=False,
                        in0=acc,
                        in1=L[j][k],
                        in2=l_conj,
                        do_addsub=True,
                        real_valued=True,
                    )
                elif pe == "addsub":
                    acc = arithmetic.addsub(
                        is_add=False,
                        in0=acc,
                        in1=arithmetic.multiplication(
                            L[j][k], l_conj, real_valued=True
                        ),
                    )
                else:
                    acc = acc - arithmetic.multiplication(
                        L[j][k], l_conj, real_valued=True
                    )

            L_inv[j][j] = arithmetic.reciprocal_square_root(acc, real_valued=True)

            for i in range(j + 1, N_local):
                acc2 = A[i][j]
                for k in range(j):
                    l_conj = arithmetic.conjugate(L[j][k])
                    if pe == "mads":
                        acc2 = arithmetic.mads(
                            is_add=False,
                            in0=acc2,
                            in1=L[i][k],
                            in2=l_conj,
                            do_addsub=True,
                        )
                    elif pe == "addsub":
                        acc2 = arithmetic.addsub(
                            is_add=False, in0=acc2, in1=L[i][k] * l_conj
                        )
                    else:
                        acc2 = acc2 - L[i][k] * l_conj

                if pe == "mads":
                    L[i][j] = arithmetic.mads(
                        is_add=True,
                        in0=None,
                        in1=acc2,
                        in2=L_inv[j][j],
                        do_addsub=False,
                    )
                elif pe == "addsub":
                    L[i][j] = arithmetic.multiplication(
                        acc2,
                        L_inv[j][j],
                    )
                else:
                    L[i][j] = acc2 * L_inv[j][j]

        return L, L_inv

    def chol_l_inv(L, L_inv_diag):
        N_local = len(L)
        L_inv = [[None for _ in range(N_local)] for _ in range(N_local)]
        for i in range(N_local):
            L_inv[i][i] = L_inv_diag[i][i]

        for i in range(1, N_local):
            for j in range(i):
                if pe == "mads":
                    acc = arithmetic.mads(
                        is_add=True,
                        in0=None,
                        in1=L[i][j],
                        in2=L_inv[j][j],
                        do_addsub=False,
                    )
                    for k in range(j + 1, i):
                        acc = arithmetic.mads(
                            is_add=True,
                            in0=acc,
                            in1=L[i][k],
                            in2=L_inv[k][j],
                            do_addsub=True,
                        )
                    L_inv[i][j] = arithmetic.mads(
                        is_add=False,
                        in0=None,
                        in1=acc,
                        in2=L_inv[i][i],
                        do_addsub=False,
                    )
                elif pe == "addsub":
                    acc = L[i][j] * L_inv[j][j]
                    for k in range(j + 1, i):
                        acc = arithmetic.addsub(
                            is_add=True, in0=acc, in1=L[i][k] * L_inv[k][j]
                        )
                    L_inv[i][j] = arithmetic.negation(
                        acc * L_inv[i][i],
                    )
                else:
                    acc = L[i][j] * L_inv[j][j]
                    for k in range(j + 1, i):
                        acc = acc + L[i][k] * L_inv[k][j]
                    L_inv[i][j] = -(acc * L_inv[i][i])

        return L_inv

    def chol_matmul(L_inv):
        n = len(L_inv)
        res = [[None for _ in range(n)] for _ in range(n)]

        for i in range(n - 1, -1, -1):
            for j in range(i, -1, -1):
                if pe == "mads":
                    if i + 1 == n:
                        res[i][j] = arithmetic.mads(
                            is_add=True,
                            in0=None,
                            in1=L_inv[i][i],
                            in2=L_inv[i][j],
                            do_addsub=False,
                        )
                    else:
                        acc = arithmetic.mads(
                            is_add=True,
                            in0=None,
                            in1=L_inv[i][i],
                            in2=L_inv[i][j],
                            do_addsub=False,
                        )
                        for k in range(i + 1, n):
                            acc = arithmetic.mads(
                                is_add=True,
                                in0=acc,
                                in1=arithmetic.conjugate(L_inv[k][i]),
                                in2=L_inv[k][j],
                                do_addsub=True,
                            )
                        res[i][j] = acc
                elif pe == "addsub":
                    if i + 1 == n:
                        res[i][j] = L_inv[i][i] * L_inv[i][j]
                    else:
                        acc = L_inv[i][i] * L_inv[i][j]
                        for k in range(i + 1, n):
                            acc = arithmetic.addsub(
                                is_add=True,
                                in0=acc,
                                in1=arithmetic.conjugate(L_inv[k][i]) * L_inv[k][j],
                            )
                        res[i][j] = acc
                else:
                    if i + 1 == n:
                        res[i][j] = L_inv[i][i] * L_inv[i][j]
                    else:
                        acc = L_inv[i][i] * L_inv[i][j]
                        for k in range(i + 1, n):
                            acc = acc + arithmetic.conjugate(L_inv[k][i]) * L_inv[k][j]
                        res[i][j] = acc
        return res

    def chol_eqs(L, L_inv):
        n = len(L)
        res = [[None for _ in range(n)] for _ in range(n)]

        for s in range(2 * (n - 1), -1, -1):
            i_min = (s + 1) // 2
            i_max = min(s, n - 1)
            for i in range(i_max, i_min - 1, -1):
                j = s - i
                if i == j:
                    acc = L_inv[i][i]
                    for k in range(n - 1, i, -1):
                        l_conj = arithmetic.conjugate(L[k][i])
                        if pe == "mads":
                            acc = arithmetic.mads(
                                is_add=False,
                                in0=acc,
                                in1=l_conj,
                                in2=res[k][i],
                                do_addsub=True,
                                real_valued=True,
                            )
                        elif pe == "addsub":
                            acc = arithmetic.addsub(
                                is_add=False,
                                in0=acc,
                                in1=arithmetic.multiplication(
                                    l_conj, res[k][i], real_valued=True
                                ),
                            )
                        else:
                            acc = acc - arithmetic.multiplication(
                                l_conj, res[k][i], real_valued=True
                            )
                    if pe == "mads":
                        acc = arithmetic.mads(
                            is_add=True,
                            in0=None,
                            in1=acc,
                            in2=L_inv[i][i],
                            do_addsub=False,
                            real_valued=True,
                        )
                    elif pe == "addsub":
                        acc = arithmetic.multiplication(
                            acc, L_inv[i][i], real_valued=True
                        )
                    else:
                        acc = arithmetic.multiplication(
                            acc, L_inv[i][i], real_valued=True
                        )
                else:
                    res_last = arithmetic.matrix_entry(res, i, n - 1)
                    if pe == "mads":
                        acc = arithmetic.mads(
                            is_add=False,
                            in0=None,
                            in1=L[n - 1][j],
                            in2=res_last,
                            do_addsub=False,
                        )
                        for k in range(n - 2, j, -1):
                            acc = arithmetic.mads(
                                is_add=False,
                                in0=acc,
                                in1=L[k][j],
                                in2=arithmetic.matrix_entry(res, i, k),
                                do_addsub=True,
                            )
                        acc = arithmetic.mads(
                            is_add=True,
                            in0=None,
                            in1=acc,
                            in2=L_inv[j][j],
                            do_addsub=False,
                        )
                    elif pe == "addsub":
                        acc = -(L[n - 1][j] * res_last)
                        for k in range(n - 2, j, -1):
                            acc = arithmetic.addsub(
                                is_add=False,
                                in0=acc,
                                in1=L[k][j] * arithmetic.matrix_entry(res, i, k),
                            )
                        acc = acc * L_inv[j][j]
                    else:
                        acc = -L[n - 1][j] * res_last
                        for k in range(n - 2, j, -1):
                            acc = acc - L[k][j] * arithmetic.matrix_entry(res, i, k)
                        acc = acc * L_inv[j][j]
                res[i][j] = arithmetic.real(acc) if i == j else acc

        return res

    A = [[None for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(i + 1):
            in_op = arithmetic.input(i, j, mem)
            A[i][j] = in_op

    L, L_inv_diag = chol_decomposition(A)

    if mode == "mult":
        L_inv = chol_l_inv(L, L_inv_diag)
        res = chol_matmul(L_inv)
        outputs = [
            arithmetic.output(i, j, res[i][j], mem)
            for i in range(N)
            for j in range(i + 1)
        ]
    else:
        res = chol_eqs(L, L_inv_diag)
        outputs = [
            arithmetic.output(i, j, res[i][j], mem)
            for i in range(N)
            for j in range(i + 1)
        ]

    return arithmetic.graph(outputs, name)


def block_ldlt_matrix_inverse(
    N: int,
    name: str | None = None,
    mode: Literal["eqs", "mult"] = "eqs",
    pe: Literal["addsub", "mads"] | None = None,
    mem: bool = False,
    data_type: Literal["real", "complex", "split"] = "real",
    multiplication_method: Literal["four", "three", "threealt"] = "four",
) -> SFG:
    r"""
    Generate an SFG for the block LDLT matrix inverse algorithm.

    Parameters
    ----------
    N : int
        Dimension of the square input matrix.
    name : str, optional
        The name of the SFG. If None, "Block LDLT matrix-inversion".
    mode : {"eqs", "mult"}, default: "eqs"
        The mode of operation, either "mult" or "eqs".
    pe : {"addsub", "mads", None}, optional
        Processing element to use. None means separate Addition and Subtraction.
    mem : bool, default: False
        Use :class:`~b_asic.special_operations.MemoryRead` and
        :class:`~b_asic.special_operations.MemoryWrite` instead of
        :class:`~b_asic.special_operations.Input` and
        :class:`~b_asic.special_operations.Output`. Input and inverse entries
        use packed lower-triangular row order in the default unnamed memory:
        entry :math:`(i, j)` has address :math:`\frac{i(i+1)}{2} + j` for :math:`i \ge j`.
        Each matrix occupies :math:`\frac{N(N+1)}{2}` locations.
    data_type : {"real", "complex", "split"}, default: "real"
        Generate scalar real arithmetic for symmetric matrices, native complex
        arithmetic for Hermitian matrices, or real arithmetic with separate
        real and imaginary components for Hermitian matrices. Split interfaces
        are ordered ``real0, imag0, real1, imag1, ...``. Diagonal imaginary inputs
        are unused and diagonal imaginary outputs are zero. With ``mem=True``,
        components of packed entry address ``p`` use addresses ``2*p`` and
        ``2*p + 1`` in the same memory.
    multiplication_method : {"four", "three", "threealt"}, default: "four"
        Complex product implementation for ``data_type="split"``, matching
        :meth:`~b_asic.sfg.SFG.complex_to_real` and :meth:`~b_asic.sfg.SFG.transform`.
        General complex products use four real multiplications or three with
        extra additions. Real-real and real-complex products use only one and
        two real multiplications, respectively, regardless of this setting.
        Conjugate self-products use two squares and produce a real result.

    Returns
    -------
    :class:`~b_asic.sfg.SFG`
        Signal Flow Graph
    """
    arithmetic = _MatrixArithmetic(data_type, multiplication_method, pe)
    BLOCK_SIZE = 2
    if N % BLOCK_SIZE != 0:
        raise ValueError("Block size needs to be a positive divisor of N.")

    if name is None:
        name = "Block LDLT matrix-inversion"

    if mode not in ("mult", "eqs"):
        raise NotImplementedError(f"mode={mode} is not yet implemented for block LDLT.")
    if pe not in (None, "addsub", "mads"):
        raise NotImplementedError(f"pe={pe} is not yet implemented for block LDLT.")

    N_blocks = N // BLOCK_SIZE

    def _mac_blocks(
        is_add: bool,
        acc_block,
        A_block,
        B_block,
        mult_mode="regular",
        lower_triangular=False,
    ):
        res = [[None for _ in range(BLOCK_SIZE)] for _ in range(BLOCK_SIZE)]
        for r in range(BLOCK_SIZE):
            for c in range(BLOCK_SIZE):
                if lower_triangular and r < c:
                    continue

                if mult_mode == "regular":
                    v1 = [A_block[r][x] for x in range(BLOCK_SIZE)]
                    v2 = [B_block[x][c] for x in range(BLOCK_SIZE)]
                elif mult_mode == "T":
                    v1 = [A_block[r][x] for x in range(BLOCK_SIZE)]
                    v2 = [
                        arithmetic.conjugate(B_block[c][x]) for x in range(BLOCK_SIZE)
                    ]
                elif mult_mode == "T_blocks":
                    v1 = [
                        arithmetic.conjugate(A_block[x][r]) for x in range(BLOCK_SIZE)
                    ]
                    v2 = [B_block[x][c] for x in range(BLOCK_SIZE)]
                elif mult_mode == "diag_block":
                    v1 = [
                        arithmetic.matrix_entry(A_block, r, x)
                        for x in range(BLOCK_SIZE)
                    ]
                    v2 = [B_block[x][c] for x in range(BLOCK_SIZE)]
                elif mult_mode == "block_diag":
                    v1 = A_block[r]
                    v2 = [
                        arithmetic.matrix_entry(B_block, x, c)
                        for x in range(BLOCK_SIZE)
                    ]
                elif mult_mode == "T_block_diag":
                    v1 = [
                        arithmetic.conjugate(A_block[x][r]) for x in range(BLOCK_SIZE)
                    ]
                    v2 = [
                        arithmetic.matrix_entry(B_block, x, c)
                        for x in range(BLOCK_SIZE)
                    ]

                if pe == "mads":
                    if acc_block is None:
                        if is_add:
                            acc = arithmetic.mads(
                                is_add=True,
                                in0=None,
                                in1=v1[0],
                                in2=v2[0],
                                do_addsub=False,
                                real_valued=lower_triangular and r == c,
                            )
                            for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                                acc = arithmetic.mads(
                                    is_add=True,
                                    in0=acc,
                                    in1=xv1,
                                    in2=xv2,
                                    do_addsub=True,
                                    real_valued=lower_triangular and r == c,
                                )
                        else:
                            acc = arithmetic.mads(
                                is_add=False,
                                in0=None,
                                in1=v1[0],
                                in2=v2[0],
                                do_addsub=False,
                                real_valued=lower_triangular and r == c,
                            )
                            for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                                acc = arithmetic.mads(
                                    is_add=False,
                                    in0=acc,
                                    in1=xv1,
                                    in2=xv2,
                                    do_addsub=True,
                                    real_valued=lower_triangular and r == c,
                                )
                    else:
                        if acc_block[r][c] is not None:
                            acc = arithmetic.mads(
                                is_add=is_add,
                                in0=acc_block[r][c],
                                in1=v1[0],
                                in2=v2[0],
                                do_addsub=True,
                                real_valued=lower_triangular and r == c,
                            )

                        for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                            acc = arithmetic.mads(
                                is_add=is_add,
                                in0=acc,
                                in1=xv1,
                                in2=xv2,
                                do_addsub=True,
                                real_valued=lower_triangular and r == c,
                            )
                else:
                    acc = arithmetic.multiplication(
                        v1[0], v2[0], real_valued=lower_triangular and r == c
                    )
                    for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                        acc = _add_nodes(
                            acc,
                            arithmetic.multiplication(
                                xv1, xv2, real_valued=lower_triangular and r == c
                            ),
                        )
                    if acc_block is not None:
                        if acc_block[r][c] is not None:
                            acc = (
                                _add_nodes(acc_block[r][c], acc)
                                if is_add
                                else _sub_nodes(acc_block[r][c], acc)
                            )
                    else:
                        acc = acc if is_add else -acc
                res[r][c] = arithmetic.real(acc) if lower_triangular and r == c else acc
        return res

    def _copy_block(A_block):
        return [[A_block[r][c] for c in range(BLOCK_SIZE)] for r in range(BLOCK_SIZE)]

    def _copy_lower_triangular(A_block):
        res = [[None for _ in range(BLOCK_SIZE)] for _ in range(BLOCK_SIZE)]
        for r in range(BLOCK_SIZE):
            for c in range(r + 1):
                res[r][c] = A_block[r][c]
        return res

    def _add_nodes(a, b):
        if pe == "addsub":
            return arithmetic.addsub(True, a, b)
        return a + b

    def _sub_nodes(a, b):
        if pe == "addsub":
            return arithmetic.addsub(False, a, b)
        return a - b

    def _neg_block(A_block):
        return [[-A_block[r][c] for c in range(BLOCK_SIZE)] for r in range(BLOCK_SIZE)]

    def _inv_2x2_symmetric(d_val):
        res = [[None for _ in range(BLOCK_SIZE)] for _ in range(BLOCK_SIZE)]
        offdiag_conj = arithmetic.conjugate(d_val[1][0])
        if pe == "mads":
            tmp = arithmetic.mads(
                is_add=True,
                in0=None,
                in1=d_val[0][0],
                in2=d_val[1][1],
                do_addsub=False,
            )
            det = arithmetic.mads(
                is_add=False,
                in0=tmp,
                in1=d_val[1][0],
                in2=offdiag_conj,
                do_addsub=True,
            )
            inv_det = arithmetic.reciprocal(det, real_valued=True)
            res[0][0] = arithmetic.mads(
                is_add=True,
                in0=None,
                in1=d_val[1][1],
                in2=inv_det,
                do_addsub=False,
            )
            res[1][0] = arithmetic.mads(
                is_add=False,
                in0=None,
                in1=d_val[1][0],
                in2=inv_det,
                do_addsub=False,
            )
            res[1][1] = arithmetic.mads(
                is_add=True,
                in0=None,
                in1=d_val[0][0],
                in2=inv_det,
                do_addsub=False,
            )
        else:
            det = _sub_nodes(d_val[0][0] * d_val[1][1], d_val[1][0] * offdiag_conj)
            inv_det = arithmetic.reciprocal(det, real_valued=True)
            res[0][0] = d_val[1][1] * inv_det
            res[1][0] = -d_val[1][0] * inv_det
            res[1][1] = d_val[0][0] * inv_det
        return res

    A = [[None for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(i + 1):
            in_op = arithmetic.input(i, j, mem)
            A[i][j] = in_op

    L = [[None for _ in range(N_blocks)] for _ in range(N_blocks)]
    D_inv = [None for _ in range(N_blocks)]
    M = [[None for _ in range(N_blocks)] for _ in range(N_blocks)]

    A_blk = [[None for _ in range(N_blocks)] for _ in range(N_blocks)]
    for i in range(N_blocks):
        for j in range(i + 1):
            block = [[None for _ in range(BLOCK_SIZE)] for _ in range(BLOCK_SIZE)]
            for r in range(BLOCK_SIZE):
                for c in range(BLOCK_SIZE):
                    row = i * BLOCK_SIZE + r
                    col = j * BLOCK_SIZE + c
                    if row >= col:
                        block[r][c] = A[row][col]
                    else:
                        block[r][c] = arithmetic.conjugate(A[col][row])
            A_blk[i][j] = block

    for j in range(N_blocks):
        d_val = _copy_lower_triangular(A_blk[j][j])
        for k in range(j):
            d_val = _mac_blocks(False, d_val, M[j][k], L[j][k], "T", True)

        D_inv[j] = _inv_2x2_symmetric(d_val)

        for i in range(j + 1, N_blocks):
            m_blk = _copy_block(A_blk[i][j])
            for k in range(j):
                m_blk = _mac_blocks(False, m_blk, M[i][k], L[j][k], "T")
            M[i][j] = m_blk
            L[i][j] = _mac_blocks(True, None, M[i][j], D_inv[j], "block_diag")

    res_blk = [[None for _ in range(N_blocks)] for _ in range(N_blocks)]

    if mode == "mult":
        L_inv = [[None for _ in range(N_blocks)] for _ in range(N_blocks)]
        for i in range(1, N_blocks):
            for j in range(i - 1, -1, -1):
                acc = _copy_block(L[i][j])
                for k in range(j + 1, i):
                    acc = _mac_blocks(True, acc, L[i][k], L_inv[k][j])
                L_inv[i][j] = _neg_block(acc)

        for i in range(N_blocks - 1, -1, -1):
            for j in range(i, -1, -1):
                if i == j:
                    res_blk[i][j] = _copy_lower_triangular(D_inv[i])
                else:
                    res_blk[i][j] = _mac_blocks(
                        True, None, D_inv[i], L_inv[i][j], "diag_block"
                    )

                for k in range(i + 1, N_blocks):
                    t0 = _mac_blocks(True, None, L_inv[k][i], D_inv[k], "T_block_diag")
                    res_blk[i][j] = _mac_blocks(
                        True,
                        res_blk[i][j],
                        t0,
                        L_inv[k][j],
                        "regular",
                        lower_triangular=(i == j),
                    )
    else:  # mode == "eqs"
        for s in range(2 * (N_blocks - 1), -1, -1):
            i_min = (s + 1) // 2
            i_max = min(s, N_blocks - 1)
            for i in range(i_max, i_min - 1, -1):
                j = s - i
                if i == j:
                    res_blk[i][j] = _copy_lower_triangular(D_inv[i])
                    for k in range(N_blocks - 1, i, -1):
                        res_blk[i][j] = _mac_blocks(
                            False,
                            res_blk[i][j],
                            res_blk[k][i],
                            L[k][i],
                            "T_blocks",
                            True,
                        )
                else:
                    k = N_blocks - 1
                    if i == k:
                        val = _mac_blocks(
                            False, None, res_blk[i][k], L[k][j], "diag_block"
                        )
                    else:
                        val = _mac_blocks(
                            False, None, res_blk[k][i], L[k][j], "T_blocks"
                        )

                    for k in range(N_blocks - 2, j, -1):
                        if i == k:
                            val = _mac_blocks(
                                False, val, res_blk[i][k], L[k][j], "diag_block"
                            )
                        elif i > k:
                            val = _mac_blocks(
                                False, val, res_blk[i][k], L[k][j], "regular"
                            )
                        else:
                            val = _mac_blocks(
                                False, val, res_blk[k][i], L[k][j], "T_blocks"
                            )

                    res_blk[i][j] = val

    res = [[None for _ in range(N)] for _ in range(N)]
    for i in range(N_blocks):
        for j in range(i + 1):
            if i == j:
                for r in range(BLOCK_SIZE):
                    for c in range(r + 1):
                        val = res_blk[i][j][r][c]
                        row = i * BLOCK_SIZE + r
                        col = j * BLOCK_SIZE + c
                        res[row][col] = arithmetic.output(row, col, val, mem)
            else:
                for r in range(BLOCK_SIZE):
                    for c in range(BLOCK_SIZE):
                        val = res_blk[i][j][r][c]
                        row = i * BLOCK_SIZE + r
                        col = j * BLOCK_SIZE + c
                        res[row][col] = arithmetic.output(row, col, val, mem)

    outputs = [res[i][j] for i in range(N) for j in range(i + 1)]

    return arithmetic.graph(outputs, name)


def block_cholesky_matrix_inverse(
    N: int,
    name: str | None = None,
    mode: Literal["eqs", "mult"] = "eqs",
    pe: Literal["addsub", "mads"] | None = None,
    mem: bool = False,
    data_type: Literal["real", "complex", "split"] = "real",
    multiplication_method: Literal["four", "three", "threealt"] = "four",
) -> SFG:
    r"""
    Generate an SFG for the block Cholesky matrix inverse algorithm.

    Parameters
    ----------
    N : int
        Dimension of the square input matrix.
    name : str, optional
        The name of the SFG. If None, "Block Cholesky matrix-inversion".
    mode : {"eqs", "mult"}, default: "eqs"
        The mode of operation, either "mult" or "eqs".
    pe : {"addsub", "mads", None}, default: None
        Processing element to use.
    mem : bool, default: False
        Use :class:`~b_asic.special_operations.MemoryRead` and
        :class:`~b_asic.special_operations.MemoryWrite` instead of
        :class:`~b_asic.special_operations.Input` and
        :class:`~b_asic.special_operations.Output`. Input and inverse entries
        use packed lower-triangular row order in the default unnamed memory:
        entry :math:`(i, j)` has address :math:`\frac{i(i+1)}{2} + j` for :math:`i \ge j`.
        Each matrix occupies :math:`\frac{N(N+1)}{2}` locations.
    data_type : {"real", "complex", "split"}, default: "real"
        Generate scalar real arithmetic for symmetric matrices, native complex
        arithmetic for Hermitian matrices, or real arithmetic with separate
        real and imaginary components for Hermitian matrices. Split interfaces
        are ordered ``real0, imag0, real1, imag1, ...``. Diagonal imaginary inputs
        are unused and diagonal imaginary outputs are zero. With ``mem=True``,
        components of packed entry address ``p`` use addresses ``2*p`` and
        ``2*p + 1`` in the same memory.
    multiplication_method : {"four", "three", "threealt"}, default: "four"
        Complex product implementation for ``data_type="split"``, matching
        :meth:`~b_asic.sfg.SFG.complex_to_real` and :meth:`~b_asic.sfg.SFG.transform`.
        General complex products use four real multiplications or three with
        extra additions. Real-real and real-complex products use only one and
        two real multiplications, respectively, regardless of this setting.
        Conjugate self-products use two squares and produce a real result.

    Returns
    -------
    :class:`~b_asic.sfg.SFG`
        Signal Flow Graph
    """
    arithmetic = _MatrixArithmetic(data_type, multiplication_method, pe)
    BLOCK_SIZE = 2
    if N % BLOCK_SIZE != 0:
        raise ValueError("Block size needs to be a positive divisor of N.")

    if name is None:
        name = "Block Cholesky matrix-inversion"

    if mode not in ("mult", "eqs"):
        raise NotImplementedError(
            f"mode={mode} is not yet implemented for block Cholesky."
        )
    if pe not in (None, "addsub", "mads"):
        raise NotImplementedError(f"pe={pe} is not yet implemented for block Cholesky.")

    N_blocks = N // BLOCK_SIZE

    def _add_nodes(a, b):
        if pe == "addsub":
            return arithmetic.addsub(True, a, b)
        return a + b

    def _sub_nodes(a, b):
        if pe == "addsub":
            return arithmetic.addsub(False, a, b)
        return a - b

    def _mac_blocks(
        is_add: bool,
        acc_block,
        A_block,
        B_block,
        mult_mode="regular",
        lower_triangular=False,
    ):
        res = [[None for _ in range(BLOCK_SIZE)] for _ in range(BLOCK_SIZE)]
        for r in range(BLOCK_SIZE):
            for c in range(BLOCK_SIZE):
                if lower_triangular and r < c:
                    continue

                if mult_mode == "regular":
                    v1 = [A_block[r][x] for x in range(BLOCK_SIZE)]
                    v2 = [B_block[x][c] for x in range(BLOCK_SIZE)]
                elif mult_mode == "T":
                    v1 = [A_block[r][x] for x in range(BLOCK_SIZE)]
                    v2 = [
                        arithmetic.conjugate(B_block[c][x]) for x in range(BLOCK_SIZE)
                    ]
                elif mult_mode == "T_blocks":
                    v1 = [
                        arithmetic.conjugate(A_block[x][r]) for x in range(BLOCK_SIZE)
                    ]
                    v2 = [B_block[x][c] for x in range(BLOCK_SIZE)]
                elif mult_mode == "block_tri":
                    v1 = [A_block[r][x] for x in range(c, BLOCK_SIZE)]
                    v2 = [B_block[x][c] for x in range(c, BLOCK_SIZE)]
                elif mult_mode == "block_tri_T":
                    v1 = [A_block[r][x] for x in range(c + 1)]
                    v2 = [arithmetic.conjugate(B_block[c][x]) for x in range(c + 1)]
                elif mult_mode == "tri_block":
                    v1 = [A_block[r][x] for x in range(r + 1)]
                    v2 = [B_block[x][c] for x in range(r + 1)]
                elif mult_mode == "tri_T_block":
                    v1 = [
                        arithmetic.conjugate(A_block[x][r])
                        for x in range(r, BLOCK_SIZE)
                    ]
                    v2 = [B_block[x][c] for x in range(r, BLOCK_SIZE)]
                elif mult_mode == "tri_T_tri":
                    start = max(r, c)
                    v1 = [
                        arithmetic.conjugate(A_block[x][r])
                        for x in range(start, BLOCK_SIZE)
                    ]
                    v2 = [B_block[x][c] for x in range(start, BLOCK_SIZE)]
                elif mult_mode == "diag_block":
                    v1 = [
                        arithmetic.matrix_entry(A_block, r, x)
                        for x in range(BLOCK_SIZE)
                    ]
                    v2 = [B_block[x][c] for x in range(BLOCK_SIZE)]

                if pe == "mads":
                    if acc_block is None:
                        if is_add:
                            acc = arithmetic.mads(
                                is_add=True,
                                in0=None,
                                in1=v1[0],
                                in2=v2[0],
                                do_addsub=False,
                                real_valued=lower_triangular and r == c,
                            )
                            for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                                acc = arithmetic.mads(
                                    is_add=True,
                                    in0=acc,
                                    in1=xv1,
                                    in2=xv2,
                                    do_addsub=True,
                                    real_valued=lower_triangular and r == c,
                                )
                        else:
                            acc = arithmetic.mads(
                                is_add=False,
                                in0=None,
                                in1=v1[0],
                                in2=v2[0],
                                do_addsub=False,
                                real_valued=lower_triangular and r == c,
                            )
                            for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                                acc = arithmetic.mads(
                                    is_add=False,
                                    in0=acc,
                                    in1=xv1,
                                    in2=xv2,
                                    do_addsub=True,
                                    real_valued=lower_triangular and r == c,
                                )
                    else:
                        if acc_block[r][c] is not None:
                            acc = arithmetic.mads(
                                is_add=is_add,
                                in0=acc_block[r][c],
                                in1=v1[0],
                                in2=v2[0],
                                do_addsub=True,
                                real_valued=lower_triangular and r == c,
                            )

                        for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                            acc = arithmetic.mads(
                                is_add=is_add,
                                in0=acc,
                                in1=xv1,
                                in2=xv2,
                                do_addsub=True,
                                real_valued=lower_triangular and r == c,
                            )
                else:
                    acc = arithmetic.multiplication(
                        v1[0], v2[0], real_valued=lower_triangular and r == c
                    )
                    for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                        acc = _add_nodes(
                            acc,
                            arithmetic.multiplication(
                                xv1, xv2, real_valued=lower_triangular and r == c
                            ),
                        )
                    if acc_block is not None:
                        if acc_block[r][c] is not None:
                            acc = (
                                _add_nodes(acc_block[r][c], acc)
                                if is_add
                                else _sub_nodes(acc_block[r][c], acc)
                            )
                    else:
                        acc = acc if is_add else -acc
                res[r][c] = arithmetic.real(acc) if lower_triangular and r == c else acc
        return res

    def _copy_block(A_block):
        return [[A_block[r][c] for c in range(BLOCK_SIZE)] for r in range(BLOCK_SIZE)]

    def _copy_lower_triangular(A_block):
        res = [[None for _ in range(BLOCK_SIZE)] for _ in range(BLOCK_SIZE)]
        for r in range(BLOCK_SIZE):
            for c in range(r + 1):
                res[r][c] = A_block[r][c]
        return res

    def _chol_inv_2x2(acc):
        res = [[None for _ in range(BLOCK_SIZE)] for _ in range(BLOCK_SIZE)]
        inv_L00 = arithmetic.reciprocal_square_root(acc[0][0], real_valued=True)
        if pe == "mads":
            L10 = arithmetic.mads(
                is_add=True,
                in0=None,
                in1=acc[1][0],
                in2=inv_L00,
                do_addsub=False,
            )
            tmp1 = arithmetic.mads(
                is_add=False,
                in0=acc[1][1],
                in1=L10,
                in2=arithmetic.conjugate(L10),
                do_addsub=True,
            )
            inv_L11 = arithmetic.reciprocal_square_root(tmp1, real_valued=True)
            tmp2 = arithmetic.mads(
                is_add=True,
                in0=None,
                in1=L10,
                in2=inv_L00,
                do_addsub=False,
            )
            res[0][0] = inv_L00
            res[1][0] = arithmetic.mads(
                is_add=False,
                in0=None,
                in1=tmp2,
                in2=inv_L11,
                do_addsub=False,
            )
            res[1][1] = inv_L11
        elif pe == "addsub":
            L10 = arithmetic.multiplication(acc[1][0], inv_L00)
            tmp1 = _sub_nodes(
                acc[1][1], arithmetic.multiplication(L10, arithmetic.conjugate(L10))
            )
            inv_L11 = arithmetic.reciprocal_square_root(tmp1, real_valued=True)
            res[0][0] = inv_L00
            res[1][0] = arithmetic.negation(
                arithmetic.multiplication(
                    arithmetic.multiplication(L10, inv_L00), inv_L11
                )
            )
            res[1][1] = inv_L11
        else:
            L10 = acc[1][0] * inv_L00
            inv_L11 = arithmetic.reciprocal_square_root(
                _sub_nodes(acc[1][1], L10 * arithmetic.conjugate(L10)), real_valued=True
            )
            res[0][0] = inv_L00
            res[1][0] = -(L10 * inv_L00 * inv_L11)
            res[1][1] = inv_L11
        return res

    A = [[None for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(i + 1):
            in_op = arithmetic.input(i, j, mem)
            A[i][j] = in_op

    L = [[None for _ in range(N_blocks)] for _ in range(N_blocks)]
    L_inv = [[None for _ in range(N_blocks)] for _ in range(N_blocks)]

    A_blk = [[None for _ in range(N_blocks)] for _ in range(N_blocks)]
    for i in range(N_blocks):
        for j in range(i + 1):
            block = [[None for _ in range(BLOCK_SIZE)] for _ in range(BLOCK_SIZE)]
            for r in range(BLOCK_SIZE):
                for c in range(BLOCK_SIZE):
                    row = i * BLOCK_SIZE + r
                    col = j * BLOCK_SIZE + c
                    if row >= col:
                        block[r][c] = A[row][col]
                    else:
                        block[r][c] = arithmetic.conjugate(A[col][row])
            A_blk[i][j] = block

    for j in range(N_blocks):
        acc = _copy_lower_triangular(A_blk[j][j])
        for k in range(j):
            acc = _mac_blocks(False, acc, L[j][k], L[j][k], "T", lower_triangular=True)

        L_inv[j][j] = _chol_inv_2x2(acc)

        for i in range(j + 1, N_blocks):
            acc_ij = _copy_block(A_blk[i][j])
            for k in range(j):
                acc_ij = _mac_blocks(False, acc_ij, L[i][k], L[j][k], "T")

            L[i][j] = _mac_blocks(True, None, acc_ij, L_inv[j][j], "block_tri_T")

    res_blk = [[None for _ in range(N_blocks)] for _ in range(N_blocks)]

    if mode == "mult":
        for i in range(1, N_blocks):
            for j in range(i):
                acc = _mac_blocks(True, None, L[i][j], L_inv[j][j], "block_tri")
                for k in range(j + 1, i):
                    acc = _mac_blocks(True, acc, L[i][k], L_inv[k][j])

                L_inv[i][j] = _mac_blocks(False, None, L_inv[i][i], acc, "tri_block")

        for i in range(N_blocks - 1, -1, -1):
            for j in range(i, -1, -1):
                if i == j:
                    acc = _mac_blocks(
                        True,
                        None,
                        L_inv[i][i],
                        L_inv[i][j],
                        "tri_T_tri",
                        lower_triangular=True,
                    )
                else:
                    acc = _mac_blocks(
                        True, None, L_inv[i][i], L_inv[i][j], "tri_T_block"
                    )
                for k in range(i + 1, N_blocks):
                    if i == j:
                        acc = _mac_blocks(
                            True, acc, L_inv[k][i], L_inv[k][j], "T_blocks", True
                        )
                    else:
                        acc = _mac_blocks(
                            True, acc, L_inv[k][i], L_inv[k][j], "T_blocks"
                        )
                res_blk[i][j] = acc

    else:  # mode == "eqs"
        for s in range(2 * (N_blocks - 1), -1, -1):
            i_min = (s + 1) // 2
            i_max = min(s, N_blocks - 1)
            for i in range(i_max, i_min - 1, -1):
                j = s - i
                if i == j:
                    acc2 = _copy_lower_triangular(L_inv[i][i])
                    for k in range(N_blocks - 1, i, -1):
                        acc2 = _mac_blocks(
                            False, acc2, L[k][i], res_blk[k][i], "T_blocks", True
                        )
                    res_blk[i][i] = _mac_blocks(
                        True, None, L_inv[i][i], acc2, "tri_T_tri", True
                    )
                else:
                    k = N_blocks - 1
                    if i == k:
                        acc = _mac_blocks(
                            False, None, res_blk[i][k], L[k][j], "diag_block"
                        )
                    else:
                        acc = _mac_blocks(
                            False, None, res_blk[k][i], L[k][j], "T_blocks"
                        )

                    for k in range(N_blocks - 2, j, -1):
                        if k > i:
                            acc = _mac_blocks(
                                False, acc, res_blk[k][i], L[k][j], "T_blocks"
                            )
                        elif k == i:
                            acc = _mac_blocks(
                                False, acc, res_blk[i][i], L[k][j], "diag_block"
                            )
                        else:  # k < i
                            acc = _mac_blocks(
                                False, acc, res_blk[i][k], L[k][j], "regular"
                            )

                    res_blk[i][j] = _mac_blocks(
                        True, None, acc, L_inv[j][j], "block_tri"
                    )

    res = [[None for _ in range(N)] for _ in range(N)]
    for i in range(N_blocks):
        for j in range(i + 1):
            if i == j:
                for r in range(BLOCK_SIZE):
                    for c in range(r + 1):
                        val = res_blk[i][j][r][c]
                        row = i * BLOCK_SIZE + r
                        col = j * BLOCK_SIZE + c
                        res[row][col] = arithmetic.output(row, col, val, mem)
            else:
                for r in range(BLOCK_SIZE):
                    for c in range(BLOCK_SIZE):
                        val = res_blk[i][j][r][c]
                        row = i * BLOCK_SIZE + r
                        col = j * BLOCK_SIZE + c
                        res[row][col] = arithmetic.output(row, col, val, mem)

    outputs = [res[i][j] for i in range(N) for j in range(i + 1)]

    return arithmetic.graph(outputs, name)


def tile_ldlt_matrix_inverse(
    N: int,
    name: str | None = None,
    mode: Literal["eqs", "mult"] = "eqs",
    pe: Literal["addsub", "mads"] | None = None,
    mem: bool = False,
    data_type: Literal["real", "complex", "split"] = "real",
    multiplication_method: Literal["four", "three", "threealt"] = "four",
) -> SFG:
    r"""
    Generate an SFG for the tile LDLT matrix inverse algorithm.

    Parameters
    ----------
    N : int
        Dimension of the square input matrix.
    name : str, optional
        The name of the SFG. If None, "Tile LDLT matrix-inversion".
    mode : {"eqs", "mult"}, default: "eqs"
        The mode of operation, either "mult" or "eqs".
    pe : {"addsub", "mads", None}, default: None
        Processing element to use.
    mem : bool, default: False
        Use :class:`~b_asic.special_operations.MemoryRead` and
        :class:`~b_asic.special_operations.MemoryWrite` instead of
        :class:`~b_asic.special_operations.Input` and
        :class:`~b_asic.special_operations.Output`. Input and inverse entries
        use packed lower-triangular row order in the default unnamed memory:
        entry :math:`(i, j)` has address :math:`\frac{i(i+1)}{2} + j` for :math:`i \ge j`.
        Each matrix occupies :math:`\frac{N(N+1)}{2}` locations.
    data_type : {"real", "complex", "split"}, default: "real"
        Generate scalar real arithmetic for symmetric matrices, native complex
        arithmetic for Hermitian matrices, or real arithmetic with separate
        real and imaginary components for Hermitian matrices. Split interfaces
        are ordered ``real0, imag0, real1, imag1, ...``. Diagonal imaginary inputs
        are unused and diagonal imaginary outputs are zero. With ``mem=True``,
        components of packed entry address ``p`` use addresses ``2*p`` and
        ``2*p + 1`` in the same memory.
    multiplication_method : {"four", "three", "threealt"}, default: "four"
        Complex product implementation for ``data_type="split"``, matching
        :meth:`~b_asic.sfg.SFG.complex_to_real` and :meth:`~b_asic.sfg.SFG.transform`.
        General complex products use four real multiplications or three with
        extra additions. Real-real and real-complex products use only one and
        two real multiplications, respectively, regardless of this setting.
        Conjugate self-products use two squares and produce a real result.

    Returns
    -------
    :class:`~b_asic.sfg.SFG`
        Signal Flow Graph
    """
    arithmetic = _MatrixArithmetic(data_type, multiplication_method, pe)
    TILE_SIZE = 2
    if N % TILE_SIZE != 0:
        raise ValueError("Tile size needs to be a positive divisor of N.")

    if name is None:
        name = "Tile LDLT matrix-inversion"

    if mode not in ("mult", "eqs"):
        raise NotImplementedError(f"mode={mode} is not yet implemented for tile LDLT.")
    if pe not in (None, "addsub", "mads"):
        raise NotImplementedError(f"pe={pe} is not yet implemented for tile LDLT.")

    N_tiles = N // TILE_SIZE

    def _add_nodes(a, b):
        if pe == "addsub":
            return arithmetic.addsub(True, a, b)
        return a + b

    def _sub_nodes(a, b):
        if pe == "addsub":
            return arithmetic.addsub(False, a, b)
        return a - b

    def _mul_nodes(a, b, *, real_valued=False):
        if pe == "mads":
            return arithmetic.mads(
                is_add=True,
                in0=None,
                in1=a,
                in2=b,
                do_addsub=False,
                real_valued=real_valued,
            )
        return arithmetic.multiplication(a, b, real_valued=real_valued)

    def _mac_tiles(
        is_add: bool,
        acc_tile,
        A_tile,
        B_tile,
        mult_mode="regular",
        lower_triangular=False,
    ):
        res = [[None for _ in range(TILE_SIZE)] for _ in range(TILE_SIZE)]
        for r in range(TILE_SIZE):
            for c in range(TILE_SIZE):
                if lower_triangular and r < c:
                    continue

                if mult_mode == "T":
                    v1 = [A_tile[r][x] for x in range(TILE_SIZE)]
                    v2 = [arithmetic.conjugate(B_tile[c][x]) for x in range(TILE_SIZE)]
                elif mult_mode == "tile_tri_T":
                    v1 = [A_tile[r][x] for x in range(c + 1)]
                    v2 = [arithmetic.conjugate(B_tile[c][x]) for x in range(c + 1)]
                elif mult_mode == "tile_diag":
                    v1 = [A_tile[r][c]]
                    v2 = [B_tile[c][c]]

                if pe == "mads":
                    # First build the dot product positively.
                    if acc_tile is None or acc_tile[r][c] is None:
                        acc = _mul_nodes(
                            v1[0], v2[0], real_valued=lower_triangular and r == c
                        )
                        for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                            acc = arithmetic.mads(
                                is_add=True,
                                in0=acc,
                                in1=xv1,
                                in2=xv2,
                                do_addsub=True,
                                real_valued=lower_triangular and r == c,
                            )
                    else:
                        acc = arithmetic.mads(
                            is_add=is_add,
                            in0=acc_tile[r][c],
                            in1=v1[0],
                            in2=v2[0],
                            do_addsub=True,
                            real_valued=lower_triangular and r == c,
                        )
                        for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                            acc = arithmetic.mads(
                                is_add=is_add,
                                in0=acc,
                                in1=xv1,
                                in2=xv2,
                                do_addsub=True,
                                real_valued=lower_triangular and r == c,
                            )

                elif pe == "addsub":
                    acc = arithmetic.multiplication(
                        v1[0], v2[0], real_valued=lower_triangular and r == c
                    )
                    for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                        acc = _add_nodes(
                            acc,
                            arithmetic.multiplication(
                                xv1, xv2, real_valued=lower_triangular and r == c
                            ),
                        )

                    if acc_tile is not None and acc_tile[r][c] is not None:
                        acc = arithmetic.addsub(
                            is_add=is_add,
                            in0=acc_tile[r][c],
                            in1=acc,
                        )
                else:
                    acc = arithmetic.multiplication(
                        v1[0], v2[0], real_valued=lower_triangular and r == c
                    )
                    for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                        acc = acc + arithmetic.multiplication(
                            xv1, xv2, real_valued=lower_triangular and r == c
                        )

                    if acc_tile is not None and acc_tile[r][c] is not None:
                        acc = acc_tile[r][c] + acc if is_add else acc_tile[r][c] - acc

                res[r][c] = arithmetic.real(acc) if lower_triangular and r == c else acc
        return res

    A = [[None for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(i + 1):
            in_op = arithmetic.input(i, j, mem)
            A[i][j] = in_op

    L_tiles = [
        [
            [[None for _ in range(TILE_SIZE)] for _ in range(TILE_SIZE)]
            for _ in range(N_tiles)
        ]
        for _ in range(N_tiles)
    ]
    L_inv_tiles = [
        [
            [[None for _ in range(TILE_SIZE)] for _ in range(TILE_SIZE)]
            for _ in range(N_tiles)
        ]
        for _ in range(N_tiles)
    ]
    D_tiles = [
        [[None for _ in range(TILE_SIZE)] for _ in range(TILE_SIZE)]
        for _ in range(N_tiles)
    ]
    D_inv_tiles = [
        [[None for _ in range(TILE_SIZE)] for _ in range(TILE_SIZE)]
        for _ in range(N_tiles)
    ]

    A_tiles = [
        [
            [[None for _ in range(TILE_SIZE)] for _ in range(TILE_SIZE)]
            for _ in range(N_tiles)
        ]
        for _ in range(N_tiles)
    ]
    for i in range(N_tiles):
        for j in range(i + 1):
            for r in range(TILE_SIZE):
                for c in range(TILE_SIZE):
                    row = i * TILE_SIZE + r
                    col = j * TILE_SIZE + c
                    if row >= col:
                        A_tiles[i][j][r][c] = A[row][col]
                    else:
                        A_tiles[i][j][r][c] = arithmetic.conjugate(A[col][row])

    for k in range(N_tiles):
        # xSYTRF2
        A_kk = A_tiles[k][k]

        D00 = A_kk[0][0]

        D_inv00 = arithmetic.reciprocal(D00, real_valued=True)

        L10 = _mul_nodes(A_kk[1][0], D_inv00)
        L_inv10 = -L10
        offdiag_conj = arithmetic.conjugate(A_kk[1][0])

        if pe == "mads":
            D11 = arithmetic.mads(
                is_add=False,
                in0=A_kk[1][1],
                in1=L10,
                in2=offdiag_conj,
                do_addsub=True,
                real_valued=True,
            )
        elif pe == "addsub":
            D11 = arithmetic.addsub(
                is_add=False,
                in0=A_kk[1][1],
                in1=arithmetic.multiplication(L10, offdiag_conj, real_valued=True),
            )
        else:
            D11 = A_kk[1][1] - arithmetic.multiplication(
                L10, offdiag_conj, real_valued=True
            )

        D11 = arithmetic.real(D11)
        D_inv11 = arithmetic.reciprocal(D11, real_valued=True)

        L_tiles[k][k][1][0] = L10
        L_inv_tiles[k][k][1][0] = L_inv10

        D_tiles[k][0][0] = D00
        D_tiles[k][1][1] = D11

        D_inv_tiles[k][0][0] = D_inv00
        D_inv_tiles[k][1][1] = D_inv11

        if k < N_tiles - 1:
            inv_W_kk_T = [[None for _ in range(TILE_SIZE)] for _ in range(TILE_SIZE)]
            inv_W_kk_T[0][0] = D_inv00
            inv_W_kk_T[1][0] = _mul_nodes(L_inv10, D_inv11)
            inv_W_kk_T[1][1] = D_inv11

        for i in range(k + 1, N_tiles):
            # xTRSM
            L_tiles[i][k] = _mac_tiles(
                True, None, A_tiles[i][k], inv_W_kk_T, "tile_tri_T"
            )

        for i in range(k + 1, N_tiles):
            # xSYDRK
            tmp = _mac_tiles(True, None, L_tiles[i][k], D_tiles[k], "tile_diag")
            A_tiles[i][i] = _mac_tiles(
                False, A_tiles[i][i], tmp, L_tiles[i][k], "T", True
            )
            for j in range(k + 1, i):
                # xGEMDM
                A_tiles[i][j] = _mac_tiles(
                    False, A_tiles[i][j], tmp, L_tiles[j][k], "T"
                )

    L = [[None for _ in range(N)] for _ in range(N)]
    L_inv = [[None for _ in range(N)] for _ in range(N)]
    D = [None for _ in range(N)]
    D_inv = [None for _ in range(N)]

    # Copy tiles to L, L_inv, D, D_inv
    for bi in range(N_tiles):
        row_off = bi * TILE_SIZE
        for bj in range(bi + 1):
            col_off = bj * TILE_SIZE
            l_tile = L_tiles[bi][bj]
            l_inv_tile = L_inv_tiles[bi][bj]
            for r in range(TILE_SIZE):
                for c in range(TILE_SIZE):
                    l_val = l_tile[r][c]
                    if l_val is not None:
                        L[row_off + r][col_off + c] = l_val

                    l_inv_val = l_inv_tile[r][c]
                    if l_inv_val is not None:
                        L_inv[row_off + r][col_off + c] = l_inv_val

    for bi in range(N_tiles):
        off = bi * TILE_SIZE
        for d in range(TILE_SIZE):
            D[off + d] = D_tiles[bi][d][d]
            D_inv[off + d] = D_inv_tiles[bi][d][d]

    res = [[None for _ in range(N)] for _ in range(N)]
    if mode == "mult":
        # Complete strictly lower part of L_inv not produced by xSYTRF2.
        for i in range(1, N):
            for j in range(i - 1, -1, -1):
                if i % 2 == 1 and j == i - 1:
                    continue
                acc = L[i][j]
                for k in range(j + 1, i):
                    if pe == "mads":
                        acc = arithmetic.mads(
                            is_add=True,
                            in0=acc,
                            in1=L[i][k],
                            in2=L_inv[k][j],
                            do_addsub=True,
                        )
                    else:
                        acc = _add_nodes(acc, L[i][k] * L_inv[k][j])
                L_inv[i][j] = -acc

        for i in range(N - 1, -1, -1):
            for j in range(i, -1, -1):
                if i == j:
                    res[i][j] = D_inv[i]
                elif pe == "mads":
                    res[i][j] = _mul_nodes(D_inv[i], L_inv[i][j])
                else:
                    res[i][j] = D_inv[i] * L_inv[i][j]

                for k in range(i + 1, N):
                    l_inv_conj = arithmetic.conjugate(L_inv[k][i])
                    if pe == "mads":
                        t0 = _mul_nodes(l_inv_conj, D_inv[k])
                        res[i][j] = arithmetic.mads(
                            is_add=True,
                            in0=res[i][j],
                            in1=t0,
                            in2=L_inv[k][j],
                            do_addsub=True,
                            real_valued=i == j,
                        )
                    else:
                        t0 = l_inv_conj * D_inv[k]
                        res[i][j] = _add_nodes(
                            res[i][j],
                            arithmetic.multiplication(
                                t0, L_inv[k][j], real_valued=i == j
                            ),
                        )

    else:  # mode == "eqs"
        for s in range(2 * (N - 1), -1, -1):
            i_min = (s + 1) // 2
            i_max = min(s, N - 1)
            for i in range(i_max, i_min - 1, -1):
                j = s - i
                if i == j:
                    val = D_inv[i]
                    for k in range(N - 1, i, -1):
                        l_conj = arithmetic.conjugate(L[k][i])
                        if pe == "mads":
                            val = arithmetic.mads(
                                is_add=False,
                                in0=val,
                                in1=l_conj,
                                in2=res[k][i],
                                do_addsub=True,
                                real_valued=True,
                            )
                        else:
                            val = _sub_nodes(
                                val,
                                arithmetic.multiplication(
                                    l_conj, res[k][i], real_valued=True
                                ),
                            )
                elif j == i - 1 and i % 2 == 1:
                    if pe == "mads":
                        val = _mul_nodes(D_inv[i], L_inv[i][j])
                    else:
                        val = D_inv[i] * L_inv[i][j]

                    for k in range(N - 1, i, -1):
                        l_conj = arithmetic.conjugate(L[k][i])
                        if pe == "mads":
                            val = arithmetic.mads(
                                is_add=False,
                                in0=val,
                                in1=l_conj,
                                in2=res[k][j],
                                do_addsub=True,
                            )
                        else:
                            val = _sub_nodes(val, l_conj * res[k][j])
                else:
                    res_last = arithmetic.matrix_entry(res, i, N - 1)
                    if pe == "mads":
                        val = -_mul_nodes(
                            L[N - 1][j],
                            res_last,
                        )
                        for k in range(N - 2, j, -1):
                            val = arithmetic.mads(
                                is_add=False,
                                in0=val,
                                in1=L[k][j],
                                in2=arithmetic.matrix_entry(res, i, k),
                                do_addsub=True,
                            )
                    else:
                        val = -L[N - 1][j] * res_last
                        for k in range(N - 2, j, -1):
                            val = _sub_nodes(
                                val, L[k][j] * arithmetic.matrix_entry(res, i, k)
                            )
                res[i][j] = arithmetic.real(val) if i == j else val

    outputs = [
        arithmetic.output(i, j, res[i][j], mem) for i in range(N) for j in range(i + 1)
    ]

    return arithmetic.graph(outputs, name)


def analytical_block_matrix_inverse(
    N: int,
    name: str | None = None,
    mode: Literal["top", "bot", "mid"] = "mid",
    pe: Literal["addsub", "mads"] | None = None,
    mem: bool = False,
    data_type: Literal["real", "complex", "split"] = "real",
    multiplication_method: Literal["four", "three", "threealt"] = "four",
) -> SFG:
    r"""
    Generate an SFG for the analytical block matrix inverse algorithm.

    Parameters
    ----------
    N : int
        Dimension of the square input matrix.
    name : str, optional
        The name of the SFG. If None, "Analytical block matrix-inversion".
    mode : {"top", "bot", "mid"}, default: "mid"
        The mode of operation, either "top", "bot", or "mid".
    pe : {"addsub", "mads", None}, default: None
        Processing element to use.
    mem : bool, default: False
        Use :class:`~b_asic.special_operations.MemoryRead` and
        :class:`~b_asic.special_operations.MemoryWrite` instead of
        :class:`~b_asic.special_operations.Input` and
        :class:`~b_asic.special_operations.Output`. Input and inverse entries
        use packed lower-triangular row order in the default unnamed memory:
        entry :math:`(i, j)` has address :math:`\frac{i(i+1)}{2} + j` for :math:`i \ge j`.
        Each matrix occupies :math:`\frac{N(N+1)}{2}` locations.
    data_type : {"real", "complex", "split"}, default: "real"
        Generate scalar real arithmetic for symmetric matrices, native complex
        arithmetic for Hermitian matrices, or real arithmetic with separate
        real and imaginary components for Hermitian matrices. Split interfaces
        are ordered ``real0, imag0, real1, imag1, ...``. Diagonal imaginary inputs
        are unused and diagonal imaginary outputs are zero. With ``mem=True``,
        components of packed entry address ``p`` use addresses ``2*p`` and
        ``2*p + 1`` in the same memory.
    multiplication_method : {"four", "three", "threealt"}, default: "four"
        Complex product implementation for ``data_type="split"``, matching
        :meth:`~b_asic.sfg.SFG.complex_to_real` and :meth:`~b_asic.sfg.SFG.transform`.
        General complex products use four real multiplications or three with
        extra additions. Real-real and real-complex products use only one and
        two real multiplications, respectively, regardless of this setting.
        Conjugate self-products use two squares and produce a real result.

    Returns
    -------
    :class:`~b_asic.sfg.SFG`
        Signal Flow Graph
    """
    arithmetic = _MatrixArithmetic(data_type, multiplication_method, pe)
    if name is None:
        name = "Analytical block matrix-inversion"

    if mode not in {"top", "bot", "mid"}:
        raise ValueError(f"Unknown mode: {mode}")

    def _add_nodes(a, b):
        if pe == "addsub":
            return arithmetic.addsub(True, a, b)
        return a + b

    def _sub_nodes(a, b):
        if pe == "addsub":
            return arithmetic.addsub(False, a, b)
        return a - b

    def _mac_block(
        is_add: bool,
        acc_block,
        A_block,
        B_block,
        mult_mode: str = "regular",
        lower_triangular: bool = False,
    ):
        if mult_mode in {"regular", "diag_block", "block_diag"}:
            bs_a = len(A_block)
            bs_b = len(B_block[0])
            bs_inner = len(A_block[0])
        elif mult_mode == "T":
            bs_a = len(A_block)
            bs_b = len(B_block)
            bs_inner = len(A_block[0])
        elif mult_mode in {"T_blocks", "T_block_diag"}:
            bs_a = len(A_block[0])
            bs_b = len(B_block[0])
            bs_inner = len(A_block)

        res = [[None for _ in range(bs_b)] for _ in range(bs_a)]

        for r in range(bs_a):
            for c in range(bs_b):
                if lower_triangular and r < c:
                    continue

                if mult_mode == "T":
                    v1 = [A_block[r][x] for x in range(bs_inner)]
                    v2 = [arithmetic.conjugate(B_block[c][x]) for x in range(bs_inner)]
                elif mult_mode == "T_blocks":
                    v1 = [arithmetic.conjugate(A_block[x][r]) for x in range(bs_inner)]
                    v2 = [B_block[x][c] for x in range(bs_inner)]
                elif mult_mode == "diag_block":
                    v1 = [
                        arithmetic.matrix_entry(A_block, r, x) for x in range(bs_inner)
                    ]
                    v2 = [B_block[x][c] for x in range(bs_inner)]
                elif mult_mode == "block_diag":
                    v1 = [A_block[r][x] for x in range(bs_inner)]
                    v2 = [
                        arithmetic.matrix_entry(B_block, x, c) for x in range(bs_inner)
                    ]

                if pe == "mads":
                    if acc_block is None:
                        if is_add:
                            acc = arithmetic.mads(
                                is_add=True,
                                in0=None,
                                in1=v1[0],
                                in2=v2[0],
                                do_addsub=False,
                                real_valued=lower_triangular and r == c,
                            )
                            for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                                acc = arithmetic.mads(
                                    is_add=True,
                                    in0=acc,
                                    in1=xv1,
                                    in2=xv2,
                                    do_addsub=True,
                                    real_valued=lower_triangular and r == c,
                                )
                        else:
                            acc = arithmetic.mads(
                                is_add=False,
                                in0=None,
                                in1=v1[0],
                                in2=v2[0],
                                do_addsub=False,
                                real_valued=lower_triangular and r == c,
                            )
                            for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                                acc = arithmetic.mads(
                                    is_add=False,
                                    in0=acc,
                                    in1=xv1,
                                    in2=xv2,
                                    do_addsub=True,
                                    real_valued=lower_triangular and r == c,
                                )
                    else:
                        if acc_block[r][c] is not None:
                            acc = arithmetic.mads(
                                is_add=is_add,
                                in0=acc_block[r][c],
                                in1=v1[0],
                                in2=v2[0],
                                do_addsub=True,
                                real_valued=lower_triangular and r == c,
                            )

                        for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                            acc = arithmetic.mads(
                                is_add=is_add,
                                in0=acc,
                                in1=xv1,
                                in2=xv2,
                                do_addsub=True,
                                real_valued=lower_triangular and r == c,
                            )
                else:
                    acc = arithmetic.multiplication(
                        v1[0], v2[0], real_valued=lower_triangular and r == c
                    )
                    for xv1, xv2 in zip(v1[1:], v2[1:], strict=True):
                        acc = _add_nodes(
                            acc,
                            arithmetic.multiplication(
                                xv1, xv2, real_valued=lower_triangular and r == c
                            ),
                        )
                    if acc_block is not None:
                        if acc_block[r][c] is not None:
                            acc = (
                                _add_nodes(acc_block[r][c], acc)
                                if is_add
                                else _sub_nodes(acc_block[r][c], acc)
                            )
                    else:
                        acc = acc if is_add else -acc
                res[r][c] = arithmetic.real(acc) if lower_triangular and r == c else acc

        return res

    def _copy_block_full(A_block):
        bs_r = len(A_block)
        bs_c = len(A_block[0])
        res = [[None for _ in range(bs_c)] for _ in range(bs_r)]
        for r in range(bs_r):
            for c in range(bs_c):
                res[r][c] = A_block[r][c]
        return res

    def _copy_block_lower_triangular(A_block):
        bs = len(A_block)
        res = [[None for _ in range(bs)] for _ in range(bs)]
        for r in range(bs):
            for c in range(r + 1):
                res[r][c] = A_block[r][c]
        return res

    def _inv_2x2_explicit(A_block):
        res = [[None for _ in range(2)] for _ in range(2)]
        offdiag_conj = arithmetic.conjugate(A_block[1][0])
        if pe == "mads":
            tmp = arithmetic.mads(
                is_add=True,
                in0=None,
                in1=A_block[0][0],
                in2=A_block[1][1],
                do_addsub=False,
            )
            det = arithmetic.mads(
                is_add=False,
                in0=tmp,
                in1=A_block[1][0],
                in2=offdiag_conj,
                do_addsub=True,
            )
            inv_det = arithmetic.reciprocal(det, real_valued=True)
            res[0][0] = arithmetic.mads(
                is_add=True,
                in0=None,
                in1=A_block[1][1],
                in2=inv_det,
                do_addsub=False,
            )
            res[1][0] = arithmetic.mads(
                is_add=False,
                in0=None,
                in1=A_block[1][0],
                in2=inv_det,
                do_addsub=False,
            )
            res[1][1] = arithmetic.mads(
                is_add=True,
                in0=None,
                in1=A_block[0][0],
                in2=inv_det,
                do_addsub=False,
            )
        else:
            det = _sub_nodes(
                A_block[0][0] * A_block[1][1], A_block[1][0] * offdiag_conj
            )
            inv_det = arithmetic.reciprocal(det, real_valued=True)
            res[0][0] = A_block[1][1] * inv_det
            res[1][0] = -A_block[1][0] * inv_det
            res[1][1] = A_block[0][0] * inv_det
        return res

    def _analytical_block_inv_inner(matrix):
        n = len(matrix)

        if n == 1:
            inv_val = arithmetic.reciprocal(matrix[0][0], real_valued=True)
            return [[inv_val]]

        if n == 2:
            return _inv_2x2_explicit(matrix)

        # Determine split
        if mode == "top":
            n_a = 2
            n_d = n - 2
        elif mode == "bot":
            n_a = n - 2
            n_d = 2
        else:
            n_a = n // 2
            n_d = n - n_a

        # Extract blocks
        if mode == "top":
            A_blk = _copy_block_lower_triangular([row[:2] for row in matrix[:2]])
            B_blk = _copy_block_full([row[:2] for row in matrix[2:]])
            D_blk = _copy_block_lower_triangular([row[2:] for row in matrix[2:]])
        elif mode == "bot":
            A_blk = _copy_block_lower_triangular([row[:-2] for row in matrix[:-2]])
            B_blk = _copy_block_full([row[:-2] for row in matrix[-2:]])
            D_blk = _copy_block_lower_triangular([row[-2:] for row in matrix[-2:]])
        else:
            A_blk = _copy_block_lower_triangular([row[:n_a] for row in matrix[:n_a]])
            B_blk = _copy_block_full([row[:n_a] for row in matrix[n_a:]])
            D_blk = _copy_block_lower_triangular([row[n_a:] for row in matrix[n_a:]])

        # V = inv(A)
        V = _analytical_block_inv_inner(A_blk)

        # X = B @ V
        X = _mac_block(True, None, B_blk, V, "block_diag")

        # schur = D - B @ X.T (X.conj().T for Hermitian matrices)
        schur = _mac_block(False, D_blk, B_blk, X, "T", lower_triangular=True)

        # H = inv(schur)
        H = _analytical_block_inv_inner(schur)

        # F = -H @ X (which is -Z)
        F = _mac_block(False, None, H, X, "diag_block")

        # E = V - X.T @ F (X.conj().T for Hermitian matrices)
        E = _mac_block(False, V, X, F, "T_blocks", lower_triangular=True)

        # Assemble result (only lower triangular for diagonal blocks)
        matrix_inv = [[None for _ in range(n)] for _ in range(n)]
        if mode == "top":
            # Top-left
            for r in range(2):
                for c in range(r + 1):
                    matrix_inv[r][c] = E[r][c]
            # Bottom-left
            for r in range(n_d):
                for c in range(2):
                    matrix_inv[2 + r][c] = F[r][c]
            # Bottom-right
            for r in range(n_d):
                for c in range(r + 1):
                    matrix_inv[2 + r][2 + c] = H[r][c]
        elif mode == "bot":
            # Top-left
            for r in range(n_a):
                for c in range(r + 1):
                    matrix_inv[r][c] = E[r][c]
            # Bottom-left
            for r in range(2):
                for c in range(n_a):
                    matrix_inv[n_a + r][c] = F[r][c]
            # Bottom-right
            for r in range(2):
                for c in range(r + 1):
                    matrix_inv[n_a + r][n_a + c] = H[r][c]
        else:
            # Top-left
            for r in range(n_a):
                for c in range(r + 1):
                    matrix_inv[r][c] = E[r][c]
            # Bottom-left
            for r in range(n_d):
                for c in range(n_a):
                    matrix_inv[n_a + r][c] = F[r][c]
            # Bottom-right
            for r in range(n_d):
                for c in range(r + 1):
                    matrix_inv[n_a + r][n_a + c] = H[r][c]

        return matrix_inv

    A = [[None for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(i + 1):
            in_op = arithmetic.input(i, j, mem)
            A[i][j] = in_op

    result = _analytical_block_inv_inner(A)

    outputs = [
        arithmetic.output(i, j, result[i][j], mem)
        for i in range(N)
        for j in range(i + 1)
    ]

    return arithmetic.graph(outputs, name)
