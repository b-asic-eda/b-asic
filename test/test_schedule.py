"""
B-ASIC test suite for the schedule module and Schedule class.
"""
import re

import pytest

from b_asic.core_operations import Addition, Butterfly, ConstantMultiplication
from b_asic.process import OperatorProcess
from b_asic.schedule import Schedule
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Delay, Input, Output


class TestInit:
    def test_simple_filter_normal_latency(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type(Addition.type_name(), 5)
        sfg_simple_filter.set_latency_of_type(ConstantMultiplication.type_name(), 4)

        schedule = Schedule(sfg_simple_filter)

        assert schedule._start_times == {
            "in0": 0,
            "add0": 4,
            "cmul0": 0,
            "out0": 0,
        }
        assert schedule.schedule_time == 9

        with pytest.raises(
            ValueError, match="No operation with graph_id 'foo' in schedule"
        ):
            schedule.start_time_of_operation("foo")

    def test_complicated_single_outputs_normal_latency(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 4)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")

        start_times_names = {}
        for op_id, start_time in schedule._start_times.items():
            op_name = precedence_sfg_delays.find_by_id(op_id).name
            start_times_names[op_name] = start_time

        assert start_times_names == {
            "IN1": 0,
            "C0": 0,
            "B1": 0,
            "B2": 0,
            "ADD2": 3,
            "ADD1": 7,
            "Q1": 11,
            "A0": 14,
            "A1": 0,
            "A2": 0,
            "ADD3": 3,
            "ADD4": 17,
            "OUT1": 21,
        }
        assert schedule.schedule_time == 21

    def test_complicated_single_outputs_normal_latency_alap(
        self, precedence_sfg_delays
    ):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 4)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ALAP")

        start_times_names = {}
        for op_id in schedule.start_times:
            op_name = precedence_sfg_delays.find_by_id(op_id).name
            start_times_names[op_name] = schedule.start_time_of_operation(op_id)

        assert start_times_names == {
            "IN1": 4,
            "C0": 4,
            "B1": 0,
            "B2": 0,
            "ADD2": 3,
            "ADD1": 7,
            "Q1": 11,
            "A0": 14,
            "A1": 10,
            "A2": 10,
            "ADD3": 13,
            "ADD4": 17,
            "OUT1": 21,
        }
        assert schedule.schedule_time == 21

    def test_complicated_single_outputs_normal_latency_alap_with_schedule_time(
        self, precedence_sfg_delays
    ):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 4)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, schedule_time=25, algorithm="ALAP")

        start_times_names = {}
        for op_id in schedule.start_times:
            op_name = precedence_sfg_delays.find_by_id(op_id).name
            start_times_names[op_name] = schedule.start_time_of_operation(op_id)

        assert start_times_names == {
            "IN1": 8,
            "C0": 8,
            "B1": 4,
            "B2": 4,
            "ADD2": 7,
            "ADD1": 11,
            "Q1": 15,
            "A0": 18,
            "A1": 14,
            "A2": 14,
            "ADD3": 17,
            "ADD4": 21,
            "OUT1": 25,
        }
        assert schedule.schedule_time == 25

    def test_complicated_single_outputs_normal_latency_alap_too_short_schedule_time(
        self, precedence_sfg_delays
    ):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 4)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)
        with pytest.raises(ValueError, match="Too short schedule time. Minimum is 21."):
            Schedule(precedence_sfg_delays, schedule_time=19, algorithm="ALAP")

    def test_complicated_single_outputs_normal_latency_from_fixture(
        self, secondorder_iir_schedule
    ):
        start_times_names = {
            secondorder_iir_schedule.sfg.find_by_id(op_id).name: start_time
            for op_id, start_time in secondorder_iir_schedule._start_times.items()
        }

        assert start_times_names == {
            "IN1": 0,
            "C0": 0,
            "B1": 0,
            "B2": 0,
            "ADD2": 3,
            "ADD1": 7,
            "Q1": 11,
            "A0": 14,
            "A1": 0,
            "A2": 0,
            "ADD3": 3,
            "ADD4": 17,
            "OUT1": 21,
        }
        assert secondorder_iir_schedule.schedule_time == 21

    def test_complicated_single_outputs_complex_latencies(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_offsets_of_type(
            ConstantMultiplication.type_name(), {"in0": 3, "out0": 5}
        )

        precedence_sfg_delays.find_by_name("B1")[0].set_latency_offsets(
            {"in0": 4, "out0": 7}
        )
        precedence_sfg_delays.find_by_name("B2")[0].set_latency_offsets(
            {"in0": 1, "out0": 4}
        )
        precedence_sfg_delays.find_by_name("ADD2")[0].set_latency_offsets(
            {"in0": 4, "in1": 2, "out0": 4}
        )
        precedence_sfg_delays.find_by_name("ADD1")[0].set_latency_offsets(
            {"in0": 1, "in1": 2, "out0": 4}
        )
        precedence_sfg_delays.find_by_name("Q1")[0].set_latency_offsets(
            {"in0": 3, "out0": 6}
        )
        precedence_sfg_delays.find_by_name("A0")[0].set_latency_offsets(
            {"in0": 0, "out0": 2}
        )

        precedence_sfg_delays.find_by_name("A1")[0].set_latency_offsets(
            {"in0": 0, "out0": 5}
        )
        precedence_sfg_delays.find_by_name("A2")[0].set_latency_offsets(
            {"in0": 2, "out0": 3}
        )
        precedence_sfg_delays.find_by_name("ADD3")[0].set_latency_offsets(
            {"in0": 2, "in1": 1, "out0": 4}
        )
        precedence_sfg_delays.find_by_name("ADD4")[0].set_latency_offsets(
            {"in0": 6, "in1": 7, "out0": 9}
        )

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")

        start_times_names = {}
        for op_id, start_time in schedule._start_times.items():
            op_name = precedence_sfg_delays.find_by_id(op_id).name
            start_times_names[op_name] = start_time

        assert start_times_names == {
            "IN1": 0,
            "C0": 0,
            "B1": 0,
            "B2": 0,
            "ADD2": 3,
            "ADD1": 5,
            "Q1": 6,
            "A0": 12,
            "A1": 0,
            "A2": 0,
            "ADD3": 3,
            "ADD4": 8,
            "OUT1": 17,
        }

        assert schedule.schedule_time == 17

    def test_independent_sfg(self, sfg_two_inputs_two_outputs_independent_with_cmul):
        schedule = Schedule(
            sfg_two_inputs_two_outputs_independent_with_cmul,
            algorithm="ASAP",
        )

        start_times_names = {}
        for op_id, start_time in schedule._start_times.items():
            op_name = sfg_two_inputs_two_outputs_independent_with_cmul.find_by_id(
                op_id
            ).name
            start_times_names[op_name] = start_time

        assert start_times_names == {
            "C1": 0,
            "IN1": 0,
            "IN2": 0,
            "CMUL1": 0,
            "CMUL2": 5,
            "ADD1": 0,
            "CMUL3": 7,
            "OUT1": 9,
            "OUT2": 10,
        }
        assert schedule.schedule_time == 10


class TestSlacks:
    def test_forward_backward_slack_normal_latency(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")
        assert (
            schedule.forward_slack(
                precedence_sfg_delays.find_by_name("ADD3")[0].graph_id
            )
            == 7
        )
        assert (
            schedule.backward_slack(
                precedence_sfg_delays.find_by_name("ADD3")[0].graph_id
            )
            == 0
        )

        assert (
            schedule.forward_slack(precedence_sfg_delays.find_by_name("A2")[0].graph_id)
            == 0
        )
        assert (
            schedule.backward_slack(
                precedence_sfg_delays.find_by_name("A2")[0].graph_id
            )
            == 16
        )

    def test_slacks_normal_latency(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")
        assert schedule.slacks(
            precedence_sfg_delays.find_by_name("ADD3")[0].graph_id
        ) == (0, 7)
        assert schedule.slacks(
            precedence_sfg_delays.find_by_name("A2")[0].graph_id
        ) == (16, 0)

    def test_print_slacks(self, capsys, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")
        schedule.print_slacks()
        captured = capsys.readouterr()
        assert captured.out == """Graph ID | Backward |  Forward
---------|----------|---------
add0     |        0 |        0
add1     |        0 |        0
add2     |        0 |        0
add3     |        0 |        7
cmul0    |        0 |        1
cmul1    |        0 |        0
cmul2    |        0 |        0
cmul3    |        4 |        0
cmul4    |       16 |        0
cmul5    |       16 |        0
cmul6    |        4 |        0
in0      |       oo |        0
out0     |        0 |       oo
"""
        assert captured.err == ""

    def test_print_slacks_sorting(self, capsys, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")
        schedule.print_slacks(1)
        captured = capsys.readouterr()
        assert captured.out == """Graph ID | Backward |  Forward
---------|----------|---------
cmul0    |        0 |        1
add0     |        0 |        0
add1     |        0 |        0
cmul1    |        0 |        0
cmul2    |        0 |        0
add3     |        0 |        7
add2     |        0 |        0
out0     |        0 |       oo
cmul3    |        4 |        0
cmul6    |        4 |        0
cmul4    |       16 |        0
cmul5    |       16 |        0
in0      |       oo |        0
"""
        assert captured.err == ""

    def test_slacks_errors(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")
        with pytest.raises(
            ValueError, match="No operation with graph_id 'foo' in schedule"
        ):
            schedule.forward_slack("foo")
        with pytest.raises(
            ValueError, match="No operation with graph_id 'foo' in schedule"
        ):
            schedule.backward_slack("foo")
        with pytest.raises(
            ValueError, match="No operation with graph_id 'foo' in schedule"
        ):
            schedule.slacks("foo")


class TestRescheduling:
    def test_move_operation(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 4)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")

        schedule.move_operation(
            precedence_sfg_delays.find_by_name("ADD3")[0].graph_id, 4
        )
        schedule.move_operation(precedence_sfg_delays.find_by_name("A2")[0].graph_id, 2)

        start_times_names = {}
        for op_id, start_time in schedule._start_times.items():
            op_name = precedence_sfg_delays.find_by_id(op_id).name
            start_times_names[op_name] = start_time

        assert start_times_names == {
            "IN1": 0,
            "C0": 0,
            "B1": 0,
            "B2": 0,
            "ADD2": 3,
            "ADD1": 7,
            "Q1": 11,
            "A0": 14,
            "A1": 0,
            "A2": 2,
            "ADD3": 7,
            "ADD4": 17,
            "OUT1": 21,
        }

        with pytest.raises(
            ValueError, match="No operation with graph_id 'foo' in schedule"
        ):
            schedule.move_operation("foo", 0)

    def test_move_operation_slack_after_rescheduling(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")
        add3_id = precedence_sfg_delays.find_by_name("ADD3")[0].graph_id
        schedule.move_operation(add3_id, 4)
        assert schedule.forward_slack(add3_id) == 3
        assert schedule.backward_slack(add3_id) == 4

        a2_id = precedence_sfg_delays.find_by_name("A2")[0].graph_id
        assert schedule.forward_slack(a2_id) == 4
        assert schedule.backward_slack(a2_id) == 16

        schedule.move_operation(a2_id, 2)

        assert schedule.forward_slack(add3_id) == 3
        assert schedule.backward_slack(add3_id) == 2

        assert schedule.forward_slack(a2_id) == 2
        assert schedule.backward_slack(a2_id) == 18

    def test_move_operation_incorrect_move_backward(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")
        with pytest.raises(
            ValueError,
            match="Operation 'add3' got incorrect move: -4. Must be between 0 and 7.",
        ):
            schedule.move_operation(
                precedence_sfg_delays.find_by_name("ADD3")[0].graph_id, -4
            )

    def test_move_operation_incorrect_move_forward(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")
        with pytest.raises(
            ValueError,
            match="Operation 'add3' got incorrect move: 10. Must be between 0 and 7.",
        ):
            schedule.move_operation(
                precedence_sfg_delays.find_by_name("ADD3")[0].graph_id, 10
            )

    def test_move_operation_asap(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")
        assert schedule.backward_slack('cmul5') == 16
        assert schedule.forward_slack('cmul5') == 0
        schedule.move_operation_asap('cmul5')
        assert schedule.start_time_of_operation('in0') == 0
        assert schedule.laps['cmul5'] == 0
        assert schedule.backward_slack('cmul5') == 0
        assert schedule.forward_slack('cmul5') == 16

    def test_move_input_asap_does_not_mess_up_laps(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type(ConstantMultiplication.type_name(), 3)

        schedule = Schedule(precedence_sfg_delays, algorithm="ASAP")
        old_laps = schedule.laps['in0']
        schedule.move_operation_asap('in0')
        assert schedule.start_time_of_operation('in0') == 0
        assert schedule.laps['in0'] == old_laps

    def test_move_operation_acc(self):
        in0 = Input()
        d = Delay()
        a = d + in0
        out0 = Output(a)
        d <<= a
        sfg = SFG([in0], [out0])
        sfg.set_latency_of_type(Addition.type_name(), 1)
        schedule = Schedule(sfg, cyclic=True)

        # Check initial conditions
        assert schedule.laps[sfg.find_by_id("add0").input(0).signals[0].graph_id] == 1
        assert schedule.laps[sfg.find_by_id("add0").input(1).signals[0].graph_id] == 0
        assert schedule._start_times["add0"] == 0
        assert schedule.laps[sfg.find_by_id("out0").input(0).signals[0].graph_id] == 0
        assert schedule._start_times["out0"] == 1

        # Move and scheduling algorithm behaves differently
        schedule.move_operation("out0", 0)
        assert schedule.laps[sfg.find_by_id("out0").input(0).signals[0].graph_id] == 0
        assert schedule.laps[sfg.find_by_id("add0").input(0).signals[0].graph_id] == 1
        assert schedule.laps[sfg.find_by_id("add0").input(1).signals[0].graph_id] == 0
        assert schedule._start_times["out0"] == 1
        assert schedule._start_times["add0"] == 0

        # Increase schedule time
        schedule.set_schedule_time(2)
        assert schedule.laps[sfg.find_by_id("out0").input(0).signals[0].graph_id] == 0
        assert schedule.laps[sfg.find_by_id("add0").input(0).signals[0].graph_id] == 1
        assert schedule.laps[sfg.find_by_id("add0").input(1).signals[0].graph_id] == 0
        assert schedule._start_times["out0"] == 1
        assert schedule._start_times["add0"] == 0

        # Move out one time unit
        schedule.move_operation("out0", 1)
        assert schedule.laps[sfg.find_by_id("out0").input(0).signals[0].graph_id] == 0
        assert schedule.laps[sfg.find_by_id("add0").input(0).signals[0].graph_id] == 1
        assert schedule.laps[sfg.find_by_id("add0").input(1).signals[0].graph_id] == 0
        assert schedule._start_times["out0"] == 2
        assert schedule._start_times["add0"] == 0

        # Move add one time unit
        schedule.move_operation("add0", 1)
        assert schedule.laps[sfg.find_by_id("add0").input(0).signals[0].graph_id] == 1
        assert schedule.laps[sfg.find_by_id("add0").input(1).signals[0].graph_id] == 0
        assert schedule.laps[sfg.find_by_id("out0").input(0).signals[0].graph_id] == 0
        assert schedule._start_times["add0"] == 1
        assert schedule._start_times["out0"] == 2

        # Move add back one time unit
        schedule.move_operation("add0", -1)
        assert schedule.laps[sfg.find_by_id("add0").input(0).signals[0].graph_id] == 1
        assert schedule.laps[sfg.find_by_id("add0").input(1).signals[0].graph_id] == 0
        assert schedule.laps[sfg.find_by_id("out0").input(0).signals[0].graph_id] == 0
        assert schedule._start_times["add0"] == 0
        assert schedule._start_times["out0"] == 2


class TestTimeResolution:
    def test_increase_time_resolution(
        self, sfg_two_inputs_two_outputs_independent_with_cmul
    ):
        schedule = Schedule(
            sfg_two_inputs_two_outputs_independent_with_cmul,
            algorithm="ASAP",
        )
        old_schedule_time = schedule.schedule_time
        assert schedule.get_possible_time_resolution_decrements() == [1]

        schedule.increase_time_resolution(2)

        start_times_names = {}
        for op_id, start_time in schedule._start_times.items():
            op_name = sfg_two_inputs_two_outputs_independent_with_cmul.find_by_id(
                op_id
            ).name
            start_times_names[op_name] = start_time

        assert start_times_names == {
            "C1": 0,
            "IN1": 0,
            "IN2": 0,
            "CMUL1": 0,
            "CMUL2": 10,
            "ADD1": 0,
            "CMUL3": 14,
            "OUT1": 18,
            "OUT2": 20,
        }

        assert 2 * old_schedule_time == schedule.schedule_time
        assert schedule.get_possible_time_resolution_decrements() == [1, 2]

    def test_increase_time_resolution_twice(
        self, sfg_two_inputs_two_outputs_independent_with_cmul
    ):
        schedule = Schedule(
            sfg_two_inputs_two_outputs_independent_with_cmul,
            algorithm="ASAP",
        )
        old_schedule_time = schedule.schedule_time

        schedule.increase_time_resolution(2)
        schedule.increase_time_resolution(3)

        start_times_names = {}
        for op_id, start_time in schedule._start_times.items():
            op = sfg_two_inputs_two_outputs_independent_with_cmul.find_by_id(op_id)
            start_times_names[op.name] = (start_time, op.latency, op.execution_time)

        assert start_times_names == {
            "C1": (0, 0, None),
            "IN1": (0, 0, 0),
            "IN2": (0, 0, 0),
            "CMUL1": (0, 30, 18),
            "CMUL2": (30, 24, 6),
            "ADD1": (0, 42, 12),
            "CMUL3": (42, 18, 6),
            "OUT1": (54, 0, 0),
            "OUT2": (60, 0, 0),
        }

        assert 6 * old_schedule_time == schedule.schedule_time
        assert schedule.get_possible_time_resolution_decrements() == [
            1,
            2,
            3,
            6,
        ]

    def test_increase_decrease_time_resolution(
        self, sfg_two_inputs_two_outputs_independent_with_cmul
    ):
        schedule = Schedule(
            sfg_two_inputs_two_outputs_independent_with_cmul,
            algorithm="ASAP",
        )
        old_schedule_time = schedule.schedule_time
        assert schedule.get_possible_time_resolution_decrements() == [1]

        schedule.increase_time_resolution(6)

        start_times_names = {}
        for op_id, start_time in schedule._start_times.items():
            op_name = sfg_two_inputs_two_outputs_independent_with_cmul.find_by_id(
                op_id
            ).name
            start_times_names[op_name] = start_time

        assert start_times_names == {
            "C1": 0,
            "IN1": 0,
            "IN2": 0,
            "CMUL1": 0,
            "CMUL2": 30,
            "ADD1": 0,
            "CMUL3": 42,
            "OUT1": 54,
            "OUT2": 60,
        }

        with pytest.raises(ValueError, match="Not possible to decrease resolution"):
            schedule.decrease_time_resolution(4)

        schedule.decrease_time_resolution(3)
        start_times_names = {}
        for op_id, start_time in schedule._start_times.items():
            op_name = sfg_two_inputs_two_outputs_independent_with_cmul.find_by_id(
                op_id
            ).name
            start_times_names[op_name] = start_time

        assert start_times_names == {
            "C1": 0,
            "IN1": 0,
            "IN2": 0,
            "CMUL1": 0,
            "CMUL2": 10,
            "ADD1": 0,
            "CMUL3": 14,
            "OUT1": 18,
            "OUT2": 20,
        }

        assert 2 * old_schedule_time == schedule.schedule_time
        assert schedule.get_possible_time_resolution_decrements() == [1, 2]


class TestProcesses:
    def test__get_memory_variables_list(self, secondorder_iir_schedule):
        mvl = secondorder_iir_schedule._get_memory_variables_list()
        assert len(mvl) == 12
        pc = secondorder_iir_schedule.get_memory_variables()
        assert len(pc) == 12

    def test_get_operations(self, secondorder_iir_schedule_with_execution_times):
        pc = secondorder_iir_schedule_with_execution_times.get_operations()
        assert len(pc) == 13
        assert all(isinstance(operand, OperatorProcess) for operand in pc.collection)


class TestFigureGeneration:
    @pytest.mark.mpl_image_compare(remove_text=True, style='mpl20')
    def test__get_figure_no_execution_times(self, secondorder_iir_schedule):
        return secondorder_iir_schedule._get_figure()


class TestErrors:
    def test_no_latency(self, sfg_simple_filter):
        with pytest.raises(
            ValueError,
            match="Input port 0 of operation add0 has no latency-offset.",
        ):
            Schedule(sfg_simple_filter)

    def test_no_output_latency(self):
        in1 = Input()
        in2 = Input()
        bfly = Butterfly(in1, in2, latency_offsets={"in0": 4, "in1": 2, "out0": 10})
        out1 = Output(bfly.output(0))
        out2 = Output(bfly.output(1))
        sfg = SFG([in1, in2], [out1, out2])
        with pytest.raises(
            ValueError,
            match="Output port 1 of operation bfly0 has no latency-offset.",
        ):
            Schedule(sfg)
        in1 = Input()
        in2 = Input()
        bfly1 = Butterfly(in1, in2, latency_offsets={"in0": 4, "in1": 2, "out1": 10})
        bfly2 = Butterfly(
            bfly1.output(0),
            bfly1.output(1),
            latency_offsets={"in0": 4, "in1": 2, "out0": 10, "out1": 8},
        )
        out1 = Output(bfly2.output(0))
        out2 = Output(bfly2.output(1))
        sfg = SFG([in1, in2], [out1, out2])
        with pytest.raises(
            ValueError,
            match="Output port 0 of operation bfly0 has no latency-offset.",
        ):
            Schedule(sfg)

    def test_too_short_schedule_time(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type(Addition.type_name(), 5)
        sfg_simple_filter.set_latency_of_type(ConstantMultiplication.type_name(), 4)
        with pytest.raises(ValueError, match="Too short schedule time. Minimum is 9."):
            Schedule(sfg_simple_filter, schedule_time=3)

        schedule = Schedule(sfg_simple_filter)
        with pytest.raises(
            ValueError,
            match=re.escape("New schedule time (3) too short, minimum: 9."),
        ):
            schedule.set_schedule_time(3)

    def test_incorrect_scheduling_algorithm(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type(Addition.type_name(), 1)
        sfg_simple_filter.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        with pytest.raises(
            NotImplementedError, match="No algorithm with name: foo defined."
        ):
            Schedule(sfg_simple_filter, algorithm="foo")

    def test_no_sfg(self):
        with pytest.raises(TypeError, match="An SFG must be provided"):
            Schedule(1)

    def test_provided_no_start_times(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type(Addition.type_name(), 1)
        sfg_simple_filter.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        with pytest.raises(
            ValueError, match="Must provide start_times when using 'provided'"
        ):
            Schedule(sfg_simple_filter, algorithm="provided")

    def test_provided_no_laps(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type(Addition.type_name(), 1)
        sfg_simple_filter.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        with pytest.raises(ValueError, match="Must provide laps when using 'provided'"):
            Schedule(sfg_simple_filter, algorithm="provided", start_times={'in0': 0})


class TestGetUsedTypeNames:
    def test_secondorder_iir_schedule(self, secondorder_iir_schedule):
        assert secondorder_iir_schedule.get_used_type_names() == [
            'add',
            'cmul',
            'in',
            'out',
        ]


class TestYLocations:
    def test_provided_no_laps(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type(Addition.type_name(), 1)
        sfg_simple_filter.set_latency_of_type(ConstantMultiplication.type_name(), 2)
        schedule = Schedule(sfg_simple_filter)
        # Assign locations
        schedule.show()
        print(schedule._y_locations)
        assert schedule._y_locations == {'in0': 0, 'cmul0': 1, 'add0': 2, 'out0': 3}
        schedule.move_y_location('add0', 1, insert=True)
        assert schedule._y_locations == {'in0': 0, 'cmul0': 2, 'add0': 1, 'out0': 3}
        schedule.move_y_location('out0', 1)
        assert schedule._y_locations == {'in0': 0, 'cmul0': 2, 'add0': 1, 'out0': 1}
