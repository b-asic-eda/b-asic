import sys
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import TYPE_CHECKING, Optional, cast

from b_asic.port import OutputPort
from b_asic.special_operations import Delay, Input, Output
from b_asic.types import TypeName

if TYPE_CHECKING:
    from b_asic.schedule import Schedule


class Scheduler(ABC):
    @abstractmethod
    def apply_scheduling(self, schedule: "Schedule") -> None:
        """Applies the scheduling algorithm on the given Schedule.

        Parameters
        ----------
        schedule : Schedule
            Schedule to apply the scheduling algorithm on.
        """
        raise NotImplementedError

    def _handle_outputs(self, schedule, non_schedulable_ops=set()) -> None:
        for output in schedule.sfg.find_by_type_name(Output.type_name()):
            output = cast(Output, output)
            source_port = cast(OutputPort, output.inputs[0].signals[0].source)
            if source_port.operation.graph_id in non_schedulable_ops:
                schedule.start_times[output.graph_id] = 0
            else:
                if source_port.latency_offset is None:
                    raise ValueError(
                        f"Output port {source_port.index} of operation"
                        f" {source_port.operation.graph_id} has no"
                        " latency-offset."
                    )
                schedule.start_times[output.graph_id] = schedule.start_times[
                    source_port.operation.graph_id
                ] + cast(int, source_port.latency_offset)


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
        non_schedulable_ops = set()
        for outport in prec_list[0]:
            operation = outport.operation
            if operation.type_name() == Delay.type_name():
                non_schedulable_ops.add(operation.graph_id)
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


class EarliestDeadlineScheduler(Scheduler):
    """
    Scheduler that implements the earliest-deadline-first algorithm.

    Parameters
    ----------
    max_resources : dict, optional
        Dictionary like ``{Addition.type_name(): 2}`` denoting the maximum number of
        resources for a given operation type if the scheduling algorithm considers
        that. If not provided, or an operation type is not provided, at most one
        resource is used.
    """

    def __init__(self, max_resources: Optional[dict[TypeName, int]] = None) -> None:
        if max_resources:
            self._max_resources = max_resources
        else:
            self._max_resources = {}

    def apply_scheduling(self, schedule: "Schedule") -> None:
        """Applies the scheduling algorithm on the given Schedule.

        Parameters
        ----------
        schedule : Schedule
            Schedule to apply the scheduling algorithm on.
        """

        ALAPScheduler().apply_scheduling(schedule)

        # move all inputs ASAP to ensure correct operation
        for input_op in schedule.sfg.find_by_type_name(Input.type_name()):
            input_op = cast(Input, input_op)
            schedule.move_operation_asap(input_op.graph_id)

        # construct the set of remaining operations, excluding inputs
        remaining_ops = list(schedule.start_times.keys())
        remaining_ops = [elem for elem in remaining_ops if not elem.startswith("in")]

        # construct a dictionarry for storing how many times until a resource is available again
        used_resources_ready_times = {}

        # iterate through all remaining operations and schedule them
        # while not exceeding the available resources
        remaining_resources = self._max_resources.copy()
        current_time = 0
        while remaining_ops:
            best_candidate = self._find_best_candidate(
                schedule, remaining_ops, remaining_resources, current_time
            )

            if not best_candidate:
                current_time += 1

                # update available operators
                for operation, ready_time in used_resources_ready_times.items():
                    if ready_time == current_time:
                        remaining_resources[operation.type_name()] += 1
                # remaining_resources = self._max_resources.copy()
                continue

            # if the resource is constrained, update remaining resources
            if best_candidate.type_name() in remaining_resources:
                remaining_resources[best_candidate.type_name()] -= 1
                if best_candidate.execution_time:
                    used_resources_ready_times[best_candidate] = (
                        current_time + best_candidate.execution_time
                    )
                else:
                    used_resources_ready_times[best_candidate] = (
                        current_time + best_candidate.latency
                    )

            # schedule the best candidate to the current time
            remaining_ops.remove(best_candidate.graph_id)
            schedule.start_times[best_candidate.graph_id] = current_time

        # move all inputs and outputs ALAP now that operations have moved
        for input_op in schedule.sfg.find_by_type_name(Input.type_name()):
            input_op = cast(Input, input_op)
            schedule.move_operation_alap(input_op.graph_id)
        self._handle_outputs(schedule)

    @staticmethod
    def _find_best_candidate(
        schedule, remaining_ops, remaining_resources, current_time
    ):
        sfg = schedule.sfg
        source_end_times = defaultdict(float)

        # find the best candidate
        best_candidate = None
        best_deadline = float('inf')
        for op_id in remaining_ops:
            operation = sfg.find_by_id(op_id)

            # compute maximum end times of preceding operations
            for op_input in operation.inputs:
                source_op = op_input.signals[0].source.operation
                if not isinstance(source_op, Delay):
                    source_end_times[op_id] = max(
                        source_end_times[op_id],
                        schedule.start_times[source_op.graph_id] + source_op.latency,
                    )
                    # ensure that the source is already scheduled
                    if source_op.graph_id in remaining_ops:
                        source_end_times[op_id] = sys.maxsize

            # check resource constraints
            if operation.type_name() in remaining_resources:
                if remaining_resources[operation.type_name()] == 0:
                    continue

            # check if all inputs are available
            if source_end_times[op_id] <= current_time:
                operation_deadline = schedule.start_times[op_id] + operation.latency
                if operation_deadline < best_deadline:
                    best_candidate = operation
                    best_deadline = operation_deadline

        return best_candidate
