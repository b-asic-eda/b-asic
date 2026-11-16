"""
=============================================
Three-stage CIC decimator with two AddSub PEs
=============================================

Implement a decimation-by-four CIC filter with three integrator/comb stages
and unit differential delay. Input samples arrive every other clock cycle,
and one output is produced every eight cycles. Convert the arithmetic to
AddSub operations, use recursive CP scheduling, and jointly allocate the
processing elements and memories to obtain an architecture.

A second implementation unfolds two iterations into a sixteen-cycle period
to avoid memory-to-memory transfers, retaining the same input/output rates
and two AddSub PEs.

This example requires the optional CP dependencies (``pip install b-asic[cp]``)
and Graphviz for rendering the architecture.
"""  # noqa: D400, D415

import numpy as np

from b_asic.architecture import Architecture, Memory
from b_asic.core_operations import Addition, AddSub, Subtraction
from b_asic.resource_assigner import assign_processing_elements_and_memories
from b_asic.schedule import Schedule
from b_asic.scheduler import CPRecursiveScheduler
from b_asic.sfg_generators import cic
from b_asic.simulation import Simulation
from b_asic.special_operations import Input, Output

# %%
# Build the conventional CIC decimator. Leave its gain unnormalized so the
# implementation needs only additions, subtractions, and storage.
factor = 4
stages = 3
input_interval = 2
period = factor * input_interval
filter_sfg = cic(factor, stages=stages, differential_delay=1)
filter_sfg  # noqa: B018

# %%
# Map additions and subtractions to the same configurable AddSub operation,
# allowing integrators and combs to share hardware.
addsub_sfg = filter_sfg.rewrite(AddSub, Addition).rewrite(AddSub, Subtraction)
addsub_sfg  # noqa: B018

# %%
# Normalize the rate-changing SFG before scheduling. One iteration consumes
# four consecutive input samples and produces one output. The phase graph
# contains twelve integrator additions and three comb subtractions, so two
# AddSub PEs provide sixteen execution slots for fifteen operations per period.
normalization = addsub_sfg.to_single_rate()
assert normalization.input_samples == (factor,)
assert normalization.output_samples == (1,)
sfg = normalization.sfg
sfg.set_latency_of_type(AddSub, 1)
sfg.set_execution_time_of_type(AddSub, 1)
sfg  # noqa: B018

# %%
# Check the transformed graph against the equivalent FIR: three cascaded
# four-sample moving sums, followed by retaining phase zero of every four
# samples. Append zeros to include the complete filter tail.
samples = np.pad(np.arange(1, 17), (0, 12))
inputs = [samples[phase::factor] for phase in range(factor)]
coefficients = np.ones(1)
for _ in range(stages):
    coefficients = np.convolve(coefficients, np.ones(factor))
reference = np.convolve(samples, coefficients)[: len(samples) : factor]
simulation = Simulation(sfg, inputs)
simulation.run()
np.testing.assert_allclose(
    simulation.results[sfg.output_operations[0].graph_id], reference
)

# %%
# Serialize the four logical input ports at cycles 0, 2, 4, and 6. Let the
# scheduler place the output as soon as its result is ready. Repeating this
# cyclic schedule gives an input every two cycles and an output every eight.
# CPRecursiveScheduler handles the integrator feedback and computations
# spanning the period boundary while minimizing concurrent resource use.
input_times = {
    operation.graph_id: phase * input_interval
    for phase, operation in enumerate(sfg.input_operations)
}
schedule = Schedule(
    sfg,
    scheduler=CPRecursiveScheduler(
        input_times=input_times,
        time_limit=10,
        num_search_workers=1,
        random_seed=0,
    ),
    schedule_time=period,
    cyclic=True,
)
for graph_id, time in input_times.items():
    assert schedule.start_times[graph_id] == time
assert schedule.backward_slack(sfg.output_operations[0].graph_id) == 0
assert (
    schedule.get_operations()
    .get_by_type_name(AddSub.type_name())
    .processing_element_bound()
    == 2
)
schedule  # noqa: B018

# %%
# Reintroduce the scheduled delays and verify that wrapping computations
# across the period boundary preserves the filter's outputs.
scheduled_sfg = schedule.sfg
scheduled_simulation = Simulation(scheduled_sfg, inputs)
scheduled_simulation.run()
np.testing.assert_allclose(
    scheduled_simulation.results[scheduled_sfg.output_operations[0].graph_id],
    reference,
)

# %%
# Jointly assign operations to two AddSub PEs and the serialized input/output
# interfaces, and assign intermediate values to memories. The CP min-mux
# strategy minimizes interconnects while respecting one read and one write
# port per RAM. The input and output resources each represent one physical
# interface, even though the phase graph has four logical input ports.
resources = {AddSub.type_name(): 2, Input.type_name(): 1, Output.type_name(): 1}
pes, memories, direct = assign_processing_elements_and_memories(
    schedule,
    strategy="cp_min_mux",
    resources=resources,
    memory_read_ports=1,
    memory_write_ports=1,
    memory_total_ports=2,
    memory_type="RAM",
    strat_params={
        "time_limit": 10,
        "num_search_workers": 1,
        "random_seed": 0,
        "log_search_progress": False,
    },
)
assert sum(pe.operation_type is AddSub for pe in pes) == 2

# %%
# Display the architecture, including the two shared AddSub PEs, RAMs,
# multiplexers, and I/O. In a Python console, arch.show() opens a viewer.
arch = Architecture(
    pes,
    memories,
    entity_name="cic_decimator",
    direct_interconnects=direct,
)
print(f"CIC decimator: two AddSub PEs, {len(memories)} RAMs, {period}-cycle period.")
arch  # noqa: B018

# %%
# Unfolding to avoid memory-to-memory transfers
# -------------------------------------------
# Values whose lifetime exceeds the schedule period are split into chains
# during resource allocation, introducing memory-to-memory transfers. Unfold
# two iterations so values can remain in their original memory until needed.
# Use the reconstructed scheduled SFG, which includes its delay elements.
unfold_factor = 2
unfolded_sfg = scheduled_sfg.unfold(unfold_factor)
unfolded_period = unfold_factor * period
unfolded_sfg  # noqa: B018

# %%
# The unfolded graph consumes eight samples and produces two outputs in a
# sixteen-cycle period. Inputs arrive at 0, 2, ..., 14, and the outputs are
# spaced eight cycles apart. Relative output times let the scheduler remove
# slack before the output pair, preserving the original sample rates.
# Schedule thirty AddSub operations on the same two PEs, with thirty-two
# available execution slots.
unfolded_input_times = {
    operation.graph_id: phase * input_interval
    for phase, operation in enumerate(unfolded_sfg.input_operations)
}
unfolded_output_delta_times = {
    operation.graph_id: phase * period
    for phase, operation in enumerate(unfolded_sfg.output_operations)
}
unfolded_schedule = Schedule(
    unfolded_sfg,
    scheduler=CPRecursiveScheduler(
        input_times=unfolded_input_times,
        output_delta_times=unfolded_output_delta_times,
        time_limit=10,
        num_search_workers=1,
        random_seed=0,
    ),
    schedule_time=unfolded_period,
    cyclic=True,
)
for graph_id, time in unfolded_input_times.items():
    assert unfolded_schedule.start_times[graph_id] == time
unfolded_output_base = unfolded_schedule.start_times[
    unfolded_sfg.output_operations[0].graph_id
]
for graph_id, delta in unfolded_output_delta_times.items():
    assert unfolded_schedule.start_times[graph_id] == unfolded_output_base + delta
assert (
    min(
        unfolded_schedule.backward_slack(output.graph_id)
        for output in unfolded_sfg.output_operations
    )
    == 0
)
assert (
    unfolded_schedule.get_operations()
    .get_by_type_name(AddSub.type_name())
    .processing_element_bound()
    == 2
)
assert all(
    variable.execution_time <= unfolded_period
    for variable in unfolded_schedule.get_memory_variables()
)
unfolded_schedule  # noqa: B018

# %%
# Verify the scheduled, unfolded graph against the FIR reference. Pad the
# input to complete a pair of iterations and interleave the two output ports
# to recover the chronological decimated stream.
unfolded_samples = np.pad(samples, (0, -len(samples) % (unfold_factor * factor)))
unfolded_inputs = [
    unfolded_samples[phase :: unfold_factor * factor]
    for phase in range(unfold_factor * factor)
]
unfolded_scheduled_sfg = unfolded_schedule.sfg
unfolded_simulation = Simulation(unfolded_scheduled_sfg, unfolded_inputs)
unfolded_simulation.run()
unfolded_results = np.column_stack(
    [
        unfolded_simulation.results[output.graph_id]
        for output in unfolded_scheduled_sfg.output_operations
    ]
).ravel()
unfolded_reference = np.convolve(unfolded_samples, coefficients)[
    : len(unfolded_samples) : factor
]
np.testing.assert_allclose(unfolded_results, unfolded_reference)

# %%
# Repeat the joint CP allocation with the same two AddSub PEs, one input
# interface, one output interface, and one-read/one-write RAMs. No variable
# now needs chaining because every lifetime fits within the longer period.
unfolded_pes, unfolded_memories, unfolded_direct = (
    assign_processing_elements_and_memories(
        unfolded_schedule,
        strategy="cp_min_mux",
        resources=resources,
        memory_read_ports=1,
        memory_write_ports=1,
        memory_total_ports=2,
        memory_type="RAM",
        strat_params={
            "time_limit": 10,
            "num_search_workers": 1,
            "random_seed": 0,
            "log_search_progress": False,
        },
    )
)
assert sum(pe.operation_type is AddSub for pe in unfolded_pes) == 2

# %%
# Display the second architecture and check its actual memory connections:
# all memory writes come from PEs or the input interface, with no RAM relays.
unfolded_arch = Architecture(
    unfolded_pes,
    unfolded_memories,
    entity_name="cic_decimator_unfolded",
    direct_interconnects=unfolded_direct,
)
for memory in unfolded_arch.memories:
    write_sources, _ = unfolded_arch.get_interconnects_for_memory(memory)
    assert all(
        not isinstance(source, Memory) for port in write_sources for source, _ in port
    )
print(
    f"Unfolded CIC: two AddSub PEs, {len(unfolded_memories)} RAMs, "
    f"{unfolded_period}-cycle period, no memory-to-memory transfers."
)
unfolded_arch  # noqa: B018
