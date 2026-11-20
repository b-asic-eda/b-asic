****************************
``b_asic.resource_assigner``
****************************

.. automodule:: b_asic.resource_assigner
   :members:
   :undoc-members:

The ``cp_min_mux`` strategy uses CPMpy with OR-Tools by default. Install the
optional dependencies with ``pip install 'b-asic[cp]'``. For example:

.. code-block:: python

   pes, memories, direct = assign_processing_elements_and_memories(
       schedule,
       strategy="cp_min_mux",
       memory_read_ports=1,
       memory_write_ports=1,
       memory_total_ports=2,
       max_mux_size=4,
       solver="ortools",
       strat_params={"time_limit": 60, "log_search_progress": False},
   )

Pass strategy-specific options through ``strat_params``. For example,
``strat_params={"restarts": 4, "seed": 42}`` configures ``greedy_min_mux``;
``strat_params={"coloring_strategy": "largest_first", "interchange": True}``
configures ``greedy_graph_color``. The supplied dictionary is not modified.

Long-lived memory variables
--------------------------

Variables with lifetimes longer than the schedule period are preserved by
default. The assigner repeats their memory accesses over the smallest integer
number of periods that can hold the longest lifetime. Each original iteration
still needs only its original writes and reads; no relay transfers are added.
PEs and direct interconnects keep their original period.

``chain_split_strategy=None`` (the default) preserves variables. Set it to
``"fixed"`` to request memory-to-memory chains with maximum-length segments,
or ``"min_ports"`` to greedily choose relay times using peak combined, read,
and write load, followed by squared combined load. Without an explicit
unfolding factor, each segment then fits in one schedule period. Both
strategies keep the minimum number of segments per variable; ``"min_ports"``
does not guarantee a globally optimal load.

To bound the memory control period, pass ``memory_unfolding_factor``. For
example, this allows two schedule periods of storage before splitting any
remaining long lifetimes::

    pes, memories, direct = assign_processing_elements_and_memories(
        schedule,
        memory_unfolding_factor=2,
        chain_split_strategy="min_ports",
    )

The factor must be a positive integer. If splitting is disabled, an explicit
factor that cannot hold the longest lifetime raises ``ValueError``. For manual
assignment, :meth:`~b_asic.resources.ProcessCollection.unfold` repeats the
memory variables before port and cell allocation, including reconnecting
existing relay chains. Unfold all connected chain variables together.

:class:`~b_asic.architecture.Architecture` exposes the original PE period as
``schedule_time`` and the memory period as ``memory_schedule_time``.
VHDL generation uses separate schedule counters and control ROMs when those
periods differ. Memory addresses and interconnect selectors follow the longer
period, while PE parameters retain the original period. Both counters pause
and reset together. Distributed control generation also supports these periods.

Memory port configurations
--------------------------

For multiport memories, use ``strategy="left_edge"`` with the desired
``memory_read_ports``, ``memory_write_ports``, and ``memory_total_ports``.
The assigner obtains a feasible memory-count upper bound using
``greedy_port_packing`` and reuses that assignment for the memories.
Processing elements still use left-edge allocation. Per-cycle reads, writes,
and their sum must fit the corresponding port limits. This is a heuristic
upper bound, not a proof of the minimum memory count.

``ilp_min_mux``, ``cp_min_mux``, and ``greedy_min_mux`` also support multiple read and write ports.
Their models enforce per-cycle read, write, and combined access capacities,
including accesses that wrap around the schedule. Missing multiport memory
bounds and ILP warm starts use ``greedy_port_packing``. Single-port models
retain their exclusion constraints and symmetry breaking; access groups can
only be fixed to distinct memories when their capacity is one.
All three mux strategies count connections between individual physical ports.
Different read ports of the same memory are distinct inputs to a destination
multiplexer. Each memory write port has its own multiplexer and its own
``max_mux_size`` limit. PE output and input indices and memory-to-memory relay
connections are included as well.

The ILP and CP models jointly choose each variable's memory and the physical
port for every read and write access. Simultaneous distinct accesses cannot
use the same port of the same memory. Consumers reading the same variable at
the same delay share one broadcast read. The selected ports are retained in
the assigned collections and exposed through ``Memory.port_assignment``, so
architecture connections, drawings, and multiplexer counts use the solution
selected by the model. Each key is ``(variable, delay)``, with ``None`` denoting
the write access.

``greedy_min_mux`` retains saturation coloring for single-port exclusions.
For multiport memories it combines unit-capacity exclusion groups with
per-cycle load counters, prioritizing variables that use busy cycles.
Initial placement, recoloring, and swaps all respect the read, write, and
combined limits. Swaps check the net load change in both memories together.
For each candidate resource assignment it also improves port allocation by
moving accesses to unused ports and swapping simultaneous accesses between
ports. These moves minimize fan-in violations before connection count.
The heuristic can fail within the supplied resource bounds even when a
feasible assignment exists; more restarts or an exact strategy may help.

The other joint assignment strategies require one read port, one write port,
and one or two total ports. Missing bounds use graph coloring for
single-read/single-write memories. Supplied bounds skip those estimates,
except that ``ilp_min_mux`` retains heuristic colorings for warm starts.
``left_edge`` computes its assignments directly without preliminary bounds,
and ``greedy_graph_color`` reuses its final colorings as any missing bounds.

All three mux minimization strategies count physical connections, including inputs
with fan-in one, within the supplied resource budgets, with
``memory_total_ports=1`` enforcing a shared port. If resource budgets are
omitted, greedy coloring or port packing supplies them;
these budgets can restrict the best achievable mux cost.
