import numpy as np
import pytest
from scipy import signal

from b_asic.core_operations import (
    Addition,
    Butterfly,
    ConstantMultiplication,
    SymmetricTwoportAdaptor,
)
from b_asic.sfg_generators import (
    direct_form_1_iir,
    direct_form_2_iir,
    direct_form_fir,
    radix_2_dif_fft,
    transposed_direct_form_fir,
    wdf_allpass,
)
from b_asic.signal_generator import Constant, Impulse, ZeroPad
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


class TestDirectFormIIRType1:
    def test_correct_number_of_operations_and_name(self):
        N = 17

        b = [i + 1 for i in range(N + 1)]
        a = [i + 1 for i in range(N + 1)]

        sfg = direct_form_1_iir(b, a, name="test iir direct form 1")

        amount_of_muls = len(sfg.find_by_type_name(ConstantMultiplication.type_name()))
        assert amount_of_muls == 2 * N + 1

        amount_of_adds = len(sfg.find_by_type_name(Addition.type_name()))
        assert amount_of_adds == 2 * N

        amount_of_delays = len(sfg.find_by_type_name(Delay.type_name()))
        assert amount_of_delays == 2 * N

        amount_of_ops = len(sfg.operations)
        assert amount_of_ops == 6 * N + 3

        assert sfg.name == "test iir direct form 1"

    def test_b_single_coeff(self):
        with pytest.raises(
            ValueError,
            match="Size of coefficient lists a and b needs to contain at least 2 element.",
        ):
            direct_form_1_iir([1], [2, 3])

    def test_a_single_coeff(self):
        with pytest.raises(
            ValueError,
            match="Size of coefficient lists a and b needs to contain at least 2 element.",
        ):
            direct_form_1_iir([1, 2], [3])

    def test_coeffs_not_same_size(self):
        with pytest.raises(
            ValueError, match="Size of coefficient lists a and b are not the same."
        ):
            direct_form_1_iir([1, 2, 3], [1, 2])

        with pytest.raises(
            ValueError, match="Size of coefficient lists a and b are not the same."
        ):
            direct_form_1_iir([i for i in range(10)], [i for i in range(11)])

        with pytest.raises(
            ValueError, match="Size of coefficient lists a and b are not the same."
        ):
            direct_form_1_iir([i for i in range(10)], [i for i in range(11)])

    def test_a0_not_1(self):
        with pytest.raises(ValueError, match=r"The value of a\[0] must be 1\."):
            direct_form_1_iir(b=[1, 2, 3], a=[1.1, 2, 3])

    def test_first_order_filter(self):
        N = 1
        Wc = 0.5

        b, a = signal.butter(N, Wc, btype="lowpass", output="ba")

        input_signal = np.random.randn(100)
        reference_filter_output = signal.lfilter(b, a, input_signal)

        sfg = direct_form_1_iir(b, a, name="test iir direct form 1")

        sim = Simulation(sfg, [ZeroPad(input_signal)])
        sim.run_for(100)

        assert np.allclose(sim.results['0'], reference_filter_output)

    def test_random_input_compare_with_scipy_butterworth_filter(self):
        N = 10
        Wc = 0.3

        b, a = signal.butter(N, Wc, btype="lowpass", output="ba")

        input_signal = np.random.randn(100)
        reference_filter_output = signal.lfilter(b, a, input_signal)

        sfg = direct_form_1_iir(b, a, name="test iir direct form 1")

        sim = Simulation(sfg, [ZeroPad(input_signal)])
        sim.run_for(100)

        assert np.allclose(sim.results['0'], reference_filter_output)

    def test_random_input_compare_with_scipy_elliptic_filter(self):
        N = 2
        Wc = 0.3

        b, a = signal.ellip(N, 0.1, 60, Wc, btype='low', analog=False)
        b, a = signal.butter(N, Wc, btype="lowpass", output="ba")

        input_signal = np.random.randn(100)
        reference_filter_output = signal.lfilter(b, a, input_signal)

        sfg = direct_form_1_iir(b, a, name="test iir direct form 1")

        sim = Simulation(sfg, [ZeroPad(input_signal)])
        sim.run_for(100)

        assert np.allclose(sim.results['0'], reference_filter_output)

    def test_add_and_mult_properties(self):
        N = 17

        b = [i + 1 for i in range(N + 1)]
        a = [i + 1 for i in range(N + 1)]

        sfg = direct_form_1_iir(
            b,
            a,
            mult_properties={"latency": 5, "execution_time": 2},
            add_properties={"latency": 3, "execution_time": 1},
        )

        adds = sfg.find_by_type_name(Addition.type_name())
        for add in adds:
            assert add.latency == 3
            assert add.execution_time == 1

        muls = sfg.find_by_type_name(ConstantMultiplication.type_name())
        for mul in muls:
            assert mul.latency == 5
            assert mul.execution_time == 2


class TestDirectFormIIRType2:
    def test_correct_number_of_operations_and_name(self):
        N = 17

        b = [i + 1 for i in range(N + 1)]
        a = [i + 1 for i in range(N + 1)]

        sfg = direct_form_2_iir(b, a, name="test iir direct form 2")

        amount_of_muls = len(sfg.find_by_type_name(ConstantMultiplication.type_name()))
        assert amount_of_muls == 2 * N + 1

        amount_of_adds = len(sfg.find_by_type_name(Addition.type_name()))
        assert amount_of_adds == 2 * N

        amount_of_delays = len(sfg.find_by_type_name(Delay.type_name()))
        assert amount_of_delays == N

        amount_of_ops = len(sfg.operations)
        assert amount_of_ops == 5 * N + 3

        assert sfg.name == "test iir direct form 2"

    def test_b_single_coeff(self):
        with pytest.raises(
            ValueError,
            match="Size of coefficient lists a and b needs to contain at least 2 element.",
        ):
            direct_form_2_iir([1], [2, 3])

    def test_a_single_coeff(self):
        with pytest.raises(
            ValueError,
            match="Size of coefficient lists a and b needs to contain at least 2 element.",
        ):
            direct_form_2_iir([1, 2], [3])

    def test_a0_not_1(self):
        with pytest.raises(ValueError, match=r"The value of a\[0] must be 1\."):
            direct_form_2_iir(b=[1, 2, 3], a=[1.1, 2, 3])

    def test_coeffs_not_same_size(self):
        with pytest.raises(
            ValueError, match="Size of coefficient lists a and b are not the same."
        ):
            direct_form_2_iir([1, 2, 3], [1, 2])

    def test_first_order_filter(self):
        N = 1
        Wc = 0.5

        b, a = signal.butter(N, Wc, btype="lowpass", output="ba")

        input_signal = np.random.randn(100)
        reference_filter_output = signal.lfilter(b, a, input_signal)

        sfg = direct_form_2_iir(b, a, name="test iir direct form 1")

        sim = Simulation(sfg, [ZeroPad(input_signal)])
        sim.run_for(100)

        assert np.allclose(sim.results['0'], reference_filter_output)

    def test_random_input_compare_with_scipy_butterworth_filter(self):
        N = 10
        Wc = 0.3

        b, a = signal.butter(N, Wc, btype="lowpass", output="ba")

        input_signal = np.random.randn(100)
        reference_filter_output = signal.lfilter(b, a, input_signal)

        sfg = direct_form_2_iir(b, a, name="test iir direct form 1")

        sim = Simulation(sfg, [ZeroPad(input_signal)])
        sim.run_for(100)

        assert np.allclose(sim.results['0'], reference_filter_output)

    def test_random_input_compare_with_scipy_elliptic_filter(self):
        N = 2
        Wc = 0.3

        b, a = signal.ellip(N, 0.1, 60, Wc, btype='low', analog=False)
        b, a = signal.butter(N, Wc, btype="lowpass", output="ba")

        input_signal = np.random.randn(100)
        reference_filter_output = signal.lfilter(b, a, input_signal)

        sfg = direct_form_2_iir(b, a, name="test iir direct form 1")

        sim = Simulation(sfg, [ZeroPad(input_signal)])
        sim.run_for(100)

        assert np.allclose(sim.results['0'], reference_filter_output)

    def test_add_and_mult_properties(self):
        N = 17

        b = [i + 1 for i in range(N + 1)]
        a = [i + 1 for i in range(N + 1)]

        sfg = direct_form_2_iir(
            b,
            a,
            mult_properties={"latency": 5, "execution_time": 2},
            add_properties={"latency": 3, "execution_time": 1},
        )

        adds = sfg.find_by_type_name(Addition.type_name())
        for add in adds:
            assert add.latency == 3
            assert add.execution_time == 1

        muls = sfg.find_by_type_name(ConstantMultiplication.type_name())
        for mul in muls:
            assert mul.latency == 5
            assert mul.execution_time == 2


class TestRadix2FFT:
    def test_4_points_constant_input(self):
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

    def test_8_points_impulse_input(self):
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

    def test_8_points_sinus_input(self):
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

    def test_16_points_sinus_input(self):
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

    def test_256_points_sinus_input(self):
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

    def test_512_points_multi_tone_input(self):
        POINTS = 512
        sfg = radix_2_dif_fft(points=POINTS)

        assert len(sfg.inputs) == POINTS
        assert len(sfg.outputs) == POINTS

        n = np.linspace(0, 2 * np.pi, POINTS)
        waveform = np.sin(n) + np.sin(0.5 * n) + np.sin(0.1 * n)
        input_samples = [Constant(waveform[i]) for i in range(POINTS)]

        sim = Simulation(sfg, input_samples)
        sim.run_for(1)

        exp_res = np.fft.fft(waveform)
        res = sim.results
        for i in range(POINTS):
            a = res[str(i)]
            b = exp_res[i]
            assert np.isclose(a, b)

    def test_negative_number_of_points(self):
        POINTS = -8
        with pytest.raises(ValueError, match="Points must be positive number."):
            radix_2_dif_fft(points=POINTS)

    def test_number_of_points_not_power_of_2(self):
        POINTS = 5
        with pytest.raises(ValueError, match="Points must be a power of two."):
            radix_2_dif_fft(points=POINTS)
