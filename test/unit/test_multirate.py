"""Rate-changing graphs, phase normalization, and native-rate simulation traces."""

import numpy as np
import pytest

from b_asic import (
    SFG,
    Addition,
    Compression,
    Constant,
    Expansion,
    FastSimulation,
    Input,
    Output,
    R2Butterfly,
    Schedule,
    Sink,
)
from b_asic.data_type import DataType
from b_asic.save_load_structure import sfg_to_python
from b_asic.sfg_generators import fir
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay


@pytest.mark.parametrize("operation_type", [Expansion, Compression])
@pytest.mark.parametrize("factor", [0, -1])
def test_invalid_factor(operation_type, factor):
    with pytest.raises(ValueError, match="positive"):
        operation_type(factor)


@pytest.mark.parametrize("operation_type", [Expansion, Compression])
@pytest.mark.parametrize("factor", [True, 2.5, "2"])
def test_noninteger_factor(operation_type, factor):
    with pytest.raises(TypeError, match="integer"):
        operation_type(factor)


@pytest.mark.parametrize("operation_type", [Expansion, Compression])
@pytest.mark.parametrize("phase", [-1, 3])
def test_invalid_phase(operation_type, phase):
    with pytest.raises(ValueError, match="phase"):
        operation_type(3, phase=phase)


@pytest.mark.parametrize("operation_type", [Expansion, Compression])
@pytest.mark.parametrize("phase", [True, 0.5])
def test_noninteger_phase(operation_type, phase):
    with pytest.raises(TypeError, match="integer"):
        operation_type(3, phase=phase)


@pytest.mark.parametrize("operation_type", [Expansion, Compression])
def test_operation_copy_and_serialization(operation_type):
    source = Input()
    graph = SFG(source, Output(operation_type(3, source, name="converter", phase=2)))
    copy = graph()
    operation = copy.find_by_name("converter")[0]
    assert operation.factor == 3
    assert operation.phase == 2
    assert operation.input_count == operation.output_count == 1
    namespace = {}
    exec(sfg_to_python(graph), namespace)
    restored = namespace["sfg"].find_by_name("converter")[0]
    assert restored.factor == 3
    assert restored.phase == 2


@pytest.mark.parametrize(("factor", "phase"), [(1, 0), (2, 0), (2, 1), (3, 2)])
def test_expansion(factor, phase):
    source = Input()
    graph = SFG(source, Output(Expansion(factor, source, phase=phase)))
    samples = np.array([1, -2, 3, 4j])
    simulation = Simulation(graph, [samples])
    simulation.run()
    expected = np.zeros(factor * len(samples), dtype=complex)
    expected[phase::factor] = samples
    np.testing.assert_array_equal(simulation.results["out0"], expected)
    np.testing.assert_array_equal(simulation.results["expand0"], expected)
    np.testing.assert_array_equal(simulation.results["in0"], samples)
    assert simulation.input_samples_per_iteration == (1,)
    assert simulation.output_samples_per_iteration == (factor,)
    assert simulation.iteration == len(samples)
    assert simulation.sfg.is_multirate


@pytest.mark.parametrize(("factor", "phase"), [(1, 0), (2, 0), (2, 1), (3, 2)])
def test_compression(factor, phase):
    source = Input()
    graph = SFG(source, Output(Compression(factor, source, phase=phase)))
    samples = np.arange(6 * factor)
    simulation = Simulation(graph, [samples])
    assert simulation.run() == [samples[phase::factor][-1]]
    np.testing.assert_array_equal(simulation.results["out0"], samples[phase::factor])
    np.testing.assert_array_equal(
        simulation.results["compress0"], samples[phase::factor]
    )
    np.testing.assert_array_equal(simulation.results["in0"], samples)
    assert simulation.input_samples_per_iteration == (factor,)
    assert simulation.output_samples_per_iteration == (1,)
    assert simulation.iteration == 6


def test_rational_conversion():
    source = Input()
    graph = SFG(source, Output(Compression(3, Expansion(2, source))))
    samples = np.arange(1, 13)
    simulation = Simulation(graph, [samples])
    simulation.run()
    expanded = np.zeros(2 * len(samples))
    expanded[::2] = samples
    np.testing.assert_array_equal(simulation.results["out0"], expanded[::3])
    assert simulation.input_samples_per_iteration == (3,)
    assert simulation.output_samples_per_iteration == (2,)


@pytest.mark.parametrize("position", ["before", "after"])
@pytest.mark.parametrize("operation_type", [Expansion, Compression])
def test_filter_across_rate_change(position, operation_type):
    source = Input()
    coefficients = np.array([1.0, -2.0, 0.5, 3.0])
    filter_graph = fir(coefficients)
    if position == "before":
        output = operation_type(3, filter_graph(source))
    else:
        output = filter_graph(operation_type(3, source))
    graph = SFG(source, Output(output))
    samples = np.arange(1.0, 19.0)

    def convert(values):
        if operation_type is Compression:
            return values[::3]
        expanded = np.zeros(3 * len(values))
        expanded[::3] = values
        return expanded

    if position == "before":
        expected = convert(np.convolve(samples, coefficients)[: len(samples)])
    else:
        converted = convert(samples)
        expected = np.convolve(converted, coefficients)[: len(converted)]
    simulation = Simulation(graph, [samples])
    simulation.run()
    np.testing.assert_allclose(simulation.results["out0"], expected)


def test_constants_in_multiple_rate_domains():
    source = Input()
    constant = Constant(1)
    low = Addition(source, constant)
    high = Addition(Expansion(2, source), constant)
    graph = SFG(source, [Output(low), Output(high)])
    simulation = Simulation(graph, [[2, 3, 4]])
    simulation.run()
    np.testing.assert_array_equal(simulation.results["out0"], [3, 4, 5])
    np.testing.assert_array_equal(simulation.results["out1"], [3, 1, 4, 1, 5, 1])


def test_expanded_constant_is_not_folded_to_constant():
    graph = SFG([], Output(Expansion(3, Constant(5))))
    simulation = Simulation(graph.constant_propagation())
    simulation.run_for(2)
    np.testing.assert_array_equal(simulation.results["out0"], [5, 0, 0, 5, 0, 0])


def test_two_inputs_with_different_rates():
    high, low = Input(), Input()
    graph = SFG([high, low], Output(Addition(Compression(3, high), low)))
    simulation = Simulation(graph, [np.arange(9), [10, 20, 30]])
    simulation.run()
    np.testing.assert_array_equal(simulation.results["out0"], [10, 23, 36])
    assert simulation.input_samples_per_iteration == (3, 1)


def test_disconnected_components_share_a_common_period():
    first, second = Input(), Input()
    graph = SFG(
        [first, second],
        [Output(Compression(2, first)), Output(Compression(3, second))],
    )
    samples = np.arange(12)
    simulation = Simulation(graph, [samples, samples])
    simulation.run()
    assert simulation.input_samples_per_iteration == (6, 6)
    assert simulation.output_samples_per_iteration == (3, 2)
    np.testing.assert_array_equal(simulation.results["out0"], samples[::2])
    np.testing.assert_array_equal(simulation.results["out1"], samples[::3])


def test_callables_use_local_sample_index_and_can_be_replaced():
    source = Input()
    graph = SFG(source, Output(Compression(3, source)))
    indices = []

    def provider(index):
        indices.append(index)
        return index

    simulation = Simulation(graph, [provider])
    assert simulation.step() == [0]
    assert simulation.run_for(2) == [6]
    assert indices == list(range(9))
    simulation.set_input(0, lambda index: 10 + index)
    assert simulation.step() == [19]


def test_nested_graph_and_hierarchical_trace_keys():
    inner_input = Input()
    inner = SFG(inner_input, Output(Expansion(2, inner_input)))
    outer_input = Input()
    graph = SFG(outer_input, Output(inner(outer_input)))
    simulation = Simulation(graph, [[1, 2, 3]])
    simulation.run()
    expected = [1, 0, 2, 0, 3, 0]
    for key in ("out0", "sfg0", "sfg0.expand0", "sfg0.out0"):
        np.testing.assert_array_equal(simulation.results[key], expected)


def test_multiple_output_operation():
    first, second = Input(), Input()
    butterfly = R2Butterfly(Expansion(2, first), Expansion(2, second))
    graph = SFG([first, second], [Output(butterfly.output(i)) for i in range(2)])
    simulation = Simulation(graph, [[1, 2], [3, 4]])
    simulation.run()
    np.testing.assert_array_equal(simulation.results["out0"], [4, 0, 6, 0])
    np.testing.assert_array_equal(simulation.results["out1"], [-2, 0, -2, 0])


def test_feedback_through_rate_changes():
    source = Input()
    delay = Delay()
    total = Addition(source, Compression(2, Expansion(2, delay)))
    delay <<= total
    graph = SFG(source, Output(total))
    simulation = Simulation(graph, [[1, 2, 3, 4]])
    simulation.run()
    np.testing.assert_array_equal(simulation.results["out0"], [1, 3, 6, 10])


def test_rate_mismatch_and_unbalanced_feedback_are_rejected():
    source = Input()
    graph = SFG(source, Output(Addition(source, Expansion(2, source))))
    with pytest.raises(ValueError, match="Inconsistent sample rates"):
        Simulation(graph)
    assert graph.is_multirate
    delay = Delay()
    expanded = Expansion(2, delay)
    delay <<= expanded
    with pytest.raises(ValueError, match="Inconsistent sample rates"):
        SFG([], Output(expanded)).to_single_rate()


def test_normalization_is_independent_and_can_be_scheduled():
    source = Input()
    graph = SFG(source, Output(Compression(3, Addition(source, source, latency=1))))
    normalization = graph.to_single_rate()
    assert graph.is_multirate
    assert not normalization.sfg.is_multirate
    assert normalization.input_samples == (3,)
    assert normalization.output_samples == (1,)
    assert normalization.input_phases == ((0, 0), (0, 1), (0, 2))
    assert normalization.output_phases == ((0, 0),)
    assert len(normalization.sfg.find_by_type(Sink)) >= 2
    Schedule(normalization.sfg.sink_propagation())
    with pytest.raises(ValueError, match="normalized before scheduling"):
        Schedule(graph)


def test_normalized_graph_with_native_simulator():
    source = Input()
    graph = SFG(source, Output(Expansion(2, source)))
    normalization = graph.to_single_rate()
    simulation = FastSimulation(normalization.sfg, [[1, 2, 3]])
    simulation.run()
    phase_outputs = np.column_stack(
        [simulation.results[f"out{i}"] for i in range(normalization.sfg.output_count)]
    )
    np.testing.assert_array_equal(phase_outputs.ravel(), [1, 0, 2, 0, 3, 0])


def test_single_rate_analysis_requires_normalization():
    source = Input()
    graph = SFG(source, Output(Expansion(2, source)))
    with pytest.raises(ValueError, match="single-rate graph"):
        graph.unfold(2)
    with pytest.raises(ValueError, match="single-rate graph"):
        graph.to_ss()


def test_complete_periods_and_matching_input_durations_required():
    first, second = Input(), Input()
    graph = SFG([first, second], Output(Addition(Compression(3, first), second)))
    with pytest.raises(ValueError, match="whole simulation periods"):
        Simulation(graph, [[1, 2, 3, 4], [1]])
    with pytest.raises(ValueError, match="Inconsistent input length"):
        Simulation(graph, [[1, 2, 3, 4, 5, 6], [1]])


def test_incremental_execution_clear_results_and_clear_state():
    source = Input()
    graph = SFG(source, Output(Compression(2, Delay(source))))
    simulation = Simulation(graph, [lambda index: index + 1])
    assert simulation.step(save_results=False) == [0]
    assert not simulation.results
    assert simulation.step() == [2]
    np.testing.assert_array_equal(simulation.results["out0"], [2])
    simulation.clear_results()
    assert not simulation.results
    simulation.clear_state()
    assert simulation.step() == [0]
    assert simulation.run_until(5) == [8]
    np.testing.assert_array_equal(simulation.results["out0"], [0, 6, 8])


def test_finite_word_length_expansion():
    source = Input()
    graph = SFG(source, Output(Expansion(2, Delay(source))))
    simulation = Simulation(graph, [[0.25, 0.5, 0.75]], DataType(wl=(2, 4)))
    simulation.run()
    assert [float(value) for value in simulation.results["out0"]] == [
        0,
        0,
        0.25,
        0,
        0.5,
        0,
    ]


def test_primitive_wrapping_and_single_rate_normalization():
    for operation in (Expansion(3), Compression(2)):
        assert operation.to_sfg().flatten(expand=True).is_multirate
        assert operation.split() == [operation]
        with pytest.raises(ValueError, match="stream evaluation"):
            operation.evaluate(1)
    source = Input()
    graph = SFG(source, Output(Delay(source)))
    normalization = graph.to_single_rate()
    assert normalization.input_samples == normalization.output_samples == (1,)
    simulation = Simulation(normalization.sfg, [[1, 2, 3]])
    simulation.run()
    np.testing.assert_array_equal(
        simulation.results[normalization.sfg.output_operations[0].graph_id],
        [0, 1, 2],
    )
