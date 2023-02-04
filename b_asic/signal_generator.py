"""
B-ASIC signal generators

These can be used as input to Simulation to algorithmically provide signal values.
"""

from math import pi, sin
from numbers import Number
from typing import Callable, Sequence


class SignalGenerator:
    def __call__(self, time: int) -> complex:
        raise NotImplementedError

    def __add__(self, other) -> "AddGenerator":
        if isinstance(other, Number):
            return AddGenerator(self, Constant(other))
        return AddGenerator(self, other)

    def __radd__(self, other) -> "AddGenerator":
        if isinstance(other, Number):
            return AddGenerator(self, Constant(other))
        return AddGenerator(self, other)

    def __sub__(self, other) -> "SubGenerator":
        if isinstance(other, Number):
            return SubGenerator(self, Constant(other))
        return SubGenerator(self, other)

    def __rsub__(self, other) -> "SubGenerator":
        if isinstance(other, Number):
            return SubGenerator(Constant(other), self)
        return SubGenerator(other, self)

    def __mul__(self, other) -> "MulGenerator":
        if isinstance(other, Number):
            return MultGenerator(self, Constant(other))
        return MultGenerator(self, other)

    def __rmul__(self, other) -> "MulGenerator":
        if isinstance(other, Number):
            return MultGenerator(self, Constant(other))
        return MultGenerator(self, other)


class Impulse(SignalGenerator):
    """
    Signal generator that creates an impulse at a given delay.

    Parameters
    ----------
    delay : int, default: 0
        The delay before the signal goes to 1 for one sample.
    """

    def __init__(self, delay: int = 0) -> Callable[[int], complex]:
        self._delay = delay

    def __call__(self, time: int) -> complex:
        return 1 if time == self._delay else 0


class Step(SignalGenerator):
    """
    Signal generator that creates a step at a given delay.

    Parameters
    ----------
    delay : int, default: 0
        The delay before the signal goes to 1.
    """

    def __init__(self, delay: int = 0) -> Callable[[int], complex]:
        self._delay = delay

    def __call__(self, time: int) -> complex:
        return 1 if time >= self._delay else 0


class Constant(SignalGenerator):
    """
    Signal generator that outputs a constant value.

    Parameters
    ----------
    constant : complex, default: 1.0
        The constant.
    """

    def __init__(self, constant: complex = 1.0) -> Callable[[int], complex]:
        self._constant = constant

    def __call__(self, time: int) -> complex:
        return self._constant


class ZeroPad(SignalGenerator):
    """
    Signal generator that pads a sequence with zeros.

    Parameters
    ----------
    data : 1-D array
        The data that should be padded.
    """

    def __init__(self, data: Sequence[complex]) -> Callable[[int], complex]:
        self._data = data
        self._len = len(data)

    def __call__(self, time: int) -> complex:
        if 0 <= time < self._len:
            return self._data[time]
        return 0.0


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

    def __init__(
        self, frequency: float, phase: float = 0.0
    ) -> Callable[[int], complex]:
        self._frequency = frequency
        self._phase = phase

    def __call__(self, time: int) -> complex:
        return sin(pi * (self._frequency * time + self._phase))


class AddGenerator:
    """
    Signal generator that adds two signals.
    """

    def __init__(
        self, a: SignalGenerator, b: SignalGenerator
    ) -> Callable[[int], complex]:
        self._a = a
        self._b = b

    def __call__(self, time: int) -> complex:
        return self._a(time) + self._b(time)


class SubGenerator:
    """
    Signal generator that subtracts two signals.
    """

    def __init__(
        self, a: SignalGenerator, b: SignalGenerator
    ) -> Callable[[int], complex]:
        self._a = a
        self._b = b

    def __call__(self, time: int) -> complex:
        return self._a(time) - self._b(time)


class MultGenerator:
    """
    Signal generator that multiplies two signals.
    """

    def __init__(
        self, a: SignalGenerator, b: SignalGenerator
    ) -> Callable[[int], complex]:
        self._a = a
        self._b = b

    def __call__(self, time: int) -> complex:
        return self._a(time) * self._b(time)