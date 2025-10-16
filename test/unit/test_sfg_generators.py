import numpy as np
import pytest

from b_asic.core_operations import (
    MADS,
    Addition,
    ConstantMultiplication,
    Reciprocal,
    SymmetricTwoportAdaptor,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.sfg_generators import (
    direct_form_1_iir,
    direct_form_2_iir,
    direct_form_fir,
    ldlt_matrix_inverse,
    matrix_multiplication,
    radix_2_dif_fft,
    symmetric_fir,
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
    assert np.allclose(sim.results["out0"], impulse_response)

    impulse_response = [0.3, 0.4, 0.5, 0.6, 0.3]
    sfg = direct_form_fir(
        (0.3, 0.4, 0.5, 0.6, 0.3),
        mult_properties={"latency": 2, "execution_time": 1},
        add_properties={"latency": 1, "execution_time": 1},
    )
    assert sfg.critical_path_time() == 6

    sim = Simulation(sfg, [Impulse()])
    sim.run_for(6)
    impulse_response.append(0.0)
    assert np.allclose(sim.results["out0"], impulse_response)

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
    assert np.allclose(sim.results["out0"], impulse_response)

    impulse_response = [0.3, 0.4, 0.5, 0.6, 0.3]
    sfg = transposed_direct_form_fir(
        (0.3, 0.4, 0.5, 0.6, 0.3),
        mult_properties={"latency": 2, "execution_time": 1},
        add_properties={"latency": 1, "execution_time": 1},
    )
    assert sfg.critical_path_time() == 3

    sim = Simulation(sfg, [Impulse()])
    sim.run_for(6)
    impulse_response.append(0.0)
    assert np.allclose(sim.results["out0"], impulse_response)

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


def test_symmetric_fir():
    impulse_response = [0.3, 0.5, 0.5, 0.3]
    sfg = symmetric_fir(impulse_response)
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, ConstantMultiplication)
            ]
        )
        == 2
    )
    assert len([comp for comp in sfg.components if isinstance(comp, Addition)]) == 3
    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 3

    sim = Simulation(sfg, [Impulse()])
    sim.run_for(5)
    impulse_response.append(0.0)
    assert np.allclose(sim.results["out0"], impulse_response)

    impulse_response = [0.1, 0.2, 0.3, 0.4, 0.4, 0.3, 0.2, 0.1]
    sfg = symmetric_fir(
        impulse_response,
        mult_properties={"latency": 2, "execution_time": 1},
        add_properties={"latency": 1, "execution_time": 1},
    )
    assert sfg.critical_path_time() == 6

    sim = Simulation(sfg, [Impulse()])
    sim.run_for(9)
    impulse_response.append(0.0)
    assert np.allclose(sim.results["out0"], impulse_response)

    impulse_response = [0.3]
    sfg = symmetric_fir(impulse_response)
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

    impulse_response = [0.1 + i for i in range(8)]
    impulse_response += reversed(impulse_response)
    sfg = symmetric_fir(impulse_response)
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, ConstantMultiplication)
            ]
        )
        == 8
    )
    assert len([comp for comp in sfg.components if isinstance(comp, Addition)]) == 15
    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 15

    sim = Simulation(sfg, [Impulse()])
    sim.run_for(17)
    impulse_response.append(0.0)
    assert np.allclose(sim.results["out0"], impulse_response)

    impulse_response = [0.1 + i for i in range(50)]
    impulse_response += reversed(impulse_response)
    sfg = symmetric_fir(impulse_response)
    assert (
        len(
            [
                comp
                for comp in sfg.components
                if isinstance(comp, ConstantMultiplication)
            ]
        )
        == 50
    )
    assert len([comp for comp in sfg.components if isinstance(comp, Addition)]) == 99
    assert len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 99

    sim = Simulation(sfg, [Impulse()])
    sim.run_for(101)
    impulse_response.append(0.0)
    assert np.allclose(sim.results["out0"], impulse_response)

    with pytest.raises(ValueError, match=r"Coefficients must be of even length"):
        symmetric_fir([0.1, 0.2, 0.1])


def test_sfg_generator_errors():
    sfg_gens = [wdf_allpass, transposed_direct_form_fir, direct_form_fir, symmetric_fir]
    for gen in sfg_gens:
        with pytest.raises(ValueError, match=r"Coefficients cannot be empty"):
            gen([])
        with pytest.raises(TypeError, match=r"coefficients must be a 1D-array"):
            gen([[1, 2], [1, 3]])


class TestDirectFormIIRType1:
    def test_correct_number_of_operations_and_name(self):
        N = 17

        b = [i + 1 for i in range(N + 1)]
        a = [i + 1 for i in range(N + 1)]

        sfg = direct_form_1_iir(b, a, name="test iir direct form 1")

        amount_of_muls = len(sfg.find_by_type_name(ConstantMultiplication.type_name()))
        assert amount_of_muls == 2 * N

        amount_of_adds = len(sfg.find_by_type_name(Addition.type_name()))
        assert amount_of_adds == 2 * N

        amount_of_delays = len(sfg.find_by_type_name(Delay.type_name()))
        assert amount_of_delays == 2 * N

        amount_of_ops = len(sfg.operations)
        assert amount_of_ops == 6 * N + 2

        assert sfg.name == "test iir direct form 1"

        b = [1, 0.1, 0.1, 1, 1]
        a = [1, 0.1, 0.1, -1, -1]

        sfg = direct_form_1_iir(b, a, name="test iir direct form 1")

        amount_of_muls = len(sfg.find_by_type_name(ConstantMultiplication.type_name()))
        assert amount_of_muls == 4

        amount_of_adds = len(sfg.find_by_type_name(Addition.type_name()))
        assert amount_of_adds == 8

        amount_of_delays = len(sfg.find_by_type_name(Delay.type_name()))
        assert amount_of_delays == 8

        amount_of_ops = len(sfg.operations)
        assert amount_of_ops == 22

        b = [1, 1, 1, 1, 1]
        a = [1, -1, -1, -1, -1]

        sfg = direct_form_1_iir(b, a, name="test iir direct form 1")

        amount_of_muls = len(sfg.find_by_type_name(ConstantMultiplication.type_name()))
        assert amount_of_muls == 0

        amount_of_adds = len(sfg.find_by_type_name(Addition.type_name()))
        assert amount_of_adds == 8

        amount_of_delays = len(sfg.find_by_type_name(Delay.type_name()))
        assert amount_of_delays == 8

        amount_of_ops = len(sfg.operations)
        assert amount_of_ops == 18

    def test_b_single_coeff(self):
        with pytest.raises(
            ValueError,
            match=r"Size of coefficient lists a and b needs to contain at least 2 element.",
        ):
            direct_form_1_iir([1], [2, 3])

    def test_a_single_coeff(self):
        with pytest.raises(
            ValueError,
            match=r"Size of coefficient lists a and b needs to contain at least 2 element.",
        ):
            direct_form_1_iir([1, 2], [3])

    def test_coeffs_not_same_size(self):
        with pytest.raises(
            ValueError, match=r"Size of coefficient lists a and b are not the same."
        ):
            direct_form_1_iir([1, 2, 3], [1, 2])

        with pytest.raises(
            ValueError, match=r"Size of coefficient lists a and b are not the same."
        ):
            direct_form_1_iir(list(range(10)), list(range(11)))

        with pytest.raises(
            ValueError, match=r"Size of coefficient lists a and b are not the same."
        ):
            direct_form_1_iir(list(range(10)), list(range(11)))

    def test_a0_not_1(self):
        with pytest.raises(ValueError, match=r"The value of a\[0] must be 1\."):
            direct_form_1_iir(b=[1, 2, 3], a=[1.1, 2, 3])

    def test_first_order_filter(self):
        # First-order Butterworth
        b = np.array([0.5, 0.5])
        a = np.array([1, 0])

        sfg = direct_form_1_iir(b, a, name="test iir direct form 1")

        sp = pytest.importorskip("scipy")

        input_signal = np.random.default_rng().standard_normal(100)
        reference_filter_output = sp.signal.lfilter(b, a, input_signal)

        sim = Simulation(sfg, [ZeroPad(input_signal)])
        sim.run_for(100)

        assert np.allclose(sim.results["out0"], reference_filter_output)

    def test_random_input_compare_with_scipy_butterworth_filter(self):
        # Tenth-order Butterworth
        b = np.array(
            [
                4.96135121e-05,
                4.96135121e-04,
                2.23260804e-03,
                5.95362145e-03,
                1.04188375e-02,
                1.25026050e-02,
                1.04188375e-02,
                5.95362145e-03,
                2.23260804e-03,
                4.96135121e-04,
                4.96135121e-05,
            ]
        )
        a = np.array(
            [
                1.00000000e00,
                -3.98765437e00,
                8.09440659e00,
                -1.04762754e01,
                9.42333716e00,
                -6.08421408e00,
                2.83526165e00,
                -9.36403463e-01,
                2.08912325e-01,
                -2.83358587e-02,
                1.76963187e-03,
            ]
        )

        input_signal = np.random.default_rng().standard_normal(100)
        sp = pytest.importorskip("scipy")
        reference_filter_output = sp.signal.lfilter(b, a, input_signal)

        sfg = direct_form_1_iir(b, a, name="test iir direct form 1")

        sim = Simulation(sfg, [ZeroPad(input_signal)])
        sim.run_for(100)

        assert np.allclose(sim.results["out0"], reference_filter_output)

    def test_random_input_compare_with_scipy_elliptic_filter(self):
        N = 2
        Wc = 0.3

        sp = pytest.importorskip("scipy")

        b, a = sp.signal.ellip(N, 0.1, 60, Wc, btype="low", analog=False)
        # b, a = sp.signal.butter(N, Wc, btype="lowpass", output="ba")

        input_signal = np.random.default_rng().standard_normal(100)
        reference_filter_output = sp.signal.lfilter(b, a, input_signal)

        sfg = direct_form_1_iir(b, a, name="test iir direct form 1")

        sim = Simulation(sfg, [ZeroPad(input_signal)])
        sim.run_for(100)

        assert np.allclose(sim.results["out0"], reference_filter_output)

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
        b = list(range(N + 1))
        a = [i + 1 for i in range(N + 1)]
        sfg = direct_form_2_iir(b, a, name="test iir direct form 2")

        amount_of_muls = len(sfg.find_by_type_name(ConstantMultiplication.type_name()))
        assert amount_of_muls == 2 * N

        amount_of_adds = len(sfg.find_by_type_name(Addition.type_name()))
        assert amount_of_adds == 2 * N

        amount_of_delays = len(sfg.find_by_type_name(Delay.type_name()))
        assert amount_of_delays == N

        amount_of_ops = len(sfg.operations)
        assert amount_of_ops == 5 * N + 2

        b = [i + 1 for i in range(N + 1)]
        sfg = direct_form_2_iir(b, a, name="test iir direct form 2")

        amount_of_muls = len(sfg.find_by_type_name(ConstantMultiplication.type_name()))
        assert amount_of_muls == 2 * N

        amount_of_adds = len(sfg.find_by_type_name(Addition.type_name()))
        assert amount_of_adds == 2 * N

        amount_of_delays = len(sfg.find_by_type_name(Delay.type_name()))
        assert amount_of_delays == N

        amount_of_ops = len(sfg.operations)
        assert amount_of_ops == 5 * N + 2

        assert sfg.name == "test iir direct form 2"

        b = [1, 0.1, 1, 0.1]
        a = [1, -1, -1, 0.1]
        sfg = direct_form_2_iir(b, a)

        amount_of_muls = len(sfg.find_by_type_name(ConstantMultiplication.type_name()))
        assert amount_of_muls == 3

        amount_of_adds = len(sfg.find_by_type_name(Addition.type_name()))
        assert amount_of_adds == 6

        amount_of_delays = len(sfg.find_by_type_name(Delay.type_name()))
        assert amount_of_delays == 3

        amount_of_ops = len(sfg.operations)
        assert amount_of_ops == 14

        b = [1, 1, 1, 1, 1]
        a = [1, -1, -1, -1, -1]

        sfg = direct_form_2_iir(b, a, name="test iir direct form 1")

        amount_of_muls = len(sfg.find_by_type_name(ConstantMultiplication.type_name()))
        assert amount_of_muls == 0

        amount_of_adds = len(sfg.find_by_type_name(Addition.type_name()))
        assert amount_of_adds == 8

        amount_of_delays = len(sfg.find_by_type_name(Delay.type_name()))
        assert amount_of_delays == 4

        amount_of_ops = len(sfg.operations)
        assert amount_of_ops == 14

    def test_b_single_coeff(self):
        with pytest.raises(
            ValueError,
            match=r"Size of coefficient lists a and b needs to contain at least 2 element.",
        ):
            direct_form_2_iir([1], [2, 3])

    def test_a_single_coeff(self):
        with pytest.raises(
            ValueError,
            match=r"Size of coefficient lists a and b needs to contain at least 2 element.",
        ):
            direct_form_2_iir([1, 2], [3])

    def test_a0_not_1(self):
        with pytest.raises(ValueError, match=r"The value of a\[0] must be 1\."):
            direct_form_2_iir(b=[1, 2, 3], a=[1.1, 2, 3])

    def test_coeffs_not_same_size(self):
        with pytest.raises(
            ValueError, match=r"Size of coefficient lists a and b are not the same."
        ):
            direct_form_2_iir([1, 2, 3], [1, 2])

    def test_first_order_filter(self):
        # First-order Butterworth
        b = np.array([0.5, 0.5])
        a = np.array([1, 0])
        sp = pytest.importorskip("scipy")
        input_signal = np.random.default_rng().standard_normal(100)
        reference_filter_output = sp.signal.lfilter(b, a, input_signal)

        sfg = direct_form_2_iir(b, a, name="test iir direct form 1")

        sim = Simulation(sfg, [ZeroPad(input_signal)])
        sim.run_for(100)

        assert np.allclose(sim.results["out0"], reference_filter_output)

    def test_random_input_compare_with_scipy_butterworth_filter(self):
        N = 10
        Wc = 0.3
        sp = pytest.importorskip("scipy")

        b, a = sp.signal.butter(N, Wc, btype="lowpass", output="ba")

        input_signal = np.random.default_rng().standard_normal(100)
        reference_filter_output = sp.signal.lfilter(b, a, input_signal)

        sfg = direct_form_2_iir(b, a, name="test iir direct form 1")

        sim = Simulation(sfg, [ZeroPad(input_signal)])
        sim.run_for(100)

        assert np.allclose(sim.results["out0"], reference_filter_output)

    def test_random_input_compare_with_scipy_elliptic_filter(self):
        N = 2
        Wc = 0.3
        sp = pytest.importorskip("scipy")

        b, a = sp.signal.ellip(N, 0.1, 60, Wc, btype="low", analog=False)
        # b, a = sp.signal.butter(N, Wc, btype="lowpass", output="ba")

        input_signal = np.random.default_rng().standard_normal(100)
        reference_filter_output = sp.signal.lfilter(b, a, input_signal)

        sfg = direct_form_2_iir(b, a, name="test iir direct form 1")

        sim = Simulation(sfg, [ZeroPad(input_signal)])
        sim.run_for(100)

        assert np.allclose(sim.results["out0"], reference_filter_output)

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

        bfs = sfg.find_by_type_name(R2Butterfly.type_name())
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
            assert np.allclose(res[f"out{i}"], exp_res)

    def test_8_points_impulse_input(self):
        sfg = radix_2_dif_fft(points=8)

        assert len(sfg.inputs) == 8
        assert len(sfg.outputs) == 8

        bfs = sfg.find_by_type_name(R2Butterfly.type_name())
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
            assert np.allclose(res[f"out{i}"], 1)

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
            a = abs(res[f"out{i}"])
            b = exp_res[i]
            assert np.isclose(a, b)

    def test_16_points_sinus_input(self):
        POINTS = 16
        sfg = radix_2_dif_fft(points=POINTS)

        assert len(sfg.inputs) == POINTS
        assert len(sfg.outputs) == POINTS

        bfs = sfg.find_by_type_name(R2Butterfly.type_name())
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
            a = res[f"out{i}"]
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
            a = res[f"out{i}"]
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
            a = res[f"out{i}"]
            b = exp_res[i]
            assert np.isclose(a, b)

    def test_negative_number_of_points(self):
        POINTS = -8
        with pytest.raises(ValueError, match=r"Points must be positive number."):
            radix_2_dif_fft(points=POINTS)

    def test_number_of_points_not_power_of_2(self):
        POINTS = 5
        with pytest.raises(ValueError, match=r"Points must be a power of two."):
            radix_2_dif_fft(points=POINTS)


class TestLdltMatrixInverse:
    def test_1x1(self):
        sfg = ldlt_matrix_inverse(N=1)

        assert len(sfg.inputs) == 1
        assert len(sfg.outputs) == 1

        assert len(sfg.find_by_type_name(MADS.type_name())) == 0
        assert len(sfg.find_by_type_name(Reciprocal.type_name())) == 1

        A_input = [Constant(5)]

        sim = Simulation(sfg, A_input)
        sim.run_for(1)

        res = sim.results
        assert np.isclose(res["out0"], 0.2)

    def test_2x2_simple_spd(self):
        sfg = ldlt_matrix_inverse(N=2)

        assert len(sfg.inputs) == 3
        assert len(sfg.outputs) == 3

        assert len(sfg.find_by_type_name(MADS.type_name())) == 4
        assert len(sfg.find_by_type_name(Reciprocal.type_name())) == 2

        A = np.array([[1, 2], [2, 1]])
        A_input = [Constant(1), Constant(2), Constant(1)]

        A_inv = np.linalg.inv(A)

        sim = Simulation(sfg, A_input)
        sim.run_for(1)

        res = sim.results
        assert np.isclose(res["out0"], A_inv[0, 0])
        assert np.isclose(res["out1"], A_inv[0, 1])
        assert np.isclose(res["out2"], A_inv[1, 1])

    def test_3x3_simple_spd(self):
        sfg = ldlt_matrix_inverse(N=3)

        assert len(sfg.inputs) == 6
        assert len(sfg.outputs) == 6

        assert len(sfg.find_by_type_name(MADS.type_name())) == 15
        assert len(sfg.find_by_type_name(Reciprocal.type_name())) == 3

        A = np.array([[2, -1, 0], [-1, 3, -1], [0, -1, 2]])
        A_input = [
            Constant(2),
            Constant(-1),
            Constant(0),
            Constant(3),
            Constant(-1),
            Constant(2),
        ]

        A_inv = np.linalg.inv(A)

        sim = Simulation(sfg, A_input)
        sim.run_for(1)

        res = sim.results
        assert np.isclose(res["out0"], A_inv[0, 0])
        assert np.isclose(res["out1"], A_inv[0, 1])
        assert np.isclose(res["out2"], A_inv[0, 2])
        assert np.isclose(res["out3"], A_inv[1, 1])
        assert np.isclose(res["out4"], A_inv[1, 2])
        assert np.isclose(res["out5"], A_inv[2, 2])

    def test_5x5_random_spd(self):
        N = 5

        sfg = ldlt_matrix_inverse(N=N)

        assert len(sfg.inputs) == 15
        assert len(sfg.outputs) == 15

        assert len(sfg.find_by_type_name(MADS.type_name())) == 70
        assert len(sfg.find_by_type_name(Reciprocal.type_name())) == N

        A = self._generate_random_spd_matrix(N)

        upper_tridiag = A[np.triu_indices_from(A)]

        A_input = [Constant(num) for num in upper_tridiag]
        A_inv = np.linalg.inv(A)

        sim = Simulation(sfg, A_input)
        sim.run_for(1)
        res = sim.results

        row_indices, col_indices = np.triu_indices(N)
        expected_values = A_inv[row_indices, col_indices]
        actual_values = [res[f"out{i}"] for i in range(len(expected_values))]

        for i in range(len(expected_values)):
            assert np.isclose(actual_values[i], expected_values[i])

    def test_20x20_random_spd(self):
        N = 20

        sfg = ldlt_matrix_inverse(N=N)

        A = self._generate_random_spd_matrix(N)

        assert len(sfg.inputs) == len(A[np.triu_indices_from(A)])
        assert len(sfg.outputs) == len(A[np.triu_indices_from(A)])

        assert len(sfg.find_by_type_name(Reciprocal.type_name())) == N

        upper_tridiag = A[np.triu_indices_from(A)]

        A_input = [Constant(num) for num in upper_tridiag]
        A_inv = np.linalg.inv(A)

        sim = Simulation(sfg, A_input)
        sim.run_for(1)
        res = sim.results

        row_indices, col_indices = np.triu_indices(N)
        expected_values = A_inv[row_indices, col_indices]
        actual_values = [res[f"out{i}"] for i in range(len(expected_values))]

        for i in range(len(expected_values)):
            assert np.isclose(actual_values[i], expected_values[i])

    # def test_2x2_random_complex_spd(self):
    #     N = 2

    #     sfg = ldlt_matrix_inverse(N=N, is_complex=True)

    #     # A = self._generate_random_complex_spd_matrix(N)
    #     A = np.array([[2, 1+1j],[1-1j, 3]])

    #     assert len(sfg.inputs) == len(A[np.triu_indices_from(A)])
    #     assert len(sfg.outputs) == len(A[np.triu_indices_from(A)])

    #     assert len(sfg.find_by_type_name(Reciprocal.type_name())) == N

    #     upper_tridiag = A[np.triu_indices_from(A)]

    #     A_input = [Constant(num) for num in upper_tridiag]
    #     A_inv = np.linalg.inv(A)

    #     sim = Simulation(sfg, A_input)
    #     sim.run_for(1)
    #     res = sim.results

    #     row_indices, col_indices = np.triu_indices(N)
    #     expected_values = A_inv[row_indices, col_indices]
    #     actual_values = [res[f"out{i}"] for i in range(len(expected_values))]

    #     for i in range(len(expected_values)):
    #         assert np.isclose(actual_values[i], expected_values[i])

    def _generate_random_spd_matrix(self, N: int) -> np.ndarray:
        A = np.random.default_rng().random((N, N))
        A = (A + A.T) / 2  # ensure symmetric
        min_eig = np.min(np.linalg.eigvals(A))
        A += (np.abs(min_eig) + 0.1) * np.eye(N)  # ensure positive definiteness
        return A

    # def _generate_random_complex_spd_matrix(self, N: int) -> np.ndarray:
    #     A = np.random.randn(N, N) + 1j * np.random.randn(N, N)
    #     A = (A + A.conj().T) / 2  # ensure symmetric
    #     min_eig = np.min(np.linalg.eigvals(A))
    #     A += (np.abs(min_eig) + 0.1) * np.eye(N)  # ensure positive definiteness
    #     return A


class TestMatrixMultiplication:
    def test_1x1_1x1(self):
        sfg = matrix_multiplication(1, 1, 1)

        assert len(sfg.inputs) == 2
        assert len(sfg.outputs) == 1

        assert len(sfg.find_by_type_name("dontcare")) == 1
        assert len(sfg.find_by_type_name("mad")) == 1

        sim = Simulation(sfg, [Constant(2), Constant(3)])

        sim.run_for(1)
        assert np.isclose(sim.results["out0"], 6)

    def test_2x1_1x1(self):
        sfg = matrix_multiplication(2, 1, 1)

        assert len(sfg.inputs) == 3
        assert len(sfg.outputs) == 2

        assert len(sfg.find_by_type_name("dontcare")) == 2
        assert len(sfg.find_by_type_name("mad")) == 2

        sim = Simulation(sfg, [Constant(2), Constant(3), Constant(5)])

        sim.run_for(1)
        assert np.isclose(sim.results["out0"], 10)
        assert np.isclose(sim.results["out1"], 15)

    def test_2x2_2x2(self):
        sfg = matrix_multiplication(2, 2, 2)

        assert len(sfg.inputs) == 8
        assert len(sfg.outputs) == 4

        assert len(sfg.find_by_type_name("dontcare")) == 4
        assert len(sfg.find_by_type_name("mad")) == 8

        sim = Simulation(
            sfg,
            [
                Constant(3),
                Constant(5),
                Constant(7),
                Constant(11),
                Constant(2),
                Constant(4),
                Constant(9),
                Constant(13),
            ],
        )

        sim.run_for(1)
        assert np.isclose(sim.results["out0"], 51)
        assert np.isclose(sim.results["out1"], 77)
        assert np.isclose(sim.results["out2"], 113)
        assert np.isclose(sim.results["out3"], 171)

    def test_2x3_3x2(self):
        sfg = matrix_multiplication(2, 3, 2)

        assert len(sfg.inputs) == 12
        assert len(sfg.outputs) == 4

        assert len(sfg.find_by_type_name("dontcare")) == 4
        assert len(sfg.find_by_type_name("mad")) == 12

        sim = Simulation(
            sfg,
            [
                Constant(1),
                Constant(2),
                Constant(3),
                Constant(4),
                Constant(5),
                Constant(6),
                Constant(7),
                Constant(8),
                Constant(9),
                Constant(10),
                Constant(11),
                Constant(12),
            ],
        )

        sim.run_for(1)
        assert np.isclose(sim.results["out0"], 58)
        assert np.isclose(sim.results["out1"], 64)
        assert np.isclose(sim.results["out2"], 139)
        assert np.isclose(sim.results["out3"], 154)
