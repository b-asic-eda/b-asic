import numpy as np
import pytest

from b_asic.core_operations import (
    Addition,
    Butterfly,
    ConstantMultiplication,
    SymmetricTwoportAdaptor,
)
from b_asic.sfg_generators import (
    direct_form_fir,
    radix_2_dif_fft,
    transposed_direct_form_fir,
    wdf_allpass,
)
from b_asic.signal_generator import Constant, Impulse
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay


def test_wdf_allpass():
    # Third-order
    sfg = wdf_allpass([0.3, 0.5, 0.7])
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, SymmetricTwoportAdaptor)
            ]
        )
        == 3
    )

    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 3

    # Fourth-order
    sfg = wdf_allpass([0.3, 0.5, 0.7, 0.9])
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, SymmetricTwoportAdaptor)
            ]
        )
        == 4
    )

    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 4

    # First-order
    sfg = wdf_allpass([0.3])
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, SymmetricTwoportAdaptor)
            ]
        )
        == 1
    )

    # First-order with scalar input (happens to work)
    sfg = wdf_allpass(0.3)
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, SymmetricTwoportAdaptor)
            ]
        )
        == 1
    )

    # Bi-reciprocal third-order
    sfg = wdf_allpass([0.0, 0.5, 0.0])
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, SymmetricTwoportAdaptor)
            ]
        )
        == 1
    )

    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 3

    # Second-order all zeros third-order
    sfg = wdf_allpass([0.0, 0.0])
    assert not [
        comp for comp in sfg.components if isinstance(comp, SymmetricTwoportAdaptor)
    ]

    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 2


def test_direct_form_fir():
    impulse_response = [0.3, 0.5, 0.7]
    sfg = direct_form_fir(impulse_response)
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, ConstantMultiplication)
            ]
        )
        == 3
    )
    assert len([comp for comp in sfg.components if isinstance(comp, Addition)]) == 2
    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 2

    sim = Simulation(sfg, [Impulse()])
    sim.run_for(4)
    impulse_response.append(0.0)
    assert np.allclose(sim.results['0'], impulse_response)

    impulse_response = [0.3, 0.4, 0.5, 0.6, 0.3]
    sfg = direct_form_fir(
        (0.3, 0.4, 0.5, 0.6, 0.3),
        mult_properties={'latency': 2, 'execution_time': 1},
        add_properties={'latency': 1, 'execution_time': 1},
    )
    assert sfg.critical_path_time() == 6

    sim = Simulation(sfg, [Impulse()])
    sim.run_for(6)
    impulse_response.append(0.0)
    assert np.allclose(sim.results['0'], impulse_response)

    impulse_response = [0.3]
    sfg = direct_form_fir(impulse_response)
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, ConstantMultiplication)
            ]
        )
        == 1
    )
    assert len([comp for comp in sfg.components if isinstance(comp, Addition)]) == 0
    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 0

    impulse_response = 0.3
    sfg = direct_form_fir(impulse_response)
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, ConstantMultiplication)
            ]
        )
        == 1
    )
    assert len([comp for comp in sfg.components if isinstance(comp, Addition)]) == 0
    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 0


def test_transposed_direct_form_fir():
    impulse_response = [0.3, 0.5, 0.7]
    sfg = transposed_direct_form_fir(impulse_response)
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, ConstantMultiplication)
            ]
        )
        == 3
    )
    assert len([comp for comp in sfg.components if isinstance(comp, Addition)]) == 2
    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 2

    sim = Simulation(sfg, [Impulse()])
    sim.run_for(4)
    impulse_response.append(0.0)
    assert np.allclose(sim.results['0'], impulse_response)

    impulse_response = [0.3, 0.4, 0.5, 0.6, 0.3]
    sfg = transposed_direct_form_fir(
        (0.3, 0.4, 0.5, 0.6, 0.3),
        mult_properties={'latency': 2, 'execution_time': 1},
        add_properties={'latency': 1, 'execution_time': 1},
    )
    assert sfg.critical_path_time() == 3

    sim = Simulation(sfg, [Impulse()])
    sim.run_for(6)
    impulse_response.append(0.0)
    assert np.allclose(sim.results['0'], impulse_response)

    impulse_response = [0.3]
    sfg = transposed_direct_form_fir(impulse_response)
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, ConstantMultiplication)
            ]
        )
        == 1
    )
    assert len([comp for comp in sfg.components if isinstance(comp, Addition)]) == 0
    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 0

    impulse_response = 0.3
    sfg = transposed_direct_form_fir(impulse_response)
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, ConstantMultiplication)
            ]
        )
        == 1
    )
    assert len([comp for comp in sfg.components if isinstance(comp, Addition)]) == 0
    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 0


def test_sfg_generator_errors():
    sfg_gens = [wdf_allpass, transposed_direct_form_fir, direct_form_fir]
    for gen in sfg_gens:
        with pytest.raises(ValueError, match="Coefficients cannot be empty"):
            gen([])
        with pytest.raises(TypeError, match="coefficients must be a 1D-array"):
            gen([[1, 2], [1, 3]])


def test_radix_2_dif_fft_4_points_constant_input():
    sfg = radix_2_dif_fft(points=4)

    assert len(sfg.inputs) == 4
    assert len(sfg.outputs) == 4

    bfs = sfg.find_by_type_name(Butterfly.type_name())
    assert len(bfs) == 4

    muls = sfg.find_by_type_name(ConstantMultiplication.type_name())
    assert len(muls) == 1

    # simulate when the input signal is a constant 1
    input_samples = [Impulse() for _ in range(4)]
    sim = Simulation(sfg, input_samples)
    sim.run_for(1)

    # ensure that the result is an impulse at time 0 with weight 4
    res = sim.results
    for i in range(4):
        exp_res = 4 if i == 0 else 0
        assert np.allclose(res[str(i)], exp_res)


def test_radix_2_dif_fft_8_points_impulse_input():
    sfg = radix_2_dif_fft(points=8)

    assert len(sfg.inputs) == 8
    assert len(sfg.outputs) == 8

    bfs = sfg.find_by_type_name(Butterfly.type_name())
    assert len(bfs) == 12

    muls = sfg.find_by_type_name(ConstantMultiplication.type_name())
    assert len(muls) == 5

    # simulate when the input signal is an impulse at time 0
    input_samples = [Impulse(), 0, 0, 0, 0, 0, 0, 0]
    sim = Simulation(sfg, input_samples)
    sim.run_for(1)

    # ensure that the result is a constant 1
    res = sim.results
    for i in range(8):
        assert np.allclose(res[str(i)], 1)


def test_radix_2_dif_fft_8_points_sinus_input():
    POINTS = 8
    sfg = radix_2_dif_fft(points=POINTS)

    assert len(sfg.inputs) == POINTS
    assert len(sfg.outputs) == POINTS

    n = np.linspace(0, 2 * np.pi, POINTS)
    waveform = np.sin(n)
    input_samples = [Constant(waveform[i]) for i in range(POINTS)]

    sim = Simulation(sfg, input_samples)
    sim.run_for(1)

    exp_res = abs(np.fft.fft(waveform))

    res = sim.results
    for i in range(POINTS):
        a = abs(res[str(i)])
        b = exp_res[i]
        assert np.isclose(a, b)


def test_radix_2_dif_fft_16_points_sinus_input():
    POINTS = 16
    sfg = radix_2_dif_fft(points=POINTS)

    assert len(sfg.inputs) == POINTS
    assert len(sfg.outputs) == POINTS

    bfs = sfg.find_by_type_name(Butterfly.type_name())
    assert len(bfs) == 8 * 4

    muls = sfg.find_by_type_name(ConstantMultiplication.type_name())
    assert len(muls) == 17

    n = np.linspace(0, 2 * np.pi, POINTS)
    waveform = np.sin(n)
    input_samples = [Constant(waveform[i]) for i in range(POINTS)]

    sim = Simulation(sfg, input_samples)
    sim.run_for(1)

    exp_res = np.fft.fft(waveform)
    res = sim.results
    for i in range(POINTS):
        a = res[str(i)]
        b = exp_res[i]
        assert np.isclose(a, b)


def test_radix_2_dif_fft_256_points_sinus_input():
    POINTS = 256
    sfg = radix_2_dif_fft(points=POINTS)

    assert len(sfg.inputs) == POINTS
    assert len(sfg.outputs) == POINTS

    n = np.linspace(0, 2 * np.pi, POINTS)
    waveform = np.sin(n)
    input_samples = [Constant(waveform[i]) for i in range(POINTS)]

    sim = Simulation(sfg, input_samples)
    sim.run_for(1)

    exp_res = np.fft.fft(waveform)
    res = sim.results
    for i in range(POINTS):
        a = res[str(i)]
        b = exp_res[i]
        assert np.isclose(a, b)


def test_radix_2_dif_fft_negative_number_of_points():
    POINTS = -8
    with pytest.raises(ValueError, match="Points must be positive number."):
        radix_2_dif_fft(points=POINTS)


def test_radix_2_dif_fft_number_of_points_not_power_of_2():
    POINTS = 5
    with pytest.raises(ValueError, match="Points must be a power of two."):
        radix_2_dif_fft(points=POINTS)
