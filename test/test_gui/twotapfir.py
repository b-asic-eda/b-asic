
"""
B-ASIC automatically generated SFG file.
Name: twotapfir
Last saved: 2023-01-24 14:38:17.654639.
"""
from b_asic import SFG, Signal, Input, Output, ConstantMultiplication, Delay, Input, Output, Addition
# Inputs:
in1 = Input(name="in1")

# Outputs:
out1 = Output(name="")

# Operations:
t1 = Delay(initial_value=0, name="")
cmul1 = ConstantMultiplication(value=0.5, name="cmul2", latency_offsets={'in0': None, 'out0': None})
add1 = Addition(name="add1", latency_offsets={'in0': None, 'in1': None, 'out0': None})
cmul2 = ConstantMultiplication(value=0.5, name="cmul", latency_offsets={'in0': None, 'out0': None})

# Signals:

Signal(source=t1.output(0), destination=cmul1.input(0))
Signal(source=in1.output(0), destination=t1.input(0))
Signal(source=in1.output(0), destination=cmul2.input(0))
Signal(source=cmul1.output(0), destination=add1.input(0))
Signal(source=add1.output(0), destination=out1.input(0))
Signal(source=cmul2.output(0), destination=add1.input(1))
twotapfir = SFG(inputs=[in1], outputs=[out1], name='twotapfir')

# SFG Properties:
prop = {'name':twotapfir}
positions = {'t1': (-209, 19), 'cmul1': (-95, 76), 'add1': (0, 95), 'cmul2': (-209, 114), 'out1': (76, 95), 'in1': (-323, 19)}
