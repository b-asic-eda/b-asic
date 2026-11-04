"""
========================
Connecting multiple SFGs
========================

It is sometimes useful to create several SFGs and later on connect them.
One reason is using the SFG generators.

The resulting SFG can also be flattened, replacing nested SFGs with their
internal operations using :meth:`~b_asic.sfg.SFG.flatten`.

This example illustrates how it can be done.
"""

from b_asic.sfg_generators import wdf_allpass
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output

# Generate allpass branches for fifth-order LWDF filter
allpass1 = wdf_allpass([0.2, 0.5])
allpass2 = wdf_allpass([-0.5, 0.2, 0.5])

in_lwdf = Input()
out_lwdf = Output((allpass1(in_lwdf) + allpass2(in_lwdf)) * 0.5)

# Create SFG of LWDF with two internal SFGs
sfg_with_sfgs = SFG(
    in_lwdf, out_lwdf, name="LWDF with separate internals SFGs for allpass branches"
)

# %%
# The resulting SFG looks like:

sfg_with_sfgs

# %%
# Create a flattened LWDF without modifying the original SFGs.

flattened_sfg = sfg_with_sfgs.flatten()

# %%
# Resulting in:

flattened_sfg
