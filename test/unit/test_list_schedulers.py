import sys

import numpy as np
import pytest
from scipy import signal

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import (
    MADS,
    Addition,
    Butterfly,
    ConstantMultiplication,
    Reciprocal,
)
from b_asic.list_schedulers import (
    EarliestDeadlineScheduler,
    HybridScheduler,
    LeastSlackTimeScheduler,
    MaxFanOutScheduler,
)
from b_asic.schedule import Schedule
from b_asic.scheduler import ListScheduler, RecursiveListScheduler
from b_asic.sfg_generators import (
    direct_form_1_iir,
    direct_form_2_iir,
    ldlt_matrix_inverse,
    radix_2_dif_fft,
)
from b_asic.signal_flow_graph import SFG
from b_asic.signal_generator import Constant, Impulse
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay, Input, Output


class TestEarliestDeadlineScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=EarliestDeadlineScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([0.1, 0.2, 0.3], [1, 2, 3])

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

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
            "cmul3": 0,
            "cmul4": 1,
            "cmul0": 2,
            "add1": 3,
            "cmul1": 3,
            "cmul2": 4,
            "add0": 6,
            "add3": 7,
            "add2": 10,
            "out0": 13,
        }
        assert schedule.schedule_time == 13
        _validate_recreated_sfg_filter(sfg, schedule)

    def test_direct_form_2_iir_1_add_1_mul(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 2)
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type_name(
            ConstantMultiplication.type_name(), 1
        )
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type_name(
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
            "cmul3": 0,
            "cmul4": 1,
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
        _validate_recreated_sfg_filter(sfg_direct_form_iir_lp_filter, schedule)

    def test_direct_form_2_iir_2_add_3_mul(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 2)
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type_name(
            ConstantMultiplication.type_name(), 1
        )
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type_name(
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
        _validate_recreated_sfg_filter(sfg_direct_form_iir_lp_filter, schedule)

    def test_radix_2_fft_8_points(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)

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
        _validate_recreated_sfg_fft(schedule, 8)


class TestLeastSlackTimeScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=LeastSlackTimeScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([0.1, 0.2, 0.3], [1, 2, 3])

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

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
            "cmul3": 0,
            "cmul4": 1,
            "cmul0": 2,
            "add1": 3,
            "cmul1": 3,
            "cmul2": 4,
            "add0": 6,
            "add3": 7,
            "add2": 10,
            "out0": 13,
        }
        assert schedule.schedule_time == 13
        _validate_recreated_sfg_filter(sfg, schedule)

    def test_direct_form_2_iir_1_add_1_mul(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 2)
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type_name(
            ConstantMultiplication.type_name(), 1
        )
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type_name(
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
            "cmul3": 0,
            "cmul4": 1,
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
        _validate_recreated_sfg_filter(sfg_direct_form_iir_lp_filter, schedule)

    def test_direct_form_2_iir_2_add_3_mul(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 2)
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type_name(
            ConstantMultiplication.type_name(), 1
        )
        sfg_direct_form_iir_lp_filter.set_execution_time_of_type_name(
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
        _validate_recreated_sfg_filter(sfg_direct_form_iir_lp_filter, schedule)

    def test_radix_2_fft_8_points(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)

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
        _validate_recreated_sfg_fft(schedule, 8)


class TestMaxFanOutScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=MaxFanOutScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([0.1, 0.2, 0.3], [1, 2, 3])

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

        resources = {Addition.type_name(): 1, ConstantMultiplication.type_name(): 1}
        schedule = Schedule(sfg, scheduler=MaxFanOutScheduler(max_resources=resources))

        assert schedule.start_times == {
            "in0": 0,
            "cmul0": 0,
            "cmul1": 1,
            "cmul2": 2,
            "cmul3": 3,
            "cmul4": 4,
            "add3": 4,
            "add1": 6,
            "add0": 9,
            "add2": 12,
            "out0": 15,
        }
        assert schedule.schedule_time == 15
        _validate_recreated_sfg_filter(sfg, schedule)

    def test_ldlt_inverse_3x3(self):
        sfg = ldlt_matrix_inverse(N=3)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

        resources = {MADS.type_name(): 1, Reciprocal.type_name(): 1}
        schedule = Schedule(sfg, scheduler=MaxFanOutScheduler(resources))

        assert schedule.start_times == {
            "in1": 0,
            "in2": 1,
            "in0": 2,
            "rec0": 2,
            "in4": 3,
            "in5": 4,
            "mads1": 4,
            "dontcare4": 4,
            "dontcare5": 5,
            "in3": 5,
            "mads0": 5,
            "mads13": 7,
            "mads12": 8,
            "mads14": 9,
            "rec1": 12,
            "mads8": 14,
            "dontcare2": 14,
            "mads10": 17,
            "rec2": 20,
            "mads9": 22,
            "out5": 22,
            "dontcare0": 22,
            "dontcare1": 23,
            "mads11": 23,
            "mads7": 25,
            "out4": 25,
            "mads3": 26,
            "mads6": 27,
            "dontcare3": 27,
            "out3": 28,
            "mads2": 29,
            "out2": 29,
            "mads5": 30,
            "mads4": 33,
            "out1": 33,
            "out0": 36,
        }
        assert schedule.schedule_time == 36
        _validate_recreated_sfg_ldlt_matrix_inverse(schedule, 3)


class TestHybridScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(sfg_empty, scheduler=HybridScheduler())

    def test_direct_form_1_iir(self):
        sfg = direct_form_1_iir([0.1, 0.2, 0.3], [1, 2, 3])

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

        resources = {Addition.type_name(): 1, ConstantMultiplication.type_name(): 1}
        schedule = Schedule(sfg, scheduler=HybridScheduler(max_resources=resources))

        assert schedule.start_times == {
            "in0": 0,
            "cmul3": 0,
            "cmul4": 1,
            "cmul0": 2,
            "add1": 3,
            "cmul1": 3,
            "cmul2": 4,
            "add0": 6,
            "add3": 7,
            "add2": 10,
            "out0": 13,
        }
        assert schedule.schedule_time == 13
        _validate_recreated_sfg_filter(sfg, schedule)

    def test_radix_2_fft_8_points(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)

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
        _validate_recreated_sfg_fft(schedule, 8)

    def test_radix_2_fft_8_points_one_output(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)

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
            "out2": 6,
            "out3": 7,
            "out7": 8,
            "out6": 9,
            "out4": 10,
            "out1": 11,
            "out5": 12,
        }
        assert schedule.schedule_time == 12
        _validate_recreated_sfg_fft(schedule, 8)

    # This schedule that this test is checking against is faulty and will yield a non-working
    # fft implementation, however, it is kept commented out for reference
    def test_radix_2_fft_8_points_specified_IO_times_cyclic(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type_name(Butterfly.type_name(), 3)
        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

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
            "out0": 0,
            "out1": 1,
            "out2": 2,
            "out3": 3,
            "out4": 4,
            "out5": 5,
            "out6": 6,
            "out7": 7,
        }
        schedule = Schedule(
            sfg,
            scheduler=HybridScheduler(
                resources, input_times=input_times, output_delta_times=output_times
            ),
            schedule_time=20,
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
            "bfly3": 15,
            "cmul1": 15,
            "bfly10": 16,
            "bfly4": 17,
            "out0": 17,
            "out1": 18,
            "out2": 19,
            "out3": 20,
            "out4": 1,
            "out5": 2,
            "out6": 3,
            "out7": 4,
        }
        assert schedule.schedule_time == 20

        # impulse input -> constant output
        sim = Simulation(schedule.sfg, [Impulse()] + [0 for i in range(7)])
        sim.run_for(2)
        assert np.allclose(sim.results["0"], [1, 0])
        assert np.allclose(sim.results["1"], [1, 0])
        assert np.allclose(sim.results["2"], [1, 0])
        assert np.allclose(sim.results["3"], [1, 0])
        assert np.allclose(sim.results["4"], [0, 1])
        assert np.allclose(sim.results["5"], [0, 1])
        assert np.allclose(sim.results["6"], [0, 1])
        assert np.allclose(sim.results["7"], [0, 1])

        # constant input -> impulse (with weight=points) output
        sim = Simulation(schedule.sfg, [Impulse() for i in range(8)])
        sim.run_for(2)
        assert np.allclose(sim.results["0"], [8, 0])
        assert np.allclose(sim.results["1"], [0, 0])
        assert np.allclose(sim.results["2"], [0, 0])
        assert np.allclose(sim.results["3"], [0, 0])
        assert np.allclose(sim.results["4"], [0, 0])
        assert np.allclose(sim.results["5"], [0, 0])
        assert np.allclose(sim.results["6"], [0, 0])
        assert np.allclose(sim.results["7"], [0, 0])

    def test_radix_2_fft_8_points_specified_IO_times_non_cyclic(self):
        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type_name(Butterfly.type_name(), 3)
        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

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
            "out0": 0,
            "out1": 1,
            "out2": 2,
            "out3": 3,
            "out4": 4,
            "out5": 5,
            "out6": 6,
            "out7": 7,
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
            "bfly3": 15,
            "cmul1": 15,
            "bfly10": 16,
            "bfly4": 17,
            "out0": 17,
            "out1": 18,
            "out2": 19,
            "out3": 20,
            "out4": 21,
            "out5": 22,
            "out6": 23,
            "out7": 24,
        }
        assert schedule.schedule_time == 24
        _validate_recreated_sfg_fft(schedule, 8)

    def test_ldlt_inverse_2x2(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

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
        _validate_recreated_sfg_ldlt_matrix_inverse(schedule, 2)

    def test_ldlt_inverse_2x2_specified_IO_times_cyclic(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

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
            schedule_time=16,
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

        # validate regenerated sfg with random 2x2 real s.p.d. matrix
        A = np.random.default_rng().random((2, 2))
        A = np.dot(A, A.T)
        A_inv = np.linalg.inv(A)
        input_signals = []
        for i in range(2):
            for j in range(i, 2):
                input_signals.append(Constant(A[i, j]))

        sim = Simulation(schedule.sfg, input_signals)
        sim.run_for(2)
        assert np.allclose(sim.results["0"], [A_inv[0, 0], A_inv[0, 0]])
        assert np.allclose(sim.results["1"], [0, A_inv[0, 1]])
        assert np.allclose(sim.results["2"], [0, A_inv[1, 1]])

    def test_invalid_max_resources(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

        resources = 2
        with pytest.raises(
            ValueError, match="Provided max_resources must be a dictionary."
        ):
            Schedule(sfg, scheduler=HybridScheduler(resources))

        resources = "test"
        with pytest.raises(
            ValueError, match="Provided max_resources must be a dictionary."
        ):
            Schedule(sfg, scheduler=HybridScheduler(resources))

        resources = []
        with pytest.raises(
            ValueError, match="Provided max_resources must be a dictionary."
        ):
            Schedule(sfg, scheduler=HybridScheduler(resources))

        resources = {1: 1}
        with pytest.raises(
            ValueError, match="Provided max_resources keys must be strings."
        ):
            Schedule(sfg, scheduler=HybridScheduler(resources))

        resources = {MADS.type_name(): "test"}
        with pytest.raises(
            ValueError, match="Provided max_resources values must be integers."
        ):
            Schedule(sfg, scheduler=HybridScheduler(resources))

    def test_invalid_max_concurrent_writes(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

        max_concurrent_writes = "5"
        with pytest.raises(
            ValueError, match="Provided max_concurrent_writes must be an integer."
        ):
            Schedule(
                sfg,
                scheduler=HybridScheduler(max_concurrent_writes=max_concurrent_writes),
            )

        max_concurrent_writes = 0
        with pytest.raises(
            ValueError, match="Provided max_concurrent_writes must be larger than 0."
        ):
            Schedule(
                sfg,
                scheduler=HybridScheduler(max_concurrent_writes=max_concurrent_writes),
            )

        max_concurrent_writes = -1
        with pytest.raises(
            ValueError, match="Provided max_concurrent_writes must be larger than 0."
        ):
            Schedule(
                sfg,
                scheduler=HybridScheduler(max_concurrent_writes=max_concurrent_writes),
            )

    def test_invalid_max_concurrent_reads(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

        max_concurrent_reads = "5"
        with pytest.raises(
            ValueError, match="Provided max_concurrent_reads must be an integer."
        ):
            Schedule(
                sfg,
                scheduler=HybridScheduler(max_concurrent_reads=max_concurrent_reads),
            )

        max_concurrent_reads = 0
        with pytest.raises(
            ValueError, match="Provided max_concurrent_reads must be larger than 0."
        ):
            Schedule(
                sfg,
                scheduler=HybridScheduler(max_concurrent_reads=max_concurrent_reads),
            )

        max_concurrent_reads = -1
        with pytest.raises(
            ValueError, match="Provided max_concurrent_reads must be larger than 0."
        ):
            Schedule(
                sfg,
                scheduler=HybridScheduler(max_concurrent_reads=max_concurrent_reads),
            )

    def test_invalid_input_times(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

        input_times = 5
        with pytest.raises(
            ValueError, match="Provided input_times must be a dictionary."
        ):
            Schedule(sfg, scheduler=HybridScheduler(input_times=input_times))

        input_times = "test1"
        with pytest.raises(
            ValueError, match="Provided input_times must be a dictionary."
        ):
            Schedule(sfg, scheduler=HybridScheduler(input_times=input_times))

        input_times = []
        with pytest.raises(
            ValueError, match="Provided input_times must be a dictionary."
        ):
            Schedule(sfg, scheduler=HybridScheduler(input_times=input_times))

        input_times = {3: 3}
        with pytest.raises(
            ValueError, match="Provided input_times keys must be strings."
        ):
            Schedule(sfg, scheduler=HybridScheduler(input_times=input_times))

        input_times = {"in0": "foo"}
        with pytest.raises(
            ValueError, match="Provided input_times values must be integers."
        ):
            Schedule(sfg, scheduler=HybridScheduler(input_times=input_times))

        input_times = {"in0": -1}
        with pytest.raises(
            ValueError, match="Provided input_times values must be non-negative."
        ):
            Schedule(sfg, scheduler=HybridScheduler(input_times=input_times))

    def test_invalid_output_delta_times(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

        output_delta_times = 10
        with pytest.raises(
            ValueError, match="Provided output_delta_times must be a dictionary."
        ):
            Schedule(
                sfg, scheduler=HybridScheduler(output_delta_times=output_delta_times)
            )

        output_delta_times = "test2"
        with pytest.raises(
            ValueError, match="Provided output_delta_times must be a dictionary."
        ):
            Schedule(
                sfg, scheduler=HybridScheduler(output_delta_times=output_delta_times)
            )

        output_delta_times = []
        with pytest.raises(
            ValueError, match="Provided output_delta_times must be a dictionary."
        ):
            Schedule(
                sfg, scheduler=HybridScheduler(output_delta_times=output_delta_times)
            )

        output_delta_times = {4: 4}
        with pytest.raises(
            ValueError, match="Provided output_delta_times keys must be strings."
        ):
            Schedule(
                sfg, scheduler=HybridScheduler(output_delta_times=output_delta_times)
            )

        output_delta_times = {"out0": "foo"}
        with pytest.raises(
            ValueError, match="Provided output_delta_times values must be integers."
        ):
            Schedule(
                sfg, scheduler=HybridScheduler(output_delta_times=output_delta_times)
            )

        output_delta_times = {"out0": -1}
        with pytest.raises(
            ValueError, match="Provided output_delta_times values must be non-negative."
        ):
            Schedule(
                sfg, scheduler=HybridScheduler(output_delta_times=output_delta_times)
            )

    def test_resource_not_in_sfg(self):
        sfg = ldlt_matrix_inverse(N=3)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

        resources = {
            MADS.type_name(): 1,
            Reciprocal.type_name(): 1,
            Addition.type_name(): 2,
        }
        with pytest.raises(
            ValueError,
            match="Provided max resource of type add cannot be found in the provided SFG.",
        ):
            Schedule(sfg, scheduler=HybridScheduler(resources))

    def test_input_not_in_sfg(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

        input_times = {"in100": 4}
        with pytest.raises(
            ValueError,
            match="Provided input time with GraphID in100 cannot be found in the provided SFG.",
        ):
            Schedule(sfg, scheduler=HybridScheduler(input_times=input_times))

    def test_output_not_in_sfg(self):
        sfg = ldlt_matrix_inverse(N=2)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

        output_delta_times = {"out90": 2}
        with pytest.raises(
            ValueError,
            match="Provided output delta time with GraphID out90 cannot be found in the provided SFG.",
        ):
            Schedule(
                sfg, scheduler=HybridScheduler(output_delta_times=output_delta_times)
            )

    def test_ldlt_inverse_3x3_read_and_write_constrained(self):
        sfg = ldlt_matrix_inverse(N=3)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

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
        _validate_recreated_sfg_ldlt_matrix_inverse(schedule, 3)

    def test_32_point_fft_custom_io_times(self):
        POINTS = 32
        sfg = radix_2_dif_fft(POINTS)

        sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 3)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

        resources = {Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}
        input_times = {f"in{i}": i for i in range(POINTS)}
        output_delta_times = {f"out{i}": i for i in range(POINTS)}
        schedule = Schedule(
            sfg,
            scheduler=HybridScheduler(
                resources,
                input_times=input_times,
                output_delta_times=output_delta_times,
            ),
        )

        for i in range(POINTS):
            assert schedule.start_times[f"in{i}"] == i
            assert schedule.start_times[f"out{i}"] == 81 + i

    # too slow for pipeline timeout
    # def test_64_point_fft_custom_io_times(self):
    #     POINTS = 64
    #     sfg = radix_2_dif_fft(POINTS)

    #     sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
    #     sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 3)
    #     sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)
    #     sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

    #     resources = {Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}
    #     input_times = {f"in{i}": i for i in range(POINTS)}
    #     output_delta_times = {f"out{i}": i for i in range(POINTS)}
    #     schedule = Schedule(
    #         sfg,
    #         scheduler=HybridScheduler(
    #             resources,
    #             input_times=input_times,
    #             output_delta_times=output_delta_times,
    #         ),
    #     )

    #     for i in range(POINTS):
    #         assert schedule.start_times[f"in{i}"] == i
    #         assert (
    #             schedule.start_times[f"out{i}"]
    #             == schedule.get_max_non_io_end_time() - 1 + i
    #         )

    def test_32_point_fft_custom_io_times_cyclic(self):
        POINTS = 32
        sfg = radix_2_dif_fft(POINTS)

        sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 3)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

        resources = {Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}
        input_times = {f"in{i}": i for i in range(POINTS)}
        output_delta_times = {f"out{i}": i for i in range(POINTS)}
        schedule = Schedule(
            sfg,
            scheduler=HybridScheduler(
                resources,
                input_times=input_times,
                output_delta_times=output_delta_times,
            ),
            schedule_time=96,
            cyclic=True,
        )

        for i in range(POINTS):
            assert schedule.start_times[f"in{i}"] == i
            expected_value = ((81 + i - 1) % 96) + 1
            assert schedule.start_times[f"out{i}"] == expected_value

    def test_cyclic_scheduling(self):
        sfg = radix_2_dif_fft(points=4)

        sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 3)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

        resources = {
            Butterfly.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
        }
        schedule_1 = Schedule(sfg, scheduler=HybridScheduler(resources))
        schedule_2 = Schedule(
            sfg, scheduler=HybridScheduler(resources), schedule_time=6, cyclic=True
        )
        schedule_3 = Schedule(
            sfg, scheduler=HybridScheduler(resources), schedule_time=5, cyclic=True
        )
        schedule_4 = Schedule(
            sfg, scheduler=HybridScheduler(resources), schedule_time=4, cyclic=True
        )

        assert schedule_1.start_times == {
            "in1": 0,
            "in3": 1,
            "bfly3": 1,
            "cmul0": 2,
            "in0": 2,
            "in2": 3,
            "bfly0": 3,
            "bfly1": 4,
            "bfly2": 5,
            "out0": 5,
            "out1": 6,
            "out3": 7,
            "out2": 8,
        }
        assert schedule_1.laps == {
            "s4": 0,
            "s6": 0,
            "s5": 0,
            "s7": 0,
            "s8": 0,
            "s12": 0,
            "s10": 0,
            "s9": 0,
            "s0": 0,
            "s2": 0,
            "s11": 0,
            "s1": 0,
            "s3": 0,
        }
        assert schedule_1.schedule_time == 8

        assert schedule_2.start_times == {
            "in1": 0,
            "in3": 1,
            "bfly3": 1,
            "cmul0": 2,
            "in0": 2,
            "in2": 3,
            "bfly0": 3,
            "bfly1": 4,
            "bfly2": 5,
            "out0": 5,
            "out1": 6,
            "out3": 1,
            "out2": 2,
        }
        assert schedule_2.laps == {
            "s4": 0,
            "s6": 1,
            "s5": 0,
            "s7": 1,
            "s8": 0,
            "s12": 0,
            "s10": 0,
            "s9": 0,
            "s0": 0,
            "s2": 0,
            "s11": 0,
            "s1": 0,
            "s3": 0,
        }
        assert schedule_2.schedule_time == 6

        assert schedule_3.start_times == {
            "in1": 0,
            "in3": 1,
            "bfly3": 1,
            "cmul0": 2,
            "in0": 2,
            "in2": 3,
            "bfly0": 3,
            "bfly1": 4,
            "bfly2": 0,
            "out0": 5,
            "out1": 1,
            "out3": 2,
            "out2": 3,
        }
        assert schedule_3.laps == {
            "s4": 0,
            "s6": 1,
            "s5": 0,
            "s7": 0,
            "s8": 0,
            "s12": 0,
            "s10": 1,
            "s9": 1,
            "s0": 0,
            "s2": 0,
            "s11": 0,
            "s1": 0,
            "s3": 0,
        }
        assert schedule_3.schedule_time == 5

        assert schedule_4.start_times == {
            "in1": 0,
            "in3": 1,
            "bfly3": 1,
            "cmul0": 2,
            "in0": 2,
            "in2": 3,
            "bfly0": 3,
            "bfly1": 0,
            "out0": 1,
            "bfly2": 2,
            "out2": 2,
            "out1": 3,
            "out3": 4,
        }
        assert schedule_4.laps == {
            "s4": 0,
            "s6": 0,
            "s5": 0,
            "s7": 0,
            "s8": 1,
            "s12": 1,
            "s10": 0,
            "s9": 1,
            "s0": 0,
            "s2": 0,
            "s11": 0,
            "s1": 0,
            "s3": 0,
        }
        assert schedule_4.schedule_time == 4

    def test_resources_not_enough(self):
        sfg = ldlt_matrix_inverse(N=3)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

        resources = {MADS.type_name(): 1, Reciprocal.type_name(): 1}
        with pytest.raises(
            ValueError,
            match="Amount of resource: mads is not enough to realize schedule for scheduling time: 5.",
        ):
            Schedule(
                sfg,
                scheduler=HybridScheduler(
                    max_resources=resources,
                ),
                schedule_time=5,
            )

        sfg = radix_2_dif_fft(points=8)

        sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 3)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

        resources = {
            Butterfly.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
        }
        with pytest.raises(
            ValueError,
            match="Amount of resource: bfly is not enough to realize schedule for scheduling time: 6.",
        ):
            Schedule(
                sfg,
                scheduler=HybridScheduler(
                    resources, max_concurrent_reads=2, max_concurrent_writes=2
                ),
                schedule_time=6,
                cyclic=True,
            )

    def test_scheduling_time_not_enough(self):
        sfg = ldlt_matrix_inverse(N=3)

        sfg.set_latency_of_type_name(MADS.type_name(), 3)
        sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
        sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
        sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

        resources = {MADS.type_name(): 10, Reciprocal.type_name(): 10}
        with pytest.raises(
            ValueError,
            match="Provided scheduling time 5 cannot be reached, try to enable the cyclic property or increase the time to at least 30.",
        ):
            Schedule(
                sfg,
                scheduler=HybridScheduler(
                    max_resources=resources,
                ),
                schedule_time=5,
            )

    def test_cyclic_scheduling_write_and_read_constrained(self):
        sfg = radix_2_dif_fft(points=4)

        sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 3)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

        resources = {
            Butterfly.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
        }
        schedule = Schedule(
            sfg,
            scheduler=HybridScheduler(
                resources, max_concurrent_reads=2, max_concurrent_writes=3
            ),
            schedule_time=6,
            cyclic=True,
        )

        assert schedule.start_times == {
            "in1": 0,
            "in3": 1,
            "bfly3": 1,
            "cmul0": 2,
            "in0": 2,
            "in2": 3,
            "bfly0": 3,
            "bfly1": 4,
            "bfly2": 5,
            "out0": 5,
            "out1": 6,
            "out3": 1,
            "out2": 2,
        }
        assert schedule.laps == {
            "s4": 0,
            "s6": 1,
            "s5": 0,
            "s7": 1,
            "s8": 0,
            "s12": 0,
            "s10": 0,
            "s9": 0,
            "s0": 0,
            "s2": 0,
            "s11": 0,
            "s1": 0,
            "s3": 0,
        }
        assert schedule.schedule_time == 6

        _validate_recreated_sfg_fft(schedule, points=4, delays=[0, 0, 1, 1])

        _, mem_vars = schedule.get_memory_variables().split_on_length()
        assert mem_vars.read_ports_bound() <= 2
        assert mem_vars.write_ports_bound() <= 3

    def test_cyclic_scheduling_several_inputs_and_outputs(self):
        sfg = radix_2_dif_fft(points=4)

        sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 3)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

        resources = {
            Butterfly.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
            Input.type_name(): 2,
            Output.type_name(): 2,
        }
        schedule = Schedule(
            sfg, scheduler=HybridScheduler(resources), schedule_time=4, cyclic=True
        )

        assert schedule.schedule_time == 4
        _validate_recreated_sfg_fft(schedule, points=4, delays=[0, 1, 0, 1])

    def test_invalid_output_delta_time(self):
        sfg = radix_2_dif_fft(points=4)

        sfg.set_latency_of_type_name(Butterfly.type_name(), 1)
        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 3)
        sfg.set_execution_time_of_type_name(Butterfly.type_name(), 1)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

        resources = {
            Butterfly.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
            Input.type_name(): 2,
            Output.type_name(): 2,
        }
        output_delta_times = {"out0": 0, "out1": 1, "out2": 2, "out3": 3}

        with pytest.raises(
            ValueError,
            match="Cannot place output out2 at time 6 for scheduling time 5. Try to relax the scheduling time, change the output delta times or enable cyclic.",
        ):
            Schedule(
                sfg,
                scheduler=HybridScheduler(
                    resources, output_delta_times=output_delta_times
                ),
                schedule_time=5,
            )

    def test_iteration_period_bound(self):
        sfg = direct_form_1_iir([0.1, 0.2, 0.3], [1, 2, 3])

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

        resources = {
            Addition.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
        }

        with pytest.raises(
            ValueError,
            match="Provided scheduling time 5 must be larger or equal to the iteration period bound: 8.",
        ):
            Schedule(
                sfg,
                scheduler=EarliestDeadlineScheduler(max_resources=resources),
                schedule_time=5,
                cyclic=True,
            )

    def test_latency_offsets(self):
        sfg = ldlt_matrix_inverse(
            N=3,
            mads_properties={
                "latency_offsets": {"in0": 3, "in1": 0, "in2": 0, "out0": 4},
                "execution_time": 1,
            },
            reciprocal_properties={"latency": 10, "execution_time": 1},
        )
        schedule = Schedule(sfg, scheduler=HybridScheduler())

        assert schedule.start_times == {
            "dontcare0": 49,
            "dontcare1": 50,
            "dontcare2": 31,
            "dontcare3": 55,
            "dontcare4": 14,
            "dontcare5": 13,
            "in0": 0,
            "in1": 1,
            "in2": 3,
            "in3": 2,
            "in4": 4,
            "in5": 5,
            "mads0": 10,
            "mads1": 11,
            "mads10": 32,
            "mads11": 47,
            "mads12": 16,
            "mads13": 15,
            "mads14": 14,
            "mads2": 55,
            "mads3": 51,
            "mads4": 58,
            "mads5": 54,
            "mads6": 52,
            "mads7": 50,
            "mads8": 28,
            "mads9": 46,
            "out0": 62,
            "out1": 58,
            "out2": 55,
            "out3": 54,
            "out4": 50,
            "out5": 46,
            "rec0": 0,
            "rec1": 18,
            "rec2": 36,
        }

        assert all(val == 0 for val in schedule.laps.values())
        _validate_recreated_sfg_ldlt_matrix_inverse(schedule, 3)

    def test_latency_offsets_cyclic(self):
        sfg = ldlt_matrix_inverse(
            N=3,
            mads_properties={
                "latency_offsets": {"in0": 3, "in1": 0, "in2": 0, "out0": 4},
                "execution_time": 1,
            },
            reciprocal_properties={"latency": 10, "execution_time": 1},
        )
        schedule = Schedule(
            sfg,
            scheduler=HybridScheduler(),
            schedule_time=49,
            cyclic=True,
        )

        assert schedule.schedule_time == 49
        _validate_recreated_sfg_ldlt_matrix_inverse(
            schedule, N=3, delays=[1, 1, 1, 1, 1, 0]
        )

    def test_latency_offsets_cyclic_min_schedule_time(self):
        sfg = ldlt_matrix_inverse(
            N=3,
            mads_properties={
                "latency_offsets": {"in0": 3, "in1": 0, "in2": 0, "out0": 4},
                "execution_time": 1,
            },
            reciprocal_properties={"latency": 10, "execution_time": 1},
        )
        schedule = Schedule(
            sfg,
            scheduler=HybridScheduler(),
            schedule_time=15,
            cyclic=True,
        )

        assert schedule.schedule_time == 15
        _validate_recreated_sfg_ldlt_matrix_inverse(
            schedule, N=3, delays=[4, 4, 3, 3, 3, 3]
        )


class TestListScheduler:
    def test_latencies_and_execution_times_not_set(self):
        N = 3
        Wc = 0.2
        b, a = signal.butter(N, Wc, btype="lowpass", output="ba")
        sfg = direct_form_1_iir(b, a)

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)

        resources = {
            Addition.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
            Input.type_name(): 1,
            Output.type_name(): 1,
        }

        with pytest.raises(
            ValueError,
            match="Input port 0 of operation add4 has no latency-offset.",
        ):
            Schedule(
                sfg,
                scheduler=ListScheduler(
                    sort_order=((1, True), (3, False), (4, False)),
                    max_resources=resources,
                ),
            )

        sfg.set_latency_offsets_of_type_name(Addition.type_name(), {"in0": 0, "in1": 0})
        with pytest.raises(
            ValueError,
            match="Output port 0 of operation add4 has no latency-offset.",
        ):
            Schedule(
                sfg,
                scheduler=ListScheduler(
                    sort_order=((1, True), (3, False), (4, False)),
                    max_resources=resources,
                ),
            )

        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), None)
        sfg.set_execution_time_of_type_name(Addition.type_name(), None)

        with pytest.raises(
            ValueError,
            match="All operations in the SFG must have a specified execution time. Missing operation: cmul0.",
        ):
            Schedule(
                sfg,
                scheduler=ListScheduler(
                    sort_order=((1, True), (3, False), (4, False)),
                    max_resources=resources,
                ),
            )

        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

        with pytest.raises(
            ValueError,
            match="All operations in the SFG must have a specified execution time. Missing operation: add0.",
        ):
            Schedule(
                sfg,
                scheduler=ListScheduler(
                    sort_order=((1, True), (3, False), (4, False)),
                    max_resources=resources,
                ),
            )

        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

        Schedule(
            sfg,
            scheduler=ListScheduler(
                sort_order=((1, True), (3, False), (4, False)), max_resources=resources
            ),
        )

    def test_execution_time_not_one_port_constrained(self):
        sfg = radix_2_dif_fft(points=16)

        sfg.set_latency_of_type(Butterfly, 3)
        sfg.set_latency_of_type(ConstantMultiplication, 10)
        sfg.set_execution_time_of_type(Butterfly, 2)
        sfg.set_execution_time_of_type(ConstantMultiplication, 10)

        resources = {Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}

        schedule = Schedule(
            sfg,
            scheduler=ListScheduler(
                sort_order=((2, True), (3, True)),
                max_resources=resources,
                max_concurrent_reads=2,
                max_concurrent_writes=2,
            ),
        )

        direct, mem_vars = schedule.get_memory_variables().split_on_length()
        assert mem_vars.read_ports_bound() == 2
        assert mem_vars.write_ports_bound() == 2
        _validate_recreated_sfg_fft(schedule, points=16)

        schedule = Schedule(
            sfg,
            scheduler=ListScheduler(
                sort_order=((1, True), (3, False)),
                max_resources=resources,
                max_concurrent_reads=2,
                max_concurrent_writes=2,
            ),
        )

        direct, mem_vars = schedule.get_memory_variables().split_on_length()
        assert mem_vars.read_ports_bound() == 2
        assert mem_vars.write_ports_bound() == 2
        _validate_recreated_sfg_fft(schedule, points=16)

        operations = schedule.get_operations()
        bfs = operations.get_by_type_name(Butterfly.type_name())
        const_muls = operations.get_by_type_name(ConstantMultiplication.type_name())
        inputs = operations.get_by_type_name(Input.type_name())
        outputs = operations.get_by_type_name(Output.type_name())

        bf_pe = ProcessingElement(bfs, entity_name="bf1")
        mul_pe = ProcessingElement(const_muls, entity_name="mul1")

        pe_in = ProcessingElement(inputs, entity_name="input")
        pe_out = ProcessingElement(outputs, entity_name="output")

        processing_elements = [bf_pe, mul_pe, pe_in, pe_out]

        mem_vars = schedule.get_memory_variables()
        direct, mem_vars = mem_vars.split_on_length()

        mem_vars_set = mem_vars.split_on_ports(
            read_ports=1,
            write_ports=1,
            total_ports=2,
            strategy="ilp_graph_color",
            processing_elements=processing_elements,
            max_colors=2,
        )

        memories = []
        for i, mem in enumerate(mem_vars_set):
            memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
            memories.append(memory)
            memory.assign("graph_color")

        arch = Architecture(
            processing_elements,
            memories,
            direct_interconnects=direct,
        )
        assert len(arch.processing_elements) == 4
        assert len(arch.memories) == 2

    def test_execution_time_not_one_and_latency_offsets_port_constrained(self):
        sfg = radix_2_dif_fft(points=16)

        sfg.set_latency_offsets_of_type(
            Butterfly, {"in0": 0, "in1": 1, "out0": 2, "out1": 3}
        )
        sfg.set_latency_of_type(ConstantMultiplication, 7)
        sfg.set_execution_time_of_type(Butterfly, 2)
        sfg.set_execution_time_of_type(ConstantMultiplication, 5)

        resources = {Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}

        schedule = Schedule(
            sfg,
            scheduler=ListScheduler(
                sort_order=((2, True), (3, True)),
                max_resources=resources,
                max_concurrent_reads=2,
                max_concurrent_writes=2,
            ),
        )

        direct, mem_vars = schedule.get_memory_variables().split_on_length()
        assert mem_vars.read_ports_bound() == 2
        assert mem_vars.write_ports_bound() == 2
        _validate_recreated_sfg_fft(schedule, points=16)

        schedule = Schedule(
            sfg,
            scheduler=ListScheduler(
                sort_order=((1, True), (3, False)),
                max_resources=resources,
                max_concurrent_reads=2,
                max_concurrent_writes=2,
            ),
        )

        direct, mem_vars = schedule.get_memory_variables().split_on_length()
        assert mem_vars.read_ports_bound() == 2
        assert mem_vars.write_ports_bound() == 2
        _validate_recreated_sfg_fft(schedule, points=16)

        operations = schedule.get_operations()
        bfs = operations.get_by_type_name(Butterfly.type_name())
        const_muls = operations.get_by_type_name(ConstantMultiplication.type_name())
        inputs = operations.get_by_type_name(Input.type_name())
        outputs = operations.get_by_type_name(Output.type_name())

        bf_pe = ProcessingElement(bfs, entity_name="bf1")
        mul_pe = ProcessingElement(const_muls, entity_name="mul1")

        pe_in = ProcessingElement(inputs, entity_name="input")
        pe_out = ProcessingElement(outputs, entity_name="output")

        processing_elements = [bf_pe, mul_pe, pe_in, pe_out]

        mem_vars = schedule.get_memory_variables()
        direct, mem_vars = mem_vars.split_on_length()

        mem_vars_set = mem_vars.split_on_ports(
            read_ports=1,
            write_ports=1,
            total_ports=2,
            strategy="ilp_graph_color",
            processing_elements=processing_elements,
            max_colors=2,
        )

        memories = []
        for i, mem in enumerate(mem_vars_set):
            memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
            memories.append(memory)
            memory.assign("graph_color")

        arch = Architecture(
            processing_elements,
            memories,
            direct_interconnects=direct,
        )
        assert len(arch.processing_elements) == 4
        assert len(arch.memories) == 2


class TestRecursiveListScheduler:
    def test_empty_sfg(self, sfg_empty):
        with pytest.raises(
            ValueError, match="Empty signal flow graph cannot be scheduled."
        ):
            Schedule(
                sfg_empty,
                scheduler=RecursiveListScheduler(
                    sort_order=((1, True), (3, False), (4, False))
                ),
            )

    def test_direct_form_1_iir(self):
        N = 3
        Wc = 0.2
        b, a = signal.butter(N, Wc, btype="lowpass", output="ba")
        sfg = direct_form_1_iir(b, a)

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

        resources = {
            Addition.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
            Input.type_name(): 1,
            Output.type_name(): 1,
        }
        schedule = Schedule(
            sfg,
            scheduler=RecursiveListScheduler(
                sort_order=((1, True), (3, False), (4, False)), max_resources=resources
            ),
        )
        _validate_recreated_sfg_filter(sfg, schedule)
        assert schedule.schedule_time == sfg.iteration_period_bound()
        for op_id in schedule.start_times:
            assert schedule.backward_slack(op_id) >= 0
            assert schedule.forward_slack(op_id) >= 0

    def test_direct_form_2_iir(self):
        N = 3
        Wc = 0.2
        b, a = signal.butter(N, Wc, btype="lowpass", output="ba")
        sfg = direct_form_2_iir(b, a)

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

        resources = {
            Addition.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
            Input.type_name(): 1,
            Output.type_name(): 1,
        }
        schedule = Schedule(
            sfg,
            scheduler=RecursiveListScheduler(
                sort_order=((1, True), (3, False), (4, False)), max_resources=resources
            ),
        )
        _validate_recreated_sfg_filter(sfg, schedule)
        assert schedule.schedule_time == sfg.iteration_period_bound()
        for op_id in schedule.start_times:
            assert schedule.backward_slack(op_id) >= 0
            assert schedule.forward_slack(op_id) >= 0

    def test_large_direct_form_2_iir(self):
        N = 8
        Wc = 0.2
        b, a = signal.butter(N, Wc, btype="lowpass", output="ba")
        sfg = direct_form_2_iir(b, a)

        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)
        sfg.set_latency_of_type_name(Addition.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)

        resources = {
            Addition.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
            Input.type_name(): 1,
            Output.type_name(): 1,
        }
        schedule = Schedule(
            sfg,
            scheduler=RecursiveListScheduler(
                sort_order=((1, True), (3, False), (4, False)), max_resources=resources
            ),
        )
        _validate_recreated_sfg_filter(sfg, schedule)
        for op_id in schedule.start_times:
            assert schedule.backward_slack(op_id) >= 0
            assert schedule.forward_slack(op_id) >= 0

    def test_custom_recursive_filter(self):
        # Create the SFG for a digital filter (seen in an exam question from TSTE87).
        x = Input()
        t0 = Delay()
        t1 = Delay(t0)
        b = ConstantMultiplication(0.5, x)
        d = ConstantMultiplication(0.5, t1)
        a1 = Addition(x, d)
        a = ConstantMultiplication(0.5, a1)
        t2 = Delay(a1)
        c = ConstantMultiplication(0.5, t2)
        a2 = Addition(b, c)
        a3 = Addition(a2, a)
        t0.input(0).connect(a3)
        y = Output(a2)
        sfg = SFG([x], [y])

        sfg.set_latency_of_type_name(Addition.type_name(), 1)
        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

        resources = {
            Addition.type_name(): 1,
            ConstantMultiplication.type_name(): 1,
            Input.type_name(): 1,
            Output.type_name(): 1,
        }
        schedule = Schedule(
            sfg,
            scheduler=RecursiveListScheduler(
                sort_order=((1, True), (3, False), (4, False)), max_resources=resources
            ),
        )
        _validate_recreated_sfg_filter(sfg, schedule)
        assert schedule.schedule_time == 4  # all slots filled with cmul executions
        for op_id in schedule.start_times:
            assert schedule.backward_slack(op_id) >= 0
            assert schedule.forward_slack(op_id) >= 0


def _validate_recreated_sfg_filter(sfg: SFG, schedule: Schedule) -> None:
    # compare the impulse response of the original sfg and recreated one
    sim1 = Simulation(sfg, [Impulse()])
    sim1.run_for(1024)
    sim2 = Simulation(schedule.sfg, [Impulse()])
    sim2.run_for(1024)

    spectrum_1 = abs(np.fft.fft(sim1.results["0"]))
    spectrum_2 = abs(np.fft.fft(sim2.results["0"]))
    assert np.allclose(spectrum_1, spectrum_2)


def _validate_recreated_sfg_fft(
    schedule: Schedule, points: int, delays: list[int] | None = None
) -> None:
    if delays is None:
        delays = [0 for i in range(points)]
    # impulse input -> constant output
    sim = Simulation(schedule.sfg, [Constant()] + [0 for i in range(points - 1)])
    sim.run_for(128)
    for i in range(points):
        assert np.all(np.isclose(sim.results[str(i)][delays[i] :], 1))

    # constant input -> impulse (with weight=points) output
    sim = Simulation(schedule.sfg, [Constant() for i in range(points)])
    sim.run_for(128)
    assert np.allclose(sim.results["0"][delays[0] :], points)
    for i in range(1, points):
        assert np.all(np.isclose(sim.results[str(i)][delays[i] :], 0))

    # sine input -> compare with numpy fft
    n = np.linspace(0, 2 * np.pi, points)
    waveform = np.sin(n)
    input_samples = [Constant(waveform[i]) for i in range(points)]
    sim = Simulation(schedule.sfg, input_samples)
    sim.run_for(128)
    exp_res = np.fft.fft(waveform)
    res = sim.results
    for i in range(points):
        a = res[str(i)][delays[i] :]
        b = exp_res[i]
        assert np.all(np.isclose(a, b))

    # multi-tone input -> compare with numpy fft
    n = np.linspace(0, 2 * np.pi, points)
    waveform = (
        2 * np.sin(n)
        + 1.3 * np.sin(0.9 * n)
        + 0.9 * np.sin(0.6 * n)
        + 0.35 * np.sin(0.3 * n)
        + 2.4 * np.sin(0.1 * n)
    )
    input_samples = [Constant(waveform[i]) for i in range(points)]
    sim = Simulation(schedule.sfg, input_samples)
    sim.run_for(128)
    exp_res = np.fft.fft(waveform)
    res = sim.results
    for i in range(points):
        a = res[str(i)][delays[i] :]
        b = exp_res[i]
        assert np.all(np.isclose(a, b))


def _validate_recreated_sfg_ldlt_matrix_inverse(
    schedule: Schedule, N: int, delays: list[int] | None = None
) -> None:
    if delays is None:
        num_of_outputs = N * (N + 1) // 2
        delays = [0 for i in range(num_of_outputs)]

    # random real s.p.d matrix
    A = np.random.default_rng().random((N, N))
    A = np.dot(A, A.T)

    # iterate through the upper diagonal and construct the input to the SFG
    input_signals = []
    for i in range(N):
        for j in range(i, N):
            input_signals.append(Constant(A[i, j]))

    A_inv = np.linalg.inv(A)
    sim = Simulation(schedule.sfg, input_signals)
    sim.run_for(128)

    # iterate through the upper diagonal and check
    count = 0
    for i in range(N):
        for j in range(i, N):
            assert np.all(
                np.isclose(sim.results[str(count)][delays[count] :], A_inv[i, j])
            )
            count += 1
