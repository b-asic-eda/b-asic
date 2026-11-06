"""Zero-state invariants simplify unexcited feedback without freezing live state."""

import numpy as np
import pytest

from b_asic.core_operations import (
    Addition,
    Constant,
    ConstantMultiplication,
    Multiplication,
)
from b_asic.sfg import SFG
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay, Input, Output
from b_asic.utility_operations import Sink
from test.unit.test_wdf_propagation import ADAPTORS


def _simulate(sfg, inputs=None):
    simulation = Simulation(sfg, inputs)
    simulation.run_for(5)
    return [simulation.results[op.graph_id] for op in sfg.output_operations]


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
def test_unexcited_adaptor_feedback_removed(adaptor_type, coefficient, ports):
    delays = [Delay() for _ in range(ports)]
    adaptor = adaptor_type(coefficient, *delays)
    for delay, output in zip(delays, adaptor.outputs, strict=True):
        delay <<= output
    original = SFG([], [Output(port) for port in adaptor.outputs])
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(adaptor_type)
    assert not simplified.find_by_type(Delay)
    np.testing.assert_array_equal(_simulate(simplified), _simulate(original))
    assert len(original.find_by_type(Delay)) == ports
    assert original.find_by_type(adaptor_type)
    preserved = original.constant_propagation(assume_zero_initial_state=False)
    assert preserved.find_by_type(adaptor_type)
    assert len(preserved.find_by_type(Delay)) == ports


def test_zero_feedback_applies_to_arithmetic():
    first, second = Delay(), Delay()
    first <<= Addition(second, Constant(0))
    second <<= ConstantMultiplication(0.5, first)
    original = SFG([], [Output(first), Output(second)])
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(Delay)
    assert not simplified.find_by_type(Addition)
    assert not simplified.find_by_type(ConstantMultiplication)
    assert simplified.evaluate_outputs([]) == [0, 0]


@pytest.mark.parametrize("propagation", ["constant_propagation", "sink_propagation"])
def test_assumption_overrides_only_copy_initial_state(propagation):
    source = Input()
    delay = Delay(source, initial_value=7)
    original = SFG([source], [Output(delay)])
    simplified = getattr(original, propagation)()
    assert simplified.find_by_type(Delay)[0].initial_value == 0
    assert original.find_by_type(Delay)[0].initial_value == 7
    preserved = getattr(original, propagation)(assume_zero_initial_state=False)
    assert preserved.find_by_type(Delay)[0].initial_value == 7


def test_self_feedback_nonzero_initial_state_opt_out():
    delay = Delay(initial_value=7)
    delay <<= delay
    original = SFG([], [Output(delay)])
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(Delay)
    assert simplified.evaluate_outputs([]) == [0]
    preserved = original.constant_propagation(assume_zero_initial_state=False)
    np.testing.assert_array_equal(_simulate(preserved), [[7] * 5])


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
def test_live_input_feedback_is_not_constant(adaptor_type, coefficient, ports):
    source = Input()
    delays = [Delay() for _ in range(ports - 1)]
    adaptor = adaptor_type(coefficient, source, *delays)
    for delay, output in zip(delays, adaptor.outputs[1:], strict=True):
        delay <<= output
    original = SFG([source], [Output(port) for port in adaptor.outputs])
    simplified = original.constant_propagation()
    assert len(simplified.find_by_type(Delay)) == ports - 1
    values = [[1, 2, -3, 4, 0]]
    np.testing.assert_allclose(
        _simulate(simplified, values), _simulate(original, values)
    )


def test_delay_chain_driven_by_live_input_not_constant():
    source = Input()
    original = SFG([source], [Output(Delay(Delay(source)))])
    simplified = original.constant_propagation()
    assert len(simplified.find_by_type(Delay)) == 2
    values = [[1, 2, 3, 4, 5]]
    np.testing.assert_array_equal(_simulate(simplified, values), [[0, 0, 1, 2, 3]])


def test_nonzero_constant_excites_feedback():
    delay = Delay()
    delay <<= Addition(delay, Constant(1))
    original = SFG([], [Output(delay)])
    simplified = original.constant_propagation()
    assert simplified.find_by_type(Delay)
    np.testing.assert_array_equal(_simulate(simplified), [[0, 1, 2, 3, 4]])


def test_zero_product_cuts_live_input_out_of_feedback():
    source = Input()
    delay = Delay()
    delay <<= Addition(delay, Multiplication(source, Constant(0)))
    original = SFG([source], [Output(delay)])
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(Delay)
    assert not simplified.find_by_type(Addition)
    assert not simplified.find_by_type(Multiplication)
    assert simplified.evaluate_outputs([8]) == [0]


def test_zero_adaptor_output_with_other_live_outputs():
    from b_asic.wdf_operations import ReflectionFreeSeriesThreeportAdaptor

    source = Input()
    delay = Delay()
    adaptor = ReflectionFreeSeriesThreeportAdaptor(0.25, delay, source, Constant(0))
    # The reflection-free result is zero even though the other two results
    # depend on the live input. It feeds the delay, making its state invariant.
    delay <<= adaptor.output(1)
    original = SFG([source], [Output(port) for port in adaptor.outputs])
    simplified = original.constant_propagation()
    assert not simplified.find_by_type(Delay)
    assert not simplified.find_by_type(ReflectionFreeSeriesThreeportAdaptor)
    values = [[1, 2, -3, 4, 5]]
    np.testing.assert_allclose(
        _simulate(simplified, values), _simulate(original, values)
    )


@pytest.mark.parametrize(("adaptor_type", "coefficient", "ports"), ADAPTORS)
def test_targeted_adaptor_uses_zero_feedback_facts(adaptor_type, coefficient, ports):
    delays = [Delay() for _ in range(ports)]
    adaptor = adaptor_type(coefficient, *delays)
    for delay, output in zip(delays, adaptor.outputs, strict=True):
        delay <<= output
    original = SFG([], [Output(adaptor.output(0))])
    simplified = original.constant_propagation(adaptor_type)
    assert not simplified.find_by_type(adaptor_type)
    assert not simplified.find_by_type(Delay)
    assert simplified.evaluate_outputs([]) == [0]


def test_sink_simplification_uses_zero_feedback_facts():
    from b_asic.wdf_operations import SymmetricTwoportAdaptor

    delay = Delay()
    delay <<= ConstantMultiplication(0.5, delay)
    source = Input()
    adaptor = SymmetricTwoportAdaptor(0.25, delay, source)
    Sink().input(0).connect(adaptor.output(1))
    original = SFG([source], [Output(adaptor.output(0))])
    simplified = original.sink_propagation()
    assert not simplified.find_by_type(Delay)
    assert not simplified.find_by_type(SymmetricTwoportAdaptor)
    values = [[1, 2, 3, 4, 5]]
    np.testing.assert_allclose(
        _simulate(simplified, values), _simulate(original, values)
    )
