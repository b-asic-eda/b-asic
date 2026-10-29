"""
====================================
Deriving a polyphase FIR interpolator
====================================

Unfold a six-tap FIR filter by three, set two input phases to zero, and
propagate those zeros to obtain a three-phase interpolator. The three outputs
are consecutive samples of the interpolated signal, produced for each sample
at the remaining low-rate input.
"""

import numpy as np

from b_asic.core_operations import Constant
from b_asic.sfg import SFG
from b_asic.sfg_generators import fir
from b_asic.simulation import Simulation

# %%
# Start with a small direct-form FIR filter. Six taps give two coefficients
# per phase when the interpolation factor is three.
coefficients = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
fir_sfg = fir(coefficients)
fir_sfg.input_operations[0].name = "x"
fir_sfg.output_operations[0].name = "y"
fir_sfg

# %%
# Unfold by three. One iteration of the unfolded graph processes three
# consecutive input samples and produces three consecutive output samples.
factor = 3
unfolded = fir_sfg.unfold(factor)
unfolded

# %%
# Zero insertion for interpolation keeps phase zero and sets phases one and
# two to constant zero. Remove those two unused input ports from the interface
# so the graph takes just one new sample per iteration.
zero_stuffed = unfolded
for input_operation in unfolded.input_operations[1:]:
    zero_stuffed = zero_stuffed.replace(input_operation.graph_id, Constant(0))
zero_stuffed = SFG(
    inputs=[zero_stuffed.input_operations[0]],
    outputs=zero_stuffed.output_operations,
    name="Zero-stuffed unfolded FIR",
)
zero_stuffed

# %%
# Propagate zeros through multipliers, additions, and zero-initialized delays.
# The result is a polyphase interpolator: output r uses coefficients h[r],
# h[r + 3], ... and all three phases share the same low-rate input history.
polyphase = zero_stuffed.constant_propagation()
polyphase.name = "Three-phase FIR interpolator"
polyphase

# %%
# Verify the result against explicit zero insertion followed by FIR filtering.
# Append one low-rate zero to flush the two-tap polyphase branches.
samples = np.array([1.0, -2.0, 3.0, 0.5, 0.0])
simulation = Simulation(polyphase, [samples])
simulation.run()
phase_outputs = np.column_stack(
    [simulation.results[output.graph_id] for output in polyphase.output_operations]
)
interpolated = phase_outputs.ravel()

upsampled = np.zeros(factor * len(samples))
upsampled[::factor] = samples
reference = np.convolve(upsampled, coefficients)[: len(upsampled)]
np.testing.assert_allclose(interpolated, reference, atol=1e-14)
print("Polyphase outputs match zero insertion followed by FIR filtering.")
