"""
B-ASIC test suite for the AbstractOperation class.
"""
import re

import pytest

from b_asic import (
    MAD,
    Addition,
    Butterfly,
    Constant,
    ConstantMultiplication,
    Division,
    Multiplication,
    Reciprocal,
    SquareRoot,
    Subtraction,
)


class TestOperationOverloading:
    def test_addition_overload(self):
        """Tests addition overloading for both operation and number argument."""
        add1 = Addition(None, None, "add1")
        add2 = Addition(None, None, "add2")

        add3 = add1 + add2
        assert isinstance(add3, Addition)
        assert add3.input(0).signals == add1.output(0).signals
        assert add3.input(1).signals == add2.output(0).signals

        add4 = add3 + 5
        assert isinstance(add4, Addition)
        assert add4.input(0).signals == add3.output(0).signals
        assert add4.input(1).signals[0].source.operation.value == 5

        add5 = 5 + add4
        assert isinstance(add5, Addition)
        assert add5.input(0).signals[0].source.operation.value == 5
        assert add5.input(1).signals == add4.output(0).signals

        bfly = Butterfly()
        add6 = bfly.output(0) + add5
        assert isinstance(add6, Addition)
        assert add6.input(0).signals == bfly.output(0).signals
        assert add6.input(1).signals == add5.output(0).signals

    def test_subtraction_overload(self):
        """Tests subtraction overloading for both operation and number argument."""
        add1 = Addition(None, None, "add1")
        add2 = Addition(None, None, "add2")

        sub1 = add1 - add2
        assert isinstance(sub1, Subtraction)
        assert sub1.input(0).signals == add1.output(0).signals
        assert sub1.input(1).signals == add2.output(0).signals

        sub2 = sub1 - 5
        assert isinstance(sub2, Subtraction)
        assert sub2.input(0).signals == sub1.output(0).signals
        assert sub2.input(1).signals[0].source.operation.value == 5

        sub3 = 5 - sub2
        assert isinstance(sub3, Subtraction)
        assert sub3.input(0).signals[0].source.operation.value == 5
        assert sub3.input(1).signals == sub2.output(0).signals

        bfly = Butterfly()
        sub4 = bfly.output(0) - sub3
        assert isinstance(sub4, Subtraction)
        assert sub4.input(0).signals == bfly.output(0).signals
        assert sub4.input(1).signals == sub3.output(0).signals

    def test_multiplication_overload(self):
        """Tests multiplication overloading for both operation and number argument."""
        add1 = Addition(None, None, "add1")
        add2 = Addition(None, None, "add2")

        mul1 = add1 * add2
        assert isinstance(mul1, Multiplication)
        assert mul1.input(0).signals == add1.output(0).signals
        assert mul1.input(1).signals == add2.output(0).signals

        mul2 = mul1 * 5
        assert isinstance(mul2, ConstantMultiplication)
        assert mul2.input(0).signals == mul1.output(0).signals
        assert mul2.value == 5

        mul3 = 5 * mul2
        assert isinstance(mul3, ConstantMultiplication)
        assert mul3.input(0).signals == mul2.output(0).signals
        assert mul3.value == 5

    def test_division_overload(self):
        """Tests division overloading for both operation and number argument."""
        add1 = Addition(None, None, "add1")
        add2 = Addition(None, None, "add2")

        div1 = add1 / add2
        assert isinstance(div1, Division)
        assert div1.input(0).signals == add1.output(0).signals
        assert div1.input(1).signals == add2.output(0).signals

        div2 = div1 / 5
        assert isinstance(div2, Division)
        assert div2.input(0).signals == div1.output(0).signals
        assert div2.input(1).signals[0].source.operation.value == 5

        div3 = 5 / div2
        assert isinstance(div3, Division)
        assert div3.input(0).signals[0].source.operation.value == 5
        assert div3.input(1).signals == div2.output(0).signals

        div4 = 1 / div3
        assert isinstance(div4, Reciprocal)
        assert div4.input(0).signals == div3.output(0).signals


class TestTraverse:
    def test_traverse_single_tree(self, operation):
        """Traverse a tree consisting of one operation."""
        constant = Constant(None)
        assert list(constant.traverse()) == [constant]

    def test_traverse_tree(self, operation_tree):
        """Traverse a basic addition tree with two constants."""
        assert len(list(operation_tree.traverse())) == 5

    def test_traverse_large_tree(self, large_operation_tree):
        """Traverse a larger tree."""
        assert len(list(large_operation_tree.traverse())) == 13

    def test_traverse_type(self, large_operation_tree):
        result = list(large_operation_tree.traverse())
        assert len(list(filter(lambda type_: isinstance(type_, Addition), result))) == 3
        assert len(list(filter(lambda type_: isinstance(type_, Constant), result))) == 4

    def test_traverse_loop(self, operation_graph_with_cycle):
        assert len(list(operation_graph_with_cycle.traverse())) == 8


class TestToSfg:
    def test_convert_mad_to_sfg(self):
        mad1 = MAD()
        mad1_sfg = mad1.to_sfg()

        assert mad1.evaluate(1, 1, 1) == mad1_sfg.evaluate(1, 1, 1)
        assert len(mad1_sfg.operations) == 6

    def test_butterfly_to_sfg(self):
        but1 = Butterfly()
        but1_sfg = but1.to_sfg()

        assert but1.evaluate(1, 1)[0] == but1_sfg.evaluate(1, 1)[0]
        assert but1.evaluate(1, 1)[1] == but1_sfg.evaluate(1, 1)[1]
        assert len(but1_sfg.operations) == 6

    def test_add_to_sfg(self):
        add1 = Addition()
        add1_sfg = add1.to_sfg()

        assert len(add1_sfg.operations) == 4

    def test_sqrt_to_sfg(self):
        sqrt1 = SquareRoot()
        sqrt1_sfg = sqrt1.to_sfg()

        assert len(sqrt1_sfg.operations) == 3


class TestLatency:
    def test_latency_constructor(self):
        bfly = Butterfly(latency=5)

        assert bfly.latency == 5
        assert bfly.latency_offsets == {
            "in0": 0,
            "in1": 0,
            "out0": 5,
            "out1": 5,
        }

    def test_latency_offsets_constructor(self):
        bfly = Butterfly(latency_offsets={"in0": 2, "in1": 3, "out0": 5, "out1": 10})

        assert bfly.latency == 8
        assert bfly.latency_offsets == {
            "in0": 2,
            "in1": 3,
            "out0": 5,
            "out1": 10,
        }

    def test_latency_and_latency_offsets_constructor(self):
        bfly = Butterfly(latency=5, latency_offsets={"in1": 2, "out0": 9})

        assert bfly.latency == 9
        assert bfly.latency_offsets == {
            "in0": 0,
            "in1": 2,
            "out0": 9,
            "out1": 5,
        }

    def test_set_latency(self):
        bfly = Butterfly()

        bfly.set_latency(9)

        assert bfly.latency == 9
        assert bfly.latency_offsets == {
            "in0": 0,
            "in1": 0,
            "out0": 9,
            "out1": 9,
        }

    def test_set_latency_negative(self):
        with pytest.raises(ValueError, match="Latency cannot be negative"):
            Butterfly(latency=-1)


class TestExecutionTime:
    def test_execution_time_constructor(self):
        pass

    def test_set_execution_time(self):
        bfly = Butterfly()
        bfly.execution_time = 3

        assert bfly.execution_time == 3

    def test_set_execution_time_negative(self):
        bfly = Butterfly()
        with pytest.raises(ValueError, match="Execution time cannot be negative"):
            bfly.execution_time = -1


class TestCopyOperation:
    def test_copy_butterfly_latency_offsets(self):
        bfly = Butterfly(latency_offsets={"in0": 4, "in1": 2, "out0": 10, "out1": 9})

        bfly_copy = bfly.copy()

        assert bfly_copy.latency_offsets == {
            "in0": 4,
            "in1": 2,
            "out0": 10,
            "out1": 9,
        }

    def test_copy_execution_time(self):
        add = Addition()
        add.execution_time = 2

        add_copy = add.copy()

        assert add_copy.execution_time == 2


class TestPlotCoordinates:
    def test_simple_case(self):
        cmult = ConstantMultiplication(0.5)
        cmult.execution_time = 1
        cmult.set_latency(3)

        lat, exe = cmult.get_plot_coordinates()
        assert lat == ((0, 0), (0, 1), (3, 1), (3, 0), (0, 0))
        assert exe == ((0, 0), (0, 1), (1, 1), (1, 0), (0, 0))

    def test_complicated_case(self):
        bfly = Butterfly(latency_offsets={"in0": 2, "in1": 3, "out0": 5, "out1": 10})
        bfly.execution_time = 7

        lat, exe = bfly.get_plot_coordinates()
        assert lat == (
            (2, 0),
            (2, 0.5),
            (3, 0.5),
            (3, 1),
            (10, 1),
            (10, 0.5),
            (5, 0.5),
            (5, 0),
            (2, 0),
        )
        assert exe == ((0, 0), (0, 1), (7, 1), (7, 0), (0, 0))


class TestIOCoordinates:
    def test_simple_case(self):
        cmult = ConstantMultiplication(0.5)
        cmult.execution_time = 1
        cmult.set_latency(3)

        assert cmult.get_input_coordinates() == ((0, 0.5),)
        assert cmult.get_output_coordinates() == ((3, 0.5),)

    def test_complicated_case(self):
        bfly = Butterfly(latency_offsets={"in0": 2, "in1": 3, "out0": 5, "out1": 10})
        bfly.execution_time = 7

        assert bfly.get_input_coordinates() == ((2, 0.25), (3, 0.75))
        assert bfly.get_output_coordinates() == ((5, 0.25), (10, 0.75))

    def test_io_coordinates_error(self):
        bfly = Butterfly()

        bfly.set_latency_offsets({"in0": 3, "out1": 5})
        with pytest.raises(
            ValueError, match="Missing latencies for input\\(s\\) \\[1\\]"
        ):
            bfly.get_input_coordinates()

        with pytest.raises(
            ValueError, match="Missing latencies for output\\(s\\) \\[0\\]"
        ):
            bfly.get_output_coordinates()


class TestSplit:
    def test_simple_case(self):
        bfly = Butterfly()
        split = bfly.split()
        assert len(split) == 2
        assert sum(isinstance(op, Addition) for op in split) == 1
        assert sum(isinstance(op, Subtraction) for op in split) == 1


class TestLatencyOffset:
    def test_set_latency_offsets(self):
        bfly = Butterfly()

        bfly.set_latency_offsets({"in0": 3, "out1": 5})

        assert bfly.latency_offsets == {
            "in0": 3,
            "in1": None,
            "out0": None,
            "out1": 5,
        }

    def test_set_latency_offsets_error(self):
        bfly = Butterfly()

        with pytest.raises(
            ValueError,
            match=re.escape(
                "Incorrectly formatted index in string, expected 'in' + index,"
                " got: 'ina'"
            ),
        ):
            bfly.set_latency_offsets({"ina": 3, "out1": 5})

        with pytest.raises(
            ValueError,
            match=re.escape(
                "Incorrectly formatted index in string, expected 'out' +"
                " index, got: 'outb'"
            ),
        ):
            bfly.set_latency_offsets({"in1": 3, "outb": 5})

        with pytest.raises(
            ValueError,
            match=re.escape(
                "Incorrectly formatted string, expected 'in' + index or 'out'"
                " + index, got: 'foo'"
            ),
        ):
            bfly.set_latency_offsets({"foo": 3, "out2": 5})


class TestIsSwappable:
    def test_butterfly_is_swappable(self):
        bfly = Butterfly()
        assert not bfly.is_swappable
        with pytest.raises(TypeError, match="operation io cannot be swapped"):
            bfly.swap_io()
