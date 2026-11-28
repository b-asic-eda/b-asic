# ruff: noqa: D400, D415
"""
=======================================
Precedence of QR-based matrix inversion
=======================================

Compare precedence histograms for the four QR-based inverse modes of a
4-by-4 real symmetric matrix. All graphs use Householder reflections and
separate arithmetic operations, so the inverse recovery strategy is the only
difference between the subplots. Change ``method`` to ``"givens"`` to compare
graphs based on Givens rotations instead.

Each bar counts the computational operations in one precedence step. Inputs,
outputs, constants, delays, DontCare, and Sink operations are excluded. These
steps describe dependencies, without operation latencies or resource limits.
"""

# %%
# Generate one graph for each inverse recovery strategy. The two implicit-Q
# variants retain the transformation parameters instead of constructing Q.

import matplotlib.pyplot as plt

from b_asic.sfg_generators import qr_matrix_inverse

method = "householder"
variants = [
    ("eqs", "eqs: explicit Q and back substitution"),
    ("mult", "mult: triangular inverse and matrix product"),
    ("implicitq", "implicitq: triangular inverse and transformations"),
    ("implicitq_eqs", "implicitq_eqs: transformed unit vectors and solves"),
]

# %%
# Use shared axes to compare both the depth of the graphs and the available
# parallelism. Zero-count steps retain their original positions. The ``eqs``
# and ``implicitq_eqs`` histograms can coincide: constructing the latter one
# column at a time does not itself impose a sequential hardware schedule.

fig, axes = plt.subplots(
    2, 2, figsize=(12, 7), sharex=True, sharey=True, layout="constrained"
)
for ax, (mode, title) in zip(axes.flat, variants, strict=True):
    sfg = qr_matrix_inverse(4, mode=mode, method=method, pe=None)
    sfg.precedence_histogram(ax=ax)
    ax.set_title(title, fontsize=10)

fig.suptitle(f"Precedence of 4 x 4 QR-based matrix inversion ({method.capitalize()})")
plt.show()
