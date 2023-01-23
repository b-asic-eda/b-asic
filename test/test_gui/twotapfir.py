
"""
B-ASIC automatically generated SFG file.
Name: twotapfir
Last saved: 2023-01-23 12:02:27.343483.
"""
from b_asic import SFG, Signal, Input, Output, ConstantMultiplication, Addition, Delay, Input, Output
# Inputs:
in1 = Input(name="")

# Outputs:
out1 = Output(name="")

# Operations:
cmul1 = ConstantMultiplication(value=0.5, name="cmul", latency_offsets={'in0': None, 'out0': None})
in1 = Input(name="")
add1 = Addition(name="", latency_offsets={'in0': None, 'in1': None, 'out0': None})
cmul2 = ConstantMultiplication(value=0.5, name="cmul2", latency_offsets={'in0': None, 'out0': None})
out1 = Output(name="")
t1 = Delay(initial_value=0, name="")
in1 = Input(name="")

# Signals:

Signal(source=cmul1.output(0), destination=add1.input(1))
Signal(source=in1.output(0), destination=cmul1.input(0))
Signal(source=in1.output(0), destination=t1.input(0))
Signal(source=add1.output(0), destination=out1.input(0))
Signal(source=cmul2.output(0), destination=add1.input(0))
Signal(source=t1.output(0), destination=cmul2.input(0))
twotapfir = SFG(inputs=[in1], outputs=[out1], name='twotapfir')

# SFG Properties:
prop = {'name':twotapfir}
positions = {'cmul1': (-181, -67), 'in1': (-264, -202), 'add1': (91, 93), 'cmul2': (-27, -66), 'out1': (216, 92), 't1': (-135, -204)}
