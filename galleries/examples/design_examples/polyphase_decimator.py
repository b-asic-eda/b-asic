"""
==================================
Deriving a polyphase FIR decimator
==================================

Unfold a six-tap FIR filter by three, discard two output phases using Sink
nodes, and propagate the unused results backwards. The resulting polyphase
decimator consumes three consecutive input samples per iteration and produces
one output sample at a third of the input rate.
"""

import numpy as np

from b_asic.sfg_generators import fir
from b_asic.simulation import Simulation
from b_asic.utility_operations import Sink

# %%
# Start with a small FIR filter. With three phases, these six coefficients
# give two taps per phase.
coefficients = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
fir_sfg = fir(coefficients)
fir_sfg.input_operations[0].name = "x"
fir_sfg.output_operations[0].name = "y"
fir_sfg

# %%
# Unfold by three. The input/output ports are in chronological order, so each
# iteration now processes three consecutive samples and computes three outputs.
factor = 3
unfolded = fir_sfg.unfold(factor)
unfolded

# %%
# Retain output phase zero: y[0], y[3], y[6], ... . Replacing the other two
# Output nodes by Sinks removes their ports from the graph interface and marks
# the corresponding values as unused, while keeping the branches visible.
sink_connected = unfolded
for output in unfolded.output_operations[1:]:
    sink_connected = sink_connected.replace(output.graph_id, Sink())
sink_connected

# %%
# Propagate Sinks backwards. Computations serving only discarded phases are
# removed; shared input history needed by the retained phase is preserved.
# All three input phases contribute to the remaining decimated output.
polyphase = sink_connected.sink_propagation()
polyphase.name = "Three-phase FIR decimator"
polyphase

# %%
# Verify against FIR filtering followed by retaining every third sample.
# Input port r receives x[3k + r] at iteration k. Each graph delay now stores
# history across three input samples, i.e. one low-rate iteration.
samples = np.array([1.0, -2.0, 3.0, 0.5, 2.0, -1.0, 0.0, 0.0, 0.0])
inputs = [samples[phase::factor] for phase in range(factor)]
simulation = Simulation(polyphase, inputs)
simulation.run()
decimated = simulation.results[polyphase.output_operations[0].graph_id]
reference = np.convolve(samples, coefficients)[: len(samples) : factor]
np.testing.assert_allclose(decimated, reference, atol=1e-14)
print("Polyphase outputs match FIR filtering followed by decimation by three.")
