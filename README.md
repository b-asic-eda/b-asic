![tests](https://github.com/b-asic-eda/b-asic/actions/workflows/tests.yml/badge.svg) [![codecov](https://codecov.io/gh/b-asic-eda/b-asic/graph/badge.svg?token=4OETEUSUCM)](https://codecov.io/gh/b-asic-eda/b-asic) ![GitHub License](https://img.shields.io/github/license/b-asic-eda/b-asic) [![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/b-asic-eda/b-asic/documentation.yml?label=documentation)](https://b-asic-eda.github.io/b-asic)

<img src="logos/logo.png" width="278" height="100">

B-ASIC is a Python framework for efficient hardware implementation of static algorithms.
It provides a path from algorithm to RTL code while giving the designer full control of every step.

## Documentation

**https://b-asic.org/**

## Installation

B-ASIC requires Python 3.12 or newer. Install the current source version with:

```bash
python -m pip install git+https://github.com/b-asic-eda/b-asic.git
```

This installs the core Python dependencies, including NumPy, SciPy, Matplotlib,
NetworkX, APyTypes, and PuLP with HiGHS. The native simulation extension is built
from C++ sources, so source installations need a C++17 compiler, such as GCC,
Clang, or MSVC. Pip installs the Python build requirements automatically.

Choose optional extras for the features you use. They can be combined in one
installation; for example, this enables the PySide6 GUIs, constraint-programming
schedulers, and LLVM import:

```bash
python -m pip install "b-asic[pyside6,cp,llvm] @ git+https://github.com/b-asic-eda/b-asic.git"
```

| Extra           | Features and Python dependencies                                                                                           |
| --------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `pyqt6`         | GUI support using PyQt6.                                                                                                   |
| `pyside6`       | GUI support using PySide6. Choose either this or `pyqt6`.                                                                  |
| `cp`            | Constraint-programming schedulers and resource assignment using CPMpy, OR-Tools, and compatible HiGHS bindings.            |
| `llvm`          | LLVM IR import and C/C++ frontends using llvmlite. Clang is needed to compile C/C++.                                       |
| `hdl`           | HDL testbench and simulation tools: cocotb and VUnit.                                                                      |
| `test`          | pytest, coverage, Qt testing, timeout, virtual-display, and parallel-test plugins. Add a Qt binding to run the full suite. |
| `test_optional` | Additional HDL test dependencies; currently the same packages as `hdl`.                                                    |
| `doc`           | Sphinx, the documentation theme, Sphinx-Gallery, and other documentation extensions.                                       |
| `dev`           | Meson-Python, Ninja, and pre-commit for development builds and checks.                                                     |

Some features also require system tools that pip does not install:

| System tool                                                                                           | When it is needed                                                                                                                                        |
| ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Graphviz](https://graphviz.org/download/) (`dot`)                                                    | Rendering SFGs and other graphs, including the examples below. The Python `graphviz` package alone does not provide it.                                  |
| [Clang](https://releases.llvm.org/) (`clang`)                                                         | Compiling C/C++ to LLVM IR. Reading an existing LLVM IR file only needs the `llvm` extra. Clang's output must be compatible with llvmlite's LLVM reader. |
| An HDL simulator, such as [GHDL](https://github.com/ghdl/ghdl) or [NVC](https://github.com/nickg/nvc) | Executing HDL simulations and the corresponding tests. Installing `hdl` does not install a simulator.                                                    |

Put the required executables on `PATH`. QtPy and QtAwesome are installed with
the core package, but a Qt binding is optional and must be selected through
`pyqt6` or `pyside6` to use the GUIs. Interactive Qt applications also need a
desktop display; Linux CI can use Xvfb for GUI tests.

The [C-to-SFG gallery example](galleries/examples/creating_and_transforming_sfgs/c_to_sfg.py)
shows a [C function](galleries/examples/creating_and_transforming_sfgs/llvm_kernel.c)
and its generated graph, and skips conversion if Clang is unavailable. See the
[LLVM import guide](docs_sphinx/llvm.rst) for source-writing restrictions and C++
`constexpr` examples.

For a development checkout with GUI, test, and documentation dependencies:

```bash
git clone https://github.com/b-asic-eda/b-asic.git
cd b-asic
python -m pip install meson-python ninja setuptools_scm
python -m pip install --no-build-isolation --editable ".[dev,test,doc,pyqt6,llvm]"
pre-commit install
pytest
python -m sphinx -b html docs_sphinx public
```

Add `cp` or `hdl` to the extras as needed. The documentation executes gallery
examples, so install Graphviz and Clang to render the LLVM example fully.
Further setup details are in the [contributing guide](docs_sphinx/contributing.rst).

## Example

```python
from b_asic import SFG, Delay, Input, Output

# Build the signal flow graph of a 7-tap FIR filter
x = Input(name="x")

d0 = Delay(x)
d1 = Delay(d0)
d2 = Delay(d1)
d3 = Delay(d2)
d4 = Delay(d3)
d5 = Delay(d4)

y = Output(
    0.5 * x + 0.25 * d0 + 0.25 * d1 + 0.5 * d2 + 0.25 * d3 + 0.25 * d4 + 0.5 * d5,
    name="y",
)

fir = SFG(x, y, name="7-tap FIR")
fir.show()
```

## Contributing

Contributions are very welcome.
Bug reports, feature requests, and pull requests are all appreciated.
See the [contributing guide](https://b-asic-eda.github.io/b-asic/contributing.html) for how to set up a development environment, run tests, and build the docs.

## License

B-ASIC is distributed under the [MIT license](LICENSE).
