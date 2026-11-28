"""Numerical and interface tests for adaptive FIR graph generation."""

import numpy as np
import pytest

from b_asic.core_operations import ComplexConjugate
from b_asic.sfg_generators import adaptive_fir
from b_asic.signal_generator import ZeroPad
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay


@pytest.mark.parametrize("method", ["lms", "nlms"])
@pytest.mark.parametrize("taps", [1, 4])
@pytest.mark.parametrize("complex_data", [False, True])
def test_adaptive_fir_reference(method, taps, complex_data):
    rng = np.random.default_rng(82)
    x = rng.normal(size=40)
    desired = rng.normal(size=40)
    weights = np.linspace(0.1, 0.4, taps)
    if complex_data:
        x = x + 1j * rng.normal(size=len(x))
        desired = desired + 1j * rng.normal(size=len(x))
        weights = weights + 0.2j
    initial_weights = weights.copy()
    history = np.zeros(taps, dtype=x.dtype)
    expected_y, expected_e = [], []
    for sample, target in zip(x, desired, strict=True):
        history[1:] = history[:-1]
        history[0] = sample
        y = np.dot(weights, history)
        error = target - y
        gain = 0.05
        if method == "nlms":
            gain /= 0.001 + np.vdot(history, history).real
        weights = weights + gain * error * history.conj()
        expected_y.append(y)
        expected_e.append(error)

    graph = adaptive_fir(
        taps,
        0.05,
        update_method=method,
        initial_weights=initial_weights,
        epsilon=0.001,
    )
    sim = Simulation(graph, [ZeroPad(x), ZeroPad(desired)])
    sim.run_for(len(x))
    np.testing.assert_allclose(sim.results["out0"], expected_y, atol=1e-12)
    np.testing.assert_allclose(sim.results["out1"], expected_e, atol=1e-12)


def test_adaptive_fir_custom_update():
    calls = []

    def leaky_lms(weights, samples, error, step_size):
        calls.append(len(weights))
        return [
            0.9 * w + step_size * error * ComplexConjugate(x)
            for w, x in zip(weights, samples, strict=True)
        ]

    graph = adaptive_fir(1, 0.1, update_method=leaky_lms, initial_weights=[1])
    sim = Simulation(graph, [1, 2])
    sim.run_for(3)
    np.testing.assert_allclose(sim.results["out0"], [1, 1, 1])
    assert calls == [1]


@pytest.mark.parametrize("method", ["lms", "nlms"])
def test_adaptive_fir_zero_step_and_initial_weights(method):
    graph = adaptive_fir(2, 0, update_method=method, initial_weights=[2, -1])
    sim = Simulation(graph, [ZeroPad([1, 2, 3, 0]), 0])
    sim.run_for(4)
    np.testing.assert_allclose(sim.results["out0"], [2, 3, 4, -3])


def test_adaptive_fir_defaults_and_silence():
    graph = adaptive_fir(3, update_method="nlms")
    assert graph.name == "Adaptive FIR filter"
    assert graph.input_count == graph.output_count == 2
    assert len(graph.find_by_type_name(Delay.type_name())) == 5
    sim = Simulation(graph, [0, 1])
    sim.run_for(5)
    np.testing.assert_array_equal(sim.results["out0"], np.zeros(5))
    np.testing.assert_array_equal(sim.results["out1"], np.ones(5))
    assert adaptive_fir(1, name="custom").name == "custom"


def test_adaptive_fir_lms_converges():
    rng = np.random.default_rng(14)
    x = rng.normal(size=600)
    desired = np.convolve(x, [0.5, -0.25, 0.1])[: len(x)]
    sim = Simulation(adaptive_fir(3, 0.05), [ZeroPad(x), ZeroPad(desired)])
    sim.run_for(len(x))
    np.testing.assert_allclose(sim.results["out0"][-20:], desired[-20:], atol=1e-9)


@pytest.mark.parametrize("taps", [0, -1])
def test_adaptive_fir_invalid_taps(taps):
    with pytest.raises(ValueError, match="taps must be positive"):
        adaptive_fir(taps)


@pytest.mark.parametrize("taps", [True, 1.5])
def test_adaptive_fir_noninteger_taps(taps):
    with pytest.raises(TypeError, match="taps must be an integer"):
        adaptive_fir(taps)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"step_size": -0.1}, "step_size"),
        ({"step_size": np.nan}, "step_size"),
        ({"step_size": np.inf}, "step_size"),
        ({"update_method": "unknown"}, "update_method"),
        ({"epsilon": 0}, "epsilon"),
        ({"epsilon": np.inf}, "epsilon"),
        ({"initial_weights": []}, "exactly taps"),
        ({"initial_weights": [np.nan]}, "finite values"),
        ({"update_method": lambda *args: []}, "exactly taps"),
    ],
)
def test_adaptive_fir_invalid_arguments(kwargs, message):
    with pytest.raises(ValueError, match=message):
        adaptive_fir(1, **kwargs)


def test_adaptive_fir_invalid_custom_sources():
    with pytest.raises(TypeError, match="signal sources"):
        adaptive_fir(1, update_method=lambda *args: [1])
