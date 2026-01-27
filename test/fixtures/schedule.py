import pytest

from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.scheduler import ASAPScheduler
from b_asic.sfg import SFG


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


@pytest.fixture
def schedule_r2bf(sfg_r2bf: SFG):
    sfg_r2bf.set_latency_of_type_name("add", 1)
    sfg_r2bf.set_latency_of_type_name("sub", 1)
    schedule = Schedule(sfg_r2bf, cyclic=True)
    schedule.set_schedule_time(2)
    schedule.move_operation("out1", 1)
    schedule.move_operation("sub0", 1)
    schedule.move_operation("out1", 1)
    schedule.move_operation("sub0", 1)
    schedule.move_operation("out0", 1)
    schedule.move_operation("add0", 1)
    schedule.move_operation("in1", 1)
    return schedule


@pytest.fixture
def schedule_simple_loop(sfg_simple_loop: SFG):
    sfg_simple_loop.set_execution_time_of_type_name("add", 1)
    sfg_simple_loop.set_latency_of_type_name("add", 1)
    sfg_simple_loop.set_execution_time_of_type_name("cmul", 1)
    sfg_simple_loop.set_latency_of_type_name("cmul", 1)
    sched = Schedule(sfg_simple_loop)
    sched.set_schedule_time(2)
    sched.move_operation("out0", 1)
    return sched


@pytest.fixture
def schedule_two_inputs_two_outputs_independent_with_cmul_scaled(
    sfg_two_inputs_two_outputs_independent_with_cmul_scaled: SFG,
):
    sfg = sfg_two_inputs_two_outputs_independent_with_cmul_scaled
    sfg.set_latency_of_type_name("add", 7)
    sfg.set_latency_of_type_name("cmul", 3)
    return Schedule(sfg)
