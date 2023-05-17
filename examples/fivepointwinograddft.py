"""
=======================
Five-point Winograd DFT
=======================
"""

from math import cos, pi, sin

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

# Reschedule to only use one AddSub and one multiplier

schedule.move_operation('out2', 4)
schedule.move_operation('out3', 4)
schedule.move_operation('out4', 3)
schedule.move_operation('out5', 6)
schedule.set_schedule_time(15)
schedule.move_operation('out5', 3)
schedule.move_operation('out4', 5)
schedule.move_operation('out3', 3)
schedule.move_operation('out2', 2)
schedule.move_operation('out1', 2)
schedule.move_operation('bfly4', 16)
schedule.move_operation('bfly3', 14)
schedule.move_operation('bfly2', 14)
schedule.move_operation('addsub3', 17)
schedule.move_operation('addsub5', 15)
schedule.move_operation('addsub2', 14)
schedule.move_operation('cmul5', 15)
schedule.move_operation('cmul3', 15)
schedule.move_operation('cmul1', 14)
schedule.move_operation('addsub1', 2)
schedule.move_operation('cmul2', 16)
schedule.move_operation('addsub4', 15)
schedule.move_operation('out1', 15)
schedule.move_operation('addsub1', 13)
schedule.move_operation('cmul4', 18)
schedule.move_operation('bfly1', 14)
schedule.move_operation('bfly6', 14)
schedule.move_operation('bfly5', 14)
schedule.move_operation('in5', 1)
schedule.move_operation('in3', 2)
schedule.move_operation('in2', 3)
schedule.move_operation('in4', 4)
schedule.move_operation('bfly6', -5)
schedule.move_operation('bfly5', -6)
schedule.move_operation('addsub1', -1)
schedule.move_operation('bfly1', -1)
schedule.move_operation('bfly1', -4)
schedule.move_operation('addsub1', -5)
schedule.move_operation('addsub4', -6)
schedule.move_operation('cmul4', -10)
schedule.move_operation('cmul2', -7)
schedule.move_operation('cmul1', -2)
schedule.move_operation('cmul3', -6)
schedule.move_operation('cmul5', -5)
schedule.move_operation('cmul1', -3)
schedule.move_operation('cmul5', -1)
schedule.set_schedule_time(13)
schedule.move_operation('bfly5', -6)
schedule.move_operation('bfly6', -1)
schedule.move_operation('cmul4', -6)
schedule.move_operation('addsub1', 4)
schedule.move_operation('cmul3', 4)
schedule.move_operation('cmul1', 3)
schedule.move_operation('bfly1', 3)
schedule.move_operation('cmul2', 5)
schedule.move_operation('cmul5', 4)
schedule.move_operation('addsub4', 4)
schedule.set_schedule_time(10)
schedule.move_operation('addsub1', -1)
schedule.move_operation('cmul4', 1)
schedule.move_operation('addsub4', -1)
schedule.move_operation('cmul5', -1)
schedule.move_operation('cmul2', -2)
schedule.move_operation('bfly6', -4)
schedule.move_operation('bfly1', -1)
schedule.move_operation('addsub1', -1)
schedule.move_operation('cmul1', -1)
schedule.move_operation('cmul2', -3)
schedule.move_operation('addsub2', -1)
schedule.move_operation('bfly2', -1)
schedule.move_operation('bfly1', -1)
schedule.move_operation('cmul1', -1)
schedule.move_operation('addsub2', -1)
schedule.move_operation('addsub4', -1)
schedule.move_operation('addsub4', -3)
schedule.move_operation('cmul4', -1)
schedule.move_operation('bfly1', -2)
schedule.move_operation('cmul2', -1)
schedule.move_operation('cmul1', -2)
schedule.move_operation('cmul5', -4)
schedule.move_operation('cmul1', 1)
schedule.move_operation('cmul3', -5)
schedule.move_operation('cmul5', 2)
schedule.move_operation('addsub3', -3)
schedule.move_operation('addsub1', -3)
schedule.move_operation('addsub2', -1)
schedule.move_operation('addsub3', -4)
schedule.move_operation('bfly2', -2)
schedule.move_operation('addsub5', -3)
schedule.move_operation('bfly3', -2)
schedule.show()

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
    mem.show(title=f"{memory.entity_name}")
    memory.assign("left_edge")
    memory.show_content(title=f"Assigned {memory.entity_name}")


arch = Architecture(
    {addsub, butterfly, multiplier, pe_in, pe_out},
    memories,
    direct_interconnects=direct,
)

arch
