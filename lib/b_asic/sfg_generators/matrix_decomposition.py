r"""
Signal flow graph generators for Cholesky, LDLT, and QR decompositions.

Cholesky and LDLT accept packed lower-triangular inputs for symmetric (real)
or Hermitian (complex/split) matrices, like the matrix inverse generators.
QR accepts every entry of a general real or complex square matrix in row-major order.
All generators use reciprocals and reciprocal square roots for normalization.

With memory interfaces, each output factor uses its own named memory, starting
at address zero. Split components occupy consecutive real/imaginary addresses.
"""

from typing import Literal

from b_asic.sfg import SFG
from b_asic.sfg_generators._matrix_arithmetic import _MatrixArithmetic


def cholesky_decomposition(
    N: int,
    name: str | None = None,
    *,
    pe: Literal["addsub", "mads"] | None = None,
    mem: bool = False,
    data_type: Literal["real", "complex", "split"] = "real",
    multiplication_method: Literal["four", "three", "threealt"] = "four",
) -> SFG:
    r"""
    Generate a Cholesky factorization :math:`A=LL^H`.

    Parameters
    ----------
    N : int
        Positive matrix dimension. Input must be positive definite.
    name : str, optional
        Graph name. Defaults to "Cholesky decomposition".
    pe : {"addsub", "mads", None}, optional
        Select AddSub, multiply-add/subtract, or separate arithmetic operations.
    mem : bool, default: False
        Use MemoryRead/MemoryWrite rather than Input/Output interfaces. Input
        uses the default unnamed memory; output uses memory "L". Both use
        packed lower-triangular row order, with address ``i*(i+1)//2+j``.
    data_type : {"real", "complex", "split"}, default: "real"
        Symmetric real, Hermitian complex, or Hermitian split real arithmetic.
        Split interfaces interleave real/imaginary components for every entry,
        including diagonals. Diagonal imaginary inputs are ignored and outputs
        are zero. Split memory addresses are twice the packed address for the
        real part and the next address for the imaginary part.
    multiplication_method : {"four", "three", "threealt"}, default: "four"
        Split complex product implementation, matching the inverse generators.

    Returns
    -------
    SFG
        Outputs the lower triangle of L in packed row order, including its
        positive real diagonal. Output names are ``L[i,j]`` (with ``_real`` and
        ``_imag`` suffixes for split arithmetic).
    """
    _validate_decomposition_arguments(N, pe)
    arithmetic = _MatrixArithmetic(data_type, multiplication_method, pe)
    matrix = [[arithmetic.input(i, j, mem) for j in range(i + 1)] for i in range(N)]
    L, _ = _cholesky_decomposition(matrix, arithmetic, diagonal=True)
    return arithmetic.graph(
        [
            arithmetic.output(i, j, L[i][j], mem, name=f"L[{i},{j}]", memory_name="L")
            for i in range(N)
            for j in range(i + 1)
        ],
        "Cholesky decomposition" if name is None else name,
    )


def ldlt_decomposition(
    N: int,
    name: str | None = None,
    *,
    pe: Literal["addsub", "mads"] | None = None,
    mem: bool = False,
    data_type: Literal["real", "complex", "split"] = "real",
    multiplication_method: Literal["four", "three", "threealt"] = "four",
) -> SFG:
    r"""
    Generate an unpivoted LDLT factorization :math:`A=LDL^H`.

    Parameters
    ----------
    N : int
        Positive matrix dimension. All leading principal minors must be
        nonzero; no pivoting is performed. Positive definite inputs satisfy
        this condition, but indefinite matrices can also be factorized.
    name : str, optional
        Graph name. Defaults to "LDLT decomposition".
    pe : {"addsub", "mads", None}, optional
        Select AddSub, multiply-add/subtract, or separate arithmetic operations.
    mem : bool, default: False
        Use MemoryRead/MemoryWrite interfaces. Input uses the default unnamed
        memory in packed lower-triangular row order, address ``i*(i+1)//2+j``.
        Factors use separate memories "L" (same packed layout) and "D"
        (diagonal entries at addresses ``0, ..., N-1``).
    data_type : {"real", "complex", "split"}, default: "real"
        Symmetric real, Hermitian complex, or Hermitian split real arithmetic.
        Split interfaces interleave real/imaginary components for every entry,
        including diagonals of L and D. Diagonal imaginary inputs are ignored
        and outputs are zero. Real/imaginary memory addresses are twice the
        entry address and twice the entry address plus one, respectively.
    multiplication_method : {"four", "three", "threealt"}, default: "four"
        Split complex product implementation, matching the inverse generators.

    Returns
    -------
    SFG
        Outputs all of L's lower triangle in packed row order (including unit
        diagonal), followed by D's real diagonal. Names are ``L[i,j]`` and
        ``D[i]``, with ``_real``/``_imag`` suffixes for split arithmetic.
    """
    _validate_decomposition_arguments(N, pe)
    arithmetic = _MatrixArithmetic(data_type, multiplication_method, pe)
    matrix = [[arithmetic.input(i, j, mem) for j in range(i + 1)] for i in range(N)]
    L, D, _ = _ldlt_decomposition(matrix, arithmetic)
    outputs = [
        arithmetic.output(
            i,
            j,
            arithmetic.constant(1) if i == j else L[i][j],
            mem,
            name=f"L[{i},{j}]",
            memory_name="L",
        )
        for i in range(N)
        for j in range(i + 1)
    ]
    outputs.extend(
        arithmetic.output(i, i, D[i], mem, name=f"D[{i}]", address=i, memory_name="D")
        for i in range(N)
    )
    return arithmetic.graph(outputs, "LDLT decomposition" if name is None else name)


def qr_decomposition(
    N: int,
    name: str | None = None,
    *,
    method: Literal["householder", "givens"] = "householder",
    pe: Literal["addsub", "mads"] | None = None,
    mem: bool = False,
    data_type: Literal["real", "complex", "split"] = "real",
    multiplication_method: Literal["four", "three", "threealt"] = "four",
) -> SFG:
    r"""
    Generate a QR factorization :math:`A=QR` of a general square matrix.

    Parameters
    ----------
    N : int
        Positive matrix dimension. Rank-deficient inputs are supported.
    name : str, optional
        Graph name. Defaults to "Householder QR decomposition" or
        "Givens QR decomposition".
    method : {"householder", "givens"}, default: "householder"
        Use Householder reflections or Givens rotations, as in QR inversion.
    pe : {"addsub", "mads", None}, optional
        Select AddSub, multiply-add/subtract, or separate arithmetic operations.
    mem : bool, default: False
        Use MemoryRead/MemoryWrite interfaces. Matrices use named memories
        "A", "Q", and "R", each starting at zero. A and Q occupy N*N entries
        in row-major order, address ``i*N+j``. R occupies N*(N+1)//2 entries
        in packed upper-triangular row order, address
        ``i*(2*N-i+1)//2+j-i`` for ``i <= j``.
    data_type : {"real", "complex", "split"}, default: "real"
        Real arithmetic, native complex arithmetic, or separate real/imaginary
        arithmetic. Complex Q is unitary. Split interfaces interleave real and
        imaginary parts of every entry, including diagonals of A, Q, and R.
        Split memory addresses are twice the entry address and the next address.
    multiplication_method : {"four", "three", "threealt"}, default: "four"
        Split complex product implementation, matching the inverse generators.

    Returns
    -------
    SFG
        N*N row-major inputs ``A[i,j]``; outputs are all N*N entries of Q in
        row-major order followed by R's packed upper triangle. Outputs are
        named ``Q[i,j]`` and ``R[i,j]``, with ``_real``/``_imag`` suffixes for
        split arithmetic. Complex diagonal components are preserved.
    """
    _validate_qr_arguments(N, method, pe)
    arithmetic = _MatrixArithmetic(data_type, multiplication_method, pe)
    matrix = [
        [
            arithmetic.input(
                i, j, mem, address=i * N + j, memory_name="A", real_valued=False
            )
            for j in range(N)
        ]
        for i in range(N)
    ]
    R, QH = _qr_decomposition(matrix, arithmetic, method)
    entries = [
        ("Q", i, j, i * N + j, arithmetic.conjugate(QH[j][i]))
        for i in range(N)
        for j in range(N)
    ] + [
        ("R", i, j, i * (2 * N - i + 1) // 2 + j - i, R[i][j])
        for i in range(N)
        for j in range(i, N)
    ]
    outputs = [
        arithmetic.output(
            i,
            j,
            value,
            mem,
            address=address,
            memory_name=factor,
            name=f"{factor}[{i},{j}]",
            real_valued=False,
        )
        for factor, i, j, address, value in entries
    ]
    return arithmetic.graph(
        outputs,
        f"{method.capitalize()} QR decomposition" if name is None else name,
    )


def _ldlt_decomposition(A, arithmetic):
    """Build factor sources shared by decomposition and inversion graphs."""
    pe = arithmetic.pe
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
                    in1=arithmetic.multiplication(M[j][k], l_conj, real_valued=True),
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


def _cholesky_decomposition(A, arithmetic, *, diagonal=False):
    """Build factor sources shared by decomposition and inversion graphs."""
    pe = arithmetic.pe
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
                    in1=arithmetic.multiplication(L[j][k], l_conj, real_valued=True),
                )
            else:
                acc = acc - arithmetic.multiplication(L[j][k], l_conj, real_valued=True)

        L_inv[j][j] = arithmetic.reciprocal_square_root(acc, real_valued=True)
        if diagonal:
            L[j][j] = _qr_mac(arithmetic, None, arithmetic.real(acc), L_inv[j][j])

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


def _validate_decomposition_arguments(N, pe):
    if isinstance(N, bool) or not isinstance(N, int) or N < 1:
        raise ValueError("N must be a positive integer")
    if pe not in (None, "addsub", "mads"):
        raise ValueError('pe must be "addsub", "mads", or None')


def _validate_qr_arguments(N, method, pe):
    _validate_decomposition_arguments(N, pe)
    if method not in ("householder", "givens"):
        raise ValueError('method must be "householder" or "givens"')


def _qr_mac(arithmetic, accumulator, left, right, is_add=True, *, real_valued=False):
    """Emit a product or accumulated product using the selected PE."""
    if arithmetic.pe == "mads":
        return arithmetic.mads(
            is_add,
            accumulator,
            left,
            right,
            accumulator is not None,
            real_valued=real_valued,
        )
    product = arithmetic.multiplication(left, right, real_valued=real_valued)
    if accumulator is None:
        return product if is_add else -product
    return _qr_addsub(arithmetic, accumulator, product, is_add)


def _qr_addsub(arithmetic, left, right, is_add=True):
    if arithmetic.pe == "addsub":
        return arithmetic.addsub(is_add, left, right)
    return left + right if is_add else left - right


def _qr_safe_norm(arithmetic, norm):
    """Replace a zero squared norm with one, returning its zero indicator."""
    safe_norm = arithmetic.replace_zero(norm, 1)
    is_zero = _qr_addsub(arithmetic, safe_norm, norm, False)
    return safe_norm, is_zero


def _qr_squared_norm(arithmetic, values):
    """Accumulate squared magnitudes as an explicitly real expression."""
    norm = None
    for value in values:
        norm = _qr_mac(
            arithmetic, norm, value, arithmetic.conjugate(value), real_valued=True
        )
    return arithmetic.real_part(norm)


def _qr_reciprocal(arithmetic, value):
    """Invert a QR pivot, whose phase need not be real."""
    if arithmetic.data_type == "real":
        return arithmetic.reciprocal(value, real_valued=True)
    norm = _qr_squared_norm(arithmetic, [value])
    return _qr_mac(
        arithmetic,
        None,
        arithmetic.conjugate(value),
        arithmetic.reciprocal(norm, real_valued=True),
    )


def _qr_decomposition(matrix, arithmetic, method):
    """Return R and Q conjugate transpose, applying every unitary update to both."""
    R, QH, _ = _qr_factorization(matrix, arithmetic, method)
    return R, QH


def _qr_factorization(matrix, arithmetic, method, *, form_q=True):
    """Return R, optional Q conjugate transpose, and implicit Q parameters."""
    N = len(matrix)
    R = [row.copy() for row in matrix]
    QH = (
        [[arithmetic.constant(int(i == j)) for j in range(N)] for i in range(N)]
        if form_q
        else None
    )
    transformations = []

    if method == "householder":
        for k in range(N - 1):
            norm = _qr_squared_norm(arithmetic, [R[i][k] for i in range(k, N)])
            safe_norm, _ = _qr_safe_norm(arithmetic, norm)
            norm_inverse = arithmetic.reciprocal_square_root(
                safe_norm, real_valued=True
            )
            magnitude = _qr_mac(arithmetic, None, norm, norm_inverse)
            if arithmetic.data_type == "real":
                alpha = -arithmetic.copy_sign(magnitude, R[k][k])
            else:
                # phase(a) = a / |a|, with phase(0) = 1. Choosing the
                # opposite phase avoids cancellation in the leading entry.
                leading_norm = _qr_squared_norm(arithmetic, [R[k][k]])
                safe_leading_norm, is_zero = _qr_safe_norm(arithmetic, leading_norm)
                leading_inverse = arithmetic.reciprocal_square_root(
                    safe_leading_norm, real_valued=True
                )
                phase = _qr_mac(arithmetic, is_zero, R[k][k], leading_inverse)
                alpha = -_qr_mac(arithmetic, None, phase, magnitude)
            vector = [_qr_addsub(arithmetic, R[k][k], alpha, False)] + [
                R[i][k] for i in range(k + 1, N)
            ]
            vector_norm = _qr_squared_norm(arithmetic, vector)
            safe_vector_norm, _ = _qr_safe_norm(arithmetic, vector_norm)
            beta = _qr_mac(
                arithmetic,
                None,
                arithmetic.constant(2),
                arithmetic.reciprocal(safe_vector_norm, real_valued=True),
            )
            if not form_q:
                transformations.append((k, vector, beta))
            targets = [(R, range(k + 1, N))]
            if form_q:
                targets.append((QH, range(N)))
            for target, columns in targets:
                for j in columns:
                    projection = None
                    for offset, value in enumerate(vector):
                        projection = _qr_mac(
                            arithmetic,
                            projection,
                            arithmetic.conjugate(value),
                            target[k + offset][j],
                        )
                    scale = _qr_mac(arithmetic, None, beta, projection)
                    for offset, value in enumerate(vector):
                        target[k + offset][j] = _qr_mac(
                            arithmetic, target[k + offset][j], value, scale, False
                        )
            R[k][k] = alpha
            for i in range(k + 1, N):
                R[i][k] = arithmetic.constant(0)
    else:
        for k in range(N - 1):
            for i in range(N - 1, k, -1):
                a, b = R[k][k], R[i][k]
                norm = _qr_squared_norm(arithmetic, [a, b])
                safe_norm, is_zero = _qr_safe_norm(arithmetic, norm)
                norm_inverse = arithmetic.reciprocal_square_root(
                    safe_norm, real_valued=True
                )
                # A zero pair selects the identity rotation.
                cosine = _qr_mac(
                    arithmetic, is_zero, arithmetic.conjugate(a), norm_inverse
                )
                sine = _qr_mac(arithmetic, None, arithmetic.conjugate(b), norm_inverse)
                if not form_q:
                    transformations.append((k, i, cosine, sine))
                targets = [(R, range(k + 1, N))]
                if form_q:
                    targets.append((QH, range(N)))
                for target, columns in targets:
                    for j in columns:
                        top, bottom = target[k][j], target[i][j]
                        target[k][j] = _qr_mac(
                            arithmetic,
                            _qr_mac(arithmetic, None, cosine, top),
                            sine,
                            bottom,
                        )
                        target[i][j] = _qr_mac(
                            arithmetic,
                            _qr_mac(
                                arithmetic, None, arithmetic.conjugate(cosine), bottom
                            ),
                            arithmetic.conjugate(sine),
                            top,
                            False,
                        )
                R[k][k] = _qr_mac(arithmetic, None, norm, norm_inverse)
                R[i][k] = arithmetic.constant(0)
    return R, QH, transformations
