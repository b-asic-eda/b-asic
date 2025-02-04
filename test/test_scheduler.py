import pytest

from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.scheduler import ALAPScheduler, ASAPScheduler, EarliestDeadlineScheduler


class TestASAPScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=ASAPScheduler())

    def test_direct_form_2_iir(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(sfg_direct_form_iir_lp_filter, scheduler=ASAPScheduler())

        assert schedule._start_times == {
            "in0": 0,
            "cmul1": 0,
            "cmul4": 0,
            "cmul2": 0,
            "cmul3": 0,
            "add3": 4,
            "add1": 4,
            "add0": 9,
            "cmul0": 14,
            "add2": 18,
            "out0": 23,
        }
        assert schedule.schedule_time == 23

    def test_direct_form_2_iir_with_scheduling_time(
        self, sfg_direct_form_iir_lp_filter
    ):
        sfg_direct_form_iir_lp_filter.set_latency_of_type(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter, scheduler=ASAPScheduler(), schedule_time=30
        )

        assert schedule._start_times == {
            "in0": 0,
            "cmul1": 0,
            "cmul4": 0,
            "cmul2": 0,
            "cmul3": 0,
            "add3": 4,
            "add1": 4,
            "add0": 9,
            "cmul0": 14,
            "add2": 18,
            "out0": 23,
        }
        assert schedule.schedule_time == 30


class TestALAPScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=ALAPScheduler())

    def test_direct_form_2_iir(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(sfg_direct_form_iir_lp_filter, scheduler=ALAPScheduler())

        assert schedule._start_times == {
            "cmul3": 0,
            "cmul4": 0,
            "add1": 4,
            "in0": 9,
            "cmul2": 9,
            "cmul1": 9,
            "add0": 9,
            "add3": 13,
            "cmul0": 14,
            "add2": 18,
            "out0": 23,
        }
        assert schedule.schedule_time == 23

    def test_direct_form_2_iir_with_scheduling_time(
        self, sfg_direct_form_iir_lp_filter
    ):
        sfg_direct_form_iir_lp_filter.set_latency_of_type(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter, scheduler=ALAPScheduler(), schedule_time=30
        )

        assert schedule._start_times == {
            "cmul3": 7,
            "cmul4": 7,
            "add1": 11,
            "in0": 16,
            "cmul2": 16,
            "cmul1": 16,
            "add0": 16,
            "add3": 20,
            "cmul0": 21,
            "add2": 25,
            "out0": 30,
        }
        assert schedule.schedule_time == 30


class TestEarliestDeadlineScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=EarliestDeadlineScheduler())

    def test_direct_form_2_iir_inf_resources_no_exec_time(
        self, sfg_direct_form_iir_lp_filter
    ):
        sfg_direct_form_iir_lp_filter.set_latency_of_type(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter, scheduler=EarliestDeadlineScheduler()
        )

        # should be the same as for ASAP due to infinite resources, except for input
        assert schedule._start_times == {
            "in0": 9,
            "cmul1": 0,
            "cmul4": 0,
            "cmul2": 0,
            "cmul3": 0,
            "add3": 4,
            "add1": 4,
            "add0": 9,
            "cmul0": 14,
            "add2": 18,
            "out0": 23,
        }
        assert schedule.schedule_time == 23

    def test_direct_form_2_iir_1_add_1_mul_no_exec_time(
        self, sfg_direct_form_iir_lp_filter
    ):
        sfg_direct_form_iir_lp_filter.set_latency_of_type(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type(
            ConstantMultiplication.type_name(), 4
        )

        max_resources = {ConstantMultiplication.type_name(): 1, Addition.type_name(): 1}

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter,
            scheduler=EarliestDeadlineScheduler(max_resources),
        )
        assert schedule._start_times == {
            "cmul4": 0,
            "cmul3": 4,
            "cmul1": 8,
            "add1": 8,
            "cmul2": 12,
            "in0": 13,
            "add0": 13,
            "add3": 18,
            "cmul0": 18,
            "add2": 23,
            "out0": 28,
        }

        assert schedule.schedule_time == 28

    def test_direct_form_2_iir_1_add_1_mul_exec_time_1(
        self, sfg_direct_form_iir_lp_filter
    ):
        sfg_direct_form_iir_lp_filter.set_latency_of_type(
            ConstantMultiplication.type_name(), 3
        )
        sfg_direct_form_iir_lp_filter.set_latency_of_type(Addition.type_name(), 2)
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type(
            ConstantMultiplication.type_name(), 1
        )
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type(
            Addition.type_name(), 1
        )

        max_resources = {ConstantMultiplication.type_name(): 1, Addition.type_name(): 1}

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter,
            scheduler=EarliestDeadlineScheduler(max_resources),
        )
        assert schedule._start_times == {
            "cmul4": 0,
            "cmul3": 1,
            "cmul1": 2,
            "cmul2": 3,
            "add1": 4,
            "in0": 6,
            "add0": 6,
            "add3": 7,
            "cmul0": 8,
            "add2": 11,
            "out0": 13,
        }

        assert schedule.schedule_time == 13

    def test_direct_form_2_iir_2_add_3_mul_exec_time_1(
        self, sfg_direct_form_iir_lp_filter
    ):
        sfg_direct_form_iir_lp_filter.set_latency_of_type(
            ConstantMultiplication.type_name(), 3
        )
        sfg_direct_form_iir_lp_filter.set_latency_of_type(Addition.type_name(), 2)
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type(
            ConstantMultiplication.type_name(), 1
        )
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type(
            Addition.type_name(), 1
        )

        max_resources = {ConstantMultiplication.type_name(): 3, Addition.type_name(): 2}

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter,
            scheduler=EarliestDeadlineScheduler(max_resources),
        )
        assert schedule._start_times == {
            "cmul1": 0,
            "cmul4": 0,
            "cmul3": 0,
            "cmul2": 1,
            "add1": 3,
            "add3": 4,
            "in0": 5,
            "add0": 5,
            "cmul0": 7,
            "add2": 10,
            "out0": 12,
        }

        assert schedule.schedule_time == 12
