"""
==========================================
Introduction example for the TSTE87 course
==========================================
"""
from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Delay, Input, Output

i = Input()
d = Delay()
o = Output(d)
c = ConstantMultiplication(0.5, d)
a = Addition(i, c)
d.input(0).connect(a)

sfg = SFG([i], [o])

# %%
# The SFG looks like:
sfg
