"""
========================
Three-point Winograd DFT
========================
"""

from math import cos, pi, sin

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import AddSub, ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Input, Output

u = -2 * pi / 3
c30 = cos(u) - 1
c31 = sin(u)


in0 = Input("x0")
in1 = Input("x1")
in2 = Input("x2")
a0 = AddSub(True, in1, in2)
a1 = AddSub(False, in1, in2)
a2 = AddSub(True, a0, in0)
m0 = c30 * a0
m1 = c31 * a1
a3 = AddSub(True, a2, m0)
a4 = AddSub(True, a3, m1)
a5 = AddSub(False, a3, m1)
out0 = Output(a2, "X0")
out1 = Output(a4, "X1")
out2 = Output(a5, "X2")

sfg = SFG(
    inputs=[in0, in1, in2],
    outputs=[out0, out1, out2],
    name="3-point Winograd DFT",
)

# %%
# The SFG looks like
sfg

# %%
# Set latencies and execution times
sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
sfg.set_latency_of_type(AddSub.type_name(), 1)
sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
sfg.set_execution_time_of_type(AddSub.type_name(), 1)

# %%
# Generate schedule
schedule = Schedule(sfg, cyclic=True)
schedule.show()

# Reschedule to only use one AddSub and one multiplier
schedule.set_schedule_time(10)
schedule.move_operation('out2', 3)
schedule.move_operation('out3', 4)
schedule.move_operation('addsub5', 2)
schedule.move_operation('addsub4', 3)
schedule.move_operation('addsub3', 2)
schedule.move_operation('cmul2', 2)
schedule.move_operation('cmul1', 2)
schedule.move_operation('out1', 5)
schedule.move_operation('addsub1', 3)
schedule.move_operation('addsub6', 2)
schedule.move_operation('addsub2', 2)
schedule.move_operation('in2', 1)
schedule.move_operation('in3', 2)
schedule.move_operation('cmul2', 1)
schedule.move_operation('out3', 6)
schedule.move_operation('out2', 6)
schedule.move_operation('out1', 6)
schedule.move_operation('addsub6', 1)
schedule.move_operation('addsub4', 3)
schedule.move_operation('addsub5', 4)
schedule.move_operation('addsub4', 1)
schedule.move_operation('addsub5', 4)
schedule.move_operation('cmul2', 3)
schedule.move_operation('addsub4', 2)
schedule.move_operation('cmul2', 3)
schedule.move_operation('addsub3', 5)
schedule.set_schedule_time(6)
schedule.move_operation('addsub1', 1)
schedule.move_operation('addsub4', -1)
schedule.move_operation('cmul2', -2)
schedule.move_operation('addsub4', -1)
schedule.move_operation('addsub1', -1)
schedule.move_operation('addsub3', -1)
schedule.move_operation('addsub5', -4)
schedule.show()

# Extract memory variables and operation executions
operations = schedule.get_operations()
adders = operations.get_by_type_name(AddSub.type_name())
adders.show(title="AddSub executions")
mults = operations.get_by_type_name('cmul')
mults.show(title="Multiplier executions")
inputs = operations.get_by_type_name('in')
inputs.show(title="Input executions")
outputs = operations.get_by_type_name('out')
outputs.show(title="Output executions")

addsub = ProcessingElement(adders, entity_name="addsub")
multiplier = ProcessingElement(mults, entity_name="multiplier")
pe_in = ProcessingElement(inputs, entity_name='input')
pe_out = ProcessingElement(outputs, entity_name='output')

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

arch = Architecture(
    {addsub, multiplier, pe_in, pe_out}, memories, direct_interconnects=direct
)

arch
