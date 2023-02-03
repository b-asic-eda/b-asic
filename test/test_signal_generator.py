from b_asic.signal_generator import Constant, Impulse, Step


def test_impulse():
    g = Impulse()
    assert g(0) == 1
    assert g(1) == 0
    assert g(2) == 0

    g = Impulse(1)
    assert g(0) == 0
    assert g(1) == 1
    assert g(2) == 0


def test_step():
    g = Step()
    assert g(0) == 1
    assert g(1) == 1
    assert g(2) == 1

    g = Step(1)
    assert g(0) == 0
    assert g(1) == 1
    assert g(2) == 1


def test_constant():
    g = Constant()
    assert g(0) == 1
    assert g(1) == 1
    assert g(2) == 1

    g = Constant(0.5)
    assert g(0) == 0.5
    assert g(1) == 0.5
    assert g(2) == 0.5


def test_addition():
    g = Impulse() + Impulse(2)
    assert g(0) == 1
    assert g(1) == 0
    assert g(2) == 1
    assert g(3) == 0

    g = 1 + Impulse(2)
    assert g(0) == 1
    assert g(1) == 1
    assert g(2) == 2
    assert g(3) == 1

    g = Impulse(1) + 1
    assert g(0) == 1
    assert g(1) == 2
    assert g(2) == 1
    assert g(3) == 1


def test_subtraction():
    g = Impulse() - Impulse(2)
    assert g(0) == 1
    assert g(1) == 0
    assert g(2) == -1
    assert g(3) == 0

    g = 1 - Impulse(2)
    assert g(0) == 1
    assert g(1) == 1
    assert g(2) == 0
    assert g(3) == 1

    g = Impulse(2) - 1
    assert g(0) == -1
    assert g(1) == -1
    assert g(2) == 0
    assert g(3) == -1


def test_multiplication():
    g = Impulse() * 0.5
    assert g(0) == 0.5
    assert g(1) == 0
    assert g(2) == 0
