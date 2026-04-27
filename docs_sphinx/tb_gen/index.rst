.. _tb_gen:

Testbench Generation
********************

Testbench generation using the B-ASIC toolbox.

Two testbench printers are available:

- :class:`~b_asic.tb_printer.CocotbPrinter` — generates a `cocotb <https://www.cocotb.org/>`_ testbench (Python).
- :class:`~b_asic.tb_printer.VhdlTbPrinter` — generates a VHDL testbench.

Both printers take simulation results produced by simulating ``schedule.sfg`` and drive the
generated architecture with the correct input stimuli, optionally asserting expected output values.

``CocotbPrinter``
=================

.. autoclass:: b_asic.tb_printer.cocotb.cocotb_printer.CocotbPrinter
   :members: print
   :undoc-members:

``VhdlTbPrinter``
=================

.. autoclass:: b_asic.tb_printer.vhdl.vhdl_tb_printer.VhdlTbPrinter
   :members: print
   :undoc-members:
