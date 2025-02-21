import pytest

from b_asic.core_operations import Addition, Butterfly, ConstantMultiplication
from b_asic.schedule import Schedule
from b_asic.scheduler import ALAPScheduler, ASAPScheduler
from b_asic.sfg_generators import direct_form_1_iir, radix_2_dif_fft


class TestASAPScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=ASAPScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([1, 2, 3], [1, 2, 3])

        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type(Addition.type_name(), 3)
        sfg.set_execution_time_of_type(Addition.type_name(), 1)

        schedule = Schedule(sfg, scheduler=ASAPScheduler())

        assert schedule.start_times == {
            "in0": 0,
            "cmul0": 0,
            "cmul1": 0,
            "cmul2": 0,
            "cmul3": 0,
            "cmul4": 0,
            "add3": 2,
            "add1": 2,
            "add0": 5,
            "add2": 8,
            "out0": 11,
        }
        assert schedule.schedule_time == 11

    def test_direct_form_2_iir(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(sfg_direct_form_iir_lp_filter, scheduler=ASAPScheduler())

        assert schedule.start_times == {
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

        assert schedule.start_times == {
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

    def test_radix_2_fft_8_points(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type(Butterfly.type_name(), 1)

        schedule = Schedule(sfg, scheduler=ASAPScheduler())

        assert schedule.start_times == {
            "in0": 0,
            "in1": 0,
            "in2": 0,
            "in3": 0,
            "in4": 0,
            "in5": 0,
            "in6": 0,
            "in7": 0,
            "bfly0": 0,
            "bfly6": 0,
            "bfly8": 0,
            "bfly11": 0,
            "cmul3": 1,
            "bfly7": 1,
            "cmul2": 1,
            "bfly1": 1,
            "cmul0": 1,
            "cmul4": 2,
            "bfly9": 2,
            "bfly5": 3,
            "bfly2": 3,
            "out0": 3,
            "out4": 3,
            "bfly10": 4,
            "cmul1": 4,
            "bfly3": 4,
            "out1": 5,
            "out2": 5,
            "out5": 5,
            "out6": 5,
            "bfly4": 6,
            "out3": 7,
            "out7": 7,
        }
        assert schedule.schedule_time == 7


class TestALAPScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=ALAPScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([1, 2, 3], [1, 2, 3])

        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type(Addition.type_name(), 3)
        sfg.set_execution_time_of_type(Addition.type_name(), 1)

        schedule = Schedule(sfg, scheduler=ALAPScheduler())

        assert schedule.start_times == {
            "cmul3": 0,
            "cmul4": 0,
            "add1": 2,
            "in0": 3,
            "cmul0": 3,
            "cmul1": 3,
            "cmul2": 3,
            "add3": 5,
            "add0": 5,
            "add2": 8,
            "out0": 11,
        }
        assert schedule.schedule_time == 11

    def test_direct_form_2_iir(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(sfg_direct_form_iir_lp_filter, scheduler=ALAPScheduler())

        assert schedule.start_times == {
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

        assert schedule.start_times == {
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

    def test_radix_2_fft_8_points(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type(Butterfly.type_name(), 1)

        schedule = Schedule(sfg, scheduler=ALAPScheduler())

        assert schedule.start_times == {
            "in3": 0,
            "in7": 0,
            "in1": 0,
            "in5": 0,
            "bfly6": 0,
            "bfly8": 0,
            "cmul2": 1,
            "cmul3": 1,
            "in2": 2,
            "in6": 2,
            "bfly11": 2,
            "bfly7": 3,
            "cmul0": 3,
            "bfly5": 3,
            "in0": 4,
            "in4": 4,
            "cmul4": 4,
            "cmul1": 4,
            "bfly0": 4,
            "bfly1": 5,
            "bfly2": 5,
            "bfly9": 6,
            "bfly10": 6,
            "bfly3": 6,
            "bfly4": 6,
            "out0": 7,
            "out1": 7,
            "out2": 7,
            "out3": 7,
            "out4": 7,
            "out5": 7,
            "out6": 7,
            "out7": 7,
        }
        assert schedule.schedule_time == 7
