"""B-ASIC test suite for fft operations."""

import numpy as np

from b_asic.fft_operations import (
    R2Butterfly,
    R2DIFButterfly,
    R2DITButterfly,
    R2TFButterfly,
    R3Winograd,
    R4Butterfly,
    R5Winograd,
)


class TestR2Butterfly:
    """Tests for the R2Butterfly class."""

    def test_positive(self):
        test_operation = R2Butterfly()
        assert test_operation.evaluate_output(0, [2, 3]) == 5
        assert test_operation.evaluate_output(1, [2, 3]) == -1

    def test_negative(self):
        test_operation = R2Butterfly()
        assert test_operation.evaluate_output(0, [-2, -3]) == -5
        assert test_operation.evaluate_output(1, [-2, -3]) == 1

    def test_complex(self):
        test_operation = R2Butterfly()
        assert test_operation.evaluate_output(0, [2 + 1j, 3 - 2j]) == 5 - 1j
        assert test_operation.evaluate_output(1, [2 + 1j, 3 - 2j]) == -1 + 3j


class TestR2DIFButterfly:
    """Tests for the R2DIFButterfly class."""

    def test_positive(self):
        test_operation = R2DIFButterfly(w=2)
        assert test_operation.evaluate_output(0, [2, 3]) == 5
        assert test_operation.evaluate_output(1, [2, 3]) == -2

    def test_negative(self):
        test_operation = R2DIFButterfly(w=3)
        assert test_operation.evaluate_output(0, [-2, -3]) == -5
        assert test_operation.evaluate_output(1, [-2, -3]) == 3

    def test_complex(self):
        test_operation = R2DIFButterfly(w=3 - 3j)
        assert test_operation.evaluate_output(0, [2 + 1j, 3 - 2j]) == 5 - 1j
        assert test_operation.evaluate_output(1, [2 + 1j, 3 - 2j]) == 6 + 12j

    def test_set_and_get_w(self):
        test_operation = R2DIFButterfly(w=1)
        assert test_operation.w == 1
        assert test_operation.evaluate_output(0, [2, 3]) == 5
        assert test_operation.evaluate_output(1, [2, 3]) == -1

        test_operation.w = 4
        assert test_operation.w == 4
        assert test_operation.evaluate_output(0, [2, 3]) == 5
        assert test_operation.evaluate_output(1, [2, 3]) == -4


class TestR2DITButterfly:
    """Tests for the R2DITButterfly class."""

    def test_positive(self):
        test_operation = R2DITButterfly(w=2)
        assert test_operation.evaluate_output(0, [2, 3]) == 8
        assert test_operation.evaluate_output(1, [2, 3]) == -4

    def test_negative(self):
        test_operation = R2DITButterfly(w=-3)
        assert test_operation.evaluate_output(0, [-2, -3]) == 7
        assert test_operation.evaluate_output(1, [-2, -3]) == -11

    def test_complex(self):
        test_operation = R2DITButterfly(w=-2 + 2j)
        assert test_operation.evaluate_output(0, [2 + 1j, 3 - 2j]) == 11j
        assert test_operation.evaluate_output(1, [2 + 1j, 3 - 2j]) == 4 - 9j

    def test_set_and_get_w(self):
        test_operation = R2DITButterfly(w=1)
        assert test_operation.w == 1
        assert test_operation.evaluate_output(0, [2, 3]) == 5
        assert test_operation.evaluate_output(1, [2, 3]) == -1

        test_operation.w = 3
        assert test_operation.w == 3
        assert test_operation.evaluate_output(0, [2, 3]) == 11
        assert test_operation.evaluate_output(1, [2, 3]) == -7


class TestR2TFButterfly:
    """Tests for the R2TFButterfly class."""

    def test_positive(self):
        test_operation = R2TFButterfly(w0=2, w1=3)
        assert test_operation.evaluate_output(0, [2, 3]) == 10
        assert test_operation.evaluate_output(1, [2, 3]) == -3

    def test_negative(self):
        test_operation = R2TFButterfly(w0=-2, w1=-4)
        assert test_operation.evaluate_output(0, [-2, -3]) == 10
        assert test_operation.evaluate_output(1, [-2, -3]) == -4

    def test_complex(self):
        test_operation = R2TFButterfly(w0=-3 + 5j, w1=5 - 7j)
        assert test_operation.evaluate_output(0, [2 + 1j, 3 - 2j]) == -10 + 28j
        assert test_operation.evaluate_output(1, [2 + 1j, 3 - 2j]) == 16 + 22j

    def test_set_and_get_w(self):
        test_operation = R2TFButterfly(w0=1, w1=2)
        assert test_operation.w0 == 1
        assert test_operation.w1 == 2
        assert test_operation.evaluate_output(0, [2, 3]) == 5
        assert test_operation.evaluate_output(1, [2, 3]) == -2

        test_operation.w0 = 3
        test_operation.w1 = 4
        assert test_operation.w0 == 3
        assert test_operation.w1 == 4
        assert test_operation.evaluate_output(0, [2, 3]) == 15
        assert test_operation.evaluate_output(1, [2, 3]) == -4


class TestR4Butterfly:
    """Tests for the R4Butterfly class."""

    def test_positive(self):
        input_sequence = [11, 21, 35, 193]
        expected = np.fft.fft(input_sequence)
        test_operation = R4Butterfly()
        for i, exp in enumerate(expected):
            assert test_operation.evaluate_output(i, input_sequence) == exp

    def test_negative(self):
        input_sequence = [-51, -92, -3, -401]
        expected = np.fft.fft(input_sequence)
        test_operation = R4Butterfly()
        for i, exp in enumerate(expected):
            assert test_operation.evaluate_output(i, input_sequence) == exp

    def test_complex(self):
        input_sequence = [(1.1 - 4.3j), (7.3 - 4.9j), (-6.2 - 2.6j), (8.2 + 123.3j)]
        expected = np.fft.fft(input_sequence)
        test_operation = R4Butterfly()
        for i, exp in enumerate(expected):
            assert test_operation.evaluate_output(i, input_sequence) == exp


class TestR3Winograd:
    """Tests for the R3Winograd class."""

    def test_positive(self):
        input_sequence = [11, 21, 35]
        expected = np.fft.fft(input_sequence)
        test_operation = R3Winograd()
        for i, exp in enumerate(expected):
            assert np.allclose(test_operation.evaluate_output(i, input_sequence), exp)

    def test_negative(self):
        input_sequence = [-51, -92, -3]
        expected = np.fft.fft(input_sequence)
        test_operation = R3Winograd()
        for i, exp in enumerate(expected):
            assert np.allclose(test_operation.evaluate_output(i, input_sequence), exp)

    def test_complex(self):
        input_sequence = [(1.1 - 4.3j), (7.3 - 4.9j), (-6.2 - 2.6j)]
        expected = np.fft.fft(input_sequence)
        test_operation = R3Winograd()
        for i, exp in enumerate(expected):
            assert np.allclose(test_operation.evaluate_output(i, input_sequence), exp)


class TestR5Winograd:
    """Tests for the R5Winograd class."""

    def test_positive(self):
        input_sequence = [11, 21, 35, 102, 7]
        expected = np.fft.fft(input_sequence)
        test_operation = R5Winograd()
        for i, exp in enumerate(expected):
            assert np.allclose(test_operation.evaluate_output(i, input_sequence), exp)

    def test_negative(self):
        input_sequence = [-51, -92, -3, -194, -0]
        expected = np.fft.fft(input_sequence)
        test_operation = R5Winograd()
        for i, exp in enumerate(expected):
            assert np.allclose(test_operation.evaluate_output(i, input_sequence), exp)

    def test_complex(self):
        input_sequence = [
            (1.1 - 4.3j),
            (7.3 - 4.9j),
            (-6.2 - 2.6j),
            (-10.4 + 5.6j),
            (-2.0 - 43.7j),
        ]
        expected = np.fft.fft(input_sequence)
        test_operation = R5Winograd()
        for i, exp in enumerate(expected):
            assert np.allclose(test_operation.evaluate_output(i, input_sequence), exp)
