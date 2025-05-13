"""B-ASIC test suite for fft operations."""

from b_asic.fft_operations import R2Butterfly


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
