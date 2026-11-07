SFG GUI
=================

Editing graphs
--------------

Hold the middle mouse button and drag to pan the canvas, including when starting
over an operation or a wire. The mouse wheel scrolls, and **Ctrl+wheel** zooms.
Press **F** to zoom to fit the graph.
Press **G** or choose **Show grid** in the View menu to toggle the placement
grid. Each point is one screen pixel at every zoom level. When zoomed out,
grid points are subsampled to keep dots at least five pixels apart.
Grid visibility does not change snapping.
The base grid size is ``GRID`` in ``sfg_gui/_preferences.py`` (8 scene units).
Operation sizes, port positions and stubs are derived from it. Dragging snaps
the visible upper-left corner of an operation's box, including after rotation;
automatic placement uses the same grid. Saved positions are retained when loading
older graphs: drag a node or apply **Automatic layout** to align them to this grid.

Ports appear as connection points outside each operation box. Click a port to
start a wire, then click a compatible port to connect it, or drag between ports.
Click anywhere along a signal to start a branch at that point, then click an
input port, or drag from the signal to the input. You can also start at an
unconnected input and finish on a signal. Junction dots mark the selected
branch points and follow the wire when it moves. Press Escape or right-click
to cancel. Each input accepts one
signal; an output can feed several inputs.

Twoport WDF adaptors default to 90° rotation: port 0's input/output pair is
on top and port 1's pair is on the bottom. On both sides, the input is on the
left and the output is on the right. Their rectangular boxes have the long
edge along these I/O pairs. Threeport boxes are squares with the same side
length as the long edge of a twoport box. Automatic layout uses this orientation.
Threeport adaptors pair input/output 0 on the left, pair 1 on the right, and
pair 2 on the bottom. Stub arrowheads distinguish incoming and outgoing waves.
Flipping mirrors the layout; rotation turns it. Explicit saved orientations
are retained when loading. Other operations retain inputs on the left and
outputs on the right in their default orientation.

Choose **Automatic layout** from the toolbar or Edit menu, or press **Ctrl+L**,
to arrange operations in signal-flow order. Feedback loops and disconnected
operations are supported. Feedback sections form compact blocks, and parallel
branches occupy separate bands so their operations stay together. Automatic
layout chooses rotation and flip settings for left-to-right forward paths.
Feedback loops whose external input and output meet at the same operation
stack vertically from that entry, with delays in a parallel return lane. Their
Input and Output symbols stay near the entry. Other feedback loops retain a
horizontal forward path, with flipped delays along the return path.
Outputs and Sinks align with the actual port generating their signal, rather
than taking separate rows below the graph. Constants and DontCare operations
are placed near the inputs using them; Sinks can sit on either side of their
producer. These local terminals do not create extra branch bands. Graphs without saved positions are arranged when
loaded; saved positions and orientations are preserved when loading. Newly
added operations use free space.
Signals follow orthogonal routes around operation boxes and reroute when any
operation moves, flips, or rotates. Wires from the same output can share trunks of any length. Filled dots mark
where they branch. Wires from unrelated outputs use separate lanes where possible;
crossings between unrelated wires have no junction dot.
Routing can leave a port sideways when its normal exit is obstructed and keeps
parallel lanes apart where space permits. Aligned ports connect directly when
the segment is clear. Other ports, including unconnected ones, are obstacles.
Otherwise the first bend can occur one grid step beyond the port.
During dragging, unaffected routes are reused. Signals attached to the moved
operation or near its old/new box and ports are rerouted together with their
fanout branches, while unchanged wires reserve their lanes. Releasing the mouse
runs a full routing pass to restore the complete layout optimization.
Placement and routing run in the ``b_asic._sfg_gui`` C++ extension, built with
pybind11 by the existing Meson build. It does not depend on Qt. Each editor
retains its graph, operation and port geometry, branches, and route buffers in
one native engine. Python sends changed records and paints only returned path
updates; unchanged paths stay in the engine between events. Native computations
release the Python GIL and serialize access to each engine's state.
The terminal roles are defined by the extension's ``TerminalKind`` enum and
passed through the GUI adapter. Python contains no separate placement or routing
implementation.

If overlapping operations cover a
terminal, a dashed signal marks the blocked connection instead of hiding it;
moving the obstruction restores normal routing.

Select operations and press **R** to rotate clockwise by 90 degrees, or
**Shift+R** to rotate counterclockwise. Rotation is also available in the Edit
menu and an operation's context menu. Labels stay upright, and saved graphs
retain rotation as well as position and flip state.

Choose **Flip horizontal** or **Flip vertical** in the Edit menu to mirror each
selected operation left/right or top/bottom about its own center. Both actions
have shortcuts **H** and **V**, respectively, and are also available in an
operation's context menu. The axes follow the canvas,
including for rotated operations; symbols and labels remain upright. Flips
are preserved when saving and loading graphs.

Operation symbols
-----------------

Operation icons are transparent SVGs rendered directly in the graphics scene,
so their edges remain sharp when zooming or exporting at larger sizes.
Input and output have pentagonal road-sign outlines with no inner symbol.
The point follows the terminal when flipping or rotating the operation.
Selection changes the box background and keeps the same icon.
Operation glyphs stay upright as their boxes rotate.
Delay boxes are 75% of the standard operation size.
Small arrowheads on the port stubs show signal direction,
including on flipped or rotated operations.

.. list-table:: Symbol set
   :header-rows: 1
   :widths: 60 40

   * - Operation
     - Symbol
   * - Delay
     - T
   * - DontCare / Sink
     - Small circular node, without an inner symbol
   * - Addition / subtraction / multiplication / division
     - + / − / × / ÷
   * - Constant / constant multiplication
     - c / k×
   * - Square root / magnitude / complex conjugate
     - √ / |x| / x*
   * - Minimum / maximum
     - min / max
   * - Symmetric twoport adaptor
     - Line with a central dot and two vertical bars
   * - Series twoport / threeport adaptor
     - Horizontal line with a central dot
   * - Parallel twoport adaptor
     - Two vertical bars
   * - Reflection-free series threeport adaptor
     - Series glyph, with a T mark at reflection-free port 1
   * - Custom operation
     - f(x)

Adaptor glyphs follow Figures 3.15, 3.18, 3.20 and 3.23 in
`Studies on Circulator-Tree Wave Digital Filters <https://www.diva-portal.org/smash/get/diva2:274001/FULLTEXT01.pdf>`_.
The reflection-free T marker sits outside the box between port 1's input and
output stubs. It rotates with that port, independently of the upright central
glyph.

The operation palette includes **WDF operations** and **FFT operations** groups.
Click an operation to insert it; **Ctrl+R** refreshes all built-in groups.

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
