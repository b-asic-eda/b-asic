"""
B-ASIC test suite for the utils module.
"""

from b_asic.utils import downsample, interleave


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
