import numpy as np

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
