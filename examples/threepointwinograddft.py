"""Three-point Winograd DFT.
"""

from b_asic.core_operations import Addition, ConstantMultiplication, Subtraction
from b_asic.special_operations import Input, Output
from b_asic.signal_flow_graph import SFG
from b_asic.schedule import Schedule
from math import cos, pi, sin

u = -2*pi/3
c30 = cos(u) - 1
c31 = sin(u)


in0 = Input("x0")
in1 = Input("x1")
in2 = Input("x2")
a0 = in1 + in2
a1 = in1 - in2
a2 = a0 + in0
m0 = c30 * a0
m1 = c31 * a1
a3 = a2 + m0
a4 = a3 + m1
a5 = a3 - m1
out0 = Output(a2, "X0")
out1 = Output(a4, "X1")
out2 = Output(a5, "X2")

sfg = SFG(inputs=[in0, in1, in2], outputs=[out0, out1, out2],
          name="3-point Winograd DFT")

# Set latencies and exection times
sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
sfg.set_latency_of_type(Addition.type_name(), 1)
sfg.set_latency_of_type(Subtraction.type_name(), 1)
sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
sfg.set_execution_time_of_type(Addition.type_name(), 1)
sfg.set_execution_time_of_type(Subtraction.type_name(), 1)

schedule = Schedule(sfg, cyclic=True)
