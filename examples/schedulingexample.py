"""
====================================================
Example SFG used for scheduling in the TSTE87 course
====================================================

Node numbering from the original SFG used with the Matlab toolbox::

    sfg=addoperand([],'in',1,1);
    sfg=addoperand(sfg,'constmult',1,1,2,0.25);
    sfg=addoperand(sfg,'constmult',2,4,5,0.75);
    sfg=addoperand(sfg,'add',1,[2 1],6);
    sfg=addoperand(sfg,'add',2,[2 5],3);
    sfg=addoperand(sfg,'add',3,[6 4],7);
    sfg=addoperand(sfg,'delay',1,3,4);
    sfg=addoperand(sfg,'out',1,7);
"""
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Delay, Input, Output

node1 = Input()
node2 = node1 * 0.25
node6 = node2 + node1
node4 = Delay()
node7 = node6 + node4
out = Output(node7)
node5 = 0.75 * node4
node3 = node2 + node5
node4 <<= node3

sfg = SFG([node1], [out], name="Scheduling example")
# %%
# The SFG looks like
sfg
