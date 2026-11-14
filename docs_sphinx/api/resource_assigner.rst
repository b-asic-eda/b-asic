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

Both mux minimization strategies count physical connections, including inputs
with fan-in one, within the supplied resource budgets. The CP strategy supports
one read and one write port per memory, with ``memory_total_ports=1`` enforcing
a shared port. If resource budgets are omitted, greedy coloring supplies them;
these budgets can restrict the best achievable mux cost.
