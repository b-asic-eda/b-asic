"""
B-ASIC test suite for the utils module.
"""

from b_asic.utils import (
    decompose,
    downsample,
    float_to_csd,
    int_to_csd,
    interleave,
    upsample,
)


def test_interleave():
    a = [1, 2]
    b = [3, 4]
    assert interleave(a, b) == [1, 3, 2, 4]

    c = [5, 6]
    assert interleave(a, b, c) == [1, 3, 5, 2, 4, 6]


def test_downsample():
    a = list(range(12))
    assert downsample(a, 6) == [0, 6]
    assert downsample(a, 6, 3) == [3, 9]
    assert downsample(a, 4) == [0, 4, 8]
    assert downsample(a, 3, 1) == [1, 4, 7, 10]


def test_upsample():
    a = list(range(3))
    assert upsample(a, 2) == [0, 0, 1, 0, 2, 0]
    assert upsample(a, 2, 1) == [0, 0, 0, 1, 0, 2]
    a = list(range(1, 4))
    assert upsample(a, 3) == [1, 0, 0, 2, 0, 0, 3, 0, 0]
    assert upsample(a, 3, 1) == [0, 1, 0, 0, 2, 0, 0, 3, 0]


def test_decompose():
    a = list(range(6))
    assert decompose(a, 2) == [[0, 2, 4], [1, 3, 5]]
    assert decompose(a, 3) == [[0, 3], [1, 4], [2, 5]]


def test_int_to_csd():
    assert int_to_csd(0) == []

    assert int_to_csd(1) == [1]
    assert int_to_csd(2) == [1, 0]
    assert int_to_csd(3) == [1, 0, -1]
    assert int_to_csd(4) == [1, 0, 0]
    assert int_to_csd(5) == [1, 0, 1]
    assert int_to_csd(6) == [1, 0, -1, 0]
    assert int_to_csd(7) == [1, 0, 0, -1]
    assert int_to_csd(8) == [1, 0, 0, 0]
    assert int_to_csd(9) == [1, 0, 0, 1]
    assert int_to_csd(10) == [1, 0, 1, 0]
    assert int_to_csd(11) == [1, 0, -1, 0, -1]
    assert int_to_csd(12) == [1, 0, -1, 0, 0]
    assert int_to_csd(13) == [1, 0, -1, 0, 1]
    assert int_to_csd(14) == [1, 0, 0, -1, 0]
    assert int_to_csd(15) == [1, 0, 0, 0, -1]
    assert int_to_csd(16) == [1, 0, 0, 0, 0]

    assert int_to_csd(-1) == [-1]
    assert int_to_csd(-2) == [-1, 0]
    assert int_to_csd(-3) == [-1, 0, 1]
    assert int_to_csd(-4) == [-1, 0, 0]
    assert int_to_csd(-5) == [-1, 0, -1]
    assert int_to_csd(-6) == [-1, 0, 1, 0]
    assert int_to_csd(-7) == [-1, 0, 0, 1]
    assert int_to_csd(-8) == [-1, 0, 0, 0]
    assert int_to_csd(-9) == [-1, 0, 0, -1]
    assert int_to_csd(-10) == [-1, 0, -1, 0]
    assert int_to_csd(-11) == [-1, 0, 1, 0, 1]
    assert int_to_csd(-12) == [-1, 0, 1, 0, 0]
    assert int_to_csd(-13) == [-1, 0, 1, 0, -1]
    assert int_to_csd(-14) == [-1, 0, 0, 1, 0]
    assert int_to_csd(-15) == [-1, 0, 0, 0, 1]
    assert int_to_csd(-16) == [-1, 0, 0, 0, 0]


def test_float_to_csd():
    assert float_to_csd(0) == ([], 0)

    assert float_to_csd(1) == ([1], 0)
    assert float_to_csd(2) == ([1], -1)
    assert float_to_csd(3) == ([1, 0, -1], 0)
    assert float_to_csd(4) == ([1], -2)
    assert float_to_csd(5) == ([1, 0, 1], 0)
    assert float_to_csd(6) == ([1, 0, -1], -1)
    assert float_to_csd(7) == ([1, 0, 0, -1], 0)
    assert float_to_csd(8) == ([1], -3)
    assert float_to_csd(9) == ([1, 0, 0, 1], 0)
    assert float_to_csd(10) == ([1, 0, 1], -1)
    assert float_to_csd(11) == ([1, 0, -1, 0, -1], 0)
    assert float_to_csd(12) == ([1, 0, -1], -2)
    assert float_to_csd(13) == ([1, 0, -1, 0, 1], 0)
    assert float_to_csd(14) == ([1, 0, 0, -1], -1)
    assert float_to_csd(15) == ([1, 0, 0, 0, -1], 0)
    assert float_to_csd(16) == ([1], -4)

    assert float_to_csd(2044) == ([1, 0, 0, 0, 0, 0, 0, 0, 0, -1], -2)

    assert float_to_csd(-1) == ([-1], 0)
    assert float_to_csd(-2) == ([-1], -1)
    assert float_to_csd(-3) == ([-1, 0, 1], 0)
    assert float_to_csd(-4) == ([-1], -2)
    assert float_to_csd(-5) == ([-1, 0, -1], 0)
    assert float_to_csd(-6) == ([-1, 0, 1], -1)
    assert float_to_csd(-7) == ([-1, 0, 0, 1], 0)
    assert float_to_csd(-8) == ([-1], -3)
    assert float_to_csd(-9) == ([-1, 0, 0, -1], 0)
    assert float_to_csd(-10) == ([-1, 0, -1], -1)

    assert float_to_csd(0.5) == ([1], 1)
    assert float_to_csd(0.25) == ([1], 2)
    assert float_to_csd(0.75) == ([1, 0, -1], 2)

    assert float_to_csd(-0.5) == ([-1], 1)
    assert float_to_csd(-0.25) == ([-1], 2)
    assert float_to_csd(-0.75) == ([-1, 0, 1], 2)
    assert float_to_csd(-0.71875) == ([-1, 0, 1, 0, 0, 1], 5)
    assert float_to_csd(0.71875) == ([1, 0, -1, 0, 0, -1], 5)
