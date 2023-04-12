import pytest

from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.schedule import Schedule


@pytest.fixture
def secondorder_iir_schedule(precedence_sfg_delays):
    precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 4)
    precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

    schedule = Schedule(precedence_sfg_delays, scheduling_algorithm="ASAP")
    return schedule


@pytest.fixture
def secondorder_iir_schedule_with_execution_times(precedence_sfg_delays):
    precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 4)
    precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)
    precedence_sfg_delays.set_execution_time_of_type(Addition.type_name(), 2)
    precedence_sfg_delays.set_execution_time_of_type(
        ConstantMultiplication.type_name(), 1
    )

    schedule = Schedule(precedence_sfg_delays, scheduling_algorithm="ASAP")
    return schedule
