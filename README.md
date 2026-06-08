![tests](https://github.com/b-asic-eda/b-asic/actions/workflows/tests.yml/badge.svg) [![codecov](https://codecov.io/gh/b-asic-eda/b-asic/graph/badge.svg?token=4OETEUSUCM)](https://codecov.io/gh/b-asic-eda/b-asic) ![GitHub License](https://img.shields.io/github/license/b-asic-eda/b-asic) [![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/b-asic-eda/b-asic/documentation.yml?label=documentation)](https://b-asic-eda.github.io/b-asic)

<img src="logos/logo.png" width="278" height="100">

B-ASIC is a Python framework for efficient hardware implementation of static algorithms.
It provides a path from algorithm to RTL code while giving the designer full control of every step.

## Documentation

**https://b-asic.org/**

## Installation

```bash
pip install git+https://github.com/b-asic-eda/b-asic.git
```

A Qt binding is required for GUIs (optional feature) — install either `PyQt6` or `PySide6`:

```bash
pip install PyQt6
```

## Example

```python
from b_asic import SFG, Delay, Input, Output

# Build the signal flow graph of a 6-tap FIR filter
x = Input(name="x")

d0 = Delay(x); d1 = Delay(d0); d2 = Delay(d1)
d3 = Delay(d2); d4 = Delay(d3); d5 = Delay(d4)

y = Output(
    0.5*x + 0.25*d0 + 0.25*d1 + 0.5*d2 + 0.25*d3 + 0.25*d4 + 0.5*d5,
    name="y",
)

fir = SFG([x], [y], name="6-tap FIR")
fir.show()
```

## Contributing

Contributions are very welcome.
Bug reports, feature requests, and pull requests are all appreciated.
See the [contributing guide](https://b-asic-eda.github.io/b-asic/contributing.html) for how to set up a development environment, run tests, and build the docs.

## License

B-ASIC is distributed under the [MIT license](LICENSE).
