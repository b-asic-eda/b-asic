"""B-ASIC test suite for the core operations."""
import pytest

from b_asic import (
    Absolute,
    Addition,
    AddSub,
    Butterfly,
    ComplexConjugate,
    Constant,
    ConstantMultiplication,
    Division,
    LeftShift,
    Max,
    Min,
    Multiplication,
    Reciprocal,
    RightShift,
    Shift,
    SquareRoot,
    Subtraction,
    SymmetricTwoportAdaptor,
    Sink,
    SFG,
)


class TestConstant:
    """Tests for Constant class."""

    def test_constant_positive(self):
        test_operation = Constant(3)
        assert test_operation.evaluate_output(0, []) == 3
        assert test_operation.value == 3

    def test_constant_negative(self):
        test_operation = Constant(-3)
        assert test_operation.evaluate_output(0, []) == -3

    def test_constant_complex(self):
        test_operation = Constant(3 + 4j)
        assert test_operation.evaluate_output(0, []) == 3 + 4j

    def test_constant_change_value(self):
        test_operation = Constant(3)
        assert test_operation.value == 3
        test_operation.value = 4
        assert test_operation.value == 4


class TestAddition:
    """Tests for Addition class."""

    def test_addition_positive(self):
        test_operation = Addition()
        assert test_operation.evaluate_output(0, [3, 5]) == 8

    def test_addition_negative(self):
        test_operation = Addition()
        assert test_operation.evaluate_output(0, [-3, -5]) == -8

    def test_addition_complex(self):
        test_operation = Addition()
        assert test_operation.evaluate_output(0, [3 + 5j, 4 + 6j]) == 7 + 11j


class TestSubtraction:
    """Tests for Subtraction class."""

    def test_subtraction_positive(self):
        test_operation = Subtraction()
        assert test_operation.evaluate_output(0, [5, 3]) == 2

    def test_subtraction_negative(self):
        test_operation = Subtraction()
        assert test_operation.evaluate_output(0, [-5, -3]) == -2

    def test_subtraction_complex(self):
        test_operation = Subtraction()
        assert test_operation.evaluate_output(0, [3 + 5j, 4 + 6j]) == -1 - 1j


class TestAddSub:
    """Tests for AddSub class."""

    def test_addition_positive(self):
        test_operation = AddSub(is_add=True)
        assert test_operation.evaluate_output(0, [3, 5]) == 8

    def test_addition_negative(self):
        test_operation = AddSub(is_add=True)
        assert test_operation.evaluate_output(0, [-3, -5]) == -8
        assert test_operation.is_add

    def test_addition_complex(self):
        test_operation = AddSub(is_add=True)
        assert test_operation.evaluate_output(0, [3 + 5j, 4 + 6j]) == 7 + 11j

    def test_addsub_subtraction_positive(self):
        test_operation = AddSub(is_add=False)
        assert test_operation.evaluate_output(0, [5, 3]) == 2
        assert not test_operation.is_add

    def test_addsub_subtraction_negative(self):
        test_operation = AddSub(is_add=False)
        assert test_operation.evaluate_output(0, [-5, -3]) == -2

    def test_addsub_subtraction_complex(self):
        test_operation = AddSub(is_add=False)
        assert test_operation.evaluate_output(0, [3 + 5j, 4 + 6j]) == -1 - 1j

    def test_addsub_subtraction_is_swappable(self):
        test_operation = AddSub(is_add=False)
        assert not test_operation.is_swappable

        test_operation = AddSub(is_add=True)
        assert test_operation.is_swappable


class TestMultiplication:
    """Tests for Multiplication class."""

    def test_multiplication_positive(self):
        test_operation = Multiplication()
        assert test_operation.evaluate_output(0, [5, 3]) == 15

    def test_multiplication_negative(self):
        test_operation = Multiplication()
        assert test_operation.evaluate_output(0, [-5, -3]) == 15

    def test_multiplication_complex(self):
        test_operation = Multiplication()
        assert test_operation.evaluate_output(0, [3 + 5j, 4 + 6j]) == -18 + 38j


class TestDivision:
    """Tests for Division class."""

    def test_division_positive(self):
        test_operation = Division()
        assert test_operation.evaluate_output(0, [30, 5]) == 6

    def test_division_negative(self):
        test_operation = Division()
        assert test_operation.evaluate_output(0, [-30, -5]) == 6

    def test_division_complex(self):
        test_operation = Division()
        assert test_operation.evaluate_output(0, [60 + 40j, 10 + 20j]) == 2.8 - 1.6j


class TestSquareRoot:
    """Tests for SquareRoot class."""

    def test_squareroot_positive(self):
        test_operation = SquareRoot()
        assert test_operation.evaluate_output(0, [36]) == 6

    def test_squareroot_negative(self):
        test_operation = SquareRoot()
        assert test_operation.evaluate_output(0, [-36]) == 6j

    def test_squareroot_complex(self):
        test_operation = SquareRoot()
        assert test_operation.evaluate_output(0, [48 + 64j]) == 8 + 4j


class TestComplexConjugate:
    """Tests for ComplexConjugate class."""

    def test_complexconjugate_positive(self):
        test_operation = ComplexConjugate()
        assert test_operation.evaluate_output(0, [3 + 4j]) == 3 - 4j

    def test_test_complexconjugate_negative(self):
        test_operation = ComplexConjugate()
        assert test_operation.evaluate_output(0, [-3 - 4j]) == -3 + 4j


class TestMax:
    """Tests for Max class."""

    def test_max_positive(self):
        test_operation = Max()
        assert test_operation.evaluate_output(0, [30, 5]) == 30

    def test_max_negative(self):
        test_operation = Max()
        assert test_operation.evaluate_output(0, [-30, -5]) == -5


class TestMin:
    """Tests for Min class."""

    def test_min_positive(self):
        test_operation = Min()
        assert test_operation.evaluate_output(0, [30, 5]) == 5

    def test_min_negative(self):
        test_operation = Min()
        assert test_operation.evaluate_output(0, [-30, -5]) == -30


class TestAbsolute:
    """Tests for Absolute class."""

    def test_absolute_positive(self):
        test_operation = Absolute()
        assert test_operation.evaluate_output(0, [30]) == 30

    def test_absolute_negative(self):
        test_operation = Absolute()
        assert test_operation.evaluate_output(0, [-5]) == 5

    def test_absolute_complex(self):
        test_operation = Absolute()
        assert test_operation.evaluate_output(0, [3 + 4j]) == 5.0


class TestConstantMultiplication:
    """Tests for ConstantMultiplication class."""

    def test_constantmultiplication_positive(self):
        test_operation = ConstantMultiplication(5)
        assert test_operation.evaluate_output(0, [20]) == 100
        assert test_operation.value == 5

    def test_constantmultiplication_negative(self):
        test_operation = ConstantMultiplication(5)
        assert test_operation.evaluate_output(0, [-5]) == -25

    def test_constantmultiplication_complex(self):
        test_operation = ConstantMultiplication(3 + 2j)
        assert test_operation.evaluate_output(0, [3 + 4j]) == 1 + 18j


class TestRightShift:
    """Tests for RightShift class."""

    def test_rightshift_positive(self):
        test_operation = RightShift(2)
        assert test_operation.evaluate_output(0, [20]) == 5
        assert test_operation.value == 2

    def test_rightshift_negative(self):
        test_operation = RightShift(2)
        assert test_operation.evaluate_output(0, [-5]) == -1.25

    def test_rightshift_complex(self):
        test_operation = RightShift(2)
        assert test_operation.evaluate_output(0, [2 + 1j]) == 0.5 + 0.25j

    def test_rightshift_errors(self):
        with pytest.raises(TypeError, match="value must be an int"):
            _ = RightShift(0.5)
        test_operation = RightShift(0)
        with pytest.raises(TypeError, match="value must be an int"):
            test_operation.value = 0.5

        with pytest.raises(ValueError, match="value must be non-negative"):
            _ = RightShift(-1)
        test_operation = RightShift(0)
        with pytest.raises(ValueError, match="value must be non-negative"):
            test_operation.value = -1


class TestLeftShift:
    """Tests for LeftShift class."""

    def test_leftshift_positive(self):
        test_operation = LeftShift(2)
        assert test_operation.evaluate_output(0, [5]) == 20
        assert test_operation.value == 2

    def test_leftshift_negative(self):
        test_operation = LeftShift(2)
        assert test_operation.evaluate_output(0, [-5]) == -20

    def test_leftshift_complex(self):
        test_operation = LeftShift(2)
        assert test_operation.evaluate_output(0, [0.5 + 0.25j]) == 2 + 1j

    def test_leftshift_errors(self):
        with pytest.raises(TypeError, match="value must be an int"):
            _ = LeftShift(0.5)
        test_operation = LeftShift(0)
        with pytest.raises(TypeError, match="value must be an int"):
            test_operation.value = 0.5

        with pytest.raises(ValueError, match="value must be non-negative"):
            _ = LeftShift(-1)
        test_operation = LeftShift(0)
        with pytest.raises(ValueError, match="value must be non-negative"):
            test_operation.value = -1


class TestShift:
    """Tests for Shift class."""

    def test_shift_positive(self):
        test_operation = Shift(2)
        assert test_operation.evaluate_output(0, [5]) == 20
        assert test_operation.value == 2

        test_operation = Shift(-2)
        assert test_operation.evaluate_output(0, [5]) == 1.25
        assert test_operation.value == -2

    def test_shift_negative(self):
        test_operation = Shift(2)
        assert test_operation.evaluate_output(0, [-5]) == -20

        test_operation = Shift(-2)
        assert test_operation.evaluate_output(0, [-5]) == -1.25

    def test_shift_complex(self):
        test_operation = Shift(2)
        assert test_operation.evaluate_output(0, [0.5 + 0.25j]) == 2 + 1j

        test_operation = Shift(-2)
        assert test_operation.evaluate_output(0, [2 + 1j]) == 0.5 + 0.25j

    @pytest.mark.parametrize("val", (-0.5, 0.5))
    def test_leftshift_errors(self, val):
        with pytest.raises(TypeError, match="value must be an int"):
            _ = Shift(val)
        test_operation = Shift(0)
        with pytest.raises(TypeError, match="value must be an int"):
            test_operation.value = val


class TestButterfly:
    """Tests for Butterfly class."""

    def test_butterfly_positive(self):
        test_operation = Butterfly()
        assert test_operation.evaluate_output(0, [2, 3]) == 5
        assert test_operation.evaluate_output(1, [2, 3]) == -1

    def test_butterfly_negative(self):
        test_operation = Butterfly()
        assert test_operation.evaluate_output(0, [-2, -3]) == -5
        assert test_operation.evaluate_output(1, [-2, -3]) == 1

    def test_butterfly_complex(self):
        test_operation = Butterfly()
        assert test_operation.evaluate_output(0, [2 + 1j, 3 - 2j]) == 5 - 1j
        assert test_operation.evaluate_output(1, [2 + 1j, 3 - 2j]) == -1 + 3j


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
        with pytest.raises(ValueError, match="value must be between -1 and 1"):
            _ = SymmetricTwoportAdaptor(-2)
        test_operation = SymmetricTwoportAdaptor(0)
        with pytest.raises(ValueError, match="value must be between -1 and 1"):
            test_operation.value = 2


class TestReciprocal:
    """Tests for Absolute class."""

    def test_reciprocal_positive(self):
        test_operation = Reciprocal()
        assert test_operation.evaluate_output(0, [2]) == 0.5

    def test_reciprocal_negative(self):
        test_operation = Reciprocal()
        assert test_operation.evaluate_output(0, [-5]) == -0.2

    def test_reciprocal_complex(self):
        test_operation = Reciprocal()
        assert test_operation.evaluate_output(0, [1 + 1j]) == 0.5 - 0.5j


class TestDepends:
    def test_depends_addition(self):
        add1 = Addition()
        assert set(add1.inputs_required_for_output(0)) == {0, 1}

    def test_depends_butterfly(self):
        bfly1 = Butterfly()
        assert set(bfly1.inputs_required_for_output(0)) == {0, 1}
        assert set(bfly1.inputs_required_for_output(1)) == {0, 1}

class TestSink:
    def test_create_sfg_with_sink(self):
        bfly = Butterfly()
        sfg = bfly.to_sfg()
        s = Sink()
        sfg1 = sfg.replace_operation(s, "out0")
        sfg2 = SFG(sfg1.input_operations, sfg1.output_operations[1:])

        assert sfg2.output_count == 1
        assert sfg2.input_count == 2

        assert sfg.evaluate_output(1, [0,1]) == sfg2.evaluate_output(0, [0,1])
