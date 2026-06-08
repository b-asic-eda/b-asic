Contributing
============

Contributions to B-ASIC are welcome, whether in the form of bug reports,
feature requests, documentation improvements, or code.

The development of B-ASIC happens at
`https://github.com/b-asic-eda/b-asic <https://github.com/b-asic-eda/b-asic>`__.
If you find a bug or have a feature request, please open an
`issue <https://github.com/b-asic-eda/b-asic/issues>`__. If you want to
contribute code or documentation, please open a
`pull request <https://github.com/b-asic-eda/b-asic/pulls>`__.

Development install
-------------------

To set up B-ASIC for development, clone the repository and install it in
editable mode together with the additional dependencies::

   git clone https://github.com/b-asic-eda/b-asic.git
   cd b-asic
   pip install meson-python ninja setuptools_scm
   pip install --no-build-isolation --editable ".[test,test_optional,doc,dev,hdl]"

Pre-commit hooks
----------------

B-ASIC uses `pre-commit <https://pre-commit.com/>`_ to run linting and
formatting checks before each commit. After installing the development
dependencies, enable the hooks with::

   pre-commit install

Running the tests
-----------------

The test suite can be run using `pytest <https://docs.pytest.org/>`_::

   pytest

Building the documentation
--------------------------
The documentation can be built using `Sphinx <https://www.sphinx-doc.org/>`_::

   cd docs_sphinx
   make html
