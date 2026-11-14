****************************
``b_asic.code_printer.vhdl``
****************************

.. automodule:: b_asic.code_printer.vhdl
   :members:
   :undoc-members:

``vhdl_printer`` module
-----------------------

.. autoclass:: b_asic.code_printer.vhdl.vhdl_printer.VhdlPrinter
   :members: print, get_compile_order, print_vhdl_ls_toml
   :undoc-members:
   :no-index:

Streaming interfaces
--------------------

Interface selection belongs to code generation. It does not change the SFG or
its Input/Output operations. The default retains the fixed-interval synchronous
ports. For example::

    from b_asic.code_printer.vhdl.streaming import StreamInterface

    printer.print(
        architecture,
        path="hdl",
        interface=StreamInterface(
            protocol="axi4_stream",       # or "avalon_st", "synchronous"
            clock_mode="asynchronous",   # or "synchronous" (shared core clock)
            fifo_depth=64,
            startup_threshold=32,
            stallable=True,
            frame_length=1024,
        ),
        stream_inputs={"samples": ["input0", "input1"]},
        stream_outputs={"results": ["output0"]},
    )

Group members are **processing-element entity names**, not operation names.
Multiple operations already assigned to one input/output PE naturally share its
stream. Grouping several PEs combines their transfers in increasing schedule
order; each group must require at most one transfer per core cycle. The input
stream must supply samples in that order; there is no stream-ID routing.
Unlisted I/O PEs each receive a separate stream named after the PE.

Each stream has data, valid, ready, and TLAST/endofpacket ports. AXI names use
``<stream>_tdata``, ``_tvalid``, ``_tready``, and ``_tlast``. Avalon names use
``<stream>_data``, ``_valid``, ``_ready``, and ``_endofpacket``; Avalon ready
latency is zero. AXI data is padded to whole bytes with zero high bits; input
padding is ignored. Complex samples pack real bits below imaginary bits.
The sample widths follow the printer's input/output data types.

Each group gets its own input or output FIFO. A shared-clock interface uses a
synchronous FIFO (any positive depth). Independent-clock interfaces add a
``<stream>_clk`` port per stream and use Gray-coded pointers with two-stage
synchronizers; depth must be a power of two, at least four. The core always uses
``clk``. ``rst`` resets both sides, discards buffered data and framing state,
and clears errors. Assert reset across both clocks; release in the FIFO is
synchronized locally. Both clocks must run during reset recovery. Occupancy
flags in independent-clock mode include pointer synchronization delay. The
generated RAM uses show-ahead asynchronous reads; device-specific block RAM
inference is not guaranteed. Constrain Gray-pointer crossings with the target
tool's bus-skew/max-delay constraints and mark clocks as asynchronous; the
generator supplies synchronizer attributes, but does not generate device timing
constraints.

The core waits until **every input FIFO** reaches ``startup_threshold``. With
``stallable=True``, unavailable input samples or full output FIFOs disable the
entire core, including its schedule counter, memories, and enabled pipelines.
FIFO bus transfers continue during pauses, including when external ``en`` is
low. ``core_active`` indicates enabled core cycles. Custom arithmetic IP must
honor its enable for this mode to be safe. Optional top-level I/O registers
cannot be combined with streaming; the FIFOs provide the interface buffering.

With ``stallable=False``, the core runs at fixed intervals after startup. Empty
input FIFOs at scheduled reads or full output FIFOs at scheduled writes latch
``stream_error`` and stop further core execution until reset. Data from the
faulting cycle is invalid. Size the input threshold for a bounded source gap
and the output FIFO for the maximum downstream stall: no finite FIFO can
guarantee operation through an unlimited stall or sustained rate mismatch.
External ``en`` remains available for deliberate pauses; ``enable_pin=False``
removes it while retaining internal startup/fault/stall control.

Input TLAST/EOP is stored in the FIFO word. ``<stream>_core_last`` is meaningful
when ``<stream>_core_valid`` is high, identifying the sample consumed on the next
core rising edge. These signals expose framing to surrounding logic; the
arithmetic SFG does not itself interpret packet metadata. Output framing counts
successful core-to-FIFO writes and marks every ``frame_length``-th sample.
It stays aligned with data under backpressure. When ``frame_length=None``, the
output frame marker is always low; variable input packet boundaries are not
automatically propagated through arithmetic transformations.

``common`` module
-----------------

.. automodule:: b_asic.code_printer.vhdl.common
   :members:
   :undoc-members:

``memory_storage`` module
-------------------------

.. automodule:: b_asic.code_printer.vhdl.memory_storage
   :members:
   :undoc-members:

``processing_element`` module
-----------------------------

.. automodule:: b_asic.code_printer.vhdl.processing_element
   :members:
   :undoc-members:

``register_storage`` module
---------------------------

.. automodule:: b_asic.code_printer.vhdl.register_storage
   :members:
   :undoc-members:

``test_bench`` module
---------------------

.. automodule:: b_asic.code_printer.vhdl.test_bench
   :members:
   :undoc-members:

``top_level`` module
--------------------

.. automodule:: b_asic.code_printer.vhdl.top_level
   :members:
   :undoc-members:

``util`` module
---------------

.. automodule:: b_asic.code_printer.vhdl.util
   :members:
   :undoc-members:
