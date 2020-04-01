"""
B-ASIC test suite for the AbstractOperation class.
"""

from b_asic.core_operations import Addition, ConstantAddition, Subtraction, ConstantSubtraction, \
    Multiplication, ConstantMultiplication, Division, ConstantDivision

import pytest


def test_addition_overload():
    """Tests addition overloading for both operation and number argument."""
    add1 = Addition(None, None, "add1")
    add2 = Addition(None, None, "add2")

    add3 = add1 + add2

    assert isinstance(add3, Addition)
    assert add3.input(0).signals == add1.output(0).signals
    assert add3.input(1).signals == add2.output(0).signals

    add4 = add3 + 5

    assert isinstance(add4, ConstantAddition)
    assert add4.input(0).signals == add3.output(0).signals


def test_subtraction_overload():
    """Tests subtraction overloading for both operation and number argument."""
    add1 = Addition(None, None, "add1")
    add2 = Addition(None, None, "add2")

    sub1 = add1 - add2

    assert isinstance(sub1, Subtraction)
    assert sub1.input(0).signals == add1.output(0).signals
    assert sub1.input(1).signals == add2.output(0).signals

    sub2 = sub1 - 5

    assert isinstance(sub2, ConstantSubtraction)
    assert sub2.input(0).signals == sub1.output(0).signals


def test_multiplication_overload():
    """Tests multiplication overloading for both operation and number argument."""
    add1 = Addition(None, None, "add1")
    add2 = Addition(None, None, "add2")

    mul1 = add1 * add2

    assert isinstance(mul1, Multiplication)
    assert mul1.input(0).signals == add1.output(0).signals
    assert mul1.input(1).signals == add2.output(0).signals

    mul2 = mul1 * 5

    assert isinstance(mul2, ConstantMultiplication)
    assert mul2.input(0).signals == mul1.output(0).signals


def test_division_overload():
    """Tests division overloading for both operation and number argument."""
    add1 = Addition(None, None, "add1")
    add2 = Addition(None, None, "add2")

    div1 = add1 / add2

    assert isinstance(div1, Division)
    assert div1.input(0).signals == add1.output(0).signals
    assert div1.input(1).signals == add2.output(0).signals

    div2 = div1 / 5

    assert isinstance(div2, ConstantDivision)
    assert div2.input(0).signals == div1.output(0).signals

