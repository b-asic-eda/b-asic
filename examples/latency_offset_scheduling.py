"""
================================
Automatic Scheduling for different latency-offsets.
================================

This example showcases how one can synthesize an architecture where the
operations have different latency offsets for the different inputs/outputs.
"""

from b_asic.architecture import Memory, ProcessingElement
from b_asic.core_operations import MADS, Reciprocal
from b_asic.list_schedulers import HybridScheduler
from b_asic.schedule import Schedule
from b_asic.scheduler import ALAPScheduler, ASAPScheduler
from b_asic.sfg_generators import ldlt_matrix_inverse
from b_asic.special_operations import Input, Output

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
schedule = Schedule(sfg, scheduler=ASAPScheduler())
schedule.show()

# %%
# Create an ALAP schedule for reference.
schedule = Schedule(sfg, scheduler=ALAPScheduler())
schedule.show()

# %%
# Create a resource restricted schedule.
schedule = Schedule(sfg, scheduler=HybridScheduler())
schedule.show()

# %%
# Create another schedule with shorter scheduling time by enabling cyclic.
schedule = Schedule(
    sfg,
    scheduler=HybridScheduler(),
    schedule_time=49,
    cyclic=True,
)
schedule.show()

# %%
# Push the schedule time to the rate limit for one MADS operator.
schedule = Schedule(
    sfg,
    scheduler=HybridScheduler(),
    schedule_time=15,
    cyclic=True,
)
schedule.show()

# %%
# Leverage the fact that the inputs arrive at different times to limit the amount of concurrent memory accesses to 2
schedule = Schedule(
    sfg,
    scheduler=HybridScheduler(max_concurrent_writes=2, max_concurrent_reads=2),
    schedule_time=30,
    cyclic=True,
)
schedule.show()

# %%
operations = schedule.get_operations()
mads = operations.get_by_type_name(MADS.type_name())
mads.show(title="MADS executions")
reciprocals = operations.get_by_type_name(Reciprocal.type_name())
reciprocals.show(title="Reciprocal executions")
inputs = operations.get_by_type_name(Input.type_name())
inputs.show(title="Input executions")
outputs = operations.get_by_type_name(Output.type_name())
outputs.show(title="Output executions")

mads_pe = ProcessingElement(mads, entity_name="mad")
reciprocal_pe = ProcessingElement(reciprocals, entity_name="rec")

pe_in = ProcessingElement(inputs, entity_name='input')
pe_out = ProcessingElement(outputs, entity_name='output')

mem_vars = schedule.get_memory_variables()
mem_vars.show(title="All memory variables")
direct, mem_vars = mem_vars.split_on_length()
mem_vars.show(title="Non-zero time memory variables")
mem_vars_set = mem_vars.split_on_ports(
    read_ports=1, write_ports=1, total_ports=2, heuristic="graph_color"
)

# %%
memories = []
for i, mem in enumerate(mem_vars_set):
    memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
    memories.append(memory)
    mem.show(title=f"{memory.entity_name}")
    memory.assign("left_edge")
    memory.show_content(title=f"Assigned {memory.entity_name}")

direct.show(title="Direct interconnects")
