"""Delay expansion by the noble transformation."""

import numpy as np
import pytest

from b_asic.core_operations import Addition, Constant, ConstantMultiplication
from b_asic.sfg import SFG
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay, Input, Output
from b_asic.utility_operations import Sink


@pytest.mark.parametrize("n", [1, 2, 3])
def test_expand_delay_and_initial_state(n):
    source = Input("x")
    delay = Delay(source, initial_value=7, name="state")
    original = SFG([source], [Output(delay, "y")], name="filter")
    transformed = original.noble_transform(n)
    assert len(transformed.find_by_type(Delay)) == n
    assert len(original.find_by_type(Delay)) == 1
    assert all(op.initial_value == 7 for op in transformed.find_by_type(Delay))
    assert transformed.name == "filter"
    assert transformed.input_operations[0].name == "x"
    assert transformed.output_operations[0].name == "y"
    simulation = Simulation(transformed, [[1, 2, 3, 4, 5]])
    simulation.run_for(5)
    np.testing.assert_array_equal(
        simulation.results["out0"], ([7] * n + [1, 2, 3, 4, 5])[:5]
    )


def test_expand_all_delays_and_preserve_fanout():
    source = Input()
    first = Delay(source)
    second = Delay(first)
    original = SFG([source], [Output(first), Output(second)])
    transformed = original.noble_transform(3)
    assert len(transformed.find_by_type(Delay)) == 6
    simulation = Simulation(transformed, [[1] * 8])
    simulation.run_for(8)
    np.testing.assert_array_equal(simulation.results["out0"], [0] * 3 + [1] * 5)
    np.testing.assert_array_equal(simulation.results["out1"], [0] * 6 + [1] * 2)


@pytest.mark.parametrize("n", [2, 3])
def test_expand_feedback(n):
    source = Input()
    delay = Delay()
    accumulator = Addition(source, delay)
    delay <<= accumulator
    original = SFG([source], [Output(accumulator)])
    transformed = original.noble_transform(n)
    assert len(transformed.find_by_type(Delay)) == n
    simulation = Simulation(transformed, [[1] * 9])
    simulation.run_for(9)
    np.testing.assert_array_equal(
        simulation.results["out0"], [1 + i // n for i in range(9)]
    )


def test_expand_nested_sfg():
    inner_input = Input()
    inner = SFG([inner_input], [Output(Delay(inner_input))])
    source = Input()
    original = SFG([source], [Output(Delay(inner(source)))])
    transformed = original.noble_transform(3)
    assert len(transformed.find_by_type(Delay)) == 3
    assert len(transformed.find_by_type(SFG)) == 1
    assert len(transformed.find_by_type(SFG)[0].find_by_type(Delay)) == 3
    assert len(transformed.flatten().find_by_type(Delay)) == 6
    assert len(original.flatten().find_by_type(Delay)) == 2


def test_cascade_connected_transformed_instances():
    ref_input = Input()
    ref = SFG([ref_input], [Output(Delay(ref_input))])
    source = Input("foo")
    a = ref(source).noble_transform(2)
    b = ref(a).noble_transform(2)
    cascade = SFG([source], [Output(ref(b))])
    assert len(cascade.find_by_type(SFG)) == 3
    assert sorted(
        len(stage.find_by_type(Delay)) for stage in cascade.find_by_type(SFG)
    ) == [1, 2, 4]
    assert len(cascade.flatten().find_by_type(Delay)) == 7
    simulation = Simulation(cascade, [[1, 2, 3, 4, 5, 6, 7, 8]])
    simulation.run_for(8)
    np.testing.assert_array_equal(simulation.results["out0"], [0] * 7 + [1])
    upstream = b.input(0).connected_source.operation
    assert upstream.input(0).connected_source is source.output(0)
    assert len(upstream.find_by_type(Delay)) == 4
    assert len(ref.find_by_type(Delay)) == 1


def test_shared_upstream_stage_transformed_once():
    ref_input = Input()
    ref = SFG([ref_input], [Output(Delay(ref_input))])
    source = Input()
    upstream = ref(source)
    first, second = Input(), Input()
    adder = SFG([first, second], [Output(Addition(first, second))])
    result = adder(upstream, upstream).noble_transform(2)
    cascade = SFG([source], [Output(result)])
    assert len(cascade.find_by_type(SFG)) == 2
    assert len(cascade.flatten().find_by_type(Delay)) == 2
    simulation = Simulation(cascade, [[1, 2, 3, 4]])
    simulation.run_for(4)
    np.testing.assert_array_equal(simulation.results["out0"], [0, 0, 2, 4])


def test_upstream_transform_through_primitive_operations():
    ref_input = Input()
    ref = SFG([ref_input], [Output(Delay(ref_input))])
    source = Input()
    first = ref(source).noble_transform(2)
    bridge = ConstantMultiplication(3, Delay(first))
    last = ref(bridge).noble_transform(2)
    cascade = SFG([source], [Output(last)])
    assert len(cascade.find_by_type(SFG)) == 2
    assert len(cascade.flatten().find_by_type(Delay)) == 8
    simulation = Simulation(cascade, [[1] * 9])
    simulation.run_for(9)
    np.testing.assert_array_equal(simulation.results["out0"], [0] * 8 + [3])


@pytest.mark.parametrize("n", [1, 2])
def test_connected_instance_transfers_external_connections(n):
    source, other = Input(), Input()
    ref = SFG([source, other], [Output(Addition(Delay(source), other))])
    first, second = Input(), Input()
    original = ref(first, second)
    original.input(0).signals[0].name = "incoming signal"
    incoming = original.input(0).signals[0]
    consumer = Output(original)
    outgoing = consumer.input(0).signals[0]
    transformed = original.noble_transform(n)
    assert original.input(0).connected_source is None
    assert original.input(1).connected_source is None
    assert transformed.input(0).connected_source is first.output(0)
    assert transformed.input(1).connected_source is second.output(0)
    assert transformed.input(0).signals[0].name == "incoming signal"
    assert transformed.input(0).signals[0] is incoming
    assert consumer.input(0).connected_source is transformed.output(0)
    assert consumer.input(0).signals[0] is outgoing
    assert not original.output(0).signals
    assert len(first.output(0).signals) == len(second.output(0).signals) == 1
    assert len(original.find_by_type(Delay)) == 1
    assert len(transformed.find_by_type(Delay)) == n


def test_partially_connected_instance():
    first, second = Input(), Input()
    ref = SFG([first, second], [Output(Addition(first, Delay(second)))])
    source = Input()
    original = ref(source, None)
    transformed = original.noble_transform(2)
    assert transformed.input(0).connected_source is source.output(0)
    assert transformed.input(1).connected_source is None
    assert len(transformed.find_by_type(Delay)) == 2


def test_sink_branches_retained():
    source = Input()
    Sink(Delay(source), name="termination")
    Sink(ConstantMultiplication(0, source), name="constant termination")
    original = SFG([source], [Output(source)]).constant_propagation()
    transformed = original.noble_transform(2)
    assert len(transformed.find_by_type(Delay)) == 2
    assert {op.name for op in transformed.find_by_type(Sink)} == {
        "termination",
        "constant termination",
    }
    assert transformed.evaluate_outputs([3]) == [3]


def test_graph_without_delays_and_empty_graph():
    original = SFG([], [Output(Constant(3))])
    transformed = original.noble_transform(2)
    assert transformed is not original
    assert transformed.evaluate_outputs([]) == [3]
    assert not SFG().noble_transform(2).operations


@pytest.mark.parametrize("n", [0, -1])
def test_nonpositive_factor(n):
    with pytest.raises(ValueError, match="positive"):
        SFG().noble_transform(n)


@pytest.mark.parametrize("n", [1.5, "2", None, True])
def test_noninteger_factor(n):
    with pytest.raises(TypeError, match="integer"):
        SFG().noble_transform(n)
