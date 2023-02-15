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
    sfg = direct_form_fir([0.3, 0.5, 0.7])
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
    assert (
        len([comp for comp in sfg.components if isinstance(comp, Addition)])
        == 2
    )
    assert (
        len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 2
    )

    sfg = direct_form_fir(
        (0.3, 0.4, 0.5, 0.6, 0.3),
        mult_properties={'latency': 2, 'execution_time': 1},
        add_properties={'latency': 1, 'execution_time': 1},
    )
    assert sfg.critical_path() == 6


def test_transposed_direct_form_fir():
    sfg = transposed_direct_form_fir([0.3, 0.5, 0.7])
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
    assert (
        len([comp for comp in sfg.components if isinstance(comp, Addition)])
        == 2
    )
    assert (
        len([comp for comp in sfg.components if isinstance(comp, Delay)]) == 2
    )

    sfg = transposed_direct_form_fir(
        (0.3, 0.4, 0.5, 0.6, 0.3),
        mult_properties={'latency': 2, 'execution_time': 1},
        add_properties={'latency': 1, 'execution_time': 1},
    )
    assert sfg.critical_path() == 3
