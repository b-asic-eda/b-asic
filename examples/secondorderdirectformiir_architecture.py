"""
=========================================
Second-order IIR Filter with Architecture
=========================================

"""

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Delay, Input, Output

in1 = Input("IN1")
c0 = ConstantMultiplication(5, in1, "C0")
add1 = Addition(c0, None, "ADD1")
T1 = Delay(add1, 0, "T1")
T2 = Delay(T1, 0, "T2")
b2 = ConstantMultiplication(0.2, T2, "B2")
b1 = ConstantMultiplication(0.3, T1, "B1")
add2 = Addition(b1, b2, "ADD2")
add1.input(1).connect(add2)
a1 = ConstantMultiplication(0.4, T1, "A1")
a2 = ConstantMultiplication(0.6, T2, "A2")
add3 = Addition(a1, a2, "ADD3")
a0 = ConstantMultiplication(0.7, add1, "A0")
add4 = Addition(a0, add3, "ADD4")
out1 = Output(add4, "OUT1")

sfg = SFG(inputs=[in1], outputs=[out1], name="Second-order direct form IIR filter")

# %%
# Set latencies and execution times
sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
sfg.set_latency_of_type(Addition.type_name(), 1)
sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
sfg.set_execution_time_of_type(Addition.type_name(), 1)

# %%
# Create schedule
schedule = Schedule(sfg, cyclic=True)
schedule.show(title='Original schedule')

# %%
# Reschedule to only require one adder and one multiplier
schedule.move_operation('add4', 2)
schedule.move_operation('cmul5', -4)
schedule.move_operation('cmul4', -5)
schedule.move_operation('cmul6', -2)
schedule.move_operation('cmul3', 1)
schedule.show(title='Improved schedule')

# %%
# Extract operations and create processing elements
operations = schedule.get_operations()
adders = operations.get_by_type_name('add')
adders.show(title="Adder executions")
mults = operations.get_by_type_name('cmul')
mults.show(title="Multiplier executions")
inputs = operations.get_by_type_name('in')
inputs.show(title="Input executions")
outputs = operations.get_by_type_name('out')
outputs.show(title="Output executions")

p1 = ProcessingElement(adders, entity_name="adder")
p2 = ProcessingElement(mults, entity_name="cmul")
p_in = ProcessingElement(inputs, entity_name='input')
p_out = ProcessingElement(outputs, entity_name='output')

# %%
# Extract and assign memory variables
mem_vars = schedule.get_memory_variables()
mem_vars.show(title="All memory variables")
direct, mem_vars = mem_vars.split_on_length()
mem_vars.show(title="Non-zero time memory variables")
mem_vars_set = mem_vars.split_on_ports(read_ports=1, write_ports=1, total_ports=2)

memories = []
for i, mem in enumerate(mem_vars_set):
    memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
    memories.append(memory)
    mem.show(title=f"{memory.entity_name}")
    memory.assign("left_edge")
    memory.show_content(title=f"Assigned {memory.entity_name}")

direct.show(title="Direct interconnects")

# %%
# Create architecture
arch = Architecture({p1, p2, p_in, p_out}, memories, direct_interconnects=direct)

# %%
# The architecture can be rendered in enriched shells.
arch

# %%
# To reduce the amount of interconnect, the ``cuml3.0`` variable can be moved from
# ``memory0`` to ``memory2``.  In this way, ``memory0``only gets variables from the
# adder and an input multiplexer can be avoided. The memoried must be assigned again as
# the contents have changed.
arch.move_process('cmul3.0', 'memory0', 'memory2')
memories[0].assign()
memories[2].assign()

memories[0].show_content("New assigned memory0")
memories[2].show_content("New assigned memory2")

# %%
# Looking at the architecture it is clear that there is now only one input to
# ``memory0``, so no input multiplexer required.
arch

# %%
# It is of course also possible to move ``add4.0`` to ``memory2`` to save one memory
# cell.
arch.move_process('add4.0', 'memory0', 'memory2')
memories[0].assign()
memories[2].assign()

memories[0].show_content("New assigned memory0")
memories[2].show_content("New assigned memory2")

# %%
# However, this comes at the expense of an additional input to ``memory2``.
arch
