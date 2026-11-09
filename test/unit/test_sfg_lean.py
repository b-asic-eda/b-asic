"""Lean expression export tests."""

from fractions import Fraction

import pytest

from b_asic.core_operations import (
    Absolute,
    Addition,
    AddSub,
    Comparator,
    Constant,
    ConstantMultiplication,
    ImaginaryMultiplication,
    Negation,
    SquareRoot,
    Subtraction,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.operation import AbstractOperation, Operation
from b_asic.sfg import SFG
from b_asic.special_operations import Delay, Input, Output
from b_asic.wdf_operations import SymmetricTwoportAdaptor


def test_lean_shared_arithmetic_and_interface_order():
    x, y = Input("let"), Input("bad name")
    shared = x - y
    graph = SFG([y, x], [Output(shared * shared), Output(shared / -x)])
    result = graph.to_lean()
    assert result == (
        "fun (x0 : Real) (x1 : Real) =>\n"
        "  let v0 : Real := (x1 - x0)\n"
        "  let v1 : Real := (v0 * v0)\n"
        "  let v2 : Real := (-x1)\n"
        "  let v3 : Real := (v0 / v2)\n"
        "  (v1, v3)"
    )
    assert graph.to_lean() == result


@pytest.mark.parametrize(
    ("value", "literal"),
    [
        (2, "(2 : Real)"),
        (-3, "(-3 : Real)"),
        (0.5, "(1 / 2 : Real)"),
        (Fraction(-2, 3), "(-2 / 3 : Real)"),
    ],
)
def test_lean_constants(value, literal):
    result = SFG(outputs=Output(Constant(value))).to_lean()
    assert literal in result
    assert "fun" not in result


def test_lean_feedback_and_next_state():
    x = Input()
    delay = Delay(initial_value=3)
    add = Addition(x, delay)
    delay.input(0).connect(add)
    graph = SFG(x, Output(add))
    assert graph.to_lean() == (
        "structure State where\n  s0 : Real\n\n"
        "def initialState : State :=\n  { s0 := (3 : Real) }\n\n"
        "def step (state : State) (x0 : Real) : Real \u00d7 State :=\n"
        "  let v0 : Real := (x0 + state.s0)\n  (v0, { s0 := v0 })"
    )
    assert graph.find_by_type(Delay)[0].initial_value == 3


def test_lean_delay_updates_are_simultaneous():
    x = Input()
    graph = SFG(x, Output(Delay(Delay(x))))
    delays = sorted(graph.find_by_type(Delay), key=lambda op: op.graph_id)
    state_names = {op.output(0): f"state.s{i}" for i, op in enumerate(delays)}
    state_names[graph.input_operations[0].output(0)] = "x0"
    updates = [state_names[op.input(0).connected_source] for op in delays]
    output = state_names[graph.output_operations[0].input(0).connected_source]
    record = ", ".join(f"s{i} := {value}" for i, value in enumerate(updates))
    assert graph.to_lean().endswith(f"({output}, {{ {record} }})")


def test_lean_nested_graph():
    x = Input()
    inner = SFG(x, Output(ConstantMultiplication(0.5, x)))
    outer_x = Input()
    graph = SFG(outer_x, Output(inner(outer_x)))
    result = graph.to_lean()
    assert "((1 / 2 : Real) * x0)" in result
    assert len(graph.find_by_type(SFG)) == 1


@pytest.mark.parametrize("operation", [R2Butterfly, Comparator])
def test_lean_multi_output_operation(operation):
    x, y = Input(), Input()
    op = operation(x, y)
    graph = SFG([x, y], [Output(op.output(1)), Output(op.output(0))])
    result = graph.to_lean()
    if operation is R2Butterfly:
        assert "(x0 - x1)" in result
        assert "(x0 + x1)" in result
    else:
        assert "(max x0 x1)" in result
        assert "(min x0 x1)" in result
    assert result.endswith("(v0, v1)")


def test_lean_real_functions_and_scaled_addsub():
    x, y = Input(), Input()
    op = AddSub(False, x, y, in0_scale=1, in1_scale=2, out0_scale=3)
    graph = SFG([x, y], Output(SquareRoot(Absolute(op))))
    result = graph.to_lean()
    assert "((x0 / (2 : Real) ^ (1 : Int)) - (x1 / (2 : Real) ^ (2 : Int)))" in result
    assert "(2 : Real) ^ (3 : Int)" in result
    assert "(abs v0)" in result
    assert "(Real.sqrt v1)" in result


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_lean_nonfinite_constant(value):
    with pytest.raises(ValueError, match="finite"):
        SFG(outputs=Output(Constant(value))).to_lean()


def test_lean_complex_constant_and_unsupported_operation():
    with pytest.raises(NotImplementedError, match="real constants"):
        SFG(outputs=Output(Constant(1j))).to_lean()
    x = Input()
    with pytest.raises(NotImplementedError, match="ImaginaryMultiplication"):
        SFG(x, Output(ImaginaryMultiplication(x))).to_lean()


def test_lean_combinational_cycle():
    x = Input()
    add = Addition(x, x)
    graph = SFG(x, Output(add))
    internal_add = graph.find_by_type(Addition)[0]
    internal_add.input(1).signals[0].set_source(internal_add.output(0))
    with pytest.raises(ValueError, match="combinational cycles"):
        graph.to_lean()


def test_lean_empty_and_passthrough():
    assert SFG().to_lean() == "()"
    x = Input()
    assert SFG(x, Output(x)).to_lean() == "fun (x0 : Real) =>\n  x0"


def test_lean_custom_operation_dispatch():
    class CustomNegation(Negation):
        def _lean(self, inputs, output_index=0):
            assert output_index == 0
            return f"(0 - {inputs[0]})"

    x = Input()
    assert "(0 - x0)" in SFG(x, Output(CustomNegation(x))).to_lean()


def test_lean_inherited_operation_dispatch():
    class CustomAddition(Addition):
        pass

    x, y = Input(), Input()
    assert "(x0 + x1)" in SFG([x, y], Output(CustomAddition(x, y))).to_lean()


@pytest.mark.parametrize("operation", [Addition, Subtraction])
def test_lean_add_sub_scaling(operation):
    x, y = Input(), Input()
    op = operation(x, y, in0_scale=1, in1_scale=2, out0_scale=3)
    result = SFG([x, y], Output(op)).to_lean()
    operator = "+" if operation is Addition else "-"
    assert (
        f"((x0 / (2 : Real) ^ (1 : Int)) {operator} (x1 / (2 : Real) ^ (2 : Int)))"
        in result
    )
    assert "(2 : Real) ^ (3 : Int)" in result


@pytest.mark.parametrize("operation", [Addition, Subtraction, AddSub])
def test_lean_add_sub_rejects_complex_multiplication(operation):
    x, y = Input(), Input()
    op = operation(in0=x, in1=y, mul_j=True)
    with pytest.raises(NotImplementedError, match=operation.__name__):
        SFG([x, y], Output(op)).to_lean()


def test_lean_initial_state_and_transition():
    x = Input()
    delay = Delay(initial_value=Fraction(2, 3))
    add = Addition(x, delay)
    delay.input(0).connect(add)
    graph = SFG(x, Output(add))
    assert graph.to_lean() == (
        "structure State where\n  s0 : Real\n\n"
        "def initialState : State :=\n  { s0 := (2 / 3 : Real) }\n\n"
        "def step (state : State) (x0 : Real) : Real \u00d7 State :=\n"
        "  let v0 : Real := (x0 + state.s0)\n  (v0, { s0 := v0 })"
    )


def test_lean_multiple_initial_states_use_transition_order():
    x = Input()
    graph = SFG(x, Output(Delay(Delay(x, initial_value=2), initial_value=5)))
    delays = sorted(graph.find_by_type(Delay), key=lambda op: op.graph_id)
    initial = ", ".join(
        f"s{i} := ({op.initial_value} : Real)" for i, op in enumerate(delays)
    )
    result = graph.to_lean()
    assert "structure State where\n  s0 : Real\n  s1 : Real" in result
    assert f"def initialState : State :=\n  {{ {initial} }}" in result


@pytest.mark.parametrize("value", [float("inf"), float("nan"), 1j])
def test_lean_rejects_invalid_initial_state(value):
    x = Input()
    graph = SFG(x, Output(Delay(x, initial_value=value)))
    with pytest.raises(
        (ValueError, NotImplementedError), match=r"finite|real constants"
    ):
        graph.to_lean()


def test_lean_state_without_inputs():
    delay = Delay(initial_value=1)
    delay.input(0).connect(delay)
    result = SFG(outputs=Output(delay)).to_lean()
    assert "def step (state : State) : Real \u00d7 State :=" in result
    assert result.endswith("(state.s0, { s0 := state.s0 })")


def test_lean_composite_multi_output_operation():
    x, y = Input(), Input()
    adaptor = SymmetricTwoportAdaptor(0.5, x, y)
    graph = SFG([x, y], [Output(adaptor.output(1)), Output(adaptor.output(0))])
    expanded = graph.flatten(expand=True)
    assert graph.to_lean() == expanded.to_lean()
    assert len(graph.find_by_type(SymmetricTwoportAdaptor)) == 1


def test_lean_stateful_multi_output_composite():
    class RegisteredButterfly(R2Butterfly):
        _lean = Operation._lean

        def to_sfg(self):
            x, y = Input(), Input()
            state = Delay(initial_value=7)
            butterfly = R2Butterfly(x, state)
            state.input(0).connect(butterfly.output(1))
            return SFG([x, y], [Output(butterfly.output(0)), Output(state + y)])

    x, y = Input(), Input()
    operation = RegisteredButterfly(x, y)
    graph = SFG([x, y], [Output(operation.output(1)), Output(operation.output(0))])
    result = graph.to_lean()
    assert "def initialState : State :=\n  { s0 := (7 : Real) }" in result
    assert (
        "def step (state : State) (x0 : Real) (x1 : Real) : (Real \u00d7 Real) \u00d7 State :="
        in result
    )
    assert "(state.s0 + x1)" in result
    assert "(x0 + state.s0)" in result
    assert "(x0 - state.s0)" in result
    assert result.endswith("((v0, v1), { s0 := v2 })")
    assert len(graph.find_by_type(RegisteredButterfly)) == 1
    assert not graph.find_by_type(Delay)


def test_lean_multi_output_primitive_conversion():
    # Comparator cannot evaluate symbolic Inputs through Python's min/max, so
    # to_sfg() must wrap the operation while preserving both of its output ports.
    graph = Comparator().to_sfg()
    assert graph.output_count == 2
    assert graph.evaluate(5, 2) == [2, 5]
    assert "min x0 x1" in graph.to_lean()
    assert "max x0 x1" in graph.to_lean()


def test_lean_three_outputs_with_feedback_and_sharing():
    class ThreeOutputs(AbstractOperation):
        def __init__(self, source=None):
            super().__init__(input_count=1, output_count=3, input_sources=[source])

        @classmethod
        def type_name(cls):
            return "triple"

        def _lean(self, inputs, output_index=0):
            return f"({inputs[0]} + ({output_index} : Real))"

        def evaluate(self, value, data_type=None):
            return tuple(value + index for index in range(3))

    x = Input()
    delay = Delay(initial_value=4)
    operation = ThreeOutputs(x + delay)
    delay.input(0).connect(operation.output(2))
    graph = SFG(x, [Output(operation.output(i)) for i in (2, 0, 1)])
    result = graph.to_lean()
    assert "(Real \u00d7 Real \u00d7 Real) \u00d7 State" in result
    assert result.count("(x0 + state.s0)") == 1
    assert "(v0 + (2 : Real))" in result
    assert "(v0 + (0 : Real))" in result
    assert "(v0 + (1 : Real))" in result
    assert result.endswith("((v1, v2, v3), { s0 := v1 })")


def test_lean_nested_stateful_multi_output_graph():
    x = Input()
    inner = SFG(
        x, [Output(Delay(x, initial_value=2)), Output(Delay(x, initial_value=5))]
    )
    outer_input = Input()
    instance = inner(outer_input)
    graph = SFG(outer_input, [Output(instance.output(1)), Output(instance.output(0))])
    result = graph.to_lean()
    assert result == graph.flatten().to_lean()
    assert "structure State where\n  s0 : Real\n  s1 : Real" in result
    assert "(Real \u00d7 Real) \u00d7 State" in result
    assert "{ s0 := x0, s1 := x0 }" in result
    assert len(graph.find_by_type(SFG)) == 1
