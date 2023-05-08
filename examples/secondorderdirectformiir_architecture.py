"""
=====================================
Second-order IIR Filter with Schedule
=====================================

"""

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Delay, Input, Output

in1 = Input("IN1")
c0 = ConstantMultiplication(5, in1, "C0")
add1 = Addition(c0, None, "ADD1")
# Not sure what operation "Q" is supposed to be in the example
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
schedule.show()

# Rescheudle
schedule.move_operation('add4', 3)
schedule.move_operation('cmul5', -1)
schedule.move_operation('cmul4', -1)
schedule.move_operation('cmul5', -3)
schedule.move_operation('cmul4', -3)
schedule.move_operation('cmul4', -1)
schedule.move_operation('cmul6', -1)
schedule.move_operation('cmul6', -1)
schedule.move_operation('cmul3', 1)
schedule.move_operation('cmul4', 1)
schedule.move_operation('cmul5', -1)

# ARch
operations = schedule.get_operations()
adders = operations.get_by_type_name('add')
mults = operations.get_by_type_name('cmul')
inputs = operations.get_by_type_name('in')
outputs = operations.get_by_type_name('out')
p1 = ProcessingElement(adders, entity_name="adder")
p2 = ProcessingElement(mults, entity_name="cmul")
p_in = ProcessingElement(inputs, entity_name='in')
p_out = ProcessingElement(outputs, entity_name='out')

# Memories
mem_vars = schedule.get_memory_variables()
direct, mem_vars = mem_vars.split_on_length()
mem = Memory(mem_vars, entity_name="memory")

arch = Architecture({p1, p2, p_in, p_out}, {mem}, direct_interconnects=direct)
