"""
=========================================
Memory Constrained Scheduling
=========================================

"""

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import Butterfly, ConstantMultiplication
from b_asic.list_schedulers import HybridScheduler
from b_asic.schedule import Schedule
from b_asic.scheduler import ASAPScheduler
from b_asic.sfg_generators import radix_2_dif_fft
from b_asic.special_operations import Input, Output

sfg = radix_2_dif_fft(points=16)

# %%
# The SFG is
sfg

# %%
# Set latencies and execution times.
sfg.set_latency_of_type_name(Butterfly.type_name(), 3)
sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)
sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

# # %%
# Generate an ASAP schedule for reference
schedule1 = Schedule(sfg, scheduler=ASAPScheduler())
schedule1.show()

# %%
# Generate a PE constrained HybridSchedule
resources = {Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}
schedule2 = Schedule(sfg, scheduler=HybridScheduler(resources))
schedule2.show()

# %% Print the max number of read and write port accesses to non-direct memories
direct, mem_vars = schedule2.get_memory_variables().split_on_length()
print("Max read ports:", mem_vars.read_ports_bound())
print("Max write ports:", mem_vars.write_ports_bound())

# %%
operations = schedule2.get_operations()
bfs = operations.get_by_type_name(Butterfly.type_name())
bfs.show(title="Butterfly executions")
const_muls = operations.get_by_type_name(ConstantMultiplication.type_name())
const_muls.show(title="ConstMul executions")
inputs = operations.get_by_type_name(Input.type_name())
inputs.show(title="Input executions")
outputs = operations.get_by_type_name(Output.type_name())
outputs.show(title="Output executions")

bf_pe = ProcessingElement(bfs, entity_name="bf")
mul_pe = ProcessingElement(const_muls, entity_name="mul")

pe_in = ProcessingElement(inputs, entity_name='input')
pe_out = ProcessingElement(outputs, entity_name='output')

mem_vars = schedule2.get_memory_variables()
mem_vars.show(title="All memory variables")
direct, mem_vars = mem_vars.split_on_length()
mem_vars.show(title="Non-zero time memory variables")
mem_vars_set = mem_vars.split_on_ports(
    read_ports=1, write_ports=1, total_ports=2, heuristic="greedy_graph_color"
)

# %%
memories = []
for i, mem in enumerate(mem_vars_set):
    memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
    memories.append(memory)
    mem.show(title=f"{memory.entity_name}")
    memory.assign("graph_color")
    memory.show_content(title=f"Assigned {memory.entity_name}")

direct.show(title="Direct interconnects")

# %%
arch = Architecture(
    {bf_pe, mul_pe, pe_in, pe_out},
    memories,
    direct_interconnects=direct,
)
arch

# %%
# Generate another HybridSchedule but this time constrain the amount of reads and writes to reduce the amount of memories
resources = {Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}
schedule3 = Schedule(
    sfg,
    scheduler=HybridScheduler(
        resources, max_concurrent_reads=2, max_concurrent_writes=2
    ),
)
schedule3.show()

# %% Print the max number of read and write port accesses to non-direct memories
direct, mem_vars = schedule3.get_memory_variables().split_on_length()
print("Max read ports:", mem_vars.read_ports_bound())
print("Max write ports:", mem_vars.write_ports_bound())

# %% Proceed to construct PEs and plot executions and non-direct memory variables
operations = schedule3.get_operations()
bfs = operations.get_by_type_name(Butterfly.type_name())
bfs.show(title="Butterfly executions")
const_muls = operations.get_by_type_name(ConstantMultiplication.type_name())
const_muls.show(title="ConstMul executions")
inputs = operations.get_by_type_name(Input.type_name())
inputs.show(title="Input executions")
outputs = operations.get_by_type_name(Output.type_name())
outputs.show(title="Output executions")

bf_pe = ProcessingElement(bfs, entity_name="bf")
mul_pe = ProcessingElement(const_muls, entity_name="mul")

pe_in = ProcessingElement(inputs, entity_name='input')
pe_out = ProcessingElement(outputs, entity_name='output')

mem_vars.show(title="Non-zero time memory variables")
mem_vars_set = mem_vars.split_on_ports(
    heuristic="greedy_graph_color", read_ports=1, write_ports=1, total_ports=2
)

# %% Allocate memories by graph coloring
memories = []
for i, mem in enumerate(mem_vars_set):
    memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
    memories.append(memory)
    mem.show(title=f"{memory.entity_name}")
    memory.assign("graph_color")
    memory.show_content(title=f"Assigned {memory.entity_name}")

direct.show(title="Direct interconnects")

# %% Synthesize the new architecture, now only using two memories but with data rate
arch = Architecture(
    {bf_pe, mul_pe, pe_in, pe_out},
    memories,
    direct_interconnects=direct,
)
arch
