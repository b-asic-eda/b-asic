r"""
B-ASIC signal flow graph generators.

This module contains a number of functions generating SFGs for matrix inversion.

With ``data_type="complex"`` or ``data_type="split"``, the generators invert
Hermitian input matrices by default. The default ``data_type="real"`` uses
symmetric matrices. :func:`schur_matrix_inverse` additionally supports general
and complex symmetric matrices through its ``structure`` argument.
Cholesky algorithms require positive definite input matrices.
The QR generator supports symmetric or Hermitian nonsingular matrices, with
``method="householder"`` or ``method="givens"`` selecting the decomposition.
Scalar inverses use explicit :class:`~b_asic.core_operations.Reciprocal`
operations marked real-valued: Hermitian LDLT pivots and block determinants
are real, while other complex pivots use conjugates and reciprocal squared
magnitudes. Real matrices have real-valued input and output interfaces; Hermitian
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
this same external layout regardless of their internal partitioning. Schur
inversion with ``structure="general"`` instead uses full row-major interfaces.

For example, generate a Hermitian inverse directly in real arithmetic with
three real multiplications per general complex product using::

    sfg = ldlt_matrix_inverse(4, data_type="split", multiplication_method="three")
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from b_asic.sfg import SFG
from b_asic.sfg_generators._matrix_arithmetic import _MatrixArithmetic
from b_asic.sfg_generators.matrix_decomposition import (
    _cholesky_decomposition,
    _ldlt_decomposition,
    _qr_factorization,
    _qr_mac,
    _qr_reciprocal,
    _validate_qr_arguments,
)


def qr_matrix_inverse(
    N: int,
    name: str | None = None,
    *,
    mode: Literal["eqs", "mult", "implicitq", "implicitq_eqs"] = "eqs",
    method: Literal["householder", "givens"] = "householder",
    pe: Literal["addsub", "mads"] | None = None,
    mem: bool = False,
    data_type: Literal["real", "complex", "split"] = "real",
    multiplication_method: Literal["four", "three", "threealt"] = "four",
) -> SFG:
    r"""
    Generate an SFG for symmetric or Hermitian inversion using QR decomposition.

    Factor the input as :math:`A=QR`, then compute :math:`A^{-1}=R^{-1}Q^H`
    using the selected mode. The matrix must be nonsingular; positive definiteness is
    unnecessary. Normalization uses reciprocal square roots and reciprocals.

    Parameters
    ----------
    N : int
        Positive dimension of the square input matrix.
    name : str, optional
        Graph name. Defaults to "Householder QR matrix-inversion" or
        "Givens QR matrix-inversion".
    mode : {"eqs", "mult", "implicitq", "implicitq_eqs"}, default: "eqs"
        "eqs" forms Q conjugate transpose and solves RX = Q conjugate transpose
        by back substitution. "mult" forms Q conjugate transpose, inverts R,
        and multiplies R inverse by Q conjugate transpose. "implicitq" inverts R and applies the stored
        Householder reflections or Givens rotations from the right in reverse
        factorization order, without forming Q conjugate transpose or a general matrix
        product. "implicitq_eqs" applies the stored transformations from the
        left to each unit right-hand side, then solves the triangular system
        for that inverse column. It forms neither Q conjugate transpose as a
        matrix nor R inverse. Only the lower triangle of the inverse is output;
        implicit updates can also require upper-triangular intermediate entries.
        Computing every right-hand side in an unrolled SFG can yield the same
        arithmetic as "eqs" despite the different construction order.
    method : {"householder", "givens"}, default: "householder"
        Use Householder reflections or Givens rotations. Householder uses
        :class:`~b_asic.core_operations.CopySign` to avoid cancellation when
        constructing a reflector.
    pe : {"addsub", "mads", None}, optional
        Use AddSub operations, multiply-add/subtract operations, or separate
        additions, subtractions and multiplications.
    mem : bool, default: False
        Use MemoryRead/MemoryWrite interfaces in the default unnamed memory.
        Inputs and inverse outputs use packed lower-triangular row order:
        entry :math:`(i,j)` has address :math:`i(i+1)/2+j`, for :math:`i\ge j`.
        Each matrix occupies :math:`N(N+1)/2` entries. Without memory,
        Input/Output interfaces use the same order.
    data_type : {"real", "complex", "split"}, default: "real"
        Symmetric real, Hermitian complex, or Hermitian split real arithmetic.
        Split interfaces interleave real/imaginary components
        of every packed entry. Diagonal imaginary inputs are ignored and
        outputs are zero. Split memory components use addresses ``2*p`` and
        ``2*p+1`` for packed entry address ``p``.
    multiplication_method : {"four", "three", "threealt"}, default: "four"
        Split complex product implementation, matching the other inverses.

    Returns
    -------
    SFG
        Signal flow graph with packed lower-triangular input and inverse output.
    """
    _validate_qr_arguments(N, method, pe)
    if mode not in ("eqs", "mult", "implicitq", "implicitq_eqs"):
        raise ValueError('mode must be "eqs", "mult", "implicitq", or "implicitq_eqs"')
    arithmetic = _MatrixArithmetic(data_type, multiplication_method, pe)
    lower = [[arithmetic.input(i, j, mem) for j in range(i + 1)] for i in range(N)]
    matrix = [
        [arithmetic.matrix_entry(lower, i, j) for j in range(N)] for i in range(N)
    ]
    inverse = _qr_inverse(matrix, arithmetic, method, mode)

    return arithmetic.graph(
        [
            arithmetic.output(
                i,
                j,
                arithmetic.real_part(inverse[i][j]) if i == j else inverse[i][j],
                mem,
            )
            for i in range(N)
            for j in range(i + 1)
        ],
        name if name is not None else f"{method.capitalize()} QR matrix-inversion",
    )


def _qr_inverse(matrix, arithmetic, method, mode, *, lower_only=True):
    """Invert matrix sources, optionally retaining the full inverse."""
    N = len(matrix)
    R, QH, transformations = _qr_factorization(
        matrix, arithmetic, method, form_q=mode in ("eqs", "mult")
    )

    if mode == "eqs":
        inverse = [[None] * N for _ in range(N)]
        for i in range(N - 1, -1, -1):
            pivot_inverse = _qr_reciprocal(arithmetic, R[i][i])
            # Structured inverses need only the lower triangle of each solution.
            for j in range(i + 1 if lower_only else N):
                value = QH[i][j]
                for k in range(i + 1, N):
                    value = _qr_mac(arithmetic, value, R[i][k], inverse[k][j], False)
                inverse[i][j] = _qr_mac(arithmetic, None, value, pivot_inverse)
    elif mode == "implicitq_eqs":
        inverse = [[None] * N for _ in range(N)]
        pivot_inverses = [_qr_reciprocal(arithmetic, R[i][i]) for i in range(N)]
        for j in range(N):
            right_hand_side = [arithmetic.constant(int(i == j)) for i in range(N)]
            right_hand_side = _qr_apply_left(
                right_hand_side, transformations, arithmetic, method
            )
            # Structured output needs only the tail of column j.
            for i in range(N - 1, (j if lower_only else 0) - 1, -1):
                value = right_hand_side[i]
                for k in range(i + 1, N):
                    value = _qr_mac(arithmetic, value, R[i][k], inverse[k][j], False)
                inverse[i][j] = _qr_mac(arithmetic, None, value, pivot_inverses[i])
    else:
        triangular_inverse = _qr_upper_inverse(R, arithmetic)
        if mode == "mult":
            inverse = [[None] * N for _ in range(N)]
            for i in range(N):
                for j in range(i + 1 if lower_only else N):
                    value = None
                    for k in range(i, N):
                        value = _qr_mac(
                            arithmetic, value, triangular_inverse[i][k], QH[k][j]
                        )
                    inverse[i][j] = value
        else:
            inverse = _qr_apply_right(
                triangular_inverse, transformations, arithmetic, method
            )

    return inverse


def _qr_apply_left(vector, transformations, arithmetic, method):
    """Apply implicit Q conjugate transpose to one right-hand side."""
    result = vector.copy()
    # R = T_m ... T_1 A, so a right-hand side first encounters T_1.
    for transformation in transformations:
        if method == "householder":
            k, reflector, beta = transformation
            projection = None
            for offset, value in enumerate(reflector):
                projection = _qr_mac(
                    arithmetic,
                    projection,
                    arithmetic.conjugate(value),
                    result[k + offset],
                )
            scale = _qr_mac(arithmetic, None, beta, projection)
            for offset, value in enumerate(reflector):
                result[k + offset] = _qr_mac(
                    arithmetic, result[k + offset], value, scale, False
                )
        else:
            k, i, cosine, sine = transformation
            top, bottom = result[k], result[i]
            result[k] = _qr_mac(
                arithmetic, _qr_mac(arithmetic, None, cosine, top), sine, bottom
            )
            result[i] = _qr_mac(
                arithmetic,
                _qr_mac(arithmetic, None, arithmetic.conjugate(cosine), bottom),
                arithmetic.conjugate(sine),
                top,
                False,
            )
    return result


def _qr_upper_inverse(R, arithmetic):
    """Invert an upper triangular matrix with one reciprocal per diagonal."""
    N = len(R)
    result = [[arithmetic.constant(0) for _ in range(N)] for _ in range(N)]
    for i in range(N - 1, -1, -1):
        result[i][i] = _qr_reciprocal(arithmetic, R[i][i])
        for j in range(i + 1, N):
            value = None
            for k in range(i + 1, j + 1):
                value = _qr_mac(arithmetic, value, R[i][k], result[k][j])
            result[i][j] = _qr_mac(arithmetic, None, result[i][i], value, False)
    return result


def _qr_apply_right(matrix, transformations, arithmetic, method):
    """Apply implicit Q conjugate transpose to a matrix from the right."""
    result = [row.copy() for row in matrix]
    for transformation in reversed(transformations):
        if method == "householder":
            k, vector, beta = transformation
            for row in result:
                projection = None
                for offset, value in enumerate(vector):
                    projection = _qr_mac(arithmetic, projection, row[k + offset], value)
                scale = _qr_mac(arithmetic, None, beta, projection)
                for offset, value in enumerate(vector):
                    row[k + offset] = _qr_mac(
                        arithmetic,
                        row[k + offset],
                        scale,
                        arithmetic.conjugate(value),
                        False,
                    )
        else:
            k, i, cosine, sine = transformation
            for row in result:
                left, right = row[k], row[i]
                row[k] = _qr_mac(
                    arithmetic,
                    _qr_mac(arithmetic, None, cosine, left),
                    arithmetic.conjugate(sine),
                    right,
                    False,
                )
                row[i] = _qr_mac(
                    arithmetic,
                    _qr_mac(arithmetic, None, arithmetic.conjugate(cosine), right),
                    sine,
                    left,
                )
    return result


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

    A = [[None for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(i + 1):
            A[i][j] = arithmetic.input(i, j, mem)
    res = _ldlt_inverse(A, arithmetic, mode)
    return arithmetic.graph(
        [
            arithmetic.output(i, j, res[i][j], mem)
            for i in range(N)
            for j in range(i + 1)
        ],
        name,
    )


def _ldlt_inverse(A, arithmetic, mode, *, hermitian=True):
    """Build inverse sources shared by scalar and Schur generators."""
    pe = arithmetic.pe
    real_diagonal = hermitian or arithmetic.data_type == "real"

    def transpose_value(value):
        return arithmetic.conjugate(value) if hermitian else value

    def entry(matrix, i, j):
        return matrix[i][j] if i >= j else transpose_value(matrix[j][i])

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
                    l_inv_conj = transpose_value(L_inv[k][i])
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
                            real_valued=real_diagonal and i == j,
                        )
                    elif pe == "addsub":
                        t0 = l_inv_conj * D_inv[k]
                        res[i][j] = arithmetic.addsub(
                            is_add=True,
                            in0=res[i][j],
                            in1=arithmetic.multiplication(
                                t0, L_inv[k][j], real_valued=real_diagonal and i == j
                            ),
                        )
                    else:
                        t0 = l_inv_conj * D_inv[k]
                        res[i][j] = res[i][j] + arithmetic.multiplication(
                            t0, L_inv[k][j], real_valued=real_diagonal and i == j
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
                        l_conj = transpose_value(L[k][i])
                        if pe == "mads":
                            val = arithmetic.mads(
                                is_add=False,
                                in0=val,
                                in1=l_conj,
                                in2=res[k][i],
                                do_addsub=True,
                                real_valued=real_diagonal,
                            )
                        elif pe == "addsub":
                            val = arithmetic.addsub(
                                is_add=False,
                                in0=val,
                                in1=arithmetic.multiplication(
                                    l_conj, res[k][i], real_valued=real_diagonal
                                ),
                            )
                        else:
                            val = val - arithmetic.multiplication(
                                l_conj, res[k][i], real_valued=real_diagonal
                            )
                else:
                    for k in range(n - 1, j, -1):
                        res_ik = entry(res, i, k)
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
                res[i][j] = arithmetic.real(val) if real_diagonal and i == j else val

        return res

    L, _, D_inv = _ldlt_decomposition(A, arithmetic, hermitian=hermitian)

    if mode == "mult":
        L_inv = ldl_l_inv(L)
        res = ldl_matmul(L_inv, D_inv)
    else:
        res = ldl_eqs(L, D_inv)

    return res


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

    A = [[None for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(i + 1):
            A[i][j] = arithmetic.input(i, j, mem)
    res = _cholesky_inverse(A, arithmetic, mode)
    return arithmetic.graph(
        [
            arithmetic.output(i, j, res[i][j], mem)
            for i in range(N)
            for j in range(i + 1)
        ],
        name,
    )


def _cholesky_inverse(A, arithmetic, mode):
    """Build inverse sources shared by scalar and Schur generators."""
    pe = arithmetic.pe

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

    L, L_inv_diag = _cholesky_decomposition(A, arithmetic)

    if mode == "mult":
        L_inv = chol_l_inv(L, L_inv_diag)
        res = chol_matmul(L_inv)
    else:
        res = chol_eqs(L, L_inv_diag)

    return res


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


@dataclass(frozen=True)
class Leaf:
    """
    Specify a terminal block in a Schur inversion partition.

    Parameters
    ----------
    size : int
        Positive block dimension.
    method : {"analytical", "ldlt", "cholesky", "qr"}, optional
        Inversion method. None inherits the generator's ``leaf_method``.
        Selecting a method explicitly resets its options to that method's
        defaults, before applying ``options``.
    options : mapping, optional
        Algorithm-specific keyword arguments. With an inherited method, these
        override the generator's ``leaf_options``. QR accepts ``method``
        ("householder" or "givens") and ``mode`` ("eqs", "mult", "implicitq",
        or "implicitq_eqs"). LDLT and Cholesky accept ``mode`` ("eqs" or
        "mult"). Analytical leaves accept no options and have size at most 2.
    """

    size: int
    method: Literal["analytical", "ldlt", "cholesky", "qr"] | None = None
    options: Mapping[str, str] | None = None


type _SchurPartition = int | Leaf | tuple[_SchurPartition, _SchurPartition] | list[int]


def _schur_partition(
    N, partition, block_size, leaf_method, leaf_options, structure, data_type
):
    """Resolve every partition and leaf option before creating operations."""
    methods = ("analytical", "ldlt", "cholesky", "qr")
    if leaf_method not in methods:
        raise ValueError(f"leaf_method must be one of {methods}")
    if (
        isinstance(block_size, bool)
        or not isinstance(block_size, int)
        or block_size < 1
    ):
        raise ValueError("block_size must be a positive integer")

    def options_for(method, options):
        if options is not None and not isinstance(options, Mapping):
            raise ValueError("leaf options must be a mapping")
        options = dict(options or {})
        allowed = (
            {"mode", "method"}
            if method == "qr"
            else {"mode"}
            if method != "analytical"
            else set()
        )
        if options.keys() - allowed:
            raise ValueError(
                f"Unsupported {method} leaf options: {sorted(options.keys() - allowed)}"
            )
        if method != "analytical":
            options.setdefault("mode", "eqs")
            modes = (
                ("eqs", "mult", "implicitq", "implicitq_eqs")
                if method == "qr"
                else ("eqs", "mult")
            )
            if options["mode"] not in modes:
                raise ValueError(f"{method} leaf mode must be one of {modes}")
        if method == "qr":
            options.setdefault("method", "householder")
            if options["method"] not in ("householder", "givens"):
                raise ValueError('QR leaf method must be "householder" or "givens"')
        return options

    # Validate global options even when every explicit leaf overrides them.
    options_for(leaf_method, leaf_options)

    def resolve_leaf(leaf):
        if (
            isinstance(leaf.size, bool)
            or not isinstance(leaf.size, int)
            or leaf.size < 1
        ):
            raise ValueError("Leaf sizes must be positive integers")
        method = leaf_method if leaf.method is None else leaf.method
        if method not in methods:
            raise ValueError(f"Leaf method must be one of {methods}")
        if leaf.options is not None and not isinstance(leaf.options, Mapping):
            raise ValueError("leaf options must be a mapping")
        options = dict(leaf_options or {}) if leaf.method is None else {}
        options.update(leaf.options or {})
        options = options_for(method, options)
        if method == "analytical" and leaf.size > 2:
            raise ValueError("Analytical leaf size must be at most 2")
        if structure == "general" and method in ("ldlt", "cholesky"):
            raise ValueError(
                f"{method} leaves require symmetric or Hermitian structure"
            )
        if method == "cholesky" and structure == "symmetric" and data_type != "real":
            raise ValueError(
                "Cholesky leaves require real symmetric or Hermitian structure"
            )
        return Leaf(leaf.size, method, options), leaf.size

    def explicit(plan):
        if isinstance(plan, (int, Leaf)):
            return resolve_leaf(plan if isinstance(plan, Leaf) else Leaf(plan))
        if isinstance(plan, list):
            if not plan or any(
                isinstance(size, bool) or not isinstance(size, int) for size in plan
            ):
                raise ValueError(
                    "A partition list must contain positive integer block sizes"
                )
            tree = plan[-1]
            for size in reversed(plan[:-1]):
                tree = (size, tree)
            return explicit(tree)
        if isinstance(plan, tuple) and len(plan) == 2:
            left, n_left = explicit(plan[0])
            right, n_right = explicit(plan[1])
            return (left, right), n_left + n_right
        raise ValueError(
            "partition must be a preset, positive size, Leaf, size list, or pair of partitions"
        )

    def preset(n):
        if n <= block_size:
            return resolve_leaf(Leaf(n))[0]
        split = (
            block_size
            if partition == "top"
            else n - block_size
            if partition == "bot"
            else n // 2
        )
        return preset(split), preset(n - split)

    if isinstance(partition, str):
        if partition not in ("balanced", "top", "bot"):
            raise ValueError('partition preset must be "balanced", "top", or "bot"')
        return preset(N)
    tree, size = explicit(partition)
    if size != N:
        raise ValueError(f"Partition sizes must sum to N ({N}), got {size}")
    return tree


def schur_matrix_inverse(
    N: int,
    name: str | None = None,
    *,
    partition: Literal["balanced", "top", "bot"] | _SchurPartition = "balanced",
    block_size: int = 2,
    leaf_method: Literal["analytical", "ldlt", "cholesky", "qr"] = "analytical",
    leaf_options: Mapping[str, str] | None = None,
    structure: Literal["general", "symmetric", "hermitian"] = "hermitian",
    pe: Literal["addsub", "mads"] | None = None,
    mem: bool = False,
    data_type: Literal["real", "complex", "split"] = "real",
    multiplication_method: Literal["four", "three", "threealt"] = "four",
) -> SFG:
    r"""
    Generate a recursively partitioned Schur-complement matrix inverse.

    All partitions are fixed at graph generation. For a block matrix
    :math:`M=[A,B;C,D]`, invert A, form :math:`S=D-CA^{-1}B`, and invert S.
    Both selected pivot blocks must be nonsingular at every recursion level.
    There is no dynamic pivoting. Positive definite Hermitian matrices satisfy
    these conditions for every contiguous principal partition. Cholesky leaves
    additionally require positive definiteness; LDLT leaves require nonzero
    scalar pivots. Scalar inversion and normalization use Reciprocals and
    ReciprocalSquareRoots rather than divisions and square roots.

    Parameters
    ----------
    N : int
        Positive square matrix dimension.
    name : str, optional
        Graph name. Defaults to "Schur matrix-inversion".
    partition : {"balanced", "top", "bot"}, int, Leaf, list, or tuple
        "balanced" recursively halves blocks until their sizes are at most
        ``block_size``. "top" repeatedly splits off a leading block of that
        size; "bot" repeatedly leaves a trailing block of that size.
        A list gives exact leaf sizes, eliminated left to right, e.g.
        ``[2, 3, 3]`` means ``(2, (3, 3))``. Nested pairs specify the complete
        recursion tree. In each pair, the left child inverts A and the right
        child inverts S, not the original D. Integers denote terminal blocks;
        :class:`Leaf` additionally overrides their method and options.
        Explicit leaf sizes must sum to N. A single integer or Leaf selects
        an unpartitioned inverse. All blocks use contiguous indices.
    block_size : int, default: 2
        Maximum leaf size for presets only. Explicit partitions determine
        their own leaf sizes; a final remainder need not equal this size.
    leaf_method : {"analytical", "ldlt", "cholesky", "qr"}, default: "analytical"
        Default leaf algorithm. Analytical leaves have sizes 1 or 2. LDLT
        supports symmetric and Hermitian matrices. Cholesky supports real
        symmetric and Hermitian positive definite matrices. QR supports all
        structures, including general matrices.
    leaf_options : mapping, optional
        Default algorithm-specific options; see :class:`Leaf`. An explicit
        leaf method starts with its own defaults. Otherwise leaf options
        override these defaults. Arithmetic settings always come from the
        outer generator. Leaves have no separate input/output memory interface.
    structure : {"general", "symmetric", "hermitian"}, default: "hermitian"
        Mathematical assumption, independent of data_type. General matrices
        use full row-major interfaces. Symmetric and Hermitian matrices use
        packed lower-triangular row order. Symmetric matrices use transpose
        symmetry, including complex diagonals; Hermitian matrices use conjugate
        transpose symmetry and real diagonals. Values are not checked at runtime.
    pe : {"addsub", "mads", None}, optional
        AddSub, multiply-add/subtract, or separate arithmetic operations.
    mem : bool, default: False
        Use MemoryRead/MemoryWrite in the default unnamed memory. Addresses
        follow the interface order: ``i*N+j`` for general matrices and
        ``i*(i+1)//2+j`` for packed matrices. Both input and output use this layout.
    data_type : {"real", "complex", "split"}, default: "real"
        Native real, native complex, or split real arithmetic. Split interfaces
        interleave real/imaginary components, at addresses ``2*p`` and ``2*p+1``.
        Only Hermitian (and real) diagonals ignore imaginary inputs and output zero.
    multiplication_method : {"four", "three", "threealt"}, default: "four"
        Split complex product implementation, matching the other generators.

    Returns
    -------
    SFG
        Signal flow graph for the inverse with the selected external layout.

    Examples
    --------
    >>> graph = schur_matrix_inverse(8)  # Balanced analytical 2x2 leaves.
    >>> graph = schur_matrix_inverse(
    ...     8, partition=[2, 3, 3], leaf_method="qr",
    ...     leaf_options={"method": "givens", "mode": "implicitq"},
    ... )
    >>> graph = schur_matrix_inverse(
    ...     8, partition=(Leaf(3, method="qr"), Leaf(5, method="cholesky")),
    ... )
    """
    _validate_qr_arguments(N, "householder", pe)
    if structure not in ("general", "symmetric", "hermitian"):
        raise ValueError('structure must be "general", "symmetric", or "hermitian"')
    arithmetic = _MatrixArithmetic(data_type, multiplication_method, pe)
    tree = _schur_partition(
        N, partition, block_size, leaf_method, leaf_options, structure, data_type
    )
    structured = structure != "general"
    real_diagonal = data_type == "real" or structure == "hermitian"

    def transpose_value(value):
        return arithmetic.conjugate(value) if structure == "hermitian" else value

    def complete(matrix):
        if not structured:
            return matrix
        return [
            [
                arithmetic.real_part(matrix[i][j])
                if i == j and real_diagonal
                else matrix[i][j]
                if i >= j
                else transpose_value(matrix[j][i])
                for j in range(len(matrix))
            ]
            for i in range(len(matrix))
        ]

    def product(left, right, accumulator=None, *, is_add=True, lower=False):
        result = [[None] * len(right[0]) for _ in left]
        for i in range(len(left)):
            for j in range(i + 1 if lower else len(right[0])):
                value = None if accumulator is None else accumulator[i][j]
                for k in range(len(right)):
                    value = _qr_mac(
                        arithmetic,
                        value,
                        left[i][k],
                        right[k][j],
                        is_add,
                        real_valued=lower and real_diagonal and i == j,
                    )
                result[i][j] = value
        return complete(result) if lower else result

    def reciprocal(value):
        return (
            arithmetic.reciprocal(value, real_valued=True)
            if real_diagonal
            else _qr_reciprocal(arithmetic, value)
        )

    def invert_leaf(matrix, leaf):
        options = leaf.options
        if leaf.method == "analytical":
            if len(matrix) == 1:
                return [[reciprocal(matrix[0][0])]]
            a, b = matrix[0]
            c, d = matrix[1]
            det = _qr_mac(
                arithmetic,
                _qr_mac(arithmetic, None, a, d),
                b,
                c,
                False,
                real_valued=real_diagonal and structured,
            )
            inv_det = reciprocal(det)
            result = [
                [_qr_mac(arithmetic, None, d, inv_det), None],
                [
                    _qr_mac(arithmetic, None, c, inv_det, False),
                    _qr_mac(arithmetic, None, a, inv_det),
                ],
            ]
            if not structured:
                result[0][1] = _qr_mac(arithmetic, None, b, inv_det, False)
            return complete(result)
        if leaf.method == "qr":
            return complete(
                _qr_inverse(
                    matrix,
                    arithmetic,
                    options["method"],
                    options["mode"],
                    lower_only=structured,
                )
            )
        if leaf.method == "ldlt":
            return complete(
                _ldlt_inverse(
                    matrix,
                    arithmetic,
                    options["mode"],
                    hermitian=structure == "hermitian",
                )
            )
        return complete(_cholesky_inverse(matrix, arithmetic, options["mode"]))

    def size(plan):
        return plan.size if isinstance(plan, Leaf) else size(plan[0]) + size(plan[1])

    def invert(matrix, plan):
        if isinstance(plan, Leaf):
            return invert_leaf(matrix, plan)
        n_a = size(plan[0])
        A = [row[:n_a] for row in matrix[:n_a]]
        B = [row[n_a:] for row in matrix[:n_a]]
        C = [row[:n_a] for row in matrix[n_a:]]
        D = [row[n_a:] for row in matrix[n_a:]]
        V = invert(A, plan[0])
        X = product(C, V)
        S = product(X, B, D, is_add=False, lower=structured)
        H = invert(S, plan[1])
        F = product(H, X, is_add=False)
        Y = (
            [[transpose_value(X[j][i]) for j in range(len(X))] for i in range(n_a)]
            if structured
            else product(V, B)
        )
        E = product(Y, F, V, is_add=False, lower=structured)
        G = (
            [[transpose_value(F[j][i]) for j in range(len(F))] for i in range(n_a)]
            if structured
            else product(Y, H, is_add=False)
        )
        return [E[i] + G[i] for i in range(n_a)] + [F[i] + H[i] for i in range(len(H))]

    indices = [(i, j) for i in range(N) for j in range(i + 1 if structured else N)]
    matrix = [[None] * N for _ in range(N)]
    for address, (i, j) in enumerate(indices):
        matrix[i][j] = arithmetic.input(
            i,
            j,
            mem,
            address=address,
            real_valued=data_type == "real" or (real_diagonal and i == j),
        )
    result = invert(complete(matrix), tree)
    return arithmetic.graph(
        [
            arithmetic.output(
                i,
                j,
                result[i][j],
                mem,
                address=address,
                real_valued=data_type == "real" or (real_diagonal and i == j),
            )
            for address, (i, j) in enumerate(indices)
        ],
        name if name is not None else "Schur matrix-inversion",
    )


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
