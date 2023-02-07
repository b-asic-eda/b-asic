"""
B-ASIC signal generators

These can be used as input to Simulation to algorithmically provide signal values.
Especially, all classes defined here will act as a callable which accepts an integer
time index and returns the value at that time.

It is worth noting that the standard basic arithmetic operations do work on these,
so one can, e.g., write ``0.5 * Step()`` to get a step input with height 0.5.
This is handled by a number of private generator classes. Check out the source code
if you want more information.
"""

from math import pi, sin
from numbers import Number
from typing import Sequence


class SignalGenerator:
    """
    Base class for signal generators.

    Handles operator overloading and defined the ``__call__`` method that should
    be overridden.
    """

    def __call__(self, time: int) -> complex:
        raise NotImplementedError

    def __add__(self, other) -> "_AddGenerator":
        if isinstance(other, Number):
            return _AddGenerator(self, Constant(other))
        if isinstance(other, SignalGenerator):
            return _AddGenerator(self, other)
        raise TypeError(f"Cannot add {other!r} to {type(self)}")

    def __radd__(self, other) -> "_AddGenerator":
        if isinstance(other, Number):
            return _AddGenerator(Constant(other), self)
        raise TypeError(f"Cannot add {type(self)} to {other!r}")

    def __sub__(self, other) -> "_SubGenerator":
        if isinstance(other, Number):
            return _SubGenerator(self, Constant(other))
        if isinstance(other, SignalGenerator):
            return _SubGenerator(self, other)
        raise TypeError(f"Cannot subtract {other!r} from {type(self)}")

    def __rsub__(self, other) -> "_SubGenerator":
        if isinstance(other, Number):
            return _SubGenerator(Constant(other), self)
        raise TypeError(f"Cannot subtract {type(self)} from {other!r}")

    def __mul__(self, other) -> "_MulGenerator":
        if isinstance(other, Number):
            return _MulGenerator(self, Constant(other))
        if isinstance(other, SignalGenerator):
            return _MulGenerator(self, other)
        raise TypeError(f"Cannot multiply {type(self)} with {other!r}")

    def __rmul__(self, other) -> "_MulGenerator":
        if isinstance(other, Number):
            return _MulGenerator(Constant(other), self)
        raise TypeError(f"Cannot multiply {other!r} with {type(self)}")

    def __truediv__(self, other) -> "_DivGenerator":
        if isinstance(other, Number):
            return _DivGenerator(self, Constant(other))
        if isinstance(other, SignalGenerator):
            return _DivGenerator(self, other)
        raise TypeError(f"Cannot divide {type(self)} with {other!r}")

    def __rtruediv__(self, other) -> "_DivGenerator":
        if isinstance(other, Number):
            return _DivGenerator(Constant(other), self)
        raise TypeError(f"Cannot divide {other!r} with {type(self)}")


class Impulse(SignalGenerator):
    """
    Signal generator that creates an impulse at a given delay.

    Parameters
    ----------
    delay : int, default: 0
        The delay before the signal goes to 1 for one sample.
    """

    def __init__(self, delay: int = 0) -> None:
        self._delay = delay

    def __call__(self, time: int) -> complex:
        return 1 if time == self._delay else 0

    def __repr__(self):
        return f"Impulse({self._delay})" if self._delay else "Impulse()"


class Step(SignalGenerator):
    """
    Signal generator that creates a step at a given delay.

    Parameters
    ----------
    delay : int, default: 0
        The delay before the signal goes to 1.
    """

    def __init__(self, delay: int = 0) -> None:
        self._delay = delay

    def __call__(self, time: int) -> complex:
        return 1 if time >= self._delay else 0

    def __repr__(self):
        return f"Step({self._delay})" if self._delay else "Step()"


class Constant(SignalGenerator):
    """
    Signal generator that outputs a constant value.

    Parameters
    ----------
    constant : complex, default: 1.0
        The constant.
    """

    def __init__(self, constant: complex = 1.0) -> None:
        self._constant = constant

    def __call__(self, time: int) -> complex:
        return self._constant

    def __str__(self):
        return f"{self._constant}"


class ZeroPad(SignalGenerator):
    """
    Signal generator that pads a sequence with zeros.

    Parameters
    ----------
    data : 1-D array
        The data that should be padded.
    """

    def __init__(self, data: Sequence[complex]) -> None:
        self._data = data
        self._len = len(data)

    def __call__(self, time: int) -> complex:
        if 0 <= time < self._len:
            return self._data[time]
        return 0.0

    def __repr__(self):
        return f"ZeroPad({self._data})"


class Sinusoid(SignalGenerator):
    """
    Signal generator that generates a sinusoid.

    Parameters
    ----------
    frequency : float
        The normalized frequency of the sinusoid. Should normally be in the
        interval [0, 1], where 1 corresponds to half the sample rate.
    phase : float, default: 0
        The normalized phase offset.
    """

    def __init__(self, frequency: float, phase: float = 0.0) -> None:
        self._frequency = frequency
        self._phase = phase

    def __call__(self, time: int) -> complex:
        return sin(pi * (self._frequency * time + self._phase))

    def __repr__(self):
        return (
            f"Sinusoid({self._frequency}, {self._phase})"
            if self._phase
            else f"Sinusoid({self._frequency})"
        )


class _AddGenerator(SignalGenerator):
    """
    Signal generator that adds two signals.
    """

    def __init__(self, a: SignalGenerator, b: SignalGenerator) -> None:
        self._a = a
        self._b = b

    def __call__(self, time: int) -> complex:
        return self._a(time) + self._b(time)

    def __repr__(self):
        return f"{self._a} + {self._b}"


class _SubGenerator(SignalGenerator):
    """
    Signal generator that subtracts two signals.
    """

    def __init__(self, a: SignalGenerator, b: SignalGenerator) -> None:
        self._a = a
        self._b = b

    def __call__(self, time: int) -> complex:
        return self._a(time) - self._b(time)

    def __repr__(self):
        return f"{self._a} - {self._b}"


class _MulGenerator(SignalGenerator):
    """
    Signal generator that multiplies two signals.
    """

    def __init__(self, a: SignalGenerator, b: SignalGenerator) -> None:
        self._a = a
        self._b = b

    def __call__(self, time: int) -> complex:
        return self._a(time) * self._b(time)

    def __repr__(self):
        a = (
            f"({self._a})"
            if isinstance(self._a, (_AddGenerator, _SubGenerator))
            else f"{self._a}"
        )
        b = (
            f"({self._b})"
            if isinstance(self._b, (_AddGenerator, _SubGenerator))
            else f"{self._b}"
        )
        return f"{a} * {b}"


class _DivGenerator(SignalGenerator):
    """
    Signal generator that divides two signals.
    """

    def __init__(self, a: SignalGenerator, b: SignalGenerator) -> None:
        self._a = a
        self._b = b

    def __call__(self, time: int) -> complex:
        return self._a(time) / self._b(time)

    def __repr__(self):
        a = (
            f"({self._a})"
            if isinstance(self._a, (_AddGenerator, _SubGenerator))
            else f"{self._a}"
        )
        b = (
            f"({self._b})"
            if isinstance(
                self._b,
                (_AddGenerator, _SubGenerator, _MulGenerator, _DivGenerator),
            )
            else f"{self._b}"
        )
        return f"{a} / {b}"
