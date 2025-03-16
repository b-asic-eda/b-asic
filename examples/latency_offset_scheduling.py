"""
==================================================
Automatic scheduling for different latency-offsets
==================================================

This example showcases how one can generate a schedule where the
operations have different latency offsets for the different inputs/outputs.
"""

from b_asic.list_schedulers import HybridScheduler
from b_asic.schedule import Schedule
from b_asic.scheduler import ALAPScheduler, ASAPScheduler
from b_asic.sfg_generators import ldlt_matrix_inverse

sfg = ldlt_matrix_inverse(
    N=3,
    name="matrix-inv",
    mads_properties={
        "latency_offsets": {"in0": 3, "in1": 0, "in2": 0, "out0": 4},
        "execution_time": 1,
    },
    reciprocal_properties={"latency": 10, "execution_time": 1},
)

# %%
# The SFG is
sfg

# %%
# Create an ASAP schedule for reference.
schedule1 = Schedule(sfg, scheduler=ASAPScheduler())
schedule1.show()

# %%
# Create an ALAP schedule for reference.
schedule2 = Schedule(sfg, scheduler=ALAPScheduler())
schedule2.show()

# %%
# Create a resource restricted schedule.
schedule3 = Schedule(sfg, scheduler=HybridScheduler())
schedule3.show()

# %%
# Create another schedule with shorter scheduling time by enabling cyclic.
schedule4 = Schedule(
    sfg,
    scheduler=HybridScheduler(),
    schedule_time=49,
    cyclic=True,
)
schedule4.show()

# %%
# Push the schedule time to the rate limit for one MADS operator.
schedule5 = Schedule(
    sfg,
    scheduler=HybridScheduler(),
    schedule_time=15,
    cyclic=True,
)
schedule5.show()
