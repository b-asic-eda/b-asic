"""
=========================
Streaming sorting network
=========================

Sort blocks of five real-valued samples with one sample per clock cycle at
both the input and the output. Within each block, inputs arrive in index order
and outputs leave in ascending or descending value order. Compare cyclic
schedules using one and two shared Comparators for each output order.

The five-input bubble/insertion network performs ten comparisons per block.
With one Comparator, each five-sample burst therefore needs a ten-cycle block
period, leaving five idle I/O cycles between blocks. Two Comparators allow a
five-cycle period and continuous one-sample-per-cycle input and output streams
after the pipeline has filled.
"""

from b_asic.core_operations import Comparator
from b_asic.list_schedulers import HybridScheduler
from b_asic.schedule import Schedule
from b_asic.sfg_generators import bubble_sort

# %%
# Build and show the sorting SFG. Each Comparator returns the smaller value at
# output 0 and the larger value at output 1. Give each Comparator one cycle of
# latency and an execution time of one cycle.
size = 5
sfg = bubble_sort(size)
sfg.set_latency_of_type(Comparator, 1)
sfg.set_execution_time_of_type(Comparator, 1)
sfg

# %%
# Check a block containing both positive and negative samples.
samples = [7, -2, 4, 1, -5]
print("Input block:", samples)
print("Sorted output block:", sfg.evaluate_outputs(samples))

# %%
# Serialize the logical input and output ports by assigning consecutive clock
# cycles. Output times are offsets from the first output; HybridScheduler
# chooses the output latency so all results are ready when they are needed.
input_times = {f"in{i}": i for i in range(size)}
output_delta_times = {f"out{i}": i for i in range(size)}

# %%
# Schedule with one shared Comparator. The ten comparisons occupy all ten
# cycles of the period. Each five-cycle input/output burst is followed by five
# idle cycles. Cyclic schedules wrap operations and outputs across the period
# boundary, with stored values carrying data between periods.
one_comparator = Schedule(
    sfg,
    scheduler=HybridScheduler(
        max_resources={Comparator.type_name(): 1},
        input_times=input_times,
        output_delta_times=output_delta_times,
    ),
    schedule_time=size * (size - 1) // 2,
    cyclic=True,
)
one_comparator

# %%
# Schedule with two shared Comparators. A new five-sample block can now start
# every five cycles. Thus both the input and output interfaces sustain one
# sample per cycle, while independent comparisons can execute in parallel.
two_comparators = Schedule(
    sfg,
    scheduler=HybridScheduler(
        max_resources={Comparator.type_name(): 2},
        input_times=input_times,
        output_delta_times=output_delta_times,
    ),
    schedule_time=size,
    cyclic=True,
)
two_comparators

# %%
# Emit the largest value first by reversing the output time offsets. The SFG
# still assigns the smallest value to out0 and the largest to out4; scheduling
# out4 first makes the serialized output stream descend in value.
descending_output_delta_times = {f"out{i}": size - 1 - i for i in range(size)}

# %%
# Schedule descending outputs with one shared Comparator and the same
# ten-cycle block period as the ascending case.
one_comparator_descending = Schedule(
    sfg,
    scheduler=HybridScheduler(
        max_resources={Comparator.type_name(): 1},
        input_times=input_times,
        output_delta_times=descending_output_delta_times,
    ),
    schedule_time=size * (size - 1) // 2,
    cyclic=True,
)
one_comparator_descending

# %%
# Schedule descending outputs with two shared Comparators and a five-cycle
# block period, keeping both input and output streams continuous.
two_comparators_descending = Schedule(
    sfg,
    scheduler=HybridScheduler(
        max_resources={Comparator.type_name(): 2},
        input_times=input_times,
        output_delta_times=descending_output_delta_times,
    ),
    schedule_time=size,
    cyclic=True,
)
two_comparators_descending
