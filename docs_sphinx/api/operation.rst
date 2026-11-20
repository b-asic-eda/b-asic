********************
``b_asic.operation``
********************

Physical port sharing
=====================

Logical inputs and outputs have distinct physical ports by default. An arbitrary
operation can share physical ports without changing its type or signal connections::

    op = R2Butterfly(
        latency_offsets={"in0": 0, "in1": 1, "out0": 3, "out1": 4},
        execution_time=1,
    )
    op.set_port_mapping({"in0": 0, "in1": 0, "out0": 0, "out1": 0})

Input and output indices use separate namespaces. Specify all logical ports in
each direction being changed, with physical indices contiguous from zero. Omitted
directions keep their current mapping; ``op.set_port_mapping(None)`` resets both
directions to distinct ports. ``input_count`` and ``output_count`` still describe
logical ports; ``physical_input_count`` and ``physical_output_count`` describe the
hardware interface.

Use ``sfg.set_port_mapping_of_type(R2Butterfly, mapping)`` or
``sfg.set_port_mapping_of_type_name(R2Butterfly.type_name(), mapping)`` to configure
all matching operations in a graph. Copies and saved graphs preserve the mapping.

Resource assignment checks interface compatibility and physical port collisions,
including overlapping invocations and schedule wraparound. Architecture routing,
memory mux objectives, generated component interfaces, and top-level mux controls
use physical indices. Operation-specific arithmetic code must implement the declared
input/output timing and port sharing; configuring a mapping does not synthesize
that arithmetic implementation.

.. inheritance-diagram:: b_asic.operation
   :parts: 1
   :top-classes: b_asic.graph_component.GraphComponent, b_asic.port.SignalSourceProvider

.. automodule:: b_asic.operation
   :members:
   :undoc-members:
