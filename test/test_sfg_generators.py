import numpy as np
import pytest

from b_asic.core_operations import (
    Addition,
    ConstantMultiplication,
    SymmetricTwoportAdaptor,
)
from b_asic.sfg_generators import (
    direct_form_fir,
    transposed_direct_form_fir,
    wdf_allpass,
)
from b_asic.signal_generator import Impulse
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
