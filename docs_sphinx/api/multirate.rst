********************
``b_asic.multirate``
********************

Construct multi-rate graphs with :class:`~b_asic.special_operations.Expansion`
and :class:`~b_asic.special_operations.Compression`. Expansion inserts zeros;
compression retains one phase of every group of input samples. Both operations
accept a positive integer ``factor`` and an optional ``phase``.

:class:`~b_asic.simulation.Simulation` accepts these graphs directly. It normalizes
an internal copy into a graph that processes one common period per iteration.
The original graph remains available through ``simulation.sfg``. Input providers
use their own local sample indices, and saved result arrays contain consecutive
samples at each signal's own rate. Arrays for different signals can consequently
have different lengths.

For example, compression by three consumes three input samples and produces one
output sample per iteration. Expansion by three consumes one and produces three.
``input_samples_per_iteration`` and ``output_samples_per_iteration`` expose those
counts. Run methods return the last sample of each output in the last period.
Finite input arrays must contain whole periods and represent the same number
of periods across inputs; partial periods are currently rejected.

Call :meth:`~b_asic.sfg.SFG.to_single_rate` to obtain the normalized graph and its
phase mappings explicitly. The normalized graph contains ordinary operations,
zero constants, and Sinks on unused phases. It can be simplified with constant
and sink propagation before scheduling. The phase mappings refer to the graph
before simplification. Unfolding and state-space analysis also require the
normalized graph. For ``FastSimulation``, normalize explicitly and supply
one input provider per phase port; direct multi-rate execution uses the Python
``Simulation`` class.

.. automodule:: b_asic.multirate
   :members:
   :undoc-members:
   :show-inheritance:
