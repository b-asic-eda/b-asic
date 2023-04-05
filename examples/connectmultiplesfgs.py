#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
========================
Connecting multiple SFGs
========================

It is sometimes useful to create several SFGs and later on connect them.
One reason is using the SFG generators.

Although connecting several SFGs is rather straightforward, it is also of
interest to "flatten" the SFGs, i.e., get a resulting SFG not containing other
SFGs but the operations of these. To do this, one will have to use the
method :func:`~b_asic.signal_flow_graph.SFG.connect_external_signals_to_components`.

This example illustrates how this can be done.
"""

from b_asic.sfg_generators import wdf_allpass
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Input, Output

# Generate allpass branches for fifth-ordet LWDF filter
allpass1 = wdf_allpass([0.2, 0.5])
allpass2 = wdf_allpass([-0.5, 0.2, 0.5])

in_lwdf = Input()
allpass1 << in_lwdf
allpass2 << in_lwdf
out_lwdf = Output((allpass1 + allpass2) * 0.5)

# Create SFG of LWDF with two internal SFGs
sfg_with_sfgs = SFG(
    [in_lwdf], [out_lwdf], name="LWDF with separate internals SFGs for allpass branches"
)

# %%
# Rendering the SFG will result in something like:
#
# .. graphviz::
#
#   digraph {
#       rankdir=LR
#       in1 [shape=cds]
#       in1 -> sfg1
#       in1 -> sfg2
#       out1 [shape=cds]
#       cmul1 -> out1
#       sfg1 [shape=ellipse]
#       sfg1 -> add1
#       add1 [shape=ellipse]
#       sfg2 -> add1
#       sfg2 [shape=ellipse]
#       add1 -> cmul1
#       cmul1 [shape=ellipse]
#   }
#
# Now, to create a LWDF where the SFGs are flattened. Note that the original SFGs
# ``allpass1`` and ``allpass2`` currently cannot be printed etc after this operation.

allpass1.connect_external_signals_to_components()
allpass2.connect_external_signals_to_components()
flattened_sfg = SFG([in_lwdf], [out_lwdf], name="Flattened LWDF")

# %%
# Resulting in:
#
# .. graphviz::
#
#   digraph {
#       rankdir=LR
#       in1 [shape=cds]
#       in1 -> sym2p1
#       in1 -> sym2p4
#       out1 [shape=cds]
#       cmul1 -> out1
#       sym2p1 [shape=ellipse]
#       sym2p2 -> sym2p1
#       sym2p2 [shape=ellipse]
#       sym2p1 -> add1
#       add1 [shape=ellipse]
#       sym2p1 -> t1
#       t1 [shape=square]
#       t1 -> sym2p2
#       sym2p3 -> add1
#       sym2p3 [shape=ellipse]
#       add1 -> cmul1
#       cmul1 [shape=ellipse]
#       sym2p4 -> sym2p3
#       sym2p4 [shape=ellipse]
#       sym2p5 -> sym2p3
#       sym2p5 [shape=ellipse]
#       sym2p3 -> t2
#       t2 [shape=square]
#       t2 -> sym2p5
#       t3 -> sym2p5
#       t3 [shape=square]
#       sym2p5 -> t3
#       t4 -> sym2p4
#       t4 [shape=square]
#       sym2p4 -> t4
#       t5 -> sym2p2
#       t5 [shape=square]
#       sym2p2 -> t5
#   }
#
