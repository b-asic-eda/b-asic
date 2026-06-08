.. B-ASIC documentation master file, created by
   sphinx-quickstart on Fri Sep  2 20:10:06 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

B-ASIC Documentation
====================

B-ASIC is a Python framework for efficient implementation of static algorithms.
It provides a path from algorithm to RTL code while giving the designer full control of every step.

.. admonition:: Install B-ASIC

    .. code-block:: console

      $ pip install git+https://github.com/b-asic-eda/b-asic.git

.. note::

   A Qt binding is required for GUIs.
   This is not installed automatically, so you need to install either `PyQt6
   <https://pypi.org/project/PyQt6/>`_ or `PySide6
   <https://pypi.org/project/PySide6/>`_, e.g.::

      pip install PyQt6

To get started with B-ASIC, head over to the :doc:`tutorial/index`, which
walks through the core concepts step by step. Once you are comfortable with
the basics, the :doc:`examples/index` showcase a range of complete designs
that you can use as a starting point for your own work.

If you use B-ASIC in a publication, please acknowledge it.
See :doc:`publications` for how to cite B-ASIC and a list of publications that have used it.

.. toctree::
   :maxdepth: 1
   :hidden:

   tutorial/index
   examples/index

.. toctree::
   :maxdepth: 3
   :hidden:

   api/index

.. toctree::
   :maxdepth: 1
   :hidden:

   publications

.. toctree::
   :maxdepth: 1
   :hidden:

   contributing

Development
===========

B-ASIC is developed by the `Division of Electronics and Computer Engineering <https://liu.se/en/organisation/liu/isy/elda>`__ at `Linköping University <https://liu.se/>`__.

.. image:: _static/liu-white.svg
   :class: only-dark

.. image:: _static/liu-black.svg
   :class: only-light
