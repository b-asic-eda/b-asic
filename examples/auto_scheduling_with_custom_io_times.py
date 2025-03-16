"""
=========================================
Automatic scheduling with custom IO times
=========================================

It is possible to specify the IO times and provide those to the scheduling.
"""

from b_asic.core_operations import Butterfly, ConstantMultiplication
from b_asic.list_schedulers import HybridScheduler
from b_asic.schedule import Schedule
from b_asic.scheduler import ASAPScheduler
from b_asic.sfg_generators import radix_2_dif_fft

points = 8
sfg = radix_2_dif_fft(points=points)

# %%
# The SFG is:
sfg

# %%
# Set latencies and execution times.
sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 3)
sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)
sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

# %%
# Generate an ASAP schedule for reference.
schedule1 = Schedule(sfg, scheduler=ASAPScheduler())
schedule1.show()

# %%
# Generate a non-cyclic Schedule from HybridScheduler with custom IO times,
# one input and output per time unit
resources = {Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}
input_times = {f"in{i}": i for i in range(points)}
output_delta_times = {f"out{i}": i for i in range(points)}
schedule2 = Schedule(
    sfg,
    scheduler=HybridScheduler(
        resources,
        input_times=input_times,
        output_delta_times=output_delta_times,
    ),
)
schedule2.show()

# %%
# Generate a new Schedule with cyclic scheduling enabled.
schedule3 = Schedule(
    sfg,
    scheduler=HybridScheduler(
        resources,
        input_times=input_times,
        output_delta_times=output_delta_times,
    ),
    schedule_time=14,
    cyclic=True,
)
schedule3.show()

# %%
# Generate a new Schedule with even less scheduling time.
schedule4 = Schedule(
    sfg,
    scheduler=HybridScheduler(
        resources,
        input_times=input_times,
        output_delta_times=output_delta_times,
    ),
    schedule_time=13,
    cyclic=True,
)
schedule4.show()

# %%
# Try scheduling for 12 cycles, which gives full butterfly usage.
schedule5 = Schedule(
    sfg,
    scheduler=HybridScheduler(
        resources,
        input_times=input_times,
        output_delta_times=output_delta_times,
    ),
    schedule_time=12,
    cyclic=True,
)
schedule5.show()
