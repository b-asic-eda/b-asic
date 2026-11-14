"""
===================================================
Convert a 4 x 4 Cholesky inverse to real arithmetic
===================================================

Split each complex signal into real and imaginary signals, choosing either
three or four real multipliers for the complex products in MADS operations.
The Cholesky generator expects a symmetric positive definite matrix, supplied
in packed lower-triangular row order. This example uses real matrix entries
represented as complex signals; all imaginary input channels are zero.
"""

import numpy as np

from b_asic.core_operations import MADS, Multiplication, ReciprocalSquareRoot
from b_asic.sfg_generators import cholesky_matrix_inverse

# %%
# Generate the complex arithmetic graph. Its diagonal reciprocal square roots
# have real_valued=True: conversion terminates their imaginary inputs at Sinks
# and produces zero constants for their imaginary outputs.

complex_sfg = cholesky_matrix_inverse(N=4, mode="mult", pe="mads")
assert all(op.real_valued for op in complex_sfg.find_by_type(ReciprocalSquareRoot))

# %%
# Options are forwarded as keyword arguments to each operation's private
# conversion hook. Both graphs have 20 real inputs and 20 real outputs:
# real0, imag0, real1, imag1, ... for the ten lower-triangular entries.

real_four = complex_sfg.complex_to_real(multiplication_method="four")
real_three = complex_sfg.complex_to_real(multiplication_method="three")
print("Four-product multipliers:", len(real_four.find_by_type(Multiplication)))
print("Three-product multipliers:", len(real_three.find_by_type(Multiplication)))

# %%
# Check both decompositions and the original graph against NumPy.

rng = np.random.default_rng(42)
factor = rng.normal(size=(4, 4))
matrix = factor @ factor.T + np.eye(4)
lower = np.tril_indices(4)
packed = matrix[lower].astype(complex)
split_inputs = np.column_stack((packed.real, packed.imag)).ravel()
expected = np.linalg.inv(matrix)[lower]
np.testing.assert_allclose(complex_sfg.evaluate(*packed), expected, atol=1e-12)

for graph in (real_four, real_three):
    split_outputs = np.asarray(graph.evaluate(*split_inputs))
    inverse = split_outputs[0::2] + 1j * split_outputs[1::2]
    np.testing.assert_allclose(inverse, expected, atol=1e-12)

# %%
# Keep the original complex interface with split_io=False. Boundary operations
# extract and join real/imaginary signals while internal arithmetic stays real.
# With memory interfaces, addresses and memory names are preserved as well.

memory_sfg = cholesky_matrix_inverse(N=4, mode="mult", pe="mads", mem=True)
real_memory_sfg = memory_sfg.complex_to_real(
    multiplication_method="three", split_io=False
)
np.testing.assert_allclose(real_memory_sfg.evaluate(*packed), expected, atol=1e-12)

# %%
# Convert individual operations with different settings. Unselected operations
# keep their graph IDs and complex interfaces. Neighboring converted regions
# share real signals after redundant split/join pairs are removed.
# A type or iterator of types/IDs can also select several operations at once.

mads_ids = [op.graph_id for op in memory_sfg.find_by_type(MADS)]
mixed_sfg = memory_sfg.complex_to_real(
    operations=mads_ids[0], multiplication_method="three"
)
mixed_sfg = mixed_sfg.complex_to_real(
    operations=mads_ids[1], multiplication_method="four"
)
np.testing.assert_allclose(mixed_sfg.evaluate(*packed), expected, atol=1e-12)

# %%
# Display the operation counts. Constant propagation and sink propagation can
# be applied separately when the imaginary input channels are known to be zero.

real_three.operation_counter()
