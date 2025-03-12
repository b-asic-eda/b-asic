"""B-ASIC test suite for the core operations."""

import pytest

from b_asic import (
    MAD,
    MADS,
    SFG,
    Absolute,
    Addition,
    AddSub,
    Butterfly,
    ComplexConjugate,
    Constant,
    ConstantMultiplication,
    Division,
    DontCare,
    Input,
    LeftShift,
    Max,
    Min,
    Multiplication,
    Output,
    Reciprocal,
    RightShift,
    Shift,
    Sink,
    SquareRoot,
    Subtraction,
    SymmetricTwoportAdaptor,
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

    def test_constant_repr(self):
        test_operation = Constant(3)
        assert repr(test_operation) == "Constant(3)"

    def test_constant_str(self):
        test_operation = Constant(3)
        assert str(test_operation) == "3"


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

    def test_addsub_positive(self):
        test_operation = AddSub(is_add=True)
        assert test_operation.evaluate_output(0, [3, 5]) == 8

    def test_addsub_negative(self):
        test_operation = AddSub(is_add=True)
        assert test_operation.evaluate_output(0, [-3, -5]) == -8
        assert test_operation.is_add

    def test_addsub_complex(self):
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

    def test_addsub_is_add_getter(self):
        test_operation = AddSub(is_add=False)
        assert not test_operation.is_add

        test_operation = AddSub(is_add=True)
        assert test_operation.is_add

    def test_addsub_is_add_setter(self):
        test_operation = AddSub(is_add=False)
        test_operation.is_add = True
        assert test_operation.is_add

        test_operation = AddSub(is_add=True)
        test_operation.is_add = False
        assert not test_operation.is_add


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

    def test_mads_is_linear(self):
        test_operation = Division(Constant(3), Addition(Input(), Constant(3)))
        assert not test_operation.is_linear

        test_operation = Division(Addition(Input(), Constant(3)), Constant(3))
        assert test_operation.is_linear

    def test_zero_input(self):
        test_operation = Division()
        assert test_operation.evaluate_output(0, [0, 1]) == 0
        assert test_operation.evaluate_output(0, [1, 0]) == float("inf")


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

    def test_min_complex(self):
        test_operation = Min()
        with pytest.raises(
            ValueError, match="core_operations.Min does not support complex numbers."
        ):
            test_operation.evaluate_output(0, [-1 - 1j, 2 + 2j])


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

    def test_max_complex(self):
        test_operation = Max()
        with pytest.raises(
            ValueError, match="core_operations.Max does not support complex numbers."
        ):
            test_operation.evaluate_output(0, [-1 - 1j, 2 + 2j])


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


class TestMAD:
    def test_mad_positive(self):
        test_operation = MAD()
        assert test_operation.evaluate_output(0, [1, 2, 3]) == 5

    def test_mad_negative(self):
        test_operation = MAD()
        assert test_operation.evaluate_output(0, [-3, -5, -8]) == 7

    def test_mad_complex(self):
        test_operation = MAD()
        assert test_operation.evaluate_output(0, [3 + 6j, 2 + 6j, 1 + 1j]) == -29 + 31j

    def test_mad_is_linear(self):
        test_operation = MAD(
            Constant(3), Addition(Input(), Constant(3)), Addition(Input(), Constant(3))
        )
        assert test_operation.is_linear

        test_operation = MAD(
            Addition(Input(), Constant(3)), Constant(3), Addition(Input(), Constant(3))
        )
        assert test_operation.is_linear

        test_operation = MAD(
            Addition(Input(), Constant(3)), Addition(Input(), Constant(3)), Constant(3)
        )
        assert not test_operation.is_linear

    def test_mad_swap_io(self):
        test_operation = MAD()
        assert test_operation.evaluate_output(0, [1, 2, 3]) == 5
        test_operation.swap_io()
        assert test_operation.evaluate_output(0, [1, 2, 3]) == 5


class TestMADS:
    def test_mads_positive(self):
        test_operation = MADS(is_add=False)
        assert test_operation.evaluate_output(0, [1, 2, 3]) == -5

    def test_mads_negative(self):
        test_operation = MADS(is_add=False)
        assert test_operation.evaluate_output(0, [-3, -5, -8]) == -43

    def test_mads_complex(self):
        test_operation = MADS(is_add=False)
        assert test_operation.evaluate_output(0, [3 + 6j, 2 + 6j, 1 + 1j]) == 7 - 2j

    def test_mads_positive_add(self):
        test_operation = MADS(is_add=True)
        assert test_operation.evaluate_output(0, [1, 2, 3]) == 7

    def test_mads_negative_add(self):
        test_operation = MADS(is_add=True)
        assert test_operation.evaluate_output(0, [-3, -5, -8]) == 37

    def test_mads_complex_add(self):
        test_operation = MADS(is_add=True)
        assert test_operation.evaluate_output(0, [3 + 6j, 2 + 6j, 1 + 1j]) == -1 + 14j

    def test_mads_skip_addsub(self):
        test_operation = MADS(is_add=True, do_addsub=False)
        assert test_operation.evaluate_output(0, [1, 1, 1]) == 1

    def test_mads_sub_skip_addsub(self):
        test_operation = MADS(is_add=False, do_addsub=False)
        assert test_operation.evaluate_output(0, [1, 1, 1]) == -1

    def test_mads_is_linear(self):
        test_operation = MADS(
            src0=Constant(3),
            src1=Addition(Input(), Constant(3)),
            src2=Addition(Input(), Constant(3)),
        )
        assert not test_operation.is_linear

        test_operation = MADS(
            src0=Addition(Input(), Constant(3)),
            src1=Constant(3),
            src2=Addition(Input(), Constant(3)),
        )
        assert test_operation.is_linear

        test_operation = MADS(
            src0=Addition(Input(), Constant(3)),
            src1=Addition(Input(), Constant(3)),
            src2=Constant(3),
        )
        assert test_operation.is_linear

    def test_mads_swap_io(self):
        test_operation = MADS(is_add=False)
        assert test_operation.evaluate_output(0, [1, 2, 3]) == -5
        test_operation.swap_io()
        assert test_operation.evaluate_output(0, [1, 2, 3]) == -5

    def test_mads_is_add_getter(self):
        test_operation = MADS(is_add=False)
        assert not test_operation.is_add

        test_operation = MADS(is_add=True)
        assert test_operation.is_add

    def test_mads_is_add_setter(self):
        test_operation = MADS(is_add=False)
        test_operation.is_add = True
        assert test_operation.is_add

        test_operation = MADS(is_add=True)
        test_operation.is_add = False
        assert not test_operation.is_add

    def test_mads_do_addsub_getter(self):
        test_operation = MADS(do_addsub=False)
        assert not test_operation.do_addsub

        test_operation = MADS(do_addsub=True)
        assert test_operation.do_addsub

    def test_mads_do_addsub_setter(self):
        test_operation = MADS(do_addsub=False)
        test_operation.do_addsub = True
        assert test_operation.do_addsub

        test_operation = MADS(do_addsub=True)
        test_operation.do_addsub = False
        assert not test_operation.do_addsub


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

    def test_zero_input(self):
        test_operation = Reciprocal()
        assert test_operation.evaluate_output(0, [0]) == float("inf")


class TestDepends:
    def test_depends_addition(self):
        add1 = Addition()
        assert set(add1.inputs_required_for_output(0)) == {0, 1}

    def test_depends_butterfly(self):
        bfly1 = Butterfly()
        assert set(bfly1.inputs_required_for_output(0)) == {0, 1}
        assert set(bfly1.inputs_required_for_output(1)) == {0, 1}


class TestDontCare:
    def test_create_sfg_with_dontcare(self):
        i1 = Input()
        dc = DontCare()
        a = Addition(i1, dc)
        o = Output(a)
        sfg = SFG([i1], [o])

        assert sfg.output_count == 1
        assert sfg.input_count == 1

        assert sfg.evaluate_output(0, [0]) == 0
        assert sfg.evaluate_output(0, [1]) == 1

    def test_dontcare_latency_getter(self):
        test_operation = DontCare()
        assert test_operation.latency == 0

    def test_dontcare_repr(self):
        test_operation = DontCare()
        assert repr(test_operation) == "DontCare()"

    def test_dontcare_str(self):
        test_operation = DontCare()
        assert str(test_operation) == "dontcare"


class TestSink:
    def test_create_sfg_with_sink(self):
        bfly = Butterfly()
        sfg = bfly.to_sfg()
        s = Sink()
        with pytest.warns(UserWarning, match="Output port out0 has been removed"):
            sfg1 = sfg.replace_operation(s, "out0")

            assert sfg1.output_count == 1
            assert sfg1.input_count == 2

            assert sfg.evaluate_output(1, [0, 1]) == sfg1.evaluate_output(0, [0, 1])

    def test_sink_latency_getter(self):
        test_operation = Sink()
        assert test_operation.latency == 0

    def test_sink_repr(self):
        test_operation = Sink()
        assert repr(test_operation) == "Sink()"

    def test_sink_str(self):
        test_operation = Sink()
        assert str(test_operation) == "sink"
