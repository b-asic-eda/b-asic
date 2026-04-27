.. _codegen:

Code Generation
***************

Code generation using the B-ASIC toolbox.

One code printer is currently available:

- :class:`~b_asic.code_printer.VhdlPrinter` — generates a VHDL implementation of an architecture.

``VhdlPrinter``
===============

.. autoclass:: b_asic.code_printer.vhdl.vhdl_printer.VhdlPrinter
   :members: print, get_compile_order
   :undoc-members:

Internals
=========
.. toctree::
    :maxdepth: 1

    vhdl.rst
