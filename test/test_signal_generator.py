from math import sqrt

import pytest

from b_asic.signal_generator import (
    Constant,
    Delay,
    FromFile,
    Gaussian,
    Impulse,
    Sinusoid,
    Step,
    Uniform,
    ZeroPad,
    _AddGenerator,
    _DivGenerator,
    _MulGenerator,
    _SubGenerator,
)


def test_impulse():
    g = Impulse()
    assert g(-1) == 0
    assert g(0) == 1
    assert g(1) == 0
    assert g(2) == 0

    assert str(g) == "Impulse()"

    g = Impulse(1)
    assert g(-1) == 0
    assert g(0) == 0
    assert g(1) == 1
    assert g(2) == 0

    assert str(g) == "Impulse(1)"


def test_step():
    g = Step()
    assert g(-1) == 0
    assert g(0) == 1
    assert g(1) == 1
    assert g(2) == 1

    assert str(g) == "Step()"

    g = Step(1)
    assert g(-1) == 0
    assert g(0) == 0
    assert g(1) == 1
    assert g(2) == 1

    assert str(g) == "Step(1)"


def test_constant():
    g = Constant()
    assert g(-1) == 1
    assert g(0) == 1
    assert g(1) == 1
    assert g(2) == 1

    assert str(g) == "1.0"

    g = Constant(0.5)
    assert g(-1) == 0.5
    assert g(0) == 0.5
    assert g(1) == 0.5
    assert g(2) == 0.5

    assert str(g) == "0.5"


def test_zeropad():
    g = ZeroPad([0.4, 0.6])
    assert g(-1) == 0
    assert g(0) == 0.4
    assert g(1) == 0.6
    assert g(2) == 0

    assert str(g) == "ZeroPad([0.4, 0.6])"


def test_sinusoid():
    g = Sinusoid(0.5)
    assert g(0) == 0
    assert g(1) == 1
    assert g(2) == pytest.approx(0)
    assert g(3) == -1

    assert str(g) == "Sinusoid(0.5)"

    g = Sinusoid(0.5, 0.25)
    assert g(0) == pytest.approx(sqrt(2) / 2)
    assert g(1) == pytest.approx(sqrt(2) / 2)
    assert g(2) == pytest.approx(-sqrt(2) / 2)
    assert g(3) == pytest.approx(-sqrt(2) / 2)

    assert str(g) == "Sinusoid(0.5, 0.25)"


def test_delay():
    gref = Sinusoid(0.5)
    g = Delay(gref)
    assert g(0) == gref(-1)
    assert g(2) == gref(1)

    assert str(g) == "Delay(Sinusoid(0.5), 1)"

    gref = Sinusoid(0.5)
    g = Delay(gref, 3)
    assert g(0) == gref(-3)
    assert g(5) == gref(2)

    assert str(g) == "Delay(Sinusoid(0.5), 3)"


def test_gaussian():
    g = Gaussian(1234)
    assert g(0) == pytest.approx(-1.6038368053963015)
    assert g(1) == pytest.approx(0.06409991400376411)

    assert str(g) == "Gaussian(seed=1234)"

    # Check same seed gives same sequence
    g1 = Gaussian(12345)
    g2 = Gaussian(12345)

    for n in range(100):
        assert g1(n) == g2(n)

    assert str(Gaussian(1234, 1, 2)) == "Gaussian(seed=1234, loc=1, scale=2)"


def test_uniform():
    g = Uniform(1234)
    assert g(0) == pytest.approx(0.9533995333962844)
    assert g(1) == pytest.approx(-0.23960852996076443)

    assert str(g) == "Uniform(seed=1234)"

    # Check same seed gives same sequence
    g1 = Uniform(12345)
    g2 = Uniform(12345)

    for n in range(100):
        assert g1(n) == g2(n)

    assert str(Uniform(1234, 1, 2)) == "Uniform(seed=1234, low=1, high=2)"


def test_addition():
    g = Impulse() + Impulse(2)
    assert g(-1) == 0
    assert g(0) == 1
    assert g(1) == 0
    assert g(2) == 1
    assert g(3) == 0

    assert str(g) == "Impulse() + Impulse(2)"
    assert isinstance(g, _AddGenerator)

    g = 1.0 + Impulse(2)
    assert g(-1) == 1
    assert g(0) == 1
    assert g(1) == 1
    assert g(2) == 2
    assert g(3) == 1

    assert str(g) == "1.0 + Impulse(2)"
    assert isinstance(g, _AddGenerator)

    g = Impulse(1) + 1.0
    assert g(-1) == 1
    assert g(0) == 1
    assert g(1) == 2
    assert g(2) == 1
    assert g(3) == 1

    assert str(g) == "Impulse(1) + 1.0"
    assert isinstance(g, _AddGenerator)


def test_subtraction():
    g = Impulse() - Impulse(2)
    assert g(-1) == 0
    assert g(0) == 1
    assert g(1) == 0
    assert g(2) == -1
    assert g(3) == 0

    assert str(g) == "Impulse() - Impulse(2)"
    assert isinstance(g, _SubGenerator)

    g = 1.0 - Impulse(2)
    assert g(-1) == 1
    assert g(0) == 1
    assert g(1) == 1
    assert g(2) == 0
    assert g(3) == 1

    assert str(g) == "1.0 - Impulse(2)"
    assert isinstance(g, _SubGenerator)

    g = Impulse(2) - 1.0
    assert g(-1) == -1
    assert g(0) == -1
    assert g(1) == -1
    assert g(2) == 0
    assert g(3) == -1

    assert str(g) == "Impulse(2) - 1.0"
    assert isinstance(g, _SubGenerator)


def test_multiplication():
    g = Impulse() * 0.5
    assert g(-1) == 0
    assert g(0) == 0.5
    assert g(1) == 0
    assert g(2) == 0

    assert str(g) == "Impulse() * 0.5"
    assert isinstance(g, _MulGenerator)

    g = 2 * Sinusoid(0.5, 0.25)
    assert g(0) == pytest.approx(sqrt(2))
    assert g(1) == pytest.approx(sqrt(2))
    assert g(2) == pytest.approx(-sqrt(2))
    assert g(3) == pytest.approx(-sqrt(2))

    assert str(g) == "2 * Sinusoid(0.5, 0.25)"
    assert isinstance(g, _MulGenerator)

    g = Step(1) * (Sinusoid(0.5, 0.25) + 1.0)
    assert g(0) == 0
    assert g(1) == pytest.approx(sqrt(2) / 2 + 1)
    assert g(2) == pytest.approx(-sqrt(2) / 2 + 1)
    assert g(3) == pytest.approx(-sqrt(2) / 2 + 1)

    assert str(g) == "Step(1) * (Sinusoid(0.5, 0.25) + 1.0)"
    assert isinstance(g, _MulGenerator)


def test_division():
    g = Step() / 2
    assert g(-1) == 0.0
    assert g(0) == 0.5
    assert g(1) == 0.5
    assert g(2) == 0.5

    assert str(g) == "Step() / 2"
    assert isinstance(g, _DivGenerator)

    g = 0.5 / Step()
    assert g(0) == 0.5
    assert g(1) == 0.5
    assert g(2) == 0.5

    assert str(g) == "0.5 / Step()"
    assert isinstance(g, _DivGenerator)

    g = Sinusoid(0.5, 0.25) / (0.5 * Step())
    assert g(0) == pytest.approx(sqrt(2))
    assert g(1) == pytest.approx(sqrt(2))
    assert g(2) == pytest.approx(-sqrt(2))
    assert g(3) == pytest.approx(-sqrt(2))

    assert str(g) == "Sinusoid(0.5, 0.25) / (0.5 * Step())"
    assert isinstance(g, _DivGenerator)


def test_fromfile(datadir):
    g = FromFile(datadir.join('input.csv'))
    assert g(-1) == 0.0
    assert g(0) == 0
    assert g(1) == 1
    assert g(2) == 0

    with pytest.raises(FileNotFoundError, match="tset.py not found"):
        g = FromFile(datadir.join('tset.py'))

    with pytest.raises(ValueError, match="could not convert string"):
        g = FromFile(datadir.join('bad.csv'))
