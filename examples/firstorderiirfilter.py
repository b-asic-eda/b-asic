"""
======================================
First-order IIR Filter with Simulation
======================================

In this example, a direct form first-order IIR filter is designed.

First, we need to import the operations that will be used in the example:
"""
from b_asic.core_operations import ConstantMultiplication
from b_asic.special_operations import Delay, Input, Output

# %%
# Then, we continue by defining the input and delay element, which we can optionally
# name.

input = Input(name="My input")
delay = Delay(name="The only delay")

# %%
# There are a few ways to connect signals. Either explicitly, by instantiating them:

a1 = ConstantMultiplication(0.5, delay)

# %%
# By operator overloading:

first_addition = a1 + input

# %%
# Or by creating them, but connecting the input later. Each operation has a function
# :func:`~b_asic.operation.Operation.input`that is used to access a specific input
# (or output, by using :func:`~b_asic.operation.Operation.output`).

b1 = ConstantMultiplication(0.7)
b1.input(0).connect(delay)

# %%
# The latter is useful when there is not a single order to create the signal flow
# graph, e.g., for recursive algorithms. In this example, we could not connect the
# output of the delay as that was not yet available.
#
# There is also a shorthand form to connect signals using the ``<<`` operator:

delay << first_addition

# %%
# Naturally, it is also possible to write expressions when instantiating operations:

output = Output(b1 + first_addition)

# %%
# Now, we should create a signal flow graph, but first it must be imported (normally,
# this should go at the top of the file).

from b_asic.signal_flow_graph import SFG  # noqa: E402

# %%
# The signal flow graph is defined by its inputs and outputs, so these must be
# provided. As, in general, there can be multiple inputs and outputs, there should
# be provided as a list or a tuple.

firstorderiir = SFG([input], [output])

# %%
# If this is executed in an enriched terminal, such as a Jupyter Notebook, Jupyter
# QtConsole, or Spyder, just typing the variable name will return a graphical
# representation of the signal flow graph.

firstorderiir

# %%
# For now, we can print the precedence relations of the SFG
firstorderiir.print_precedence_graph()

# %%
# Executing ``firstorderiir.precedence_graph`` will show something like
#
# .. graphviz::
#
#     digraph {
#     	rankdir=LR
#     	subgraph cluster_0 {
#     		label=N0
#     		"in1.0" [label=in1 height=0.1 shape=rectangle width=0.1]
#     		"t1.0" [label=t1 height=0.1 shape=rectangle width=0.1]
#     	}
#     	subgraph cluster_1 {
#     		label=N1
#     		"cmul2.0" [label=cmul2 height=0.1 shape=rectangle width=0.1]
#     		"cmul1.0" [label=cmul1 height=0.1 shape=rectangle width=0.1]
#     	}
#     	subgraph cluster_2 {
#     		label=N2
#     		"add1.0" [label=add1 height=0.1 shape=rectangle width=0.1]
#     	}
#     	subgraph cluster_3 {
#     		label=N3
#     		"add2.0" [label=add2 height=0.1 shape=rectangle width=0.1]
#     	}
#     	"in1.0" -> add1
#     	add1 [label=add1 shape=ellipse]
#     	in1 -> "in1.0"
#     	in1 [label=in1 shape=cds]
#     	"t1.0" -> cmul2
#     	cmul2 [label=cmul2 shape=ellipse]
#     	"t1.0" -> cmul1
#     	cmul1 [label=cmul1 shape=ellipse]
#     	t1Out -> "t1.0"
#     	t1Out [label=t1 shape=square]
#     	"cmul2.0" -> add2
#     	add2 [label=add2 shape=ellipse]
#     	cmul2 -> "cmul2.0"
#     	cmul2 [label=cmul2 shape=ellipse]
#     	"cmul1.0" -> add1
#     	add1 [label=add1 shape=ellipse]
#     	cmul1 -> "cmul1.0"
#     	cmul1 [label=cmul1 shape=ellipse]
#     	"add1.0" -> t1In
#     	t1In [label=t1 shape=square]
#     	"add1.0" -> add2
#     	add2 [label=add2 shape=ellipse]
#     	add1 -> "add1.0"
#     	add1 [label=add1 shape=ellipse]
#     	"add2.0" -> out1
#     	out1 [label=out1 shape=cds]
#     	add2 -> "add2.0"
#     	add2 [label=add2 shape=ellipse]
#     }
#
# As seen, each operation has an id, in addition to the optional name.
# This can be used to access the operation. For example,
firstorderiir.find_by_id('cmul1')

# %%
# Note that this operation differs from ``a1`` defined above as the operations are
# copied and recreated once inserted into a signal flow graph.
#
# The signal flow graph can also be simulated. For this, we must import
# :class:`.Simulation`.

from b_asic.simulation import Simulation  # noqa: E402

# %%
# The :class:`.Simulation` class require that we provide inputs. These can either be
# arrays of values or we can use functions that provides the values when provided a
# time index.
#
# Let us create a simulation that simulates a short impulse response:

sim = Simulation(firstorderiir, [[1, 0, 0, 0, 0]])

# %%
# To run the simulation for all input samples, we do:

sim.run()

# %%
# The returned value is the output after the final iteration. However, we may often be
# interested in the results from the whole simulation.
# The results from the simulation, which is a dictionary of all the nodes in the signal
# flow graph, can be obtained as

sim.results

# %%
# Hence, we can obtain the results that we are interested in and, for example, plot the
# output and the value after the first addition:

import matplotlib.pyplot as plt  # noqa: E402

plt.plot(sim.results['0'], label="Output")
plt.plot(sim.results['add1'], label="After first addition")
plt.legend()
plt.show()


# %%
# To compute and plot the frequency response, it is possible to use mplsignal

from mplsignal.freq_plots import freqz_fir  # noqa: E402

freqz_fir(sim.results["0"])
plt.show()


# %%
# As seen, the output has not converged to zero, leading to that the frequency-response
# may not be correct, so we want to simulate for a longer time.
# Instead of just adding zeros to the input array, we can use a function that generates
# the impulse response instead.
# There are a number of those defined in B-ASIC for convenience, and the one for an
# impulse response is called :class:`.Impulse`.

from b_asic.signal_generator import Impulse  # noqa: E402

sim = Simulation(firstorderiir, [Impulse()])

# %%
# Now, as the functions will not have an end, we must run the simulation for a given
# number of cycles, say 30.
# This is done using :func:`~b_asic.simulation.Simulation.run_for` instead:

sim.run_for(30)

# %%
# Now, plotting the impulse results gives:

plt.plot(sim.results['0'])
plt.show()

# %%
# And the frequency-response:

freqz_fir(sim.results["0"])
plt.show()
