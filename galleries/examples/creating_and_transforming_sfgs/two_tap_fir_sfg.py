"""
==================
Two-tap FIR filter
==================
"""

from b_asic import SFG, Delay, Input, Output

x = Input(name="x")

d0 = Delay(x)

y = Output(
    0.3 * x + 0.7 * d0,
    name="y",
)

fir = SFG(inputs=[x], outputs=[y], name='fir')
fir
