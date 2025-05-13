"""B-ASIC test suite for fft operations."""

from b_asic.fft_operations import R2Butterfly, R2DIFButterfly


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
