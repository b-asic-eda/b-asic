.. B-ASIC documentation master file, created by
   sphinx-quickstart on Fri Sep  2 20:10:06 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

B-ASIC's documentation
======================

B-ASIC is a toolbox for Python 3 that simplifies implementing application-specific
circuits, primarily aimed at signal processing algorithms for both standard-cell and
FPGA technology.

It was initially developed by a group of students to replace an existing Matlab
toolbox in a course commonly referred to as "the ASIC course" at
`Division of Computer Engineering <https://liu.se/en/organisation/liu/isy/da>`_,
`Linköping University <https://liu.se/>`_, Sweden.
Hence, the name "Better ASIC toolbox" = B-ASIC.

It was initiated and is currently maintained by
`Oscar Gustafsson <https://liu.se/en/employee/oscgu95>`_.

The development of B-ASIC happens at
`https://gitlab.liu.se/da/B-ASIC <https://gitlab.liu.se/da/B-ASIC>`_.

It is not yet fully functional, but several parts of the design flow works,
while others are missing/buggy. The goal is to have a working design path from
algorithm down to a HDL-description of a custom architecture. Once it becomes a
bit more mature, we expect to make it available on pypi and conda-forge so
that it will becomes easier to access.

To install B-ASIC, the currently preferred way is::

    git clone https://gitlab.liu.se/da/B-ASIC.git
    cd B-ASIC
    python -m pip install -e .

This will install in editable mode, which is beneficial since you then easily
can pull new changes without having to reinstall it. It also makes it easy to contribute
any improvements.

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

   self
   api/index
   sfg_gui
   scheduler_gui
   gui_utils
   codegen/index
   examples/index
   research
