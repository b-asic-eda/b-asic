from test.fixtures.signal_flow_graph import precedence_sfg_delays

import pytest

from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.schedule import Schedule


@pytest.fixture
def secondorder_iir_schedule(precedence_sfg_delays):
    precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 4)
    precedence_sfg_delays.set_latency_of_type(
        ConstantMultiplication.type_name(), 3
    )

    schedule = Schedule(precedence_sfg_delays, scheduling_alg="ASAP")
    return schedule
