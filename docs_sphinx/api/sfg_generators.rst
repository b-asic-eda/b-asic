*************************
``b_asic.sfg_generators``
*************************

Schur-complement matrix inversion
=================================

``schur_matrix_inverse`` supports balanced recursion by default, using analytical
inverses for terminal blocks of size one or two. The partition is fixed when the
SFG is generated. The selected pivot blocks and their Schur complements must be
nonsingular; the generator does not perform dynamic pivoting.

For simple schemes, select a preset and maximum leaf size::

    from b_asic.sfg_generators import Leaf, schur_matrix_inverse

    balanced = schur_matrix_inverse(8)
    leading_blocks = schur_matrix_inverse(
        10, partition="top", block_size=3, leaf_method="qr",
        leaf_options={"method": "givens", "mode": "implicitq"},
    )

``"balanced"`` recursively halves the current block, ``"top"`` splits off a
leading block, and ``"bot"`` leaves a trailing block. Every preset stops when the
current dimension is at most ``block_size``; unequal remainders are supported.

A list specifies exact block sizes eliminated from left to right. Nested pairs
specify the recursion tree, with integers representing terminal blocks::

    unequal = schur_matrix_inverse(
        8, partition=[2, 3, 3], leaf_method="qr",
    )
    custom_tree = schur_matrix_inverse(
        8, partition=((2, 2), 4), leaf_method="qr",
    )

In each pair the left child inverts the leading block A, and the right child
inverts its Schur complement S. In particular, the right child does not invert
the original trailing block D. Explicit leaf dimensions must sum to N and are
independent of ``block_size``.

``leaf_method`` and ``leaf_options`` apply to all integer leaves. Use ``Leaf``
to override either at a particular terminal block::

    mixed = schur_matrix_inverse(
        8,
        partition=(
            Leaf(3, method="qr", options={"mode": "mult"}),
            Leaf(5, method="cholesky"),
        ),
    )

An inherited method also inherits global leaf options, with local options taking
precedence. An explicitly selected method starts with that method's defaults.
QR leaves accept ``method`` and ``mode``; LDLT and Cholesky accept ``mode``.
Analytical leaves accept no options and must have size one or two. Cholesky
leaves require positive definiteness and LDLT leaves require nonzero scalar
pivots. Arithmetic settings (``pe``, ``data_type``, and
``multiplication_method``) propagate to every leaf. Only the outer graph has
input/output interfaces, controlled by ``mem``.

``structure="hermitian"`` is the default. It uses packed lower-triangular
interfaces and real diagonals. ``structure="symmetric"`` uses the same packed
layout with transpose symmetry, allowing complex diagonals.
``structure="general"`` uses full row-major interfaces and permits analytical
or QR leaves. LDLT supports symmetric and Hermitian leaves; Cholesky supports
real symmetric or Hermitian leaves. Structure is a caller-provided assumption.

Native complex and split real arithmetic are supported. Split components are
interleaved at each matrix-entry address. Scalar inversion and normalization
use reciprocal and reciprocal-square-root operations.

API reference
=============

.. automodule:: b_asic.sfg_generators
   :members:
