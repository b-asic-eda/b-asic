<img src="logo.png" width="278" height="100">

# B-ASIC - Better ASIC Toolbox

B-ASIC is an ASIC toolbox for Python 3 that simplifies circuit design and optimization.

The latest documentation can be viewed at: https://da.gitlab-pages.liu.se/B-ASIC/index.html

## Development

How to build and debug the library during development.

### Prerequisites

The following packages are required in order to build the library:

-   cmake 3.8+
-   gcc 7+/clang 7+/msvc 16+
-   fmtlib
-   pybind11 2.3.0+
-   python 3.6+
-   Python:
    -   graphviz
    -   matplotlib
    -   numpy
    -   pybind11
    -   pyside2
    -   qtpy
    -   setuptools
    -   setuptools_scm

To build a binary distribution, the following additional packages are required:

-   Python:
    -   wheel

To run the test suite, the following additional packages are required:

-   Python (install with `pip install -r requirements_test.txt`):
    -   pytest
    -   pytest-qt
    -   pytest-mpl
    -   pytest-cov (for testing with coverage)
    -   pytest-xvfb (for testing without showing windows on Linux)
    -   pytest-xdist (for parallel testing)

To generate the documentation, the following additional packages are required:

-   Python (install with `pip install -r requirements_doc.txt`):
    -   sphinx
    -   furo
    -   numpydoc

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

In `B-ASIC/docs_sphinx`:

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
