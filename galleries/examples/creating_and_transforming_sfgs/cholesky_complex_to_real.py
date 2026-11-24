"""
===================================================
Convert a 4 x 4 Cholesky inverse to real arithmetic
===================================================

Split each complex signal into real and imaginary signals, choosing the
``four``, ``three``, or ``threealt`` method for complex products in MADS operations.
With ``cmplx=True``, the Cholesky generator expects a Hermitian positive definite
matrix, supplied in packed lower-triangular row order. This example uses complex
matrix entries with nonzero imaginary parts.
"""

import numpy as np

from b_asic.core_operations import MADS, Multiplication, Negation, ReciprocalSquareRoot
from b_asic.sfg_generators import cholesky_matrix_inverse

# %%
# Generate the complex arithmetic graph. Its diagonal reciprocal square roots
# have real_valued=True: conversion terminates their imaginary inputs at Sinks
# and produces zero constants for their imaginary outputs.

complex_sfg = cholesky_matrix_inverse(N=4, mode="mult", pe="mads", cmplx=True)
assert all(op.real_valued for op in complex_sfg.find_by_type(ReciprocalSquareRoot))

# %%
# Options are forwarded as keyword arguments to each operation's private
# conversion hook. All three graphs have 20 real inputs and 20 real outputs:
# real0, imag0, real1, imag1, ... for the ten lower-triangular entries.

real_four = complex_sfg.complex_to_real(multiplication_method="four")
real_three = complex_sfg.complex_to_real(multiplication_method="three")
real_threealt = complex_sfg.complex_to_real(multiplication_method="threealt")
# The threealt method shares d*(a+b), which vanishes when the second
# operand's imaginary part is zero. Constant propagation can then remove
# the surrounding additions and subtractions, leaving two real products.
print("Four-product multipliers:", len(real_four.find_by_type(Multiplication)))
print("Three-product multipliers:", len(real_three.find_by_type(Multiplication)))
print("Threealt-product multipliers:", len(real_threealt.find_by_type(Multiplication)))

# %%
# Check all three decompositions and the original graph against NumPy.

rng = np.random.default_rng(42)
factor = rng.normal(size=(4, 4)) + 1j * rng.normal(size=(4, 4))
matrix = factor @ factor.conj().T + np.eye(4)
lower = np.tril_indices(4)
packed = matrix[lower]
split_inputs = np.column_stack((packed.real, packed.imag)).ravel()
expected = np.linalg.inv(matrix)[lower]
np.testing.assert_allclose(complex_sfg.evaluate(*packed), expected, atol=1e-12)

for graph in (real_four, real_three, real_threealt):
    split_outputs = np.asarray(graph.evaluate(*split_inputs))
    inverse = split_outputs[0::2] + 1j * split_outputs[1::2]
    np.testing.assert_allclose(inverse, expected, atol=1e-12)

# %%
# Keep the original complex interface with split_io=False. Boundary operations
# extract and join real/imaginary signals while internal arithmetic stays real.
# With memory interfaces, addresses and memory names are preserved as well.

memory_sfg = cholesky_matrix_inverse(N=4, mode="mult", pe="mads", mem=True, cmplx=True)
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
mixed_sfg = mixed_sfg.complex_to_real(
    operations=mads_ids[2], multiplication_method="threealt"
)
np.testing.assert_allclose(mixed_sfg.evaluate(*packed), expected, atol=1e-12)

# %%
# Display the operation counts. Constant propagation and sink propagation can
# simplify the real arithmetic introduced by conversion.

print(real_three.operation_counter())
print(real_threealt.operation_counter())
# %%
# Apply constant and sink propagation to remove computations with known zeros,
# including the imaginary outputs of the real-valued reciprocal square roots.
# In addition, propagate negations where possible (first splitting them so that
# they can be propagated per operation) and merge redundant operations
# (which will also merge the earlier split negations that didn't propagate).
simplified_real_three = (
    real_three.constant_propagation()
    .sink_propagation()
    .split_fanout(Negation, repeat=True)
    .negation_propagation()
    .merge_redundant_operations()
)
simplified_real_threealt = (
    real_threealt.constant_propagation()
    .sink_propagation()
    .split_fanout(Negation, repeat=True)
    .negation_propagation()
    .merge_redundant_operations()
)

print("Simplified three operations:", simplified_real_three.operation_counter())
print("Simplified threealt operations:", simplified_real_threealt.operation_counter())
for graph in (simplified_real_three, simplified_real_threealt):
    split_outputs = np.asarray(graph.evaluate(*split_inputs))
    inverse = split_outputs[0::2] + 1j * split_outputs[1::2]
    np.testing.assert_allclose(inverse, expected, atol=1e-12)

# %%
