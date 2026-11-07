SFG GUI
=================

Editing graphs
--------------

Ports appear as connection points outside each operation box. Click a port to
start a wire, then click a compatible port to connect it, or drag between ports.
To branch an existing signal, start at an unconnected input and click or release
on the signal. Press Escape or right-click to cancel. Each input accepts one
signal; an output can feed several inputs.

Choose **Automatic layout** from the toolbar or Edit menu, or press **Ctrl+L**,
to arrange operations in signal-flow order. Feedback loops and disconnected
operations are supported. Graphs without saved positions are arranged when
loaded; saved positions are preserved. Newly added operations use free space.
Signals follow orthogonal routes around operation boxes and reroute when any
operation moves, flips, or rotates. Wires from the same output can share trunks of any length. Filled dots mark
where they branch. Wires from unrelated outputs use separate lanes where possible;
crossings between unrelated wires have no junction dot.

Select operations and press **R** to rotate clockwise by 90 degrees, or
**Shift+R** to rotate counterclockwise. Rotation is also available in the Edit
menu and an operation's context menu. Labels stay upright, and saved graphs
retain rotation as well as position and flip state.

Module contents
---------------

.. automodule:: b_asic.sfg_gui
   :members:
   :undoc-members:
   :show-inheritance:

Submodules
----------

sfg_gui.main\_window module
---------------------------

.. automodule:: b_asic.sfg_gui.main_window
   :members:
   :exclude-members: deque
   :undoc-members:
   :show-inheritance:

sfg_gui.arrow module
--------------------

.. automodule:: b_asic.sfg_gui.arrow
   :members:
   :undoc-members:
   :show-inheritance:

sfg_gui.drag\_button module
---------------------------

.. automodule:: b_asic.sfg_gui.drag_button
   :members:
   :undoc-members:
   :show-inheritance:

sfg_gui.gui\_interface module
-----------------------------

.. automodule:: b_asic.sfg_gui.gui_interface
   :members:
   :undoc-members:
   :show-inheritance:

sfg_gui.port\_button module
---------------------------

.. automodule:: b_asic.sfg_gui.port_button
   :members:
   :undoc-members:
   :show-inheritance:

sfg_gui.precedence\_graph\_window module
----------------------------------------

.. automodule:: b_asic.sfg_gui.precedence_graph_window
   :members:
   :undoc-members:
   :show-inheritance:

sfg_gui.properties\_window module
---------------------------------

.. automodule:: b_asic.sfg_gui.properties_window
   :members:
   :undoc-members:
   :show-inheritance:

sfg_gui.select\_sfg\_window module
----------------------------------

.. automodule:: b_asic.sfg_gui.select_sfg_window
   :members:
   :undoc-members:
   :show-inheritance:

sfg_gui.signal\_generator\_input module
---------------------------------------

.. inheritance-diagram:: b_asic.sfg_gui.signal_generator_input
   :parts: 1
   :top-classes: b_asic.sfg_gui.signal_generator_input.SignalGeneratorInput

.. automodule:: b_asic.sfg_gui.signal_generator_input
   :members:
   :undoc-members:
   :show-inheritance:

sfg_gui.simulate\_sfg\_window module
------------------------------------

.. automodule:: b_asic.sfg_gui.simulate_sfg_window
   :members:
   :undoc-members:
   :show-inheritance:

sfg_gui.simulation\_worker module
---------------------------------

.. automodule:: b_asic.sfg_gui.simulation_worker
   :members:
   :undoc-members:
   :show-inheritance:

sfg_gui.util\_dialogs module
----------------------------

.. automodule:: b_asic.sfg_gui.util_dialogs
   :members:
   :undoc-members:
   :show-inheritance:
