from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, cast

from b_asic.port import OutputPort
from b_asic.special_operations import Delay, Input, Output
from b_asic.types import TypeName

if TYPE_CHECKING:
    from b_asic.operation import Operation
    from b_asic.schedule import Schedule
    from b_asic.types import GraphID


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

    def _handle_outputs(
        self, schedule: "Schedule", non_schedulable_ops: Optional[list["GraphID"]] = []
    ) -> None:
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


class ListScheduler(Scheduler, ABC):
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
        sfg = schedule.sfg
        start_times = schedule.start_times

        used_resources_ready_times = {}
        remaining_resources = self._max_resources.copy()
        sorted_operations = self._get_sorted_operations(schedule)

        # place all inputs at time 0
        for input_op in sfg.find_by_type_name(Input.type_name()):
            start_times[input_op.graph_id] = 0

        current_time = 0
        while sorted_operations:

            # generate the best schedulable candidate
            candidate = sfg.find_by_id(sorted_operations[0])
            counter = 0
            while not self._candidate_is_schedulable(
                start_times,
                candidate,
                current_time,
                remaining_resources,
                sorted_operations,
            ):
                if counter == len(sorted_operations):
                    counter = 0
                    current_time += 1
                    # update available operators
                    for operation, ready_time in used_resources_ready_times.items():
                        if ready_time == current_time:
                            remaining_resources[operation.type_name()] += 1
                else:
                    candidate = sfg.find_by_id(sorted_operations[counter])
                    counter += 1

            # if the resource is constrained, update remaining resources
            if candidate.type_name() in remaining_resources:
                remaining_resources[candidate.type_name()] -= 1
                if candidate.execution_time:
                    used_resources_ready_times[candidate] = (
                        current_time + candidate.execution_time
                    )
                else:
                    used_resources_ready_times[candidate] = (
                        current_time + candidate.latency
                    )

            # schedule the best candidate to the current time
            sorted_operations.remove(candidate.graph_id)
            start_times[candidate.graph_id] = current_time

        schedule.set_schedule_time(current_time)

        self._handle_outputs(schedule)
        schedule.remove_delays()

        # move all inputs and outputs ALAP now that operations have moved
        for input_op in schedule.sfg.find_by_type_name(Input.type_name()):
            input_op = cast(Input, input_op)
            schedule.move_operation_alap(input_op.graph_id)

    @staticmethod
    def _candidate_is_schedulable(
        start_times: dict["GraphID"],
        operation: "Operation",
        current_time: int,
        remaining_resources: dict["GraphID", int],
        remaining_ops: list["GraphID"],
    ) -> bool:
        if (
            operation.type_name() in remaining_resources
            and remaining_resources[operation.type_name()] == 0
        ):
            return False

        earliest_start_time = 0
        for op_input in operation.inputs:
            source_op = op_input.signals[0].source.operation
            source_op_graph_id = source_op.graph_id

            if source_op_graph_id in remaining_ops:
                return False

            proceeding_op_start_time = start_times.get(source_op_graph_id)

            if not isinstance(source_op, Delay):
                earliest_start_time = max(
                    earliest_start_time, proceeding_op_start_time + source_op.latency
                )

        return earliest_start_time <= current_time

    @abstractmethod
    def _get_sorted_operations(schedule: "Schedule") -> list["GraphID"]:
        raise NotImplementedError
