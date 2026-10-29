"""
==================
Two-tap FIR filter
==================
"""

from b_asic import SFG, Delay, Input, Output

# Inputs:
x = Input(name="x")

d0 = Delay(x)

y = Output(
    0.3 * x + 0.7 * d0,
    name="y",
)

twotapfir = SFG(inputs=[x], outputs=[y], name='twotapfir')
twotapfir
