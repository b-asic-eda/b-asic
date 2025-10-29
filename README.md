![tests](https://github.com/b-asic-eda/b-asic/actions/workflows/tests.yml/badge.svg) [![codecov](https://codecov.io/gh/b-asic-eda/b-asic/graph/badge.svg?token=4OETEUSUCM)](https://codecov.io/gh/b-asic-eda/b-asic) ![GitHub License](https://img.shields.io/github/license/b-asic-eda/b-asic) [![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/b-asic-eda/b-asic/documentation.yml?label=documentation)](https://b-asic-eda.github.io/b-asic)

<img src="logos/logo.png" width="278" height="100">

# B-ASIC - Better ASIC Toolbox

B-ASIC is a Python library for the design and implementation of static algorithms that simplifies the writing of efficient RTL code targeting both standard-cell and FPGA technologies.

The latest documentation can be viewed at: https://b-asic-eda.github.io/b-asic/

## Development

How to build and debug the library during development.

### Prerequisites

The following packages are required in order to build the library:

- [Python](https://python.org/) 3.10+
- Python dependencies (will be installed as part of the
  installation process):
  - [APyTypes](https://github.com/apytypes/apytypes)
  - [Graphviz](https://graphviz.org/)
  - [Matplotlib](https://matplotlib.org/)
  - [natsort](https://github.com/SethMMorton/natsort)
  - [NetworkX](https://networkx.org/)
  - [NumPy](https://numpy.org/)
  - [PuLP](https://github.com/coin-or/pulp)
  - [QtAwesome](https://github.com/spyder-ide/qtawesome/)
  - [QtPy](https://github.com/spyder-ide/qtpy)
  - [setuptools_scm](https://github.com/pypa/setuptools_scm/)
- Qt 6, with Python bindings, one of: (install with `pip install ."[$BINDING_NAME]"`)
  - pyqt6
  - pyside6

During the compilation process, [fmtlib](https://github.com/fmtlib/fmt) and [pybind11](https://pybind11.readthedocs.io/) are used.

To build a binary distribution, the following additional packages are required:

- Python:
  - wheel

To run the test suite, the following additional packages are required:

- Python (installed with `pip install ."[test]"`):
  - [pytest](https://pytest.org/)
  - [pytest-qt](https://pytest-qt.readthedocs.io/)
  - [pytest-mpl](https://github.com/matplotlib/pytest-mpl/)
  - [pytest-cov](https://pytest-cov.readthedocs.io/en/latest/) (for testing with coverage)
  - [pytest-xvfb](https://github.com/The-Compiler/pytest-xvfb) (for testing without showing windows on Linux, you will also need to install [xvfb](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml))
  - [pytest-xdist](https://pytest-xdist.readthedocs.io/) (for parallel testing)
  - [SciPy](https://scipy.org/)

To generate the documentation, the following additional packages are required:

- Python (installed with `pip install ."[doc]"`):
  - [Sphinx](https://www.sphinx-doc.org/)
  - [Furo](https://pradyunsg.me/furo/)
  - [numpydoc](https://numpydoc.readthedocs.io/)
  - [Sphinx-Gallery](https://sphinx-gallery.github.io/)
  - [mplsignal](https://mplsignal.readthedocs.io/)
  - [sphinx-copybutton](https://sphinx-copybutton.readthedocs.io/)

### Running tests

How to run the tests using pytest in a virtual environment.

#### Linux/OS X

In `B-ASIC`:

```bash
python3 -m venv env
source env/bin/activate
pip install ."[test]"
pytest
```

#### Windows

In `B-ASIC` (as admin):

```bash
python3 -m venv env
.\env\Scripts\activate.bat
pip install ."[test]"
pytest
```

#### Test with coverage

```bash
pytest --cov=b_asic --cov-report=html test
```

#### Generate new baseline images for the tests

In `B-ASIC`:

```bash
pytest      # The image comparison tests will fail
cp -a result_images/* test/baseline_images/
```

### Generating documentation

```bash
sphinx-build -b html docs_sphinx docs_sphinx/_build
```

or in `B-ASIC/docs_sphinx`:

```bash
make html
```

The output gets written to `B-ASIC/docs_sphinx/_build`.

## Usage

How to build and use the library as a user.

### Installation

```bash
pip install ."[pyqt6]"
```

or

```bash
pip install ."[pyside6]"
```

### Importing

```bash
python3
>>> import b_asic
>>> help(b_asic)
```

## License

B-ASIC is distributed under the MIT license.
See the included LICENSE file for more information.
