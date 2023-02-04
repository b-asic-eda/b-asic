from math import sqrt

import pytest

from b_asic.signal_generator import Constant, Impulse, Sinusoid, Step, ZeroPad


def test_impulse():
    g = Impulse()
    assert g(-1) == 0
    assert g(0) == 1
    assert g(1) == 0
    assert g(2) == 0

    g = Impulse(1)
    assert g(-1) == 0
    assert g(0) == 0
    assert g(1) == 1
    assert g(2) == 0


def test_step():
    g = Step()
    assert g(-1) == 0
    assert g(0) == 1
    assert g(1) == 1
    assert g(2) == 1

    g = Step(1)
    assert g(-1) == 0
    assert g(0) == 0
    assert g(1) == 1
    assert g(2) == 1


def test_constant():
    g = Constant()
    assert g(-1) == 1
    assert g(0) == 1
    assert g(1) == 1
    assert g(2) == 1

    g = Constant(0.5)
    assert g(-1) == 0.5
    assert g(0) == 0.5
    assert g(1) == 0.5
    assert g(2) == 0.5


def test_zeropad():
    g = ZeroPad([0.4, 0.6])
    assert g(-1) == 0
    assert g(0) == 0.4
    assert g(1) == 0.6
    assert g(2) == 0


def test_sinusoid():
    g = Sinusoid(0.5)
    assert g(0) == 0
    assert g(1) == 1
    assert g(2) == pytest.approx(0)
    assert g(3) == -1

    g = Sinusoid(0.5, 0.25)
    assert g(0) == pytest.approx(sqrt(2) / 2)
    assert g(1) == pytest.approx(sqrt(2) / 2)
    assert g(2) == pytest.approx(-sqrt(2) / 2)
    assert g(3) == pytest.approx(-sqrt(2) / 2)


def test_addition():
    g = Impulse() + Impulse(2)
    assert g(-1) == 0
    assert g(0) == 1
    assert g(1) == 0
    assert g(2) == 1
    assert g(3) == 0

    g = 1 + Impulse(2)
    assert g(-1) == 1
    assert g(0) == 1
    assert g(1) == 1
    assert g(2) == 2
    assert g(3) == 1

    g = Impulse(1) + 1
    assert g(-1) == 1
    assert g(0) == 1
    assert g(1) == 2
    assert g(2) == 1
    assert g(3) == 1


def test_subtraction():
    g = Impulse() - Impulse(2)
    assert g(-1) == 0
    assert g(0) == 1
    assert g(1) == 0
    assert g(2) == -1
    assert g(3) == 0

    g = 1 - Impulse(2)
    assert g(-1) == 1
    assert g(0) == 1
    assert g(1) == 1
    assert g(2) == 0
    assert g(3) == 1

    g = Impulse(2) - 1
    assert g(-1) == -1
    assert g(0) == -1
    assert g(1) == -1
    assert g(2) == 0
    assert g(3) == -1


def test_multiplication():
    g = Impulse() * 0.5
    assert g(-1) == 0
    assert g(0) == 0.5
    assert g(1) == 0
    assert g(2) == 0

    g = 2 * Sinusoid(0.5, 0.25)
    assert g(0) == pytest.approx(sqrt(2))
    assert g(1) == pytest.approx(sqrt(2))
    assert g(2) == pytest.approx(-sqrt(2))
    assert g(3) == pytest.approx(-sqrt(2))
