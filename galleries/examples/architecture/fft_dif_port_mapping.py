"""
=========================================
8-point DIF FFT with a shared output port
=========================================

Map twelve radix-2 DIF butterflies onto one processing element. Both inputs
arrive at offset zero, while output 0 (the sum) is ready after one cycle and
output 1 (the twiddle-multiplied difference) after three cycles. The two logical
outputs therefore share one physical output port. The inputs retain their
default mapping to two distinct physical ports.

This example constructs the FFT, a cyclic schedule, and its architecture. It
illustrates the interface and interconnect; the butterfly arithmetic hardware
implementation must supply the declared output timing.
"""

import matplotlib.pyplot as plt
import numpy as np

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.fft_operations import R2DIFButterfly
from b_asic.schedule import Schedule
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output

# %%
# Construct the three DIF stages, including the twiddle factor in every
# butterfly. Natural-order inputs become bit-reversed outputs, so reorder the
# final ports to expose the frequency bins in natural order.
points = 8
inputs = [Input(name=f"x[{i}]") for i in range(points)]
ports = list(inputs)
start_by_name = {f"x[{i}]": 4 * (i % 4) for i in range(points)}

for stage, span in enumerate((8, 4, 2)):
    next_ports = ports.copy()
    butterfly_index = 0
    for group in range(0, points, span):
        for index in range(span // 2):
            first = group + index
            second = first + span // 2
            name = f"stage{stage}_bf{butterfly_index}"
            butterfly = R2DIFButterfly(
                np.exp(-2j * np.pi * index / span),
                ports[first],
                ports[second],
                name=name,
            )
            next_ports[first], next_ports[second] = butterfly.outputs
            start_by_name[name] = 16 * stage + 4 * butterfly_index
            butterfly_index += 1
    ports = next_ports

bit_reversed = [0, 4, 2, 6, 1, 5, 3, 7]
outputs = [Output(ports[index], name=f"X[{i}]") for i, index in enumerate(bit_reversed)]
sfg = SFG(inputs, outputs, name="8-point DIF FFT")

# %%
# Configure existing operation instances by type, without defining a subclass.
# Only map the outputs: the simultaneous inputs keep distinct physical ports.
sfg.set_latency_offsets_of_type(
    R2DIFButterfly, {"in0": 0, "in1": 0, "out0": 1, "out1": 3}
)
sfg.set_execution_time_of_type(R2DIFButterfly, 1)
sfg.set_port_mapping_of_type(R2DIFButterfly, {"out0": 0, "out1": 0})
sfg

# %%
# Check the complete FFT, including twiddle factors and output ordering, against
# NumPy for a block of complex samples.
samples = np.arange(points) + 1j * np.arange(points)[::-1]
fft_values = np.asarray(sfg.evaluate_outputs(samples))
np.testing.assert_allclose(fft_values, np.fft.fft(samples), atol=1e-12)
print("FFT bins:", np.round(fft_values, 3))

# %%
# Start butterflies at cycles 0, 4, ..., 44, processing one stage at a time.
# Their shared output is used at cycles 1, 3, 5, 7, ..., 45, 47. A new block
# starts every 48 cycles, so the output port is also collision-free at wraparound.
# Starting consecutive butterflies two cycles apart would cause a collision:
# the first one's output 1 and the next one's output 0 would both appear at t=3.
# The four-cycle spacing is a simple feasible choice, rather than an optimized
# FFT schedule. Execution time remains one cycle, independently of this spacing.
for output in sfg.output_operations:
    source = output.input(0).connected_source
    start_by_name[output.name] = (
        start_by_name[source.operation.name] + source.latency_offset
    )

schedule = Schedule(
    sfg,
    schedule_time=48,
    cyclic=True,
    start_times={op.graph_id: start_by_name[op.name] for op in sfg.operations},
    laps={},
)
schedule

# %%
# The first four butterfly invocations illustrate the serialization: output 0
# and output 1 occupy different cycles of the same physical output port.
fig, ax = plt.subplots(figsize=(9, 3), layout="constrained")
for offset, label, color in (
    (1, "Logical output 0", "C0"),
    (3, "Logical output 1", "C1"),
):
    cycles = np.arange(0, 16, 4) + offset
    row = 2 if offset == 1 else 1
    ax.scatter(cycles, np.full(4, row), label=label, color=color, marker="s", s=80)
    ax.scatter(cycles, np.zeros(4), color=color, marker="s", s=80)
ax.set_yticks([0, 1, 2], ["Physical output 0", "Logical output 1", "Logical output 0"])
ax.set_xticks(range(16))
ax.set_xlabel("Cycle within the 48-cycle period")
ax.set_title("Two logical butterfly outputs share one physical port")
ax.set_ylim(-0.5, 2.5)
ax.grid(axis="x", alpha=0.3)

# %%
# Assign all twelve butterflies to one PE. The four pairs of simultaneous
# input samples need two input PEs; all eight FFT bins can share one output PE
# because their availability times differ.
operations = schedule.get_operations()
butterfly_processes = operations.get_by_type_name(R2DIFButterfly.type_name())
butterfly_pe = ProcessingElement(butterfly_processes, entity_name="butterfly")
pes = [butterfly_pe]
for operation_type, prefix in ((Input, "input"), (Output, "output")):
    processes = operations.get_by_type_name(operation_type.type_name())
    pes.extend(
        ProcessingElement(collection, entity_name=f"{prefix}{i}")
        for i, collection in enumerate(processes.split_on_execution_time())
    )

# %%
# Values between stages live in one RAM with two read ports and one write port.
# Each butterfly consumes two stored operands together, but its results reach
# the write port at different times. Zero-lifetime values, including the inputs
# and the final FFT bins, use direct interconnects.
direct, stored = schedule.get_memory_variables().split_on_length()
memory = Memory(
    stored,
    memory_type="RAM",
    entity_name="interstage",
    read_ports=2,
    write_ports=1,
)
arch = Architecture(pes, [memory], direct_interconnects=direct)

print("Butterfly logical inputs/outputs:", 2, 2)
print(
    "Butterfly physical inputs/outputs:",
    butterfly_pe.input_count,
    butterfly_pe.output_count,
)
print(
    "Butterfly port mapping:", butterfly_processes.collection[0].operation.port_mapping
)
print("Schedule period:", schedule.schedule_time)

# %%
# In the architecture, both logical butterfly results leave through output 0.
# That one connection feeds the RAM during the first two stages and the output
# PE during the last stage. Two RAM outputs feed the two butterfly inputs.
arch
