***********************
``b_asic.architecture``
***********************

.. inheritance-diagram:: b_asic.architecture
   :parts: 1
   :top-classes: b_asic.architecture.HardwareBlock

.. automodule:: b_asic.architecture
   :members:
   :undoc-members:
   :inherited-members:

``get_interconnects_for_memory`` returns two lists, indexed by the memory's
write and read ports respectively, like ``get_interconnects_for_pe``. Each
list entry maps ``(connected_resource, connected_port_index)`` to an access
count. Unused ports have empty dictionaries; memory-to-memory connections
are included.

Simultaneous accesses use distinct physical ports, except consumers reading
the same variable at the same delay, which share a broadcast read.
``Memory.port_assignment`` exposes the read and write ports selected by the
joint mux assignment strategies. The architecture retains these choices when
built or rebuilt from the assigned collections. Memories without an optimized
assignment allocate consecutive ports within each cycle. Adding or removing
processes through the collection's methods invalidates its saved port assignment.
With ``wire_labels=True``, multi-output memories and PEs use labels such as
``memory0_0`` and ``memory0_1``. The suffix is retained even if only one of
their outputs is connected.
