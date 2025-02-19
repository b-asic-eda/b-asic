"""
=========================================
LDLT Matrix Inversion Algorithm
=========================================

"""

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import MADS, DontCare, Reciprocal
from b_asic.core_schedulers import (
    ALAPScheduler,
    ASAPScheduler,
    EarliestDeadlineScheduler,
    HybridScheduler,
    LeastSlackTimeScheduler,
    MaxFanOutScheduler,
)
from b_asic.schedule import Schedule
from b_asic.sfg_generators import ldlt_matrix_inverse
from b_asic.special_operations import Input, Output

sfg = ldlt_matrix_inverse(N=3)

# %%
# The SFG is
sfg

# %%
# Set latencies and execution times.
sfg.set_latency_of_type(MADS.type_name(), 3)
sfg.set_latency_of_type(Reciprocal.type_name(), 2)
sfg.set_execution_time_of_type(MADS.type_name(), 1)
sfg.set_execution_time_of_type(Reciprocal.type_name(), 1)

# %%
# Create an ASAP schedule.
schedule = Schedule(sfg, scheduler=ASAPScheduler())
print("Scheduling time:", schedule.schedule_time)
schedule.show()

# %%
# Create an ALAP schedule.
schedule = Schedule(sfg, scheduler=ALAPScheduler())
print("Scheduling time:", schedule.schedule_time)
schedule.show()

# %%
# Create an EarliestDeadline schedule that satisfies the resource constraints.
resources = {MADS.type_name(): 1, Reciprocal.type_name(): 1}
schedule = Schedule(sfg, scheduler=EarliestDeadlineScheduler(resources))
print("Scheduling time:", schedule.schedule_time)
schedule.show()

# %%
# Create a LeastSlackTime schedule that satisfies the resource constraints.
schedule = Schedule(sfg, scheduler=LeastSlackTimeScheduler(resources))
print("Scheduling time:", schedule.schedule_time)
schedule.show()

# %%
# Create a MaxFanOutScheduler schedule that satisfies the resource constraints.
schedule = Schedule(sfg, scheduler=MaxFanOutScheduler(resources))
print("Scheduling time:", schedule.schedule_time)
schedule.show()

# %%
# Create a HybridScheduler schedule that satisfies the resource constraints.
schedule = Schedule(sfg, scheduler=HybridScheduler(resources))
print("Scheduling time:", schedule.schedule_time)
schedule.show()

# %%
operations = schedule.get_operations()
mads = operations.get_by_type_name(MADS.type_name())
mads.show(title="MADS executions")
reciprocals = operations.get_by_type_name(Reciprocal.type_name())
reciprocals.show(title="Reciprocal executions")
dont_cares = operations.get_by_type_name(DontCare.type_name())
dont_cares.show(title="Dont-care executions")
inputs = operations.get_by_type_name(Input.type_name())
inputs.show(title="Input executions")
outputs = operations.get_by_type_name(Output.type_name())
outputs.show(title="Output executions")

mads_pe = ProcessingElement(mads, entity_name="mad")
reciprocal_pe = ProcessingElement(reciprocals, entity_name="rec")

dont_care_pe = ProcessingElement(dont_cares, entity_name="dc")

pe_in = ProcessingElement(inputs, entity_name='input')
pe_out = ProcessingElement(outputs, entity_name='output')

mem_vars = schedule.get_memory_variables()
mem_vars.show(title="All memory variables")
direct, mem_vars = mem_vars.split_on_length()
mem_vars.show(title="Non-zero time memory variables")
mem_vars_set = mem_vars.split_on_ports(read_ports=1, write_ports=1, total_ports=2)

# %%
memories = []
for i, mem in enumerate(mem_vars_set):
    memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
    memories.append(memory)
    mem.show(title=f"{memory.entity_name}")
    memory.assign("left_edge")
    memory.show_content(title=f"Assigned {memory.entity_name}")

direct.show(title="Direct interconnects")

# %%
arch = Architecture(
    {mads_pe, reciprocal_pe, dont_care_pe, pe_in, pe_out},
    memories,
    direct_interconnects=direct,
)

# %%
arch
# schedule.edit()
