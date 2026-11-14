import pytest

from b_asic.wdf_operations import (
    ParallelThreePortAdaptor,
    ParallelTwoportAdaptor,
    ReflectionFreeParallelThreePortAdaptor,
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
        assert test_operation.evaluate_output(0, [2, 3]) == -0.5
        assert test_operation.evaluate_output(1, [2, 3]) == -4.5
        assert test_operation.value == 0.5

    def test_seriestwoportadaptor_negative(self):
        test_operation = SeriesTwoportAdaptor(0.5)
        assert test_operation.evaluate_output(0, [-2, -3]) == 0.5
        assert test_operation.evaluate_output(1, [-2, -3]) == 4.5

    def test_seriestwoportadaptor_complex(self):
        test_operation = SeriesTwoportAdaptor(0.5)
        assert test_operation.evaluate_output(0, [2 + 1j, 3 - 2j]) == -0.5 + 1.5j
        assert test_operation.evaluate_output(1, [2 + 1j, 3 - 2j]) == -4.5 - 0.5j

    @pytest.mark.parametrize("coefficient", [0, 0.25, 0.5, 1, 1.75, 2])
    @pytest.mark.parametrize("values", [[2, 3], [-2, -3], [2 + 1j, 3 - 2j]])
    def test_equivalent_to_threeport_with_zero_third_input(self, coefficient, values):
        twoport = SeriesTwoportAdaptor(coefficient)
        threeport = SeriesThreeportAdaptor((coefficient, 2 - coefficient))
        assert twoport.evaluate_outputs(values) == pytest.approx(
            threeport.evaluate_outputs([*values, 0])[:2]
        )

    @pytest.mark.parametrize("coefficient", [0.25, 0.5, 1, 1.75])
    def test_applying_adaptor_twice_restores_incident_waves(self, coefficient):
        adaptor = SeriesTwoportAdaptor(coefficient)
        values = [2 + 1j, 3 - 2j]
        assert adaptor.evaluate_outputs(
            adaptor.evaluate_outputs(values)
        ) == pytest.approx(values)

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

    @pytest.mark.parametrize(
        ("index", "expected"), [(0, (0, 1, 2)), (1, (0, 2)), (2, (0, 1, 2))]
    )
    def test_inputs_required_for_output(self, index, expected):
        operation = ReflectionFreeSeriesThreeportAdaptor(0.25)
        assert tuple(operation.inputs_required_for_output(index)) == expected

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


class TestParallelThreePortAdaptor:
    @pytest.mark.parametrize(
        "values", [(2, 3, 4), (-2, -3, -4), (2 + 1j, 3 - 2j, 4 + 3j)]
    )
    @pytest.mark.parametrize("coefficients", [(0.5, 1.25), (0, 0), (0, 2), (2, 0)])
    def test_evaluate(self, values, coefficients):
        operation = ParallelThreePortAdaptor(coefficients)
        a, b, c = values
        v0, v1 = coefficients
        total = v0 * a + v1 * b + (2 - v0 - v1) * c
        assert operation.evaluate_outputs(values) == pytest.approx(
            [total - a, total - b, total - c]
        )
        assert operation.value == coefficients

    @pytest.mark.parametrize(
        ("coefficients", "message"),
        [
            ((-1, 1), "each value"),
            ((0, 3), "each value"),
            ((1.5, 1), "sum of values"),
            ((0,), "exactly two values"),
            ((0, 0, 0), "exactly two values"),
        ],
    )
    def test_invalid_coefficients(self, coefficients, message):
        with pytest.raises(ValueError, match=message):
            ParallelThreePortAdaptor(coefficients)
        operation = ParallelThreePortAdaptor()
        with pytest.raises(ValueError, match=message):
            operation.value = coefficients


class TestReflectionFreeParallelThreePortAdaptor:
    @pytest.mark.parametrize(
        "values", [(2, 3, 4), (-2, -3, -4), (2 + 1j, 3 - 2j, 4 + 3j)]
    )
    @pytest.mark.parametrize("coefficient", [0, 0.25, 1])
    def test_evaluate(self, values, coefficient):
        operation = ReflectionFreeParallelThreePortAdaptor(coefficient)
        normal = ParallelThreePortAdaptor((coefficient, 1))
        assert operation.evaluate_outputs(values) == pytest.approx(
            normal.evaluate_outputs(values)
        )
        a, b, c = values
        y1 = coefficient * a + (1 - coefficient) * c
        assert operation.evaluate_outputs(values) == pytest.approx(
            [y1 + b - a, y1, y1 + b - c]
        )

    @pytest.mark.parametrize("coefficient", [-1, 1.5])
    def test_invalid_coefficient(self, coefficient):
        with pytest.raises(ValueError, match="value must be between 0 and 1"):
            ReflectionFreeParallelThreePortAdaptor(coefficient)
        operation = ReflectionFreeParallelThreePortAdaptor()
        with pytest.raises(ValueError, match="value must be between 0 and 1"):
            operation.value = coefficient

    @pytest.mark.parametrize(
        ("index", "expected"), [(0, (0, 1, 2)), (1, (0, 2)), (2, (0, 1, 2))]
    )
    def test_inputs_required_for_output(self, index, expected):
        operation = ReflectionFreeParallelThreePortAdaptor(0.25)
        assert tuple(operation.inputs_required_for_output(index)) == expected


@pytest.mark.parametrize(
    "adaptor_type",
    [ReflectionFreeSeriesThreeportAdaptor, ReflectionFreeParallelThreePortAdaptor],
)
@pytest.mark.parametrize("index", [-1, 3])
def test_reflection_free_invalid_output_index(adaptor_type, index):
    with pytest.raises(IndexError, match="Output index out of range"):
        adaptor_type().inputs_required_for_output(index)
