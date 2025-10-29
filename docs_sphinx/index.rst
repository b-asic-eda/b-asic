.. B-ASIC documentation master file, created by
   sphinx-quickstart on Fri Sep  2 20:10:06 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to the documentation of B-ASIC!
=======================================

B-ASIC is a Python library for the design and implementation of static algorithms that simplifies
the writing of efficient RTL code targeting both standard-cell and FPGA technologies.

The goal is to have a working design path from algorithm down to an HDL-description of a custom architecture.
Once it becomes a bit more mature, we expect to make it available on PyPI and conda-forge
such that it will become easier to access.

To install B-ASIC, the currently preferred way is::

    git clone https://github.com/b-asic-eda/b-asic.git
    cd B-ASIC
    python -m pip install .

In addition to the dependencies that are automatically installed, you will also
need a Qt-binding, but you are free to choose between PyQt6 and PySide6.
See `https://gitlab.liu.se/da/B-ASIC <https://gitlab.liu.se/da/B-ASIC>`_ for more info.

If you use B-ASIC in a publication, please acknowledge it. Later on there will be a
citation provided, but right now, please refer to this documentation or the repository.
We will also maintain a list of publications that have used B-ASIC.

.. toctree::
   :maxdepth: 2
   :caption: Contents:



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

Table of Contents
^^^^^^^^^^^^^^^^^
.. toctree::
   :maxdepth: 1

   api/index
   sfg_gui
   scheduler_gui
   gui_utils
   codegen/index
   examples/index
   research

Development
===========

B-ASIC is developed at the `Division of Electronics and Computer Engineering <https://liu.se/en/organisation/liu/isy/elda>`__,
`Linköping University <https://liu.se/>`__, Sweden, where it was initiated by `Oscar Gustafsson <https://liu.se/en/employee/oscgu95>`__.

The development of B-ASIC happens at
`https://github.com/b-asic-eda/b-asic <https://github.com/b-asic-eda/b-asic>`__.
