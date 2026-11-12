"""
B-ASIC test suite for the schedule module and Schedule class.
"""

import io
import pickle
import re
import sys
from copy import deepcopy

import matplotlib.pyplot as plt
import matplotlib.testing.decorators
import pytest
from matplotlib.patches import PathPatch

from b_asic.core_operations import Addition, ConstantMultiplication, Subtraction
from b_asic.fft_operations import R2Butterfly
from b_asic.process import OperatorProcess
from b_asic.schedule import Schedule
from b_asic.scheduler import ALAPScheduler, ASAPScheduler
from b_asic.sfg import SFG
from b_asic.sfg_generators import direct_form_1_iir, fir
from b_asic.special_operations import Delay, Input, Output
from b_asic.utility_operations import DontCare, Sink


def test_copy_long_chain_without_recursion_limit_change():
    limit = sys.getrecursionlimit()
    source = Input()
    end = source
    for _ in range(limit + 25):
        end = ConstantMultiplication(0.5, end, latency=1)
    schedule = Schedule(SFG([source], [Output(end)]))

    cloned = schedule.copy()

    assert sys.getrecursionlimit() == limit
    assert cloned.start_times == schedule.start_times
    assert cloned.laps == schedule.laps
    assert cloned.schedule_time == schedule.schedule_time
    assert cloned._sfg is not schedule._sfg
    assert cloned._scheduler is not schedule._scheduler
    assert cloned._scheduler._schedule is cloned
    cloned.start_times["in0"] = 1
    assert schedule.start_times["in0"] == 0


@pytest.mark.parametrize("clone", [deepcopy, Schedule.copy])
def test_copy_preserves_graph_and_isolates_edits(clone, precedence_sfg_delays):
    precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
    precedence_sfg_delays.set_latency_of_type_name(
        ConstantMultiplication.type_name(), 3
    )
    schedule = Schedule(precedence_sfg_delays, cyclic=True)
    schedule._sfg._input_operations[0].value = 0.75
    operation = schedule._sfg.find_by_type(ConstantMultiplication)[0]
    shared = [1, 2]
    operation.set_param("metadata", [shared, shared])
    schedule.set_y_location(operation.graph_id, 5)
    # Populate caches containing graph objects before cloning.
    schedule._sfg.get_precedence_list()
    schedule._sfg.get_operations_topological_order()

    cloned = clone(schedule)

    assert cloned.start_times == schedule.start_times
    assert cloned.laps == schedule.laps
    assert cloned._y_locations == schedule._y_locations
    assert cloned._sfg._input_operations[0].value == 0.75
    for original in schedule._sfg.operations:
        copied = cloned._sfg.find_by_id(original.graph_id)
        assert copied is not original
        assert type(copied) is type(original)
        assert copied.name == original.name
        assert copied.latency_offsets == original.latency_offsets
        assert copied.execution_time == original.execution_time
        for port in copied.inputs:
            assert port.operation is copied
            for signal in port.signals:
                assert signal.destination is port
                source = cloned._sfg.find_by_id(signal.source.operation.graph_id)
                assert signal.source is source.output(signal.source.index)
                assert signal in signal.source.signals
    assert cloned._scheduler._schedule is cloned
    copied_operation = cloned._sfg.find_by_id(operation.graph_id)
    metadata = copied_operation.param("metadata")
    assert metadata[0] is metadata[1]
    assert metadata[0] is not shared
    metadata[0].append(3)
    copied_operation.set_latency(7)
    cloned.laps[next(iter(cloned.laps))] += 1
    cloned.set_y_location(operation.graph_id, 0)
    assert shared == [1, 2]
    assert operation.latency == 3
    assert schedule.get_y_location(operation.graph_id) == 5
    assert schedule.laps != cloned.laps


class TestInit:
    def test_simple_filter_normal_latency(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_simple_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(sfg_simple_filter, scheduler=ASAPScheduler())

        assert schedule._start_times == {
            "in0": 0,
            "add0": 4,
            "cmul0": 0,
            "out0": 0,
        }
        assert schedule.schedule_time == 9

        with pytest.raises(
            ValueError, match=r"No operation with graph_id 'foo' in schedule"
        ):
            schedule.start_time_of_operation("foo")

    def test_complicated_single_outputs_normal_latency(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 4)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())

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
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 4)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ALAPScheduler())

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
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 4)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(
            precedence_sfg_delays, schedule_time=25, scheduler=ALAPScheduler()
        )

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
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 4)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )
        with pytest.raises(
            ValueError, match=r"Too short schedule time. Minimum is 21."
        ):
            Schedule(precedence_sfg_delays, schedule_time=19, scheduler=ALAPScheduler())

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
        precedence_sfg_delays.set_latency_offsets_of_type_name(
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

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())

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
            scheduler=ASAPScheduler(),
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

    def test_provided_schedule(self):
        sfg = direct_form_1_iir([2, 2, 3], [1, 2, 3])

        sfg.set_latency_of_type_name(Addition.type_name(), 1)
        sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 3)
        sfg.set_execution_time_of_type_name(Addition.type_name(), 1)
        sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

        start_times = {
            "in0": 1,
            "cmul0": 1,
            "cmul1": 0,
            "cmul2": 0,
            "cmul3": 0,
            "cmul4": 0,
            "add3": 3,
            "add1": 3,
            "add0": 4,
            "add2": 5,
            "out0": 6,
        }
        laps = {
            "s8": 1,
            "s10": 2,
            "s15": 1,
            "s17": 2,
            "s0": 0,
            "s3": 0,
            "s12": 0,
            "s11": 0,
            "s14": 0,
            "s13": 0,
            "s6": 0,
            "s4": 0,
            "s5": 0,
            "s2": 0,
        }

        schedule = Schedule(sfg, start_times=start_times, laps=laps)

        assert schedule.start_times == start_times
        assert schedule.laps == laps
        assert schedule.schedule_time == 6


class TestSlacks:
    @pytest.mark.parametrize("cyclic", [False, True])
    def test_sink_does_not_limit_real_consumer_slack(self, cyclic):
        source = Input()
        operation = ConstantMultiplication(0.5, source, latency=1)
        Sink(operation)
        schedule = Schedule(SFG([source], [Output(operation)]), cyclic=cyclic)
        schedule.set_schedule_time(4)
        schedule.move_operation("out0", 1)

        assert schedule.forward_slack("cmul0") == 1
        with pytest.raises(ValueError, match="incorrect move"):
            schedule.move_operation("cmul0", 2)
        schedule.move_operation("cmul0", 1)
        assert schedule.start_times["sink0"] == 2
        assert schedule.forward_slack("cmul0") == 0
        schedule._validate_slacks()
        schedule._validate_laps()

    def test_sink_follows_source_across_cyclic_boundary(self):
        source = Input()
        operation = Subtraction(source, source, latency=1)
        Sink(operation)
        used = ConstantMultiplication(0.5, source, latency=5)
        schedule = Schedule(SFG([source], [Output(used)]), cyclic=True)

        schedule.move_operation("sub0", 4)
        assert schedule.start_times["sink0"] == 5
        schedule.move_operation("sub0", 2)
        assert schedule.start_times["sub0"] == 1
        assert schedule.start_times["sink0"] == 2
        schedule._validate_slacks()
        schedule._validate_laps()

    def test_dontcare_does_not_block_cyclic_backward_wrap(self):
        operation = ConstantMultiplication(0.5, DontCare(), latency=1)
        schedule = Schedule(SFG([], [Output(operation)]), cyclic=True, schedule_time=4)

        schedule.move_operation("cmul0", -1)

        assert schedule.start_times["cmul0"] == 3
        schedule._validate_slacks()
        schedule._validate_laps()

    def test_dontcare_remains_valid_when_consumer_moves_earlier(self):
        operation = ConstantMultiplication(0.5, DontCare(), latency=1)
        schedule = Schedule(SFG([], [Output(operation)]), cyclic=True, schedule_time=4)
        schedule.move_operation("out0", 2)
        schedule.move_operation("cmul0", 2)
        schedule.move_operation_alap("dontcare0")

        schedule.move_operation("cmul0", -1)

        schedule._validate_slacks()
        schedule._validate_laps()

    @pytest.mark.parametrize("cyclic", [False, True])
    def test_sink_only_operation_moves_alap_within_schedule(self, cyclic):
        source = Input()
        unused = ConstantMultiplication(0.5, source, latency=1)
        Sink(unused)
        used = ConstantMultiplication(0.25, source, latency=4)
        schedule = Schedule(SFG([source], [Output(used)]), cyclic=cyclic)
        unused_id = next(
            signal.source_operation.graph_id
            for signal in schedule._sfg.find_by_id("sink0").input(0).signals
        )

        schedule.move_operation_alap(unused_id)
        assert schedule.start_times[unused_id] == 3
        assert schedule.start_times["sink0"] == 4
        schedule._validate_slacks()
        schedule._validate_laps()

    def test_forward_backward_slack_normal_latency(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())
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
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())
        assert schedule.slacks(
            precedence_sfg_delays.find_by_name("ADD3")[0].graph_id
        ) == (0, 7)
        assert schedule.slacks(
            precedence_sfg_delays.find_by_name("A2")[0].graph_id
        ) == (16, 0)

    def test_print_slacks(self, capsys, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())
        schedule.print_slacks()
        captured = capsys.readouterr()
        assert captured.out == (
            "Graph ID | Backward |  Forward\n"
            "---------|----------|---------\n"
            "add0     |        0 |        0\n"
            "add1     |        0 |        0\n"
            "add2     |        0 |        0\n"
            "add3     |        0 |        7\n"
            "cmul0    |        0 |        1\n"
            "cmul1    |        0 |        0\n"
            "cmul2    |        0 |        0\n"
            "cmul3    |        4 |        0\n"
            "cmul4    |       16 |        0\n"
            "cmul5    |       16 |        0\n"
            "cmul6    |        4 |        0\n"
            "in0      |       oo |        0\n"
            "out0     |        0 |       oo\n"
        )
        assert captured.err == ""

    def test_print_slacks_sorting(self, capsys, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())
        schedule.print_slacks(1)
        captured = capsys.readouterr()
        assert captured.out == (
            "Graph ID | Backward |  Forward\n"
            "---------|----------|---------\n"
            "cmul0    |        0 |        1\n"
            "add0     |        0 |        0\n"
            "add1     |        0 |        0\n"
            "cmul1    |        0 |        0\n"
            "cmul2    |        0 |        0\n"
            "add3     |        0 |        7\n"
            "add2     |        0 |        0\n"
            "out0     |        0 |       oo\n"
            "cmul3    |        4 |        0\n"
            "cmul6    |        4 |        0\n"
            "cmul4    |       16 |        0\n"
            "cmul5    |       16 |        0\n"
            "in0      |       oo |        0\n"
        )
        assert captured.err == ""

    def test_print_slacks_type_name_given(self, capsys, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())
        schedule.print_slacks(1, type_name=ConstantMultiplication)
        captured = capsys.readouterr()
        assert captured.out == (
            "Graph ID | Backward |  Forward\n"
            "---------|----------|---------\n"
            "cmul0    |        0 |        1\n"
            "cmul1    |        0 |        0\n"
            "cmul2    |        0 |        0\n"
            "cmul3    |        4 |        0\n"
            "cmul6    |        4 |        0\n"
            "cmul4    |       16 |        0\n"
            "cmul5    |       16 |        0\n"
        )
        assert captured.err == ""

    def test_slacks_errors(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())
        with pytest.raises(
            ValueError, match=r"No operation with graph_id 'foo' in schedule"
        ):
            schedule.forward_slack("foo")
        with pytest.raises(
            ValueError, match=r"No operation with graph_id 'foo' in schedule"
        ):
            schedule.backward_slack("foo")
        with pytest.raises(
            ValueError, match=r"No operation with graph_id 'foo' in schedule"
        ):
            schedule.slacks("foo")


class TestRescheduling:
    @pytest.mark.parametrize("cyclic", [False, True])
    def test_schedule_time_ignores_late_sink_placeholder(self, cyclic):
        source = Input()
        operation = ConstantMultiplication(0.5, source, latency=1)
        Sink(operation)
        schedule = Schedule(SFG([source], [Output(operation)]), cyclic=cyclic)
        schedule.set_schedule_time(5)
        schedule.move_operation("sink0", 3)
        assert schedule.start_times["sink0"] == 4

        schedule.set_schedule_time(3)

        assert schedule.schedule_time == 3
        assert schedule.start_times["sink0"] == 1
        schedule._validate()

    def test_real_output_still_blocks_cyclic_boundary_reduction(self):
        source = Input()
        operation = ConstantMultiplication(0.5, source, latency=1)
        Sink(operation)
        schedule = Schedule(SFG([source], [Output(operation)]), cyclic=True)
        schedule.set_schedule_time(4)
        schedule.move_operation("out0", 3)
        schedule.move_operation("cmul0", 3)
        start_times = schedule.start_times.copy()
        laps = schedule.laps.copy()

        with pytest.raises(ValueError, match="invalidate the cyclic schedule"):
            schedule.set_schedule_time(3, allow_cyclic_wrap=True)

        assert schedule.start_times == start_times
        assert schedule.laps == laps
        schedule._validate()

    @pytest.mark.parametrize("latency", [0, 1, 2, 3])
    def test_wrap_boundary_start_time_preserves_slacks(self, latency):
        input_item = Input()
        operation = ConstantMultiplication(0.5, input_item, latency=latency)
        sfg = SFG([input_item], [Output(operation)])
        schedule = Schedule(
            sfg,
            cyclic=True,
            schedule_time=2,
            start_times={"in0": 0, "cmul0": 2, "out0": 2},
            laps={"s0": 3, "s1": 3},
        )
        original_slacks = {
            graph_id: schedule.slacks(graph_id) for graph_id in schedule.start_times
        }

        schedule.set_schedule_time(2, allow_cyclic_wrap=True)

        assert schedule.start_times == {"in0": 0, "cmul0": 0, "out0": 2}
        assert {
            graph_id: schedule.slacks(graph_id) for graph_id in schedule.start_times
        } == original_slacks
        schedule._validate()

        schedule.set_schedule_time(3, allow_cyclic_wrap=True)
        assert schedule.start_times["cmul0"] == 0
        schedule._validate()

    def test_move_operation(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 4)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())

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
            ValueError, match=r"No operation with graph_id 'foo' in schedule"
        ):
            schedule.move_operation("foo", 0)

    def test_move_operation_slack_after_rescheduling(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())
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
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())
        with pytest.raises(
            ValueError,
            match=r"Operation 'add3' got incorrect move: -4. Must be between 0 and 7.",
        ):
            schedule.move_operation(
                precedence_sfg_delays.find_by_name("ADD3")[0].graph_id, -4
            )

    def test_move_operation_incorrect_move_forward(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())
        with pytest.raises(
            ValueError,
            match=r"Operation 'add3' got incorrect move: 10. Must be between 0 and 7.",
        ):
            schedule.move_operation(
                precedence_sfg_delays.find_by_name("ADD3")[0].graph_id, 10
            )

    def test_move_operation_asap(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())
        assert schedule.backward_slack("cmul5") == 16
        assert schedule.forward_slack("cmul5") == 0
        schedule.move_operation_asap("cmul5")
        assert schedule.start_time_of_operation("in0") == 0
        assert schedule.laps["cmul5"] == 0
        assert schedule.backward_slack("cmul5") == 0
        assert schedule.forward_slack("cmul5") == 16

    def test_move_input_asap_does_not_mess_up_laps(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())
        old_laps = schedule.laps["in0"]
        schedule.move_operation_asap("in0")
        assert schedule.start_time_of_operation("in0") == 0
        assert schedule.laps["in0"] == old_laps

    def test_move_operation_acc(self):
        in0 = Input()
        d = Delay()
        a = d + in0
        out0 = Output(a)
        d <<= a
        sfg = SFG([in0], [out0])
        sfg.set_latency_of_type_name(Addition.type_name(), 1)
        schedule = Schedule(sfg, scheduler=ASAPScheduler(), cyclic=True)

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

    def test_reintroduce_delays(
        self, precedence_sfg_delays, sfg_direct_form_iir_lp_filter
    ):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 1)
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())
        sfg = schedule.sfg
        assert precedence_sfg_delays.evaluate(5) == sfg.evaluate(5)

        schedule = Schedule(sfg_direct_form_iir_lp_filter, scheduler=ASAPScheduler())
        sfg = schedule.sfg
        assert sfg_direct_form_iir_lp_filter.evaluate(5) == sfg.evaluate(5)

        fir_sfg = fir(
            list(range(1, 10)),
            mult_properties={"latency": 2, "execution_time": 1},
            add_properties={"latency": 2, "execution_time": 1},
        )
        schedule = Schedule(fir_sfg, scheduler=ASAPScheduler())
        sfg = schedule.sfg
        assert fir_sfg.evaluate(5) == sfg.evaluate(5)

    def test_rotate_forward(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, cyclic=True)
        schedule = schedule.rotate_forward()
        assert schedule.start_times == {
            "in0": 1,
            "cmul0": 1,
            "cmul3": 1,
            "cmul4": 1,
            "cmul5": 1,
            "cmul6": 1,
            "add3": 4,
            "add1": 4,
            "add0": 5,
            "cmul1": 6,
            "cmul2": 9,
            "add2": 0,
            "out0": 1,
        }

        sfg = schedule._sfg
        assert schedule.laps == {
            sfg.find_by_id("in0").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul0").input_signals[0].graph_id: 0,
            sfg.find_by_id("cmul0").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul3").input_signals[0].graph_id: 1,
            sfg.find_by_id("cmul3").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul6").input_signals[0].graph_id: 1,
            sfg.find_by_id("cmul6").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul4").input_signals[0].graph_id: 2,
            sfg.find_by_id("cmul4").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul5").input_signals[0].graph_id: 2,
            sfg.find_by_id("cmul5").output_signals[0].graph_id: 0,
            sfg.find_by_id("add3").input_signals[0].graph_id: 0,
            sfg.find_by_id("add3").input_signals[1].graph_id: 0,
            sfg.find_by_id("add3").output_signals[0].graph_id: 1,
            sfg.find_by_id("add1").input_signals[0].graph_id: 0,
            sfg.find_by_id("add1").input_signals[1].graph_id: 0,
            sfg.find_by_id("add1").output_signals[0].graph_id: 0,
            sfg.find_by_id("add0").input_signals[0].graph_id: 0,
            sfg.find_by_id("add0").input_signals[1].graph_id: 0,
            sfg.find_by_id("add0").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul1").input_signals[0].graph_id: 0,
            sfg.find_by_id("cmul1").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul1").output_signals[1].graph_id: 1,
            sfg.find_by_id("cmul1").output_signals[2].graph_id: 1,
            sfg.find_by_id("cmul1").output_signals[3].graph_id: 2,
            sfg.find_by_id("cmul1").output_signals[4].graph_id: 2,
            sfg.find_by_id("cmul2").input_signals[0].graph_id: 0,
            sfg.find_by_id("cmul2").output_signals[0].graph_id: 1,
            sfg.find_by_id("add2").input_signals[0].graph_id: 1,
            sfg.find_by_id("add2").input_signals[1].graph_id: 1,
            sfg.find_by_id("add2").output_signals[0].graph_id: 0,
            sfg.find_by_id("out0").input_signals[0].graph_id: 0,
        }

    def test_rotate_backward(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 1)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )

        schedule = Schedule(precedence_sfg_delays, cyclic=True)

        schedule = schedule.rotate_backward()
        schedule = schedule.rotate_backward()
        assert schedule.start_times == {
            "in0": 10,
            "cmul0": 10,
            "cmul3": 10,
            "cmul4": 10,
            "cmul5": 10,
            "cmul6": 10,
            "add3": 1,
            "add1": 1,
            "add0": 2,
            "cmul1": 3,
            "cmul2": 6,
            "add2": 9,
            "out0": 10,
        }

        sfg = schedule._sfg
        assert schedule.laps == {
            sfg.find_by_id("in0").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul0").input_signals[0].graph_id: 0,
            sfg.find_by_id("cmul0").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul3").input_signals[0].graph_id: 0,
            sfg.find_by_id("cmul3").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul6").input_signals[0].graph_id: 0,
            sfg.find_by_id("cmul6").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul4").input_signals[0].graph_id: 1,
            sfg.find_by_id("cmul4").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul5").input_signals[0].graph_id: 1,
            sfg.find_by_id("cmul5").output_signals[0].graph_id: 0,
            sfg.find_by_id("add3").input_signals[0].graph_id: 0,
            sfg.find_by_id("add3").input_signals[1].graph_id: 0,
            sfg.find_by_id("add3").output_signals[0].graph_id: 0,
            sfg.find_by_id("add1").input_signals[0].graph_id: 0,
            sfg.find_by_id("add1").input_signals[1].graph_id: 0,
            sfg.find_by_id("add1").output_signals[0].graph_id: 0,
            sfg.find_by_id("add0").input_signals[0].graph_id: 0,
            sfg.find_by_id("add0").input_signals[1].graph_id: 0,
            sfg.find_by_id("add0").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul1").input_signals[0].graph_id: 0,
            sfg.find_by_id("cmul1").output_signals[0].graph_id: 0,
            sfg.find_by_id("cmul1").output_signals[1].graph_id: 0,
            sfg.find_by_id("cmul1").output_signals[2].graph_id: 0,
            sfg.find_by_id("cmul1").output_signals[3].graph_id: 1,
            sfg.find_by_id("cmul1").output_signals[4].graph_id: 1,
            sfg.find_by_id("cmul2").input_signals[0].graph_id: 0,
            sfg.find_by_id("cmul2").output_signals[0].graph_id: 0,
            sfg.find_by_id("add2").input_signals[0].graph_id: 0,
            sfg.find_by_id("add2").input_signals[1].graph_id: 0,
            sfg.find_by_id("add2").output_signals[0].graph_id: 0,
            sfg.find_by_id("out0").input_signals[0].graph_id: 0,
        }

    def test_rotate_noncyclic_schedule(self):
        source = Input()
        operation = ConstantMultiplication(2, source, latency=2)
        schedule = Schedule(SFG([source], [Output(operation)]), schedule_time=5)
        original_times = schedule.start_times.copy()
        original_laps = schedule.laps.copy()

        assert schedule.rotate_forward() is schedule
        assert schedule.start_times == {
            graph_id: time + 1 for graph_id, time in original_times.items()
        }
        schedule._validate()
        assert schedule.rotate_backward() is schedule
        assert schedule.start_times == original_times
        assert schedule.laps == original_laps

    @pytest.mark.parametrize("latency", [0, 1])
    def test_rotate_noncyclic_schedule_stops_at_boundaries(self, latency):
        source = Input()
        operation = ConstantMultiplication(2, source, latency=latency, execution_time=1)
        schedule = Schedule(SFG([source], [Output(operation)]), schedule_time=5)
        original_times = schedule.start_times.copy()
        original_laps = schedule.laps.copy()
        steps = 5 - max(latency, 1)

        with pytest.raises(ValueError, match="Cannot rotate non-cyclic schedule"):
            schedule.rotate_backward()
        assert schedule.start_times == original_times
        assert schedule.laps == original_laps
        for _ in range(steps):
            schedule.rotate_forward()
        boundary_times = schedule.start_times.copy()
        with pytest.raises(ValueError, match="Cannot rotate non-cyclic schedule"):
            schedule.rotate_forward()
        assert schedule.start_times == boundary_times
        assert schedule.laps == original_laps
        for _ in range(steps):
            schedule.rotate_backward()
        assert schedule.start_times == original_times
        assert schedule.laps == original_laps

    def test_noncyclic_rotation_rejects_execution_time_wrap(self):
        source = Input()
        operation = ConstantMultiplication(2, source, latency=1, execution_time=3)
        schedule = Schedule(SFG([source], [Output(operation)]), schedule_time=5)
        original_times = schedule.start_times.copy()
        original_laps = schedule.laps.copy()

        for _ in range(2):
            schedule.rotate_forward()
        original_times = schedule.start_times.copy()
        with pytest.raises(ValueError, match="crosses the schedule boundary"):
            schedule.rotate_forward()
        assert schedule.start_times == original_times
        assert schedule.laps == original_laps

    @pytest.mark.parametrize("cyclic", [False, True])
    @pytest.mark.parametrize("direction", ["forward", "backward"])
    def test_rotate_zero_duration_schedule(self, cyclic, direction):
        source = Input()
        operation = ConstantMultiplication(2, source, latency=0)
        schedule = Schedule(SFG([source], [Output(operation)]), cyclic=cyclic)
        assert schedule.schedule_time == 0

        with pytest.raises(ValueError, match="zero duration"):
            getattr(schedule, f"rotate_{direction}")()

    @pytest.mark.parametrize("direction", ["forward", "backward"])
    def test_invalid_noncyclic_rotation_is_atomic(self, direction):
        source = Input()
        operation = ConstantMultiplication(2, source, latency=2)
        schedule = Schedule(SFG([source], [Output(operation)]), schedule_time=2)
        original_times = schedule.start_times.copy()
        original_laps = schedule.laps.copy()

        with pytest.raises(ValueError, match="Cannot rotate non-cyclic schedule"):
            getattr(schedule, f"rotate_{direction}")()
        assert schedule.start_times == original_times
        assert schedule.laps == original_laps


class TestTimeResolution:
    def test_increase_time_resolution(
        self, sfg_two_inputs_two_outputs_independent_with_cmul
    ):
        schedule = Schedule(
            sfg_two_inputs_two_outputs_independent_with_cmul,
            scheduler=ASAPScheduler(),
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
            scheduler=ASAPScheduler(),
        )
        old_schedule_time = schedule.schedule_time

        schedule.increase_time_resolution(2)
        schedule.increase_time_resolution(3)

        start_times_names = {}
        for op_id, start_time in schedule._start_times.items():
            op = sfg_two_inputs_two_outputs_independent_with_cmul.find_by_id(op_id)
            start_times_names[op.name] = (start_time, op.latency, op.execution_time)

        assert start_times_names == {
            "C1": (0, 0, 1),
            "IN1": (0, 0, 1),
            "IN2": (0, 0, 1),
            "CMUL1": (0, 30, 18),
            "CMUL2": (30, 24, 6),
            "ADD1": (0, 42, 12),
            "CMUL3": (42, 18, 6),
            "OUT1": (54, 0, 1),
            "OUT2": (60, 0, 1),
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
            scheduler=ASAPScheduler(),
        )
        old_schedule_time = schedule.schedule_time
        assert schedule.get_possible_time_resolution_decrements() == [1]

        schedule.increase_time_resolution(6)

        start_times_names = {}
        for op_id, start_time in schedule._start_times.items():
            op = sfg_two_inputs_two_outputs_independent_with_cmul.find_by_id(op_id)
            start_times_names[op.name] = (start_time, op.latency, op.execution_time)

        assert start_times_names == {
            "C1": (0, 0, 1),
            "IN1": (0, 0, 1),
            "IN2": (0, 0, 1),
            "CMUL1": (0, 30, 18),
            "CMUL2": (30, 24, 6),
            "ADD1": (0, 42, 12),
            "CMUL3": (42, 18, 6),
            "OUT1": (54, 0, 1),
            "OUT2": (60, 0, 1),
        }

        with pytest.raises(ValueError, match=r"Not possible to decrease resolution"):
            schedule.decrease_time_resolution(4)

        schedule.decrease_time_resolution(3)
        start_times_names = {}
        for op_id, start_time in schedule._start_times.items():
            op = sfg_two_inputs_two_outputs_independent_with_cmul.find_by_id(op_id)
            start_times_names[op.name] = (start_time, op.latency, op.execution_time)

        assert start_times_names == {
            "C1": (0, 0, 1),
            "IN1": (0, 0, 1),
            "IN2": (0, 0, 1),
            "CMUL1": (0, 10, 6),
            "CMUL2": (10, 8, 2),
            "ADD1": (0, 14, 4),
            "CMUL3": (14, 6, 2),
            "OUT1": (18, 0, 1),
            "OUT2": (20, 0, 1),
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
    @pytest.mark.parametrize("cyclic", [False, True])
    def test_placeholder_ports_are_crossed_without_placeholder_rows(self, cyclic):
        source = Input()
        operation = Addition(source, DontCare(), latency=1)
        Sink(operation)
        schedule = Schedule(SFG([source], [Output(operation)]), cyclic=cyclic)
        schedule.sort_y_locations_on_start_times()
        start_times = schedule.start_times.copy()
        laps = schedule.laps.copy()

        fig = schedule._get_figure()
        try:
            ax = fig.axes[0]
            assert {text.get_text() for text in ax.texts} == {"in0", "add0", "out0"}
            markers = [line for line in ax.lines if line.get_marker() == "x"]
            assert len(markers) == 2
            plotted_operation = schedule._sfg.find_by_id("add0")
            operation_label = next(
                text for text in ax.texts if text.get_text() == "add0"
            )
            operation_y = operation_label.get_position()[1] - 0.7
            expected = {
                (
                    schedule.start_times["add0"] + coordinates[index][0],
                    operation_y + coordinates[index][1],
                )
                for coordinates, index in (
                    (plotted_operation.get_input_coordinates(), 1),
                    (plotted_operation.get_output_coordinates(), 0),
                )
            }
            assert {
                (line.get_xdata()[0], line.get_ydata()[0]) for line in markers
            } == expected
            assert sum(isinstance(patch, PathPatch) for patch in ax.patches) == 2
            assert len(ax.get_yticks()) == 3
            assert fig.get_figheight() == pytest.approx(1.6)
            assert schedule.start_times == start_times
            assert schedule.laps == laps
        finally:
            plt.close(fig)

    def test_figure_default_font(self, secondorder_iir_schedule):
        fig = secondorder_iir_schedule._get_figure()
        try:
            assert fig.axes[0].xaxis.label.get_fontfamily() == ["DejaVu Serif"]
        finally:
            plt.close(fig)

    @matplotlib.testing.decorators.image_comparison(
        ["test__get_figure_no_execution_times.png"], remove_text=True, style="default"
    )
    def test__get_figure_no_execution_times(self, secondorder_iir_schedule):
        return secondorder_iir_schedule._get_figure(fontname=None)


class TestErrors:
    def test_no_latency(self, sfg_simple_filter):
        with pytest.raises(
            ValueError,
            match=r"Input port 0 of operation cmul0 has no latency-offset.",
        ):
            Schedule(sfg_simple_filter, scheduler=ASAPScheduler())

    def test_no_output_latency(self):
        in1 = Input()
        in2 = Input()
        bfly = R2Butterfly(in1, in2, latency_offsets={"in0": 4, "in1": 2, "out0": 10})
        out1 = Output(bfly.output(0))
        out2 = Output(bfly.output(1))
        sfg = SFG([in1, in2], [out1, out2])
        with pytest.raises(
            ValueError,
            match=r"Output port 1 of operation r2bfly0 has no latency-offset.",
        ):
            Schedule(sfg, scheduler=ASAPScheduler())
        in1 = Input()
        in2 = Input()
        bfly1 = R2Butterfly(in1, in2, latency_offsets={"in0": 4, "in1": 2, "out1": 10})
        bfly2 = R2Butterfly(
            bfly1.output(0),
            bfly1.output(1),
            latency_offsets={"in0": 4, "in1": 2, "out0": 10, "out1": 8},
        )
        out1 = Output(bfly2.output(0))
        out2 = Output(bfly2.output(1))
        sfg = SFG([in1, in2], [out1, out2])
        with pytest.raises(
            ValueError,
            match=r"Output port 0 of operation r2bfly0 has no latency-offset.",
        ):
            Schedule(sfg, scheduler=ASAPScheduler())

    def test_too_short_schedule_time(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_simple_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 4
        )
        with pytest.raises(ValueError, match=r"Too short schedule time. Minimum is 9."):
            Schedule(sfg_simple_filter, scheduler=ASAPScheduler(), schedule_time=3)

        schedule = Schedule(sfg_simple_filter, scheduler=ASAPScheduler())
        with pytest.raises(
            ValueError,
            match=re.escape("New schedule time (3) too short, minimum: 9."),
        ):
            schedule.set_schedule_time(3)

    # def test_incorrect_scheduling_algorithm(self, sfg_simple_filter):
    #     sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 1)
    #     sfg_simple_filter.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
    #     with pytest.raises(
    #         NotImplementedError, match=r"No algorithm with name: foo defined."
    #     ):
    #         Schedule(sfg_simple_filter, algorithm="foo")

    def test_no_sfg(self):
        with pytest.raises(TypeError, match=r"An SFG must be provided"):
            Schedule(1)

    def test_provided_no_start_times(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 1)
        sfg_simple_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 2
        )
        with pytest.raises(
            ValueError, match=r"Must provide start_times when using 'provided'"
        ):
            Schedule(sfg_simple_filter, laps={"test": 0})

    def test_provided_no_laps(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 1)
        sfg_simple_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 2
        )
        with pytest.raises(
            ValueError, match=r"Must provide laps when using 'provided'"
        ):
            Schedule(sfg_simple_filter, start_times={"in0": 0})

    def test_alap_default(self, sfg_direct_form_iir_lp_filter):
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_direct_form_iir_lp_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 4
        )

        schedule = Schedule(sfg_direct_form_iir_lp_filter)

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


class TestGetUsedTypeNames:
    def test_secondorder_iir_schedule(self, secondorder_iir_schedule):
        assert secondorder_iir_schedule.get_used_type_names() == [
            "add",
            "cmul",
            "in",
            "out",
        ]


class TestYLocations:
    def test_provided_no_laps(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 1)
        sfg_simple_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 2
        )
        schedule = Schedule(sfg_simple_filter, ASAPScheduler())

        assert schedule._y_locations == {"in0": 1, "cmul0": 0, "add0": 2, "out0": 3}
        schedule.move_y_location("add0", 1, insert=True)
        assert schedule._y_locations == {"in0": 2, "cmul0": 0, "add0": 1, "out0": 3}
        schedule.move_y_location("out0", 1)
        assert schedule._y_locations == {"in0": 2, "cmul0": 0, "add0": 1, "out0": 1}

    def test_reset(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 1)
        sfg_simple_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 2
        )
        schedule = Schedule(sfg_simple_filter, ASAPScheduler())

        assert schedule._y_locations == {"in0": 1, "cmul0": 0, "add0": 2, "out0": 3}
        schedule.reset_y_locations()
        assert schedule._y_locations["in0"] is None
        assert schedule._y_locations["cmul0"] is None
        assert schedule._y_locations["add0"] is None
        assert schedule._y_locations["add0"] is None
        assert schedule._y_locations["out0"] is None
        assert schedule._y_locations["foo"] is None


class TestGetIoLatency:
    def test_simple_filter(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_simple_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 4
        )
        schedule = Schedule(sfg_simple_filter, scheduler=ASAPScheduler())

        assert schedule.get_io_latency() == {"in0": {"out0": 9}}

    def test_precedence_sfg_delays(self, precedence_sfg_delays):
        precedence_sfg_delays.set_latency_of_type_name(Addition.type_name(), 4)
        precedence_sfg_delays.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 3
        )
        schedule = Schedule(precedence_sfg_delays, scheduler=ASAPScheduler())

        assert schedule.get_io_latency() == {"in0": {"out0": 21}}


class TestPickle:
    def test_sfg_accessible_after_pickle(self, sfg_simple_filter):
        sfg_simple_filter.set_latency_of_type_name(Addition.type_name(), 5)
        sfg_simple_filter.set_latency_of_type_name(
            ConstantMultiplication.type_name(), 4
        )
        schedule = Schedule(sfg_simple_filter, scheduler=ASAPScheduler())
        original_op_ids = {op.graph_id for op in schedule.sfg.operations}

        buf = io.BytesIO()
        pickle.dump(schedule, buf)
        buf.seek(0)
        loaded = pickle.load(buf)

        assert {op.graph_id for op in loaded.sfg.operations} == original_op_ids
