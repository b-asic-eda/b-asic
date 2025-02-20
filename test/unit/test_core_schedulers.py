import sys

import pytest

from b_asic.core_operations import (
    MADS,
    Addition,
    Butterfly,
    ConstantMultiplication,
    Reciprocal,
)
from b_asic.core_schedulers import (
    ALAPScheduler,
    ASAPScheduler,
    EarliestDeadlineScheduler,
    HybridScheduler,
    LeastSlackTimeScheduler,
    MaxFanOutScheduler,
)
from b_asic.schedule import Schedule
from b_asic.sfg_generators import (
    direct_form_1_iir,
    ldlt_matrix_inverse,
    radix_2_dif_fft,
)
from b_asic.special_operations import Input, Output


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


class TestEarliestDeadlineScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=EarliestDeadlineScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([1, 2, 3], [1, 2, 3])

        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type(Addition.type_name(), 3)
        sfg.set_execution_time_of_type(Addition.type_name(), 1)

        resources = {
            Addition.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
            Input.type_name(): sys.maxsize,
            Output.type_name(): sys.maxsize,
        }
        schedule = Schedule(
            sfg, scheduler=EarliestDeadlineScheduler(max_resources=resources)
        )

        assert schedule.start_times == {
            "in0": 0,
            "cmul4": 0,
            "cmul3": 1,
            "cmul0": 2,
            "add1": 3,
            "cmul1": 3,
            "cmul2": 4,
            "add3": 6,
            "add0": 7,
            "add2": 10,
            "out0": 13,
        }
        assert schedule.schedule_time == 13

    def test_direct_form_2_iir_1_add_1_mul(self, sfg_direct_form_iir_lp_filter):
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

        resources = {
            Addition.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
            Input.type_name(): sys.maxsize,
            Output.type_name(): sys.maxsize,
        }

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter,
            scheduler=EarliestDeadlineScheduler(resources),
        )
        assert schedule.start_times == {
            "in0": 0,
            "cmul4": 0,
            "cmul3": 1,
            "cmul1": 2,
            "cmul2": 3,
            "add1": 4,
            "add0": 6,
            "add3": 7,
            "cmul0": 8,
            "add2": 11,
            "out0": 13,
        }

        assert schedule.schedule_time == 13

    def test_direct_form_2_iir_2_add_3_mul(self, sfg_direct_form_iir_lp_filter):
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

        resources = {
            Addition.type_name(): 2,
            ConstantMultiplication.type_name(): 3,
            Input.type_name(): sys.maxsize,
            Output.type_name(): sys.maxsize,
        }

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter,
            scheduler=EarliestDeadlineScheduler(resources),
        )
        assert schedule.start_times == {
            "in0": 0,
            "cmul1": 0,
            "cmul4": 0,
            "cmul3": 0,
            "cmul2": 1,
            "add1": 3,
            "add3": 4,
            "add0": 5,
            "cmul0": 7,
            "add2": 10,
            "out0": 12,
        }

        assert schedule.schedule_time == 12

    def test_radix_2_fft_8_points(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type(Butterfly.type_name(), 1)

        resources = {
            Butterfly.type_name(): 2,
            ConstantMultiplication.type_name(): 2,
            Input.type_name(): sys.maxsize,
            Output.type_name(): sys.maxsize,
        }
        schedule = Schedule(
            sfg, scheduler=EarliestDeadlineScheduler(max_resources=resources)
        )

        assert schedule.start_times == {
            "in0": 0,
            "in1": 0,
            "in2": 0,
            "in3": 0,
            "in4": 0,
            "in5": 0,
            "in6": 0,
            "in7": 0,
            "bfly6": 0,
            "bfly8": 0,
            "cmul2": 1,
            "cmul3": 1,
            "bfly11": 1,
            "bfly7": 1,
            "cmul0": 2,
            "bfly0": 2,
            "cmul4": 2,
            "bfly5": 3,
            "bfly1": 3,
            "cmul1": 4,
            "bfly2": 4,
            "bfly9": 4,
            "bfly10": 5,
            "bfly3": 5,
            "out0": 5,
            "out4": 5,
            "bfly4": 6,
            "out1": 6,
            "out2": 6,
            "out5": 6,
            "out6": 6,
            "out7": 7,
            "out3": 7,
        }
        assert schedule.schedule_time == 7


class TestLeastSlackTimeScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=LeastSlackTimeScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([1, 2, 3], [1, 2, 3])

        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type(Addition.type_name(), 3)
        sfg.set_execution_time_of_type(Addition.type_name(), 1)

        resources = {
            Addition.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
            Input.type_name(): sys.maxsize,
            Output.type_name(): sys.maxsize,
        }
        schedule = Schedule(
            sfg, scheduler=LeastSlackTimeScheduler(max_resources=resources)
        )

        assert schedule.start_times == {
            "in0": 0,
            "cmul4": 0,
            "cmul3": 1,
            "cmul0": 2,
            "add1": 3,
            "cmul1": 3,
            "cmul2": 4,
            "add3": 6,
            "add0": 7,
            "add2": 10,
            "out0": 13,
        }
        assert schedule.schedule_time == 13

    def test_direct_form_2_iir_1_add_1_mul(self, sfg_direct_form_iir_lp_filter):
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

        resources = {
            Addition.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
            Input.type_name(): sys.maxsize,
            Output.type_name(): sys.maxsize,
        }

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter,
            scheduler=LeastSlackTimeScheduler(resources),
        )
        assert schedule.start_times == {
            "in0": 0,
            "cmul4": 0,
            "cmul3": 1,
            "cmul1": 2,
            "cmul2": 3,
            "add1": 4,
            "add0": 6,
            "add3": 7,
            "cmul0": 8,
            "add2": 11,
            "out0": 13,
        }

        assert schedule.schedule_time == 13

    def test_direct_form_2_iir_2_add_3_mul(self, sfg_direct_form_iir_lp_filter):
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

        resources = {
            Addition.type_name(): 2,
            ConstantMultiplication.type_name(): 3,
            Input.type_name(): sys.maxsize,
            Output.type_name(): sys.maxsize,
        }

        schedule = Schedule(
            sfg_direct_form_iir_lp_filter,
            scheduler=LeastSlackTimeScheduler(resources),
        )
        assert schedule.start_times == {
            "in0": 0,
            "cmul1": 0,
            "cmul4": 0,
            "cmul3": 0,
            "cmul2": 1,
            "add1": 3,
            "add3": 4,
            "add0": 5,
            "cmul0": 7,
            "add2": 10,
            "out0": 12,
        }

        assert schedule.schedule_time == 12

    def test_radix_2_fft_8_points(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type(Butterfly.type_name(), 1)

        resources = {
            Butterfly.type_name(): 2,
            ConstantMultiplication.type_name(): 2,
            Input.type_name(): sys.maxsize,
            Output.type_name(): sys.maxsize,
        }
        schedule = Schedule(
            sfg, scheduler=LeastSlackTimeScheduler(max_resources=resources)
        )

        assert schedule.start_times == {
            "in0": 0,
            "in1": 0,
            "in2": 0,
            "in3": 0,
            "in4": 0,
            "in5": 0,
            "in6": 0,
            "in7": 0,
            "bfly6": 0,
            "bfly8": 0,
            "cmul2": 1,
            "cmul3": 1,
            "bfly11": 1,
            "bfly7": 1,
            "cmul0": 2,
            "bfly0": 2,
            "cmul4": 2,
            "bfly5": 3,
            "bfly1": 3,
            "cmul1": 4,
            "bfly2": 4,
            "bfly9": 4,
            "bfly10": 5,
            "bfly3": 5,
            "out0": 5,
            "out4": 5,
            "bfly4": 6,
            "out1": 6,
            "out2": 6,
            "out5": 6,
            "out6": 6,
            "out7": 7,
            "out3": 7,
        }
        assert schedule.schedule_time == 7


class TestMaxFanOutScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=MaxFanOutScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([1, 2, 3], [1, 2, 3])

        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type(Addition.type_name(), 3)
        sfg.set_execution_time_of_type(Addition.type_name(), 1)

        resources = {Addition.type_name(): 1, ConstantMultiplication.type_name(): 1}
        schedule = Schedule(sfg, scheduler=MaxFanOutScheduler(max_resources=resources))

        assert schedule.start_times == {
            "in0": 0,
            "cmul0": 0,
            "cmul1": 1,
            "cmul2": 2,
            "cmul4": 3,
            "cmul3": 4,
            "add3": 4,
            "add1": 6,
            "add0": 9,
            "add2": 12,
            "out0": 15,
        }
        assert schedule.schedule_time == 15


class TestHybridScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=HybridScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([1, 2, 3], [1, 2, 3])

        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type(Addition.type_name(), 3)
        sfg.set_execution_time_of_type(Addition.type_name(), 1)

        resources = {Addition.type_name(): 1, ConstantMultiplication.type_name(): 1}
        schedule = Schedule(sfg, scheduler=HybridScheduler(max_resources=resources))

        assert schedule.start_times == {
            "in0": 0,
            "cmul4": 0,
            "cmul3": 1,
            "cmul0": 2,
            "add1": 3,
            "cmul1": 3,
            "cmul2": 4,
            "add3": 6,
            "add0": 7,
            "add2": 10,
            "out0": 13,
        }
        assert schedule.schedule_time == 13

    def test_radix_2_fft_8_points(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type(Butterfly.type_name(), 1)

        resources = {
            Butterfly.type_name(): 2,
            ConstantMultiplication.type_name(): 2,
            Input.type_name(): sys.maxsize,
            Output.type_name(): sys.maxsize,
        }
        schedule = Schedule(sfg, scheduler=HybridScheduler(max_resources=resources))

        assert schedule.start_times == {
            "in0": 0,
            "in1": 0,
            "in2": 0,
            "in3": 0,
            "in4": 0,
            "in5": 0,
            "in6": 0,
            "in7": 0,
            "bfly6": 0,
            "bfly8": 0,
            "cmul2": 1,
            "cmul3": 1,
            "bfly11": 1,
            "bfly7": 1,
            "cmul0": 2,
            "bfly0": 2,
            "cmul4": 2,
            "bfly5": 3,
            "bfly1": 3,
            "cmul1": 4,
            "bfly2": 4,
            "bfly9": 4,
            "bfly10": 5,
            "bfly3": 5,
            "out0": 5,
            "out4": 5,
            "bfly4": 6,
            "out1": 6,
            "out2": 6,
            "out5": 6,
            "out6": 6,
            "out7": 7,
            "out3": 7,
        }
        assert schedule.schedule_time == 7

    def test_radix_2_fft_8_points_one_output(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type(Butterfly.type_name(), 1)

        resources = {
            Butterfly.type_name(): 2,
            ConstantMultiplication.type_name(): 2,
            Input.type_name(): sys.maxsize,
            Output.type_name(): 1,
        }
        schedule = Schedule(sfg, scheduler=HybridScheduler(max_resources=resources))

        assert schedule.start_times == {
            "in0": 0,
            "in1": 0,
            "in2": 0,
            "in3": 0,
            "in4": 0,
            "in5": 0,
            "in6": 0,
            "in7": 0,
            "bfly6": 0,
            "bfly8": 0,
            "cmul2": 1,
            "cmul3": 1,
            "bfly11": 1,
            "bfly7": 1,
            "cmul0": 2,
            "bfly0": 2,
            "cmul4": 2,
            "bfly5": 3,
            "bfly1": 3,
            "cmul1": 4,
            "bfly2": 4,
            "bfly9": 4,
            "bfly10": 5,
            "bfly3": 5,
            "out0": 5,
            "bfly4": 6,
            "out1": 6,
            "out2": 12,
            "out3": 11,
            "out4": 10,
            "out5": 9,
            "out6": 8,
            "out7": 7,
        }
        assert schedule.schedule_time == 12

    def test_radix_2_fft_8_points_specified_IO_times_cyclic(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type(Butterfly.type_name(), 3)
        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)

        resources = {
            Butterfly.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
            Input.type_name(): sys.maxsize,
            Output.type_name(): sys.maxsize,
        }
        input_times = {
            "in0": 0,
            "in1": 1,
            "in2": 2,
            "in3": 3,
            "in4": 4,
            "in5": 5,
            "in6": 6,
            "in7": 7,
        }
        output_times = {
            "out0": -2,
            "out1": -1,
            "out2": 0,
            "out3": 1,
            "out4": 2,
            "out5": 3,
            "out6": 4,
            "out7": 5,
        }
        schedule = Schedule(
            sfg,
            scheduler=HybridScheduler(
                resources, input_times=input_times, output_delta_times=output_times
            ),
            cyclic=True,
        )

        assert schedule.start_times == {
            "in0": 0,
            "in1": 1,
            "in2": 2,
            "in3": 3,
            "in4": 4,
            "in5": 5,
            "in6": 6,
            "in7": 7,
            "bfly0": 4,
            "bfly8": 5,
            "bfly11": 6,
            "bfly6": 7,
            "cmul2": 8,
            "cmul0": 9,
            "bfly1": 9,
            "cmul3": 10,
            "bfly7": 10,
            "bfly2": 11,
            "bfly5": 12,
            "cmul4": 13,
            "bfly9": 13,
            "bfly10": 15,
            "cmul1": 15,
            "bfly3": 16,
            "bfly4": 17,
            "out0": 18,
            "out1": 19,
            "out2": 20,
            "out3": 1,
            "out4": 2,
            "out5": 3,
            "out6": 4,
            "out7": 5,
        }
        assert schedule.schedule_time == 20

    def test_radix_2_fft_8_points_specified_IO_times_non_cyclic(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type(Butterfly.type_name(), 3)
        sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)

        resources = {Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}
        input_times = {
            "in0": 0,
            "in1": 1,
            "in2": 2,
            "in3": 3,
            "in4": 4,
            "in5": 5,
            "in6": 6,
            "in7": 7,
        }
        output_times = {
            "out0": -2,
            "out1": -1,
            "out2": 0,
            "out3": 1,
            "out4": 2,
            "out5": 3,
            "out6": 4,
            "out7": 5,
        }
        schedule = Schedule(
            sfg,
            scheduler=HybridScheduler(
                resources, input_times=input_times, output_delta_times=output_times
            ),
            cyclic=False,
        )

        assert schedule.start_times == {
            "in0": 0,
            "in1": 1,
            "in2": 2,
            "in3": 3,
            "in4": 4,
            "in5": 5,
            "in6": 6,
            "in7": 7,
            "bfly0": 4,
            "bfly8": 5,
            "bfly11": 6,
            "bfly6": 7,
            "cmul2": 8,
            "cmul0": 9,
            "bfly1": 9,
            "cmul3": 10,
            "bfly7": 10,
            "bfly2": 11,
            "bfly5": 12,
            "cmul4": 13,
            "bfly9": 13,
            "bfly10": 15,
            "cmul1": 15,
            "bfly3": 16,
            "bfly4": 17,
            "out0": 18,
            "out1": 19,
            "out2": 20,
            "out3": 21,
            "out4": 22,
            "out5": 23,
            "out6": 24,
            "out7": 25,
        }
        assert schedule.schedule_time == 25

    def test_ldlt_inverse_2x2(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type(MADS.type_name(), 3)
        sfg.set_latency_of_type(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type(MADS.type_name(), 1)
        sfg.set_execution_time_of_type(Reciprocal.type_name(), 1)

        resources = {
            MADS.type_name(): 1,
            Reciprocal.type_name(): 1,
            Input.type_name(): sys.maxsize,
            Output.type_name(): sys.maxsize,
        }
        schedule = Schedule(
            sfg,
            scheduler=HybridScheduler(resources),
        )

        assert schedule.start_times == {
            "in0": 0,
            "in1": 0,
            "in2": 0,
            "rec0": 0,
            "dontcare1": 2,
            "mads0": 2,
            "mads3": 5,
            "rec1": 8,
            "dontcare0": 10,
            "mads2": 10,
            "mads1": 13,
            "out2": 10,
            "out1": 13,
            "out0": 16,
        }
        assert schedule.schedule_time == 16

    def test_ldlt_inverse_2x2_specified_IO_times_cyclic(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type(MADS.type_name(), 3)
        sfg.set_latency_of_type(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type(MADS.type_name(), 1)
        sfg.set_execution_time_of_type(Reciprocal.type_name(), 1)

        resources = {MADS.type_name(): 1, Reciprocal.type_name(): 1}
        input_times = {
            "in0": 0,
            "in1": 1,
            "in2": 2,
        }
        output_times = {
            "out0": 0,
            "out1": 1,
            "out2": 2,
        }
        schedule = Schedule(
            sfg,
            scheduler=HybridScheduler(
                resources, input_times=input_times, output_delta_times=output_times
            ),
            cyclic=True,
        )

        assert schedule.start_times == {
            "in0": 0,
            "in1": 1,
            "in2": 2,
            "rec0": 0,
            "dontcare1": 2,
            "mads0": 2,
            "mads3": 5,
            "rec1": 8,
            "dontcare0": 10,
            "mads2": 10,
            "mads1": 13,
            "out0": 16,
            "out1": 1,
            "out2": 2,
        }
        assert schedule.schedule_time == 16

    def test_max_invalid_resources(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type(MADS.type_name(), 3)
        sfg.set_latency_of_type(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type(MADS.type_name(), 1)
        sfg.set_execution_time_of_type(Reciprocal.type_name(), 1)

        resources = 2
        with pytest.raises(ValueError, match="max_resources must be a dictionary."):
            Schedule(sfg, scheduler=HybridScheduler(resources))

        resources = "test"
        with pytest.raises(ValueError, match="max_resources must be a dictionary."):
            Schedule(sfg, scheduler=HybridScheduler(resources))

        resources = []
        with pytest.raises(ValueError, match="max_resources must be a dictionary."):
            Schedule(sfg, scheduler=HybridScheduler(resources))

        resources = {1: 1}
        with pytest.raises(
            ValueError, match="max_resources key must be a valid type_name."
        ):
            Schedule(sfg, scheduler=HybridScheduler(resources))

        resources = {MADS.type_name(): "test"}
        with pytest.raises(ValueError, match="max_resources value must be an integer."):
            Schedule(sfg, scheduler=HybridScheduler(resources))

    def test_ldlt_inverse_3x3_read_and_write_constrained(self):
        sfg = ldlt_matrix_inverse(N=3)

        sfg.set_latency_of_type(MADS.type_name(), 3)
        sfg.set_latency_of_type(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type(MADS.type_name(), 1)
        sfg.set_execution_time_of_type(Reciprocal.type_name(), 1)

        resources = {MADS.type_name(): 1, Reciprocal.type_name(): 1}

        schedule = Schedule(
            sfg,
            scheduler=HybridScheduler(
                max_resources=resources,
                max_concurrent_reads=3,
                max_concurrent_writes=1,
            ),
        )

        direct, mem_vars = schedule.get_memory_variables().split_on_length()
        assert mem_vars.read_ports_bound() == 3
        assert mem_vars.write_ports_bound() == 1

    def test_read_constrained_too_tight(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type(MADS.type_name(), 3)
        sfg.set_latency_of_type(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type(MADS.type_name(), 1)
        sfg.set_execution_time_of_type(Reciprocal.type_name(), 1)

        resources = {MADS.type_name(): 1, Reciprocal.type_name(): 1}
        with pytest.raises(
            TimeoutError,
            match="Algorithm did not schedule any operation for 10 time steps, try relaxing constraints.",
        ):
            Schedule(
                sfg,
                scheduler=HybridScheduler(
                    max_resources=resources,
                    max_concurrent_reads=2,
                ),
            )
