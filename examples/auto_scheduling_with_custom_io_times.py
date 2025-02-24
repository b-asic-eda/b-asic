"""
=========================================
Auto Scheduling With Custom IO times
=========================================

"""

from b_asic.core_operations import Butterfly, ConstantMultiplication
from b_asic.list_schedulers import HybridScheduler
from b_asic.schedule import Schedule
from b_asic.scheduler import ASAPScheduler
from b_asic.sfg_generators import radix_2_dif_fft

points = 8
sfg = radix_2_dif_fft(points=points)

# %%
# The SFG is
sfg

# %%
# Set latencies and execution times.
sfg.set_latency_of_type(Butterfly.type_name(), 1)
sfg.set_latency_of_type(ConstantMultiplication.type_name(), 3)
sfg.set_execution_time_of_type(Butterfly.type_name(), 1)
sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)

# %%
# Generate an ASAP schedule for reference
schedule = Schedule(sfg, scheduler=ASAPScheduler())
schedule.show()

# %%
# Generate a non-cyclic Schedule from HybridScheduler with custom IO times.
resources = {Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}
input_times = {f"in{i}": i for i in range(points)}
output_delta_times = {f"out{i}": i - 2 for i in range(points)}
schedule = Schedule(
    sfg,
    scheduler=HybridScheduler(
        resources,
        input_times=input_times,
        output_delta_times=output_delta_times,
    ),
)
schedule.show()

# %%
# Generate a new Schedule with cyclic scheduling enabled
output_delta_times = {f"out{i}": i for i in range(points)}
schedule = Schedule(
    sfg,
    scheduler=HybridScheduler(
        resources,
        input_times=input_times,
        output_delta_times=output_delta_times,
    ),
    cyclic=True,
)
schedule.show()
