#!/usr/bin/env python3
"""
================================
LWDF first-order allpass section
================================

This has different latency offsets for the different inputs/outputs.
"""

from b_asic.core_operations import SymmetricTwoportAdaptor
from b_asic.schedule import Schedule
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Delay, Input, Output

in0 = Input()

d0 = Delay()
adaptor0 = SymmetricTwoportAdaptor(
    0.5, in0, d0, latency_offsets={"in0": 0, "in1": 1, "out0": 5, "out1": 6}
)
d0 <<= adaptor0.output(1)
out0 = Output(adaptor0.output(0))
adaptor0.execution_time = 2
sfg = SFG([in0], [out0])
schedule = Schedule(sfg)
schedule.show()
