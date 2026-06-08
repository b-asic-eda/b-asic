"""
=====================
Algorithmic Modelling
=====================

In B-ASIC, algorithms are represented as signal flow graphs (SFGs).
Basically, a directed graph where nodes are operations that are connected by edges representing signals.

As a first example, let us build a simple 6-tap FIR filter, as it is a common and simple algorithm.

The FIR filter is defined by the following equation:
:math:`y[n] = \sum_{k=0}^{N-1} h[k] x[n-k]`

where :math:`x[n]` is the input signal, :math:`y[n]` is the output signal, :math:`h[k]` are the filter coefficients, and :math:`N` is the number of taps (in this case, 6).

The filter coefficients can easily be derived using other libraries, such as :mod:`scipy.signal`.
"""

# %%
# Algorithm
# ---------
# Let us use :func:`scipy.signal.remez` to design a low-pass filter with a cutoff frequency of 0.2 times the Nyquist frequency, and plot the magnitude response.
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import freqz, remez

h = remez(6, [0, 0.50 / 2, 0.6 / 2, 1 / 2], [1, 0])

fig, ax = plt.subplots()
w, h = freqz(h, [1])
ax.plot(w / np.pi, 20 * np.log10(np.abs(h)))
ax.set_xlabel("Normalized frequency")
ax.set_ylabel("Magnitude, dB")

# %%
# Constructing the SFG
# --------------------
# Let us now construct the SFG of this filter.
# We start by defining the input and the delay elements to form the tapped delay line.
# Then the ``<<=`` operator is then used to connect the these components together.
# Finally, the output is defined as according to the FIR equation.

from b_asic import SFG, Delay, Input, Output

x = Input(name="x")
d0 = Delay(name="d0")
d1 = Delay(name="d1")
d2 = Delay(name="d2")
d3 = Delay(name="d3")
d4 = Delay(name="d4")
d5 = Delay(name="d5")

d0 <<= x
d1 <<= d0
d2 <<= d1
d3 <<= d2
d4 <<= d3
d5 <<= d4

y = Output(
    h[0] * x + h[1] * d0 + h[2] * d1 + h[3] * d2 + h[4] * d3 + h[5] * d4 + h[6] * d5,
    name="y",
)

# %%
# The SFG is then constructed by passing its inputs and outputs.

fir = SFG([x], [y], name="6-tap FIR")

# %%
# As possible for most objects in B-ASIC, the SFG can be rendered in an enriched shell,
# by simply writing its name.
# Otherwise, :meth:`~b_asic.sfg.SFG.show` can be used.
fir
