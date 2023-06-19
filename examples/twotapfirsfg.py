"""
==================
Two-tap FIR filter
==================
"""
from b_asic import (
    SFG,
    Addition,
    ConstantMultiplication,
    Delay,
    Input,
    Output,
    Signal,
)

# Inputs:
in0 = Input(name="in_0")

# Outputs:
out0 = Output(name="out0")

# Operations:
t0 = Delay(initial_value=0, name="t0")
cmul0 = ConstantMultiplication(
    value=0.5, name="cmul0", latency_offsets={'in0': None, 'out0': None}
)
add0 = Addition(
    name="add0", latency_offsets={'in0': None, 'in1': None, 'out0': None}
)
cmul1 = ConstantMultiplication(
    value=0.5, name="cmul1", latency_offsets={'in0': None, 'out0': None}
)

# Signals:

Signal(source=t0.output(0), destination=cmul0.input(0))
Signal(source=in0.output(0), destination=t0.input(0))
Signal(source=in0.output(0), destination=cmul1.input(0))
Signal(source=cmul0.output(0), destination=add0.input(0))
Signal(source=add0.output(0), destination=out0.input(0))
Signal(source=cmul1.output(0), destination=add0.input(1))
twotapfir = SFG(inputs=[in0], outputs=[out0], name='twotapfir')

# SFG Properties:
prop = {'name': twotapfir}
positions = {
    't0': (-209, 19),
    'cmul0': (-95, 76),
    'add0': (0, 95),
    'cmul1': (-209, 114),
    'out0': (76, 95),
    'in0': (-323, 19),
}
