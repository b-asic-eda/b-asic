"""
=============================
Third-order Bireciprocal LWDF
=============================

Small bireciprocal lattice wave digital filter.
"""
from b_asic.core_operations import Addition, SymmetricTwoportAdaptor
from b_asic.schedule import Schedule
from b_asic.signal_flow_graph import SFG
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay, Input, Output

in0 = Input("x")
D0 = Delay(in0)
D1 = Delay()
D2 = Delay(D1)
s = SymmetricTwoportAdaptor(-0.375, in0, D2)
D1 << s.output(1)
a = s.output(0) + D0
out0 = Output(a, "y")

sfg = SFG(inputs=[in0], outputs=[out0], name="Third-order BLWDF")

# Set latencies and exection times
sfg.set_latency_of_type(SymmetricTwoportAdaptor.type_name(), 4)
sfg.set_latency_of_type(Addition.type_name(), 1)
sfg.set_execution_time_of_type(SymmetricTwoportAdaptor.type_name(), 1)
sfg.set_execution_time_of_type(Addition.type_name(), 1)

sim = Simulation(sfg, [lambda n: 0 if n else 1])
sim.run_for(1000)

import scipy.signal

w, h = scipy.signal.freqz(sim.results['0'])

import matplotlib.pyplot as plt
import numpy as np

plt.plot(w, 20 * np.log10(np.abs(h) / 2))

schedule = Schedule(sfg, cyclic=True)
