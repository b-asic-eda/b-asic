import copy
from typing import TYPE_CHECKING, cast

from b_asic.scheduler import ListScheduler, Scheduler
from b_asic.special_operations import Delay, Output

if TYPE_CHECKING:
    from b_asic.schedule import Schedule
    from b_asic.types import GraphID


class ASAPScheduler(Scheduler):
    """Scheduler that implements the as-soon-as-possible (ASAP) algorithm."""

    def apply_scheduling(self, schedule: "Schedule") -> None:
        """Applies the scheduling algorithm on the given Schedule.

        Parameters
        ----------
        schedule : Schedule
            Schedule to apply the scheduling algorithm on.
        """
        prec_list = schedule.sfg.get_precedence_list()
        if len(prec_list) < 2:
            raise ValueError("Empty signal flow graph cannot be scheduled.")

        # handle the first set in precedence graph (input and delays)
        non_schedulable_ops = []
        for outport in prec_list[0]:
            operation = outport.operation
            if operation.type_name() == Delay.type_name():
                non_schedulable_ops.append(operation.graph_id)
            else:
                schedule.start_times[operation.graph_id] = 0

        # handle second set in precedence graph (first operations)
        for outport in prec_list[1]:
            operation = outport.operation
            schedule.start_times[operation.graph_id] = 0

        # handle the remaining sets
        for outports in prec_list[2:]:
            for outport in outports:
                operation = outport.operation
                if operation.graph_id not in schedule.start_times:
                    op_start_time = 0
                    for current_input in operation.inputs:
                        source_port = current_input.signals[0].source

                        if source_port.operation.graph_id in non_schedulable_ops:
                            source_end_time = 0
                        else:
                            source_op_time = schedule.start_times[
                                source_port.operation.graph_id
                            ]

                            if source_port.latency_offset is None:
                                raise ValueError(
                                    f"Output port {source_port.index} of"
                                    " operation"
                                    f" {source_port.operation.graph_id} has no"
                                    " latency-offset."
                                )

                            source_end_time = (
                                source_op_time + source_port.latency_offset
                            )

                        if current_input.latency_offset is None:
                            raise ValueError(
                                f"Input port {current_input.index} of operation"
                                f" {current_input.operation.graph_id} has no"
                                " latency-offset."
                            )
                        op_start_time_from_in = (
                            source_end_time - current_input.latency_offset
                        )
                        op_start_time = max(op_start_time, op_start_time_from_in)

                    schedule.start_times[operation.graph_id] = op_start_time

        self._handle_outputs(schedule, non_schedulable_ops)
        schedule.remove_delays()


class ALAPScheduler(Scheduler):
    """Scheduler that implements the as-late-as-possible (ALAP) algorithm."""

    def apply_scheduling(self, schedule: "Schedule") -> None:
        """Applies the scheduling algorithm on the given Schedule.

        Parameters
        ----------
        schedule : Schedule
            Schedule to apply the scheduling algorithm on.
        """
        ASAPScheduler().apply_scheduling(schedule)
        max_end_time = schedule.get_max_end_time()

        if schedule.schedule_time is None:
            schedule.set_schedule_time(max_end_time)
        elif schedule.schedule_time < max_end_time:
            raise ValueError(f"Too short schedule time. Minimum is {max_end_time}.")

        # move all outputs ALAP before operations
        for output in schedule.sfg.find_by_type_name(Output.type_name()):
            output = cast(Output, output)
            schedule.move_operation_alap(output.graph_id)

        # move all operations ALAP
        for step in reversed(schedule.sfg.get_precedence_list()):
            for outport in step:
                if not isinstance(outport.operation, Delay):
                    schedule.move_operation_alap(outport.operation.graph_id)


class EarliestDeadlineScheduler(ListScheduler):
    """Scheduler that implements the earliest-deadline-first algorithm."""

    @staticmethod
    def _get_sorted_operations(schedule: "Schedule") -> list["GraphID"]:
        schedule_copy = copy.copy(schedule)
        ALAPScheduler().apply_scheduling(schedule_copy)

        deadlines = {}
        for op_id, start_time in schedule_copy.start_times.items():
            if not op_id.startswith("in"):
                deadlines[op_id] = start_time + schedule.sfg.find_by_id(op_id).latency

        return sorted(deadlines, key=deadlines.get)


class LeastSlackTimeScheduler(ListScheduler):
    """Scheduler that implements the least slack time first algorithm."""

    @staticmethod
    def _get_sorted_operations(schedule: "Schedule") -> list["GraphID"]:
        schedule_copy = copy.copy(schedule)
        ALAPScheduler().apply_scheduling(schedule_copy)

        sorted_ops = sorted(
            schedule_copy.start_times, key=schedule_copy.start_times.get
        )
        return [op for op in sorted_ops if not op.startswith("in")]


class MaxFanOutScheduler(ListScheduler):
    """Scheduler that implements the maximum fan-out algorithm."""

    @staticmethod
    def _get_sorted_operations(schedule: "Schedule") -> list["GraphID"]:
        schedule_copy = copy.copy(schedule)
        ALAPScheduler().apply_scheduling(schedule_copy)

        fan_outs = {}
        for op_id, start_time in schedule_copy.start_times.items():
            fan_outs[op_id] = len(schedule.sfg.find_by_id(op_id).output_signals)

        sorted_ops = sorted(fan_outs, key=fan_outs.get, reverse=True)
        return [op for op in sorted_ops if not op.startswith("in")]


class HybridScheduler(ListScheduler):
    """Scheduler that implements a hybrid algorithm. Will receive a new name once finalized."""

    @staticmethod
    def _get_sorted_operations(schedule: "Schedule") -> list["GraphID"]:
        # sort least-slack and then resort ties according to max-fan-out
        schedule_copy = copy.copy(schedule)
        ALAPScheduler().apply_scheduling(schedule_copy)

        sorted_items = sorted(
            schedule_copy.start_times.items(), key=lambda item: item[1]
        )

        fan_out_sorted_items = []

        last_value = sorted_items[0][0]
        current_group = []
        for key, value in sorted_items:

            if value != last_value:
                # the group is completed, sort it internally
                sorted_group = sorted(
                    current_group,
                    key=lambda pair: len(
                        schedule.sfg.find_by_id(pair[0]).output_signals
                    ),
                    reverse=True,
                )
                fan_out_sorted_items += sorted_group
                current_group = []

            current_group.append((key, value))

            last_value = value

        sorted_group = sorted(
            current_group,
            key=lambda pair: len(schedule.sfg.find_by_id(pair[0]).output_signals),
            reverse=True,
        )
        fan_out_sorted_items += sorted_group

        sorted_op_list = [pair[0] for pair in fan_out_sorted_items]

        return [op for op in sorted_op_list if not op.startswith("in")]
