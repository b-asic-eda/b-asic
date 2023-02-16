<img src="logos/logo.png" width="278" height="100">

# B-ASIC - Better ASIC Toolbox

B-ASIC is an ASIC toolbox for Python 3 that simplifies circuit design and optimization.

The latest documentation can be viewed at: https://da.gitlab-pages.liu.se/B-ASIC/index.html

## Development

How to build and debug the library during development.

### Prerequisites

The following packages are required in order to build the library:

-   [CMake](https://cmake.org/) 3.8+
-   gcc 7+/clang 7+/msvc 16+ (C++ 17 support)
-   [Python](https://python.org/) 3.8+
-   Python dependencies (install with `pip install -r requirements.txt` or they will be installed as part of the
    installation process):
    -   [Graphviz](https://graphviz.org/)
    -   [Matplotlib](https://matplotlib.org/)
    -   [NumPy](https://numpy.org/)
    -   [QtPy](https://github.com/spyder-ide/qtpy)
    -   [setuptools_scm](https://github.com/pypa/setuptools_scm/)
-   Qt 5 or 6, with Python bindings, one of:
    - pyside2
    - pyqt5
    - pyside6
    - pyqt6

During the compilation process, [fmtlib](https://github.com/fmtlib/fmt) and [pybind11](https://pybind11.readthedocs.io/) are used.

To build a binary distribution, the following additional packages are required:

-   Python:
    -   wheel

To run the test suite, the following additional packages are required:

-   Python (install with `pip install -r requirements_test.txt`):
    -   [pytest](https://pytest.org/)
    -   [pytest-qt](https://pytest-qt.readthedocs.io/)
    -   [pytest-mpl](https://github.com/matplotlib/pytest-mpl/)
    -   [pytest-cov](https://pytest-cov.readthedocs.io/en/latest/) (for testing with coverage)
    -   [pytest-xvfb](https://github.com/The-Compiler/pytest-xvfb) (for testing without showing windows on Linux, you will also need to install [xvfb](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml))
    -   [pytest-xdist](https://pytest-xdist.readthedocs.io/) (for parallel testing)

To generate the documentation, the following additional packages are required:

-   Python (install with `pip install -r requirements_doc.txt`):
    -   [Sphinx](https://www.sphinx-doc.org/)
    -   [Furo](https://pradyunsg.me/furo/)
    -   [numpydoc](https://numpydoc.readthedocs.io/)
    -   [Sphinx-Gallery](https://sphinx-gallery.github.io/)
    -   [SciPy](https://scipy.org/)

### Using CMake directly

How to build using CMake.

#### Configuring

In `B-ASIC`:

```
mkdir build
cd build
cmake ..
```

#### Building (Debug)

In `B-ASIC/build`:

```
cmake --build .
```

The output gets written to `B-ASIC/build/lib`.

#### Building (Release)

In `B-ASIC/build`:

```
cmake --build . --config Release
```

The output gets written to `B-ASIC/build/lib`.

### Using setuptools to create a package

How to create a package using setuptools that can be installed using pip.

#### Setup (Binary distribution)

In `B-ASIC`:

```
python3 setup.py bdist_wheel
```

The output gets written to `B-ASIC/dist/b_asic-<version>-<python_tag>-<abi_tag>-<platform_tag>.whl`.

#### Setup (Source distribution)

In `B-ASIC`:

```
python3 setup.py sdist
```

The output gets written to `B-ASIC/dist/b-asic-<version>.tar.gz`.

#### Installation (Binary distribution)

In `B-ASIC/dist`:

```
pip install b_asic-<version>-<python_tag>-<abi_tag>-<platform_tag>.whl
```

#### Installation (Source distribution)

In `B-ASIC/dist`:

```
pip install b-asic-<version>.tar.gz
```

### Running tests

How to run the tests using pytest in a virtual environment.

#### Linux/OS X

In `B-ASIC`:

```
python3 -m venv env
source env/bin/activate
pip install .
pytest
```

#### Windows

In `B-ASIC` (as admin):

```
python3 -m venv env
.\env\Scripts\activate.bat
pip install .
pytest
```

#### Test with coverage

```
pytest --cov=b_asic --cov-report=html test
```

#### Test including plots

```
pytest --mpl
```


### Generating documentation

```
sphinx-build -b html docs_sphinx docs_sphinx/_build
```
or in `B-ASIC/docs_sphinx`:
```
make html
```

The output gets written to `B-ASIC/docs_sphinx/_build`.

## Usage

How to build and use the library as a user.

### Installation

```
pip install .
```

### Importing

```
python3
>>> import b_asic as asic
>>> help(asic)
```

## License

B-ASIC is distributed under the MIT license.
See the included LICENSE file for more information.
