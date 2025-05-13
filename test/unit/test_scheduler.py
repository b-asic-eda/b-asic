import pytest

from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.fft_operations import R2Butterfly
from b_asic.schedule import Schedule
from b_asic.scheduler import ALAPScheduler, ASAPScheduler, ILPScheduler
from b_asic.sfg_generators import direct_form_1_iir, radix_2_dif_fft


class TestASAPScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=ASAPScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([0.1, 0.2, 0.3], [1, 2, 3])

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

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
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
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
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
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

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(R2Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(R2Butterfly.type_name(), 1)

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
            "r2bfly0": 0,
            "r2bfly6": 0,
            "r2bfly8": 0,
            "r2bfly11": 0,
            "cmul3": 1,
            "r2bfly7": 1,
            "cmul2": 1,
            "r2bfly1": 1,
            "cmul0": 1,
            "cmul4": 2,
            "r2bfly9": 2,
            "r2bfly5": 3,
            "r2bfly2": 3,
            "out0": 3,
            "out4": 3,
            "r2bfly10": 4,
            "cmul1": 4,
            "r2bfly3": 4,
            "out1": 5,
            "out2": 5,
            "out5": 5,
            "out6": 5,
            "r2bfly4": 6,
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
        sfg = direct_form_1_iir([0.1, 0.2, 0.3], [1, 2, 3])

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

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
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
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
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
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

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(R2Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(R2Butterfly.type_name(), 1)

        schedule = Schedule(sfg, scheduler=ALAPScheduler())

        assert schedule.start_times == {
            "in3": 0,
            "in7": 0,
            "in1": 0,
            "in5": 0,
            "r2bfly6": 0,
            "r2bfly8": 0,
            "cmul2": 1,
            "cmul3": 1,
            "in2": 2,
            "in6": 2,
            "r2bfly11": 2,
            "r2bfly7": 3,
            "cmul0": 3,
            "r2bfly5": 3,
            "in0": 4,
            "in4": 4,
            "cmul4": 4,
            "cmul1": 4,
            "r2bfly0": 4,
            "r2bfly1": 5,
            "r2bfly2": 5,
            "r2bfly9": 6,
            "r2bfly10": 6,
            "r2bfly3": 6,
            "r2bfly4": 6,
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


class TestILPScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=ALAPScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([0.1, 0.2, 0.3], [1, 2, 3])

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

        schedule = Schedule(sfg, ILPScheduler(), schedule_time=11)

        assert schedule.schedule_time == 11

        schedule = Schedule(sfg, ILPScheduler(), schedule_time=50)
        assert schedule.schedule_time == 50

        ops = schedule.get_operations()
        assert (
            ops.get_by_type_name("add").processing_element_bound()
            + ops.get_by_type_name("cmul").processing_element_bound()
            + ops.get_by_type_name("in").processing_element_bound()
            + ops.get_by_type_name("out").processing_element_bound()
            == 4
        )

    def test_direct_form_2_iir(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type(Addition, 2)
        sfg_direct_form_iir_lp_filter.set_latency_of_type(ConstantMultiplication, 3)
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type(
            ConstantMultiplication, 1
        )
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type(Addition, 1)

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter, ILPScheduler(), schedule_time=15
        )
        assert schedule.schedule_time == 15

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter, ILPScheduler(), schedule_time=60
        )
        assert schedule.schedule_time == 60

        ops = schedule.get_operations()
        assert (
            ops.get_by_type_name("add").processing_element_bound()
            + ops.get_by_type_name("cmul").processing_element_bound()
            + ops.get_by_type_name("in").processing_element_bound()
            + ops.get_by_type_name("out").processing_element_bound()
            == 4
        )
