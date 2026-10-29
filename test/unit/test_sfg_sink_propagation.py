"""Backward propagation of unused results from Sink nodes."""

from collections import Counter

import numpy as np
import pytest

from b_asic.core_operations import (
    Addition,
    Constant,
    ConstantMultiplication,
    Multiplication,
    Negation,
    Subtraction,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.operation import Operation
from b_asic.sfg import SFG
from b_asic.sfg_generators import fir
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay, Input, Output
from b_asic.utility_operations import DontCare, Sink


def _sink(source):
    sink = Sink()
    sink.input(0).connect(source)
    return sink


def test_unused_chain_removed_without_changing_original():
    source = Input("x")
    unused = ConstantMultiplication(3, Delay(Addition(source, Constant(1))))
    _sink(unused)
    original = SFG([source], [Output(source, "y")], name="pruning")
    simplified = original.sink_propagation()
    assert simplified.name == original.name
    assert [op.name for op in simplified.input_operations] == ["x"]
    assert [op.name for op in simplified.output_operations] == ["y"]
    assert not simplified.find_by_type(Addition)
    assert not simplified.find_by_type(ConstantMultiplication)
    assert not simplified.find_by_type(Delay)
    assert not simplified.find_by_type(Sink)
    assert simplified.evaluate_outputs([4]) == [4]
    assert original.find_by_type(Addition)


def test_shared_producer_retained():
    first, second = Input(), Input()
    shared = Addition(first, second)
    _sink(shared)
    _sink(Multiplication(shared, second))
    original = SFG([first, second], [Output(shared)])
    simplified = original.sink_propagation()
    assert len(simplified.find_by_type(Addition)) == 1
    assert not simplified.find_by_type(Multiplication)
    assert not simplified.find_by_type(Sink)
    assert simplified.evaluate_outputs([2, 3]) == [5]


def test_entire_unused_graph_terminates_inputs():
    first, second = Input("first"), Input("second")
    _sink(Multiplication(Addition(first, second), second))
    original = SFG([first, second], [])
    simplified = original.sink_propagation()
    assert simplified.input_count == 2
    assert simplified.output_count == 0
    assert not simplified.find_by_type(Addition)
    assert not simplified.find_by_type(Multiplication)
    assert len(simplified.find_by_type(Sink)) == 2
    assert all(
        isinstance(port.signals[0].destination.operation, Sink)
        for op in simplified.input_operations
        for port in op.outputs
    )
    again = simplified.sink_propagation()
    assert Counter(type(op) for op in again.operations) == Counter(
        type(op) for op in simplified.operations
    )


def test_unused_feedback_loop_removed():
    source = Input()
    delay = Delay(initial_value=7)
    accumulator = Addition(source, delay)
    delay <<= accumulator
    _sink(accumulator)
    original = SFG([source], [Output(source)])
    simplified = original.sink_propagation()
    assert not simplified.find_by_type(Addition)
    assert not simplified.find_by_type(Delay)
    assert simplified.evaluate_outputs([3]) == [3]


def test_required_feedback_state_retained():
    source = Input()
    delay = Delay(initial_value=7)
    accumulator = Addition(source, delay)
    delay <<= accumulator
    _sink(Negation(accumulator))
    original = SFG([source], [Output(accumulator)])
    simplified = original.sink_propagation()
    assert not simplified.find_by_type(Negation)
    assert len(simplified.find_by_type(Delay)) == 1
    simulation = Simulation(simplified, [[1, 2, 3]])
    simulation.run_for(3)
    np.testing.assert_array_equal(
        simulation.results[simplified.output_operations[0].graph_id], [8, 10, 13]
    )


@pytest.mark.parametrize("kept", [0, 1])
@pytest.mark.parametrize("explicit_sink", [False, True])
def test_partially_used_butterfly(kept, explicit_sink):
    first, second = Input(), Input()
    butterfly = R2Butterfly(first, second, name="butterfly")
    if explicit_sink:
        _sink(butterfly.output(1 - kept))
    original = SFG([first, second], [Output(butterfly.output(kept))])
    simplified = original.sink_propagation()
    operation_type = Addition if kept == 0 else Subtraction
    assert not simplified.find_by_type(R2Butterfly)
    assert len(simplified.find_by_type(operation_type)) == 1
    assert not simplified.find_by_type(DontCare)
    assert not simplified.find_by_type(Sink)
    values = [2 + 1j, 3 - 2j]
    assert simplified.evaluate_outputs(values) == original.evaluate_outputs(values)
    assert len(original.find_by_type(R2Butterfly)) == 1
    replacement = original.find_by_type(R2Butterfly)[0]._sink_propagation()
    assert replacement.input_count == 2
    assert replacement.output_count == 2
    assert replacement.evaluate_output(kept, values) == original.evaluate_output(
        0, values
    )


def test_live_butterfly_not_rewritten():
    first, second = Input(), Input()
    butterfly = R2Butterfly(first, second)
    original = SFG([first, second], [Output(port) for port in butterfly.outputs])
    assert original.find_by_type(R2Butterfly)[0]._sink_propagation() is None
    simplified = original.sink_propagation()
    assert len(simplified.find_by_type(R2Butterfly)) == 1
    assert simplified.evaluate_outputs([2, 3]) == [5, -1]


def test_unsupported_partial_operation_keeps_sink():
    class OpaqueButterfly(R2Butterfly):
        _sink_propagation = Operation._sink_propagation

    first, second = Input(), Input()
    butterfly = OpaqueButterfly(first, second)
    _sink(butterfly.output(1))
    simplified = SFG([first, second], [Output(butterfly.output(0))]).sink_propagation()
    assert len(simplified.find_by_type(OpaqueButterfly)) == 1
    assert len(simplified.find_by_type(Sink)) == 1
    assert simplified.evaluate_outputs([2, 3]) == [5]


@pytest.mark.parametrize("selection", ["type", "id", "iterator", "empty"])
def test_target_selection(selection):
    first, second = Input(), Input()
    butterflies = [R2Butterfly(first, second, name=name) for name in ("a", "b")]
    for butterfly in butterflies:
        _sink(butterfly.output(1))
    original = SFG([first, second], [Output(b.output(0)) for b in butterflies])
    ids = [op.graph_id for op in original.find_by_type(R2Butterfly)]
    target = {"type": R2Butterfly, "id": ids[0], "iterator": iter(ids), "empty": []}[
        selection
    ]
    simplified = original.sink_propagation(target)
    expected_remaining = {"type": 0, "id": 1, "iterator": 0, "empty": 2}[selection]
    assert len(simplified.find_by_type(R2Butterfly)) == expected_remaining
    assert len(simplified.find_by_type(Addition)) == 2 - expected_remaining
    assert simplified.evaluate_outputs([2, 3]) == [5, 5]


@pytest.mark.parametrize("phase", [0, 1, 2])
def test_polyphase_fir_decimator(phase):
    coefficients = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    unfolded = fir(coefficients).unfold(3)
    selected = unfolded
    for index, output in enumerate(unfolded.output_operations):
        if index != phase:
            with pytest.warns(UserWarning, match="Output port"):
                selected = selected.replace(output.graph_id, Sink())
    simplified = selected.sink_propagation()
    assert simplified.input_count == 3
    assert simplified.output_count == 1
    assert len(simplified.find_by_type(ConstantMultiplication)) == 6
    assert len(simplified.find_by_type(Addition)) == 5
    assert len(selected.find_by_type(ConstantMultiplication)) == 18
    samples = np.random.default_rng(42).standard_normal(30)
    simulation = Simulation(simplified, [samples[i::3] for i in range(3)])
    simulation.run()
    expected = np.convolve(samples, coefficients)[phase : len(samples) : 3]
    np.testing.assert_allclose(
        simulation.results[simplified.output_operations[0].graph_id],
        expected,
        atol=1e-14,
    )
