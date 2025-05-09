import pytest

from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.scheduler import ASAPScheduler
from b_asic.signal_flow_graph import SFG


@pytest.fixture
def secondorder_iir_schedule(precedence_sfg_delays):
    precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 4)
    precedence_sfg_delays.set_latency_of_type_name(
        ConstantMultiplication.type_name(), 3
    )

    return Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())


@pytest.fixture
def secondorder_iir_schedule_with_execution_times(precedence_sfg_delays):
    precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 4)
    precedence_sfg_delays.set_latency_of_type_name(
        ConstantMultiplication.type_name(), 3
    )
    precedence_sfg_delays.set_execution_time_of_type_name(Addition.type_name(), 2)
    precedence_sfg_delays.set_execution_time_of_type_name(
        ConstantMultiplication.type_name(), 1
    )

    return Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())


@pytest.fixture
def schedule_direct_form_iir_lp_filter(sfg_direct_form_iir_lp_filter: SFG):
    sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 4)
    sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
        ConstantMultiplication.type_name(), 3
    )
    sfg_direct_form_iir_lp_filter.set_execution_time_of_type_name(
        Addition.type_name(), 2
    )
    sfg_direct_form_iir_lp_filter.set_execution_time_of_type_name(
        ConstantMultiplication.type_name(), 1
    )
    schedule = Schedule(
        sfg_direct_form_iir_lp_filter, scheduler=ASAPScheduler(), cyclic=True
    )
    schedule.move_operation("cmul3", -1)
    schedule.move_operation("cmul2", -1)
    schedule.move_operation("cmul3", -10)
    schedule.move_operation("cmul3", 1)
    schedule.move_operation("cmul2", -8)
    schedule.move_operation("add3", 1)
    schedule.move_operation("add3", 1)
    schedule.move_operation("cmul1", 1)
    schedule.move_operation("cmul1", 1)
    schedule.move_operation("cmul3", 2)
    return schedule
