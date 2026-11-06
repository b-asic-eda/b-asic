"""Constant propagation preserves explicit sinks and their terminated branches."""

import pytest

from b_asic.core_operations import Addition, Constant, ConstantMultiplication
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output
from b_asic.utility_operations import Sink
from test.unit.test_wdf_propagation import ADAPTORS


@pytest.mark.parametrize("has_output", [False, True])
@pytest.mark.parametrize("constant_result", [False, True])
def test_preserve_sink_through_repeated_constant_propagation(
    has_output, constant_result
):
    source = Input()
    operation = (
        ConstantMultiplication(0, source)
        if constant_result
        else Addition(source, Constant(0))
    )
    sink = Sink(operation, name="termination")
    sink.input(0).signals[0].name = "terminated signal"
    original = SFG([source], [Output(source)] if has_output else [])

    simplified = original
    for _ in range(2):
        simplified = simplified.constant_propagation()
        (retained,) = simplified.find_by_type(Sink)
        assert retained.name == "termination"
        assert retained.input(0).signals[0].name == "terminated signal"
        upstream = retained.input(0).connected_source.operation
        if constant_result:
            assert isinstance(upstream, Constant)
            assert upstream.value == 0
        else:
            assert isinstance(upstream, Input)
        assert not simplified.find_by_type(Addition)
        assert not simplified.find_by_type(ConstantMultiplication)
        assert simplified.evaluate_outputs([3]) == ([3] if has_output else [])
    assert original.find_by_type(Sink)
    assert original.find_by_type(type(operation))


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
def test_preserve_sinks_on_simplified_adaptor_outputs(adaptor_type, coefficient, ports):
    inputs = [Input() for _ in range(ports - 1)]
    adaptor = adaptor_type(coefficient, Constant(0), *inputs)
    for index in range(1, ports):
        Sink(adaptor.output(index), name=f"termination {index}")
    original = SFG(inputs, [Output(adaptor.output(0))])
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(adaptor_type)
    assert {op.name for op in simplified.find_by_type(Sink)} == {
        f"termination {index}" for index in range(1, ports)
    }
    assert all(
        op.input(0).connected_source is not None for op in simplified.find_by_type(Sink)
    )
    values = [2 + 3j] * (ports - 1)
    assert simplified.evaluate_outputs(values) == pytest.approx(
        original.evaluate_outputs(values)
    )


def test_sink_propagation_can_still_remove_terminated_arithmetic():
    source = Input()
    Sink(Addition(source, Constant(1)))
    original = SFG([source], [Output(source)])
    constants = original.constant_propagation()
    assert constants.find_by_type(Sink)
    assert constants.find_by_type(Addition)
    simplified = constants.sink_propagation()
    assert not simplified.find_by_type(Sink)
    assert not simplified.find_by_type(Addition)


@pytest.mark.parametrize("expand", [False, True])
@pytest.mark.parametrize("constant_result", [False, True])
def test_flatten_preserves_sinks(expand, constant_result):
    source = Input()
    operation = ConstantMultiplication(0, source) if constant_result else source
    Sink(operation, name="termination")
    original = SFG([source], [Output(source)]).constant_propagation()
    flattened = original.flatten(expand)
    assert len(flattened.find_by_type(Sink)) == 1
    assert flattened.find_by_type(Sink)[0].name == "termination"
    assert flattened.evaluate_outputs([3]) == [3]
    assert len(original.find_by_type(Sink)) == 1


@pytest.mark.parametrize("expand", [False, True])
@pytest.mark.parametrize("constant_result", [False, True])
@pytest.mark.parametrize("has_output", [False, True])
def test_flatten_nested_sinks(expand, constant_result, has_output):
    inner_input = Input()
    operation = (
        ConstantMultiplication(0, inner_input) if constant_result else inner_input
    )
    Sink(operation, name="nested termination")
    inner = SFG(
        [inner_input], [Output(inner_input)] if has_output else []
    ).constant_propagation()
    outer_input = Input()
    instance = inner(outer_input)
    outer = SFG([outer_input], [Output(instance)] if has_output else [])
    flattened = outer.flatten(expand)
    assert not flattened.find_by_type(SFG)
    (sink,) = flattened.find_by_type(Sink)
    assert sink.name == "nested termination"
    assert sink.input(0).connected_source is not None
    assert flattened.evaluate_outputs([3]) == ([3] if has_output else [])
    assert outer.find_by_type(SFG)


@pytest.mark.parametrize("expand", [False, True])
def test_flatten_sinks_with_unused_nested_input(expand):
    inner_input = Input()
    Sink(ConstantMultiplication(0, inner_input), name="constant termination")
    inner = SFG([inner_input], [Output(Constant(2))]).constant_propagation()
    outer_input = Input()
    outer = SFG([outer_input], [Output(inner(outer_input))])
    flattened = outer.flatten(expand)
    assert not flattened.find_by_type(SFG)
    assert len(flattened.find_by_type(Sink)) == 1
    assert flattened.evaluate_outputs([3]) == [2]


def test_expand_composite_operation_with_sink():
    from b_asic.wdf_operations import SymmetricTwoportAdaptor

    first, second = Input(), Input()
    adaptor = SymmetricTwoportAdaptor(0.25, first, second)
    Sink(adaptor.output(1), name="adaptor termination")
    original = SFG([first, second], [Output(adaptor.output(0))])
    flattened = original.flatten(True)
    assert not flattened.find_by_type(SymmetricTwoportAdaptor)
    assert not flattened.find_by_type(SFG)
    assert len(flattened.find_by_type(Sink)) == 1
    assert flattened.find_by_type(Sink)[0].name == "adaptor termination"
    assert flattened.evaluate_outputs([2, 3]) == original.evaluate_outputs([2, 3])
