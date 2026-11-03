Supporting types
================

Common types
------------

.. py:data:: b_asic.types.Name

   String used to name a graph component.

.. py:data:: b_asic.types.Num

   Numeric value accepted by B-ASIC, including Python, NumPy, and APyTypes values.

.. py:data:: b_asic.types.TypeName

   String identifying an operation type.

.. py:data:: b_asic.types.GraphID

   String identifying a graph component within an SFG.

.. py:data:: b_asic.types.GraphIDNumber

   Integer used for the numeric part of a graph ID.

Operation maps
--------------

.. py:data:: b_asic.operation.MutableResultMap

   Mutable mapping from result keys to numeric values or ``None``.

.. py:data:: b_asic.operation.MutableDelayMap

   Mutable mapping from result keys to numeric delay values.

Simulation results
------------------

.. py:data:: b_asic.simulation.ResultArrayMap

   Mapping from result keys to sequences of numeric values, one per iteration.

Operation selection
-------------------

.. py:data:: b_asic.sfg.OpSpecifier

   Graph ID, operation instance, or operation class used to select operations.
