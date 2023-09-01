"""
=======================
Five-point Winograd DFT
=======================

First, define the SFG/block diagram
"""

from math import cos, pi, sin

import matplotlib.pyplot as plt
import networkx as nx

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import AddSub, Butterfly, ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Input, Output

u = -2 * pi / 5
c50 = (cos(u) + cos(2 * u)) / 2 - 1
c51 = (cos(u) - cos(2 * u)) / 2
c52 = 1j * (sin(u) + sin(2 * u)) / 2
c53 = 1j * (sin(2 * u))
c54 = 1j * (sin(u) - sin(2 * u))


in0 = Input("x0")
in1 = Input("x1")
in2 = Input("x2")
in3 = Input("x3")
in4 = Input("x4")
bf0 = Butterfly(in1, in3)
bf1 = Butterfly(in4, in2)
bf2 = Butterfly(bf0.output(0), bf1.output(0))
a0 = AddSub(True, bf0.output(1), bf1.output(0))
a1 = AddSub(True, bf2.output(0), in0)
# Should overload float*OutputPort as well
m0 = ConstantMultiplication(c50, bf2.output(0))
m1 = ConstantMultiplication(c51, bf0.output(1))
m2 = c52 * a0
m3 = ConstantMultiplication(c53, bf2.output(1))
m4 = ConstantMultiplication(c54, bf1.output(1))
a2 = AddSub(True, m0, a1)
a3 = AddSub(False, m3, m2)
a4 = AddSub(True, m3, m4)
bf3 = Butterfly(a2, m1)
bf4 = Butterfly(bf3.output(0), a3)
bf5 = Butterfly(bf3.output(1), a4)

out0 = Output(a1, "X0")
out1 = Output(bf4.output(0), "X1")
out2 = Output(bf4.output(1), "X2")
out4 = Output(bf5.output(0), "X4")
out3 = Output(bf5.output(1), "X3")

sfg = SFG(
    inputs=[in0, in1, in2, in3, in4],
    outputs=[out0, out1, out2, out3, out4],
    name="5-point Winograd DFT",
)

# %%
# The SFG looks like
sfg

# %%
# Set latencies and execution times
sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
sfg.set_latency_of_type(AddSub.type_name(), 1)
sfg.set_latency_of_type(Butterfly.type_name(), 1)
sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
sfg.set_execution_time_of_type(AddSub.type_name(), 1)
sfg.set_execution_time_of_type(Butterfly.type_name(), 1)

# %%
# Generate schedule
schedule = Schedule(sfg, cyclic=True)
schedule.show()

# %%
# Reschedule to only use one AddSub, one Butterfly, and one ConstantMultiplication per
# time unit

schedule.set_schedule_time(10)
schedule.move_operation('out4', 12)
schedule.move_operation('out3', 11)
schedule.move_operation('out2', 10)
schedule.move_operation('out1', 9)
schedule.move_operation('out0', 12)
schedule.move_operation('bfly3', 10)
schedule.move_operation('bfly2', 9)
schedule.move_operation('bfly1', 7)
schedule.move_operation('addsub4', 5)
schedule.move_operation('addsub2', 5)
schedule.move_operation('addsub1', 5)
schedule.move_operation('cmul4', 4)
schedule.move_operation('cmul2', 4)
schedule.move_operation('cmul0', 5)
schedule.move_operation('addsub0', 6)
schedule.move_operation('cmul1', 6)
schedule.move_operation('addsub3', 4)
schedule.move_operation('bfly0', 4)
schedule.move_operation('cmul3', 6)
schedule.move_operation('bfly5', 4)
schedule.move_operation('bfly4', 4)
schedule.move_operation('in1', 1)
schedule.move_operation('in2', 2)
schedule.move_operation('in3', 3)
schedule.move_operation('in4', 4)
schedule.move_operation('bfly5', -1)
schedule.move_operation('bfly3', 1)
schedule.move_operation('cmul2', 1)
schedule.move_operation('cmul4', 1)
schedule.move_operation('bfly0', 1)
schedule.move_operation('addsub0', -1)
schedule.move_operation('cmul1', -3)
schedule.move_operation('cmul3', -2)
schedule.move_operation('cmul4', -1)
schedule.move_operation('addsub4', 1)
schedule.move_operation('addsub1', 2)
schedule.move_operation('cmul0', 1)
schedule.move_operation('bfly0', -1)
schedule.move_operation('addsub0', -1)
schedule.move_operation('bfly2', -1)
schedule.move_operation('cmul2', -1)
schedule.move_operation('cmul4', 1)
schedule.move_operation('addsub2', -1)
schedule.move_operation('addsub4', -1)
schedule.move_operation('addsub1', -1)
schedule.move_operation('bfly1', -1)
schedule.move_operation('bfly2', -2)
schedule.move_operation('bfly3', -1)
schedule.show()

# %%
# Extract memory variables and operation executions
operations = schedule.get_operations()
adders = operations.get_by_type_name(AddSub.type_name())
adders.show(title="AddSub executions")
mults = operations.get_by_type_name('cmul')
mults.show(title="Multiplier executions")
butterflies = operations.get_by_type_name(Butterfly.type_name())
butterflies.show(title="Butterfly executions")
inputs = operations.get_by_type_name('in')
inputs.show(title="Input executions")
outputs = operations.get_by_type_name('out')
outputs.show(title="Output executions")

addsub = ProcessingElement(adders, entity_name="addsub")
butterfly = ProcessingElement(butterflies, entity_name="butterfly")
multiplier = ProcessingElement(mults, entity_name="multiplier")
pe_in = ProcessingElement(inputs, entity_name='input')
pe_out = ProcessingElement(outputs, entity_name='output')

mem_vars = schedule.get_memory_variables()
mem_vars.show(title="All memory variables")
direct, mem_vars = mem_vars.split_on_length()
mem_vars.show(title="Non-zero time memory variables")
direct.show(title="Direct interconnects")
mem_vars_set = mem_vars.split_on_ports(read_ports=1, write_ports=1, total_ports=2)

memories = []
for i, mem in enumerate(mem_vars_set):
    memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
    memories.append(memory)
    mem.show(title=f"{memory.entity_name} variables")
    memory.assign("left_edge")
    memory.show_content(title=f"Assigned {memory.entity_name}")

fig, ax = plt.subplots()
fig.suptitle('Exclusion graph based on ports')
nx.draw(mem_vars.create_exclusion_graph_from_ports(1, 1, 2), ax=ax)

# %%
# Create architecture
arch = Architecture(
    [addsub, butterfly, multiplier, pe_in, pe_out],
    memories,
    direct_interconnects=direct,
)

arch

# %%
# Move memory variables to optimize architecture
arch.move_process('addsub2.0', 'memory3', 'memory2')
arch.move_process('bfly2.0', 'memory2', 'memory3')
arch.move_process('cmul2.0', 'memory1', 'memory0')
arch.move_process('bfly3.0', 'memory0', 'memory1')
arch.move_process('cmul3.0', 'memory4', 'memory0')

arch.assign_resources()

# %%
# Memory 4 is now empty, so remove it.

arch.remove_resource('memory4')

for memory in arch.memories:
    memory.show_content(title=f"Improved {memory.entity_name}")

arch
