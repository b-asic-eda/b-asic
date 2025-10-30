import pytest

from b_asic.wdf_operations import (
    ParallelTwoportAdaptor,
    ReflectionFreeSeriesThreeportAdaptor,
    SeriesThreeportAdaptor,
    SeriesTwoportAdaptor,
    SymmetricTwoportAdaptor,
)


class TestSymmetricTwoportAdaptor:
    """Tests for SymmetricTwoportAdaptor class."""

    def test_symmetrictwoportadaptor_positive(self):
        test_operation = SymmetricTwoportAdaptor(0.5)
        assert test_operation.evaluate_output(0, [2, 3]) == 3.5
        assert test_operation.evaluate_output(1, [2, 3]) == 2.5
        assert test_operation.value == 0.5

    def test_symmetrictwoportadaptor_negative(self):
        test_operation = SymmetricTwoportAdaptor(0.5)
        assert test_operation.evaluate_output(0, [-2, -3]) == -3.5
        assert test_operation.evaluate_output(1, [-2, -3]) == -2.5

    def test_symmetrictwoportadaptor_complex(self):
        test_operation = SymmetricTwoportAdaptor(0.5)
        assert test_operation.evaluate_output(0, [2 + 1j, 3 - 2j]) == 3.5 - 3.5j
        assert test_operation.evaluate_output(1, [2 + 1j, 3 - 2j]) == 2.5 - 0.5j

    def test_symmetrictwoportadaptor_swap_io(self):
        test_operation = SymmetricTwoportAdaptor(0.5)
        assert test_operation.value == 0.5
        test_operation.swap_io()
        assert test_operation.value == -0.5

    def test_symmetrictwoportadaptor_error(self):
        with pytest.raises(ValueError, match=r"value must be between -1 and 1"):
            _ = SymmetricTwoportAdaptor(-2)
        test_operation = SymmetricTwoportAdaptor(0)
        with pytest.raises(ValueError, match=r"value must be between -1 and 1"):
            test_operation.value = 2


class TestSeriesTwoportAdaptor:
    """Tests for SeriesTwoportAdaptor class."""

    def test_seriestwoportadaptor_positive(self):
        test_operation = SeriesTwoportAdaptor(0.5)
        assert test_operation.evaluate_output(0, [2, 3]) == 1.0
        assert test_operation.evaluate_output(1, [2, 3]) == -6.0
        assert test_operation.value == 0.5

    def test_seriestwoportadaptor_negative(self):
        test_operation = SeriesTwoportAdaptor(0.5)
        assert test_operation.evaluate_output(0, [-2, -3]) == -1.0
        assert test_operation.evaluate_output(1, [-2, -3]) == 6.0

    def test_seriestwoportadaptor_complex(self):
        test_operation = SeriesTwoportAdaptor(0.5)
        assert test_operation.evaluate_output(0, [2 + 1j, 3 - 2j]) == 1 + 0.5j
        assert test_operation.evaluate_output(1, [2 + 1j, 3 - 2j]) == -6 + 0.5j

    def test_seriestwoportadaptor_swap_io(self):
        test_operation = SeriesTwoportAdaptor(0.5)
        assert test_operation.value == 0.5
        test_operation.swap_io()
        assert test_operation.value == 1.5

    def test_seriestwoportadaptor_error(self):
        with pytest.raises(ValueError, match="value must be between 0 and 2"):
            _ = SeriesTwoportAdaptor(-1)
        test_operation = SeriesTwoportAdaptor(0)
        with pytest.raises(ValueError, match="value must be between 0 and 2"):
            test_operation.value = 3


class TestParallelTwoportAdaptor:
    """Tests for ParallelTwoportAdaptor class."""

    def test_seriestwoportadaptor_positive(self):
        test_operation = ParallelTwoportAdaptor(0.5)
        assert test_operation.evaluate_output(0, [2, 3]) == 3.5
        assert test_operation.evaluate_output(1, [2, 3]) == 2.5
        assert test_operation.value == 0.5

    def test_seriestwoportadaptor_negative(self):
        test_operation = ParallelTwoportAdaptor(0.5)
        assert test_operation.evaluate_output(0, [-2, -3]) == -3.5
        assert test_operation.evaluate_output(1, [-2, -3]) == -2.5

    def test_seriestwoportadaptor_complex(self):
        test_operation = ParallelTwoportAdaptor(0.5)
        assert test_operation.evaluate_output(0, [2 + 1j, 3 - 2j]) == 3.5 - 3.5j
        assert test_operation.evaluate_output(1, [2 + 1j, 3 - 2j]) == 2.5 - 0.5j

    def test_seriestwoportadaptor_swap_io(self):
        test_operation = ParallelTwoportAdaptor(0.5)
        assert test_operation.value == 0.5
        test_operation.swap_io()
        assert test_operation.value == 1.5

    def test_seriestwoportadaptor_error(self):
        with pytest.raises(ValueError, match="value must be between 0 and 2"):
            _ = ParallelTwoportAdaptor(-1)
        test_operation = ParallelTwoportAdaptor(0)
        with pytest.raises(ValueError, match="value must be between 0 and 2"):
            test_operation.value = 3


class TestSeriesThreeportAdaptor:
    """Tests for SeriesThreeportAdaptor class."""

    def test_seriesthreeportadaptor_positive(self):
        test_operation = SeriesThreeportAdaptor((0.5, 1.25))
        assert test_operation.evaluate_output(0, [2, 3, 4]) == -2.5
        assert test_operation.evaluate_output(1, [2, 3, 4]) == -8.25
        assert test_operation.evaluate_output(2, [2, 3, 4]) == 1.75
        assert test_operation.value == (0.5, 1.25)

    def test_seriesthreeportadaptor_negative(self):
        test_operation = SeriesThreeportAdaptor((0.5, 1.25))
        assert test_operation.evaluate_output(0, [-2, -3, -4]) == 2.5
        assert test_operation.evaluate_output(1, [-2, -3, -4]) == 8.25
        assert test_operation.evaluate_output(2, [-2, -3, -4]) == -1.75

    def test_seriesthreeportadaptor_complex(self):
        test_operation = SeriesThreeportAdaptor((0.5, 1.25))
        assert test_operation.evaluate_output(0, [2 + 1j, 3 - 2j, 4 + 3j]) == -2.5 + 0j
        assert (
            test_operation.evaluate_output(1, [2 + 1j, 3 - 2j, 4 + 3j]) == -8.25 - 4.5j
        )
        assert (
            test_operation.evaluate_output(2, [2 + 1j, 3 - 2j, 4 + 3j]) == 1.75 + 2.5j
        )

    def test_seriesthreeportadaptor_error(self):
        with pytest.raises(ValueError, match="each value must be between 0 and 2"):
            _ = SeriesThreeportAdaptor((-1, 3))
        with pytest.raises(ValueError, match="sum of values must be between 0 and 2"):
            _ = SeriesThreeportAdaptor((1.5, 1.5))
        test_operation = SeriesThreeportAdaptor((0, 0.5))
        with pytest.raises(ValueError, match="each value must be between 0 and 2"):
            test_operation.value = (-0.5, 1)
        with pytest.raises(ValueError, match="sum of values must be between 0 and 2"):
            test_operation.value = (0.5, 2)


class TestReflectionFreeSeriesThreeportAdaptor:
    """Tests for ReflectionFreeSeriesThreeportAdaptor class."""

    def test_reflectionfreeseriesthreeportadaptor_positive(self):
        test_operation = ReflectionFreeSeriesThreeportAdaptor(0.25)
        assert test_operation.evaluate_output(0, [2, 3, 4]) == -0.25
        assert test_operation.evaluate_output(1, [2, 3, 4]) == -6
        assert test_operation.evaluate_output(2, [2, 3, 4]) == -2.75
        assert test_operation.value == 0.25

    def test_reflectionfreeseriesthreeportadaptor_negative(self):
        test_operation = ReflectionFreeSeriesThreeportAdaptor(0.25)
        assert test_operation.evaluate_output(0, [-2, -3, -4]) == 0.25
        assert test_operation.evaluate_output(1, [-2, -3, -4]) == 6
        assert test_operation.evaluate_output(2, [-2, -3, -4]) == 2.75

    def test_reflectionfreeseriesthreeportadaptor_complex(self):
        test_operation = ReflectionFreeSeriesThreeportAdaptor(0.25)
        assert (
            test_operation.evaluate_output(0, [2 + 1j, 3 - 2j, 4 + 3j]) == -0.25 + 0.5j
        )
        assert test_operation.evaluate_output(1, [2 + 1j, 3 - 2j, 4 + 3j]) == -6 - 4j
        assert (
            test_operation.evaluate_output(2, [2 + 1j, 3 - 2j, 4 + 3j]) == -2.75 + 1.5j
        )

    def test_reflectionfreeseriesthreeportadaptor_error(self):
        with pytest.raises(ValueError, match="value must be between 0 and 1"):
            _ = ReflectionFreeSeriesThreeportAdaptor(-1)
        test_operation = ReflectionFreeSeriesThreeportAdaptor(0.5)
        with pytest.raises(ValueError, match="value must be between 0 and 1"):
            test_operation.value = 4

    def test_reflectionfree_equals_normal(self):
        test_operation1 = SeriesThreeportAdaptor((0.25, 1))
        test_operation2 = ReflectionFreeSeriesThreeportAdaptor(0.25)
        for port in range(3):
            assert test_operation1.evaluate_output(
                port, [2, 3, 4]
            ) == test_operation2.evaluate_output(port, [2, 3, 4])
