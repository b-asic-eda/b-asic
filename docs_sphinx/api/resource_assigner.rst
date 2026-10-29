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
   )

Both mux minimization strategies count physical connections, including inputs
with fan-in one, within the supplied resource budgets. The CP strategy supports
one read and one write port per memory, with ``memory_total_ports=1`` enforcing
a shared port. If resource budgets are omitted, greedy coloring supplies them;
these budgets can restrict the best achievable mux cost.
