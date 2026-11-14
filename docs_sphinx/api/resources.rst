********************
``b_asic.resources``
********************

Memory port allocation
----------------------

:meth:`~b_asic.resources.ProcessCollection.split_on_ports` supports the
following port configurations:

.. list-table:: Port constraints by allocation strategy
   :header-rows: 1
   :widths: 45 15 15 25

   * - Strategies
     - Read ports
     - Write ports
     - Total ports
   * - ``ilp_graph_color``, ``ilp_min_input_mux``, ``ilp_min_output_mux``, ``ilp_min_mux``
     - Positive integer
     - Positive integer
     - At least the larger read/write limit
   * - ``cp_graph_color``, ``cp_min_input_mux``, ``cp_min_output_mux``, ``cp_min_mux``
     - Positive integer
     - Positive integer
     - At least the larger read/write limit
   * - ``greedy_graph_color``, ``equitable_graph_color``
     - 1
     - 1
     - 1 or 2
   * - ``greedy_port_packing``, ``left_edge``, ``left_edge_min_pe_to_mem``, ``left_edge_min_mem_to_pe``
     - Positive integer
     - Positive integer
     - At least the larger read/write limit
   * - ``left_edge_min_mux``
     - Not implemented
     - Not implemented
     - Not implemented

The total port limit constrains the sum of reads and writes in each cycle.
If omitted, it defaults to the sum of the read and write limits. If supplied,
it also supplies the default for either omitted read or write limit.
CP strategies require the ``cp`` extra.

ILP and CP use the existing graph models, including clique-based symmetry
breaking, for one read port, one write port, and one or two total ports.
Other port configurations use per-cycle read, write, and combined-access
capacity constraints. If ``max_resources`` is omitted, their memory-count upper
bound comes from ``greedy_port_packing``. The mux objectives minimize distinct
PE-port-to-memory connections within that bound; they do not assign accesses
to individual physical memory ports.

For multiple read ports, use capacity-aware packing to obtain a feasible
upper bound on the memory count::

    memories = variables.split_on_ports(
        strategy="greedy_port_packing",
        read_ports=2,
        write_ports=1,
        total_ports=3,
        strat_params={"restarts": 8, "seed": 0},
    )
    upper_bound = len(memories)

The algorithm tries first-fit placement in start-time, decreasing-read-count,
and busy-cycle orders, plus ``restarts`` shuffled orders, and retains the
smallest assignment. The start-time order ensures that its memory count is
no worse than ``left_edge``. It does not guarantee an optimal memory count.
The ILP, CP, packing, and implemented ``left_edge`` strategies count accesses modulo
the schedule period, including multiple reads of a variable that fold into
the same cycle. They reject variables that cannot fit individually in a
memory; replication and automatic variable splitting are not performed.

.. automodule:: b_asic.resources
   :members:
   :undoc-members:

Internal allocation table
-------------------------

.. autoclass:: b_asic.resources._ForwardBackwardTable
