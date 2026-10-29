"""B-ASIC test suite for the core operations."""

import apytypes as apy
import pytest

from b_asic import (
    MAD,
    MADS,
    Absolute,
    Addition,
    AddSub,
    Comparator,
    ComplexConjugate,
    Constant,
    ConstantMultiplication,
    Division,
    ImaginaryMultiplication,
    Input,
    LeftShift,
    Max,
    Min,
    Multiplication,
    R2Butterfly,
    Reciprocal,
    ReciprocalSquareRoot,
    RightShift,
    Shift,
    SquareRoot,
    Subtraction,
)
from b_asic.data_type import DataType, NumRepresentation


class TestConstant:
    """Tests for Constant class."""

    @pytest.mark.parametrize(
        "value", [0, 3, -3, 0.75, -3.25, 0.1, 2.0**-100, 3.25 + 0.125j]
    )
    def test_inferred_fixed_point(self, value):
        operation = Constant(value)
        narrow = operation.evaluate_output(0, [], data_type=DataType(wl=(1, 1)))
        wide = operation.evaluate_output(0, [], data_type=DataType(wl=(8, 8)))
        assert complex(narrow) == value
        assert narrow.is_identical(wide)
        assert operation.value == value

    @pytest.mark.parametrize(
        "value",
        [
            apy.fx(3.25, 5, 6),
            apy.fx(3.25 + 0.125j, 5, 6),
            apy.fp(3.25, 8, 23),
            apy.fp(3.25 + 0.125j, 8, 23),
        ],
    )
    def test_explicit_apy_format(self, value):
        operation = Constant(value)
        assert operation.evaluate(data_type=DataType(wl=(1, 1))) is value
        ordinary = operation.evaluate_output(0, [])
        assert type(ordinary) in (float, complex)
        assert ordinary == complex(value)
        assert operation.value is value

    def test_floating_point(self):
        data_type = DataType(wl=(8, 23), num_repr=NumRepresentation.FLOATING_POINT)
        result = Constant(3.25).evaluate(data_type=data_type)
        assert result.is_identical(apy.fp(3.25, 8, 23))

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


@pytest.mark.parametrize("operation_type", [Addition, Subtraction, AddSub])
@pytest.mark.parametrize(
    ("scales", "addition", "subtraction"),
    [
        ({}, 16, 0),
        ({"in0_scale": 1}, 12, -4),
        ({"in1_scale": 2}, 10, 6),
        ({"out0_scale": 1}, 8, 0),
        ({"in0_scale": 1, "in1_scale": 2, "out0_scale": 1}, 3, 1),
    ],
)
def test_additive_scales(operation_type, scales, addition, subtraction):
    operation = operation_type(**scales)
    expected = subtraction if operation_type is Subtraction else addition
    assert operation.evaluate_output(0, [8, 8]) == expected
    assert "shift_output" not in operation.params
    assert operation.copy().params == operation.params
    if operation_type is AddSub:
        operation.is_add = False
        assert operation.evaluate_output(0, [8, 8]) == subtraction


@pytest.mark.parametrize("operation_type", [Addition, Subtraction, AddSub])
@pytest.mark.parametrize("scale_name", ["in0_scale", "in1_scale", "out0_scale"])
def test_additive_scale_validation(operation_type, scale_name):
    operation = operation_type()
    assert getattr(operation, scale_name) == 0
    setattr(operation, scale_name, 2)
    assert getattr(operation, scale_name) == 2
    for invalid, error in [(1.5, TypeError), (-1, ValueError)]:
        with pytest.raises(error, match=scale_name):
            operation_type(**{scale_name: invalid})
        with pytest.raises(error, match=scale_name):
            setattr(operation, scale_name, invalid)


@pytest.mark.parametrize("operation_type", [Addition, Subtraction, AddSub])
def test_additive_scale_division(operation_type):
    operation = operation_type(in0_scale=1)
    assert operation.evaluate_output(0, [9, 0]) == 4.5
    with pytest.raises(TypeError, match="shift_output"):
        operation_type(shift_output=1)


@pytest.mark.parametrize("operation_type", [Addition, AddSub])
def test_additive_scale_swappability(operation_type):
    operation = operation_type(in0_scale=1)
    assert not operation.is_swappable
    operation.in1_scale = 1
    assert operation.is_swappable
    operation.mul_j = True
    assert not operation.is_swappable


@pytest.mark.parametrize("operation_type", [Addition, AddSub])
def test_additive_scale_params(operation_type):
    operation = operation_type()
    operation.set_param("in0_scale", 1)
    assert operation.in0_scale == 1
    assert not operation.is_swappable
    operation.set_param("in1_scale", 1)
    assert operation.is_swappable
    operation.set_param("out0_scale", 2)
    assert operation.is_swappable
    assert operation.evaluate_output(0, [8, 8]) == 2
    operation.set_param("mul_j", True)
    assert not operation.is_swappable
    if operation_type is AddSub:
        operation.set_param("mul_j", False)
        operation.set_param("is_add", False)
        assert not operation.is_swappable


@pytest.mark.parametrize("operation_type", [Addition, Subtraction, AddSub])
@pytest.mark.parametrize("is_complex", [False, True])
def test_additive_fixed_point_scales(operation_type, is_complex):
    data_type = DataType(wl=(4, 2), is_complex=is_complex)
    first = apy.fx(-3.25 + 1.75j if is_complex else -3.25, 4, 2)
    second = apy.fx(1.75 - 2.25j if is_complex else 1.75, 4, 2)
    operation = operation_type(in0_scale=1, in1_scale=2, out0_scale=1, mul_j=is_complex)
    first_scaled = operation._cast_to_data_type(first >> 1, data_type)
    second_scaled = operation._cast_to_data_type(second >> 2, data_type)
    if is_complex:
        second_scaled = second_scaled * apy.fx(1j, 2, 0)
    expected = (
        first_scaled - second_scaled
        if operation_type is Subtraction
        else first_scaled + second_scaled
    )
    expected = operation._cast_to_data_type(expected >> 1, data_type)
    assert operation.evaluate(first, second, data_type=data_type) == expected


@pytest.mark.parametrize("operation_type", [Addition, Subtraction, AddSub])
@pytest.mark.parametrize("mul_j", [False, True])
def test_additive_scales_preserved_by_imaginary_join(operation_type, mul_j):
    operation = operation_type(in0_scale=1, in1_scale=2, out0_scale=1, mul_j=mul_j)
    joined = ImaginaryMultiplication()._join(operation)
    fused = joined.find_by_type(operation_type)[0]
    assert (fused.in0_scale, fused.in1_scale, fused.out0_scale) == (1, 2, 1)
    first, second = 9 + 3j, -7 + 5j
    assert joined.evaluate_output(0, [first, second]) == operation.evaluate_output(
        0, [first, second * 1j]
    )


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
            ValueError, match=r"core_operations.Min does not support complex numbers."
        ):
            test_operation.evaluate_output(0, [-1 - 1j, 2 + 2j])


class TestComparator:
    """Tests for Comparator class."""

    @pytest.mark.parametrize(
        ("inputs", "expected"),
        [
            ((3, 5), (3, 5)),
            ((5, 3), (3, 5)),
            ((-3, -5), (-5, -3)),
            ((-3, 5), (-3, 5)),
            ((0, 0), (0, 0)),
            ((2.5, -1.25), (-1.25, 2.5)),
        ],
    )
    def test_outputs(self, inputs, expected):
        operation = Comparator()
        assert operation.input_count == 2
        assert operation.output_count == 2
        assert operation.evaluate(*inputs) == expected
        for index, value in enumerate(expected):
            assert operation.evaluate_output(index, inputs) == value

    @pytest.mark.parametrize("inputs", [(1j, 2), (1, 2j)])
    def test_complex_inputs(self, inputs):
        with pytest.raises(
            ValueError, match="Comparator does not support complex numbers"
        ):
            Comparator().evaluate(*inputs)

    def test_data_type(self):
        data_type = DataType(wl=(4, 2))
        a = apy.fx(2.5, 4, 2)
        b = apy.fx(-1.25, 4, 2)
        smallest, largest = Comparator().evaluate(a, b, data_type=data_type)
        assert smallest is b
        assert largest is a

    def test_configuration(self):
        first, second = Input(), Input()
        operation = Comparator(first, second, name="sort", latency=3, execution_time=1)
        assert operation.type_name() == "cmp"
        assert operation.name == "sort"
        assert operation.input(0).connected_source == first.output(0)
        assert operation.input(1).connected_source == second.output(0)
        assert operation.latency_offsets == {"in0": 0, "in1": 0, "out0": 3, "out1": 3}
        assert operation.execution_time == 1

    @pytest.mark.parametrize("source", [Min, Max])
    @pytest.mark.parametrize(
        "offsets",
        [None, {"in0": 1, "in1": 2, "out0": 4, "out1": 5}],
    )
    def test_rewrite(self, source, offsets):
        comparator = Comparator(name="sort", latency_offsets=offsets, execution_time=2)
        rewritten = getattr(comparator, f"_rewrite_{source.__name__}")()
        assert rewritten.input_count == 2
        assert rewritten.output_count == 2
        assert not rewritten.find_by_type(Comparator)
        for index, operation_type in enumerate((Min, Max)):
            (operation,) = rewritten.find_by_type(operation_type)
            assert operation.name == comparator.name
            assert operation.execution_time == comparator.execution_time
            assert operation.latency_offsets == {
                "in0": comparator.input(0).latency_offset,
                "in1": comparator.input(1).latency_offset,
                "out0": comparator.output(index).latency_offset,
            }
        assert rewritten.evaluate_outputs([5, -3]) == [-3, 5]


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
            ValueError, match=r"core_operations.Max does not support complex numbers."
        ):
            test_operation.evaluate_output(0, [-1 - 1j, 2 + 2j])


class TestImaginaryMultiplication:
    """Tests for ImaginaryMultiplication class."""

    def test_imaginarymultiplication_positive(self):
        test_operation = ImaginaryMultiplication()
        assert test_operation.evaluate_output(0, [3]) == 3j

    def test_imaginarymultiplication_negative(self):
        test_operation = ImaginaryMultiplication()
        assert test_operation.evaluate_output(0, [-3]) == -3j

    def test_imaginarymultiplication_complex(self):
        test_operation = ImaginaryMultiplication()
        assert test_operation.evaluate_output(0, [3 + 4j]) == -4 + 3j


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
            in0=Constant(3),
            in1=Addition(Input(), Constant(3)),
            in2=Addition(Input(), Constant(3)),
        )
        assert not test_operation.is_linear

        test_operation = MADS(
            in0=Addition(Input(), Constant(3)),
            in1=Constant(3),
            in2=Addition(Input(), Constant(3)),
        )
        assert test_operation.is_linear

        test_operation = MADS(
            in0=Addition(Input(), Constant(3)),
            in1=Addition(Input(), Constant(3)),
            in2=Constant(3),
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
        with pytest.raises(TypeError, match=r"value must be an int"):
            _ = RightShift(0.5)
        test_operation = RightShift(0)
        with pytest.raises(TypeError, match=r"value must be an int"):
            test_operation.value = 0.5

        with pytest.raises(ValueError, match=r"value must be non-negative"):
            _ = RightShift(-1)
        test_operation = RightShift(0)
        with pytest.raises(ValueError, match=r"value must be non-negative"):
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
        with pytest.raises(TypeError, match=r"value must be an int"):
            _ = LeftShift(0.5)
        test_operation = LeftShift(0)
        with pytest.raises(TypeError, match=r"value must be an int"):
            test_operation.value = 0.5

        with pytest.raises(ValueError, match=r"value must be non-negative"):
            _ = LeftShift(-1)
        test_operation = LeftShift(0)
        with pytest.raises(ValueError, match=r"value must be non-negative"):
            test_operation.value = -1


class TestShift:
    """Tests for Shift class."""

    def test_shift_positive(self):
        test_operation = Shift(-2)
        assert test_operation.evaluate_output(0, [5]) == 20
        assert test_operation.value == -2

        test_operation = Shift(2)
        assert test_operation.evaluate_output(0, [5]) == 1.25
        assert test_operation.value == 2

    def test_shift_negative(self):
        test_operation = Shift(-2)
        assert test_operation.evaluate_output(0, [-5]) == -20

        test_operation = Shift(2)
        assert test_operation.evaluate_output(0, [-5]) == -1.25

    def test_shift_complex(self):
        test_operation = Shift(-2)
        assert test_operation.evaluate_output(0, [0.5 + 0.25j]) == 2 + 1j

        test_operation = Shift(2)
        assert test_operation.evaluate_output(0, [2 + 1j]) == 0.5 + 0.25j

    @pytest.mark.parametrize("val", [-0.5, 0.5])
    def test_leftshift_errors(self, val):
        with pytest.raises(TypeError, match=r"value must be an int"):
            _ = Shift(val)
        test_operation = Shift(0)
        with pytest.raises(TypeError, match=r"value must be an int"):
            test_operation.value = val


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


class TestReciprocalSquareRoot:
    def test_positive(self):
        test_operation = ReciprocalSquareRoot()
        assert test_operation.evaluate_output(0, [4]) == 0.5

    def test_complex(self):
        test_operation = ReciprocalSquareRoot()
        a = 4 + 2j
        result = test_operation.evaluate_output(0, [a])
        assert result == a**-0.5

    def test_zero(self):
        test_operation = ReciprocalSquareRoot()
        assert test_operation.evaluate_output(0, [0]) == float("inf")

    def test_apyfixed_positive(self):
        test_operation = ReciprocalSquareRoot()
        a = apy.fx(4.0, int_bits=4, frac_bits=4)
        assert test_operation.evaluate_output(0, [a]) == 0.5

    def test_apyfixed_complex(self):
        test_operation = ReciprocalSquareRoot()
        a = apy.APyCFixed.from_complex(4 + 2j, int_bits=4, frac_bits=4)
        result = test_operation.evaluate_output(0, [a])
        assert result == (4 + 2j) ** -0.5

    def test_apyfixed_zero(self):
        test_operation = ReciprocalSquareRoot()
        a = apy.fx(0.0, int_bits=4, frac_bits=4)
        assert test_operation.evaluate_output(0, [a]) == float("inf")

    def test_apyfloat_positive(self):
        test_operation = ReciprocalSquareRoot()
        a = apy.fp(16, exp_bits=8, man_bits=23)
        assert test_operation.evaluate_output(0, [a]) == 0.25

    def test_apyfloat_complex(self):
        test_operation = ReciprocalSquareRoot()
        a = apy.fp(-2 - 3j, exp_bits=8, man_bits=23)
        result = test_operation.evaluate_output(0, [a])
        assert result == (-2 - 3j) ** -0.5

    def test_apyfloat_zero(self):
        test_operation = ReciprocalSquareRoot()
        a = apy.fp(0.0, exp_bits=8, man_bits=23)
        assert test_operation.evaluate_output(0, [a]) == float("inf")

    def test_real_valued_complex_input(self):
        test_operation = ReciprocalSquareRoot(real_valued=True)
        assert test_operation.evaluate_output(0, [4 + 2j]) == 0.5

    def test_real_valued_apycfixed(self):
        test_operation = ReciprocalSquareRoot(real_valued=True)
        a = apy.APyCFixed.from_complex(9 + 2j, int_bits=5, frac_bits=4)
        assert test_operation.evaluate_output(0, [a]) == 1 / 3

    def test_real_valued_apycfixed_zero(self):
        test_operation = ReciprocalSquareRoot(real_valued=True)
        a = apy.APyCFixed.from_complex(0 + 2j, int_bits=4, frac_bits=4)
        assert test_operation.evaluate_output(0, [a]) == float("inf")


class TestDepends:
    def test_depends_addition(self):
        add1 = Addition()
        assert set(add1.inputs_required_for_output(0)) == {0, 1}

    def test_depends_butterfly(self):
        bfly1 = R2Butterfly()
        assert set(bfly1.inputs_required_for_output(0)) == {0, 1}
        assert set(bfly1.inputs_required_for_output(1)) == {0, 1}
