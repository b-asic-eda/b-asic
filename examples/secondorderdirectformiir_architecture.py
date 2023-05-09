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
# Rescheudle to only require one adder and one multiplier
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
p_in = ProcessingElement(inputs, entity_name='in')
p_out = ProcessingElement(outputs, entity_name='out')

# %%
# Extract memory variables
mem_vars = schedule.get_memory_variables()
mem_vars.show(title="All memory variables")
direct, mem_vars = mem_vars.split_on_length()
direct.show(title="Direct interconnects")
mem_vars.show(title="Non-zero time memory variables")
mem_vars_set = mem_vars.split_on_ports(read_ports=1, write_ports=1, total_ports=2)

memories = set()
for i, mem in enumerate(mem_vars_set):
    memories.add(Memory(mem, entity_name=f"memory{i}"))
    mem.show(title=f"memory{i}")

# %%
# Create architecture
arch = Architecture({p1, p2, p_in, p_out}, memories, direct_interconnects=direct)

# %%
# The architecture can be rendered in enriched shells.
#
# .. graphviz::
#
#        digraph {
#             node [shape=record]
#             memory1 [label="{{<in0> in0}|memory1|{<out0> out0}}"]
#             memory0 [label="{{<in0> in0}|memory0|{<out0> out0}}"]
#             memory2 [label="{{<in0> in0}|memory2|{<out0> out0}}"]
#             in [label="{in|{<out0> out0}}"]
#             out [label="{{<in0> in0}|out}"]
#             cmul [label="{{<in0> in0}|cmul|{<out0> out0}}"]
#             adder [label="{{<in0> in0|<in1> in1}|adder|{<out0> out0}}"]
#             memory1:out0 -> adder:in1 [label=1]
#             cmul:out0 -> adder:in0 [label=1]
#             cmul:out0 -> memory0:in0 [label=3]
#             memory0:out0 -> adder:in0 [label=1]
#             adder:out0 -> adder:in1 [label=1]
#             memory1:out0 -> cmul:in0 [label=5]
#             memory0:out0 -> adder:in1 [label=2]
#             adder:out0 -> memory1:in0 [label=2]
#             adder:out0 -> out:in0 [label=1]
#             memory2:out0 -> adder:in0 [label=2]
#             cmul:out0 -> memory2:in0 [label=2]
#             in:out0 -> cmul:in0 [label=1]
#        }