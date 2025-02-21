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

sfg = radix_2_dif_fft(points=8)

# %%
# The SFG is
sfg

# %%
# Set latencies and execution times.
sfg.set_latency_of_type(Butterfly.type_name(), 3)
sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
sfg.set_execution_time_of_type(Butterfly.type_name(), 1)
sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)

# %%
# Generate an ASAP schedule for reference
schedule = Schedule(sfg, scheduler=ASAPScheduler())
schedule.show()

# %%
# Generate a non-cyclic Schedule from HybridScheduler with custom IO times.
resources = {Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}
input_times = {
    "in0": 0,
    "in1": 1,
    "in2": 2,
    "in3": 3,
    "in4": 4,
    "in5": 5,
    "in6": 6,
    "in7": 7,
}
output_delta_times = {
    "out0": -2,
    "out1": -1,
    "out2": 0,
    "out3": 1,
    "out4": 2,
    "out5": 3,
    "out6": 4,
    "out7": 5,
}
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
output_delta_times = {
    "out0": 0,
    "out1": 1,
    "out2": 2,
    "out3": 3,
    "out4": 4,
    "out5": 5,
    "out6": 6,
    "out7": 7,
}
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
