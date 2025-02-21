import copy
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, cast

from b_asic.core_operations import DontCare
from b_asic.port import OutputPort
from b_asic.special_operations import Delay, Input, Output
from b_asic.types import TypeName

if TYPE_CHECKING:
    from b_asic.operation import Operation
    from b_asic.schedule import Schedule
    from b_asic.signal_flow_graph import SFG
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


class ListScheduler(Scheduler, ABC):
    def __init__(
        self,
        max_resources: Optional[dict[TypeName, int]] = None,
        max_concurrent_reads: Optional[int] = None,
        max_concurrent_writes: Optional[int] = None,
        input_times: Optional[dict["GraphID", int]] = None,
        output_delta_times: Optional[dict["GraphID", int]] = None,
        cyclic: Optional[bool] = False,
    ) -> None:
        super()
        if max_resources is not None:
            if not isinstance(max_resources, dict):
                raise ValueError("max_resources must be a dictionary.")
            for key, value in max_resources.items():
                if not isinstance(key, str):
                    raise ValueError("max_resources key must be a valid type_name.")
                if not isinstance(value, int):
                    raise ValueError("max_resources value must be an integer.")
            self._max_resources = max_resources
        else:
            self._max_resources = {}

        self._max_concurrent_reads = max_concurrent_reads or sys.maxsize
        self._max_concurrent_writes = max_concurrent_writes or sys.maxsize

        self._input_times = input_times or {}
        self._output_delta_times = output_delta_times or {}

    @property
    @abstractmethod
    def sort_indices(self) -> tuple[tuple[int, bool]]:
        raise NotImplementedError

    def apply_scheduling(self, schedule: "Schedule") -> None:
        """Applies the scheduling algorithm on the given Schedule.

        Parameters
        ----------
        schedule : Schedule
            Schedule to apply the scheduling algorithm on.
        """
        sfg = schedule.sfg

        alap_schedule = copy.copy(schedule)
        ALAPScheduler().apply_scheduling(alap_schedule)
        alap_start_times = alap_schedule.start_times
        schedule.start_times = {}

        used_resources_ready_times = {}
        remaining_resources = self._max_resources.copy()
        if Input.type_name() not in remaining_resources:
            remaining_resources[Input.type_name()] = 1
        if Output.type_name() not in remaining_resources:
            remaining_resources[Output.type_name()] = 1

        remaining_ops = (
            sfg.operations
            + sfg.find_by_type_name(Input.type_name())
            + sfg.find_by_type_name(Output.type_name())
        )
        remaining_ops = [op.graph_id for op in remaining_ops]

        schedule.start_times = {}
        remaining_reads = self._max_concurrent_reads

        # initial input placement
        if self._input_times:
            for input_id in self._input_times:
                schedule.start_times[input_id] = self._input_times[input_id]
            remaining_ops = [
                elem for elem in remaining_ops if not elem.startswith("in")
            ]

        remaining_ops = [op for op in remaining_ops if not op.startswith("dontcare")]
        remaining_ops = [op for op in remaining_ops if not op.startswith("t")]

        current_time = 0
        time_out_counter = 0
        while remaining_ops:
            ready_ops_priority_table = self._get_ready_ops_priority_table(
                sfg,
                schedule.start_times,
                current_time,
                alap_start_times,
                remaining_ops,
                remaining_resources,
                remaining_reads,
            )
            while ready_ops_priority_table:
                next_op = sfg.find_by_id(self._get_next_op_id(ready_ops_priority_table))

                if next_op.type_name() in remaining_resources:
                    remaining_resources[next_op.type_name()] -= 1
                    if (
                        next_op.type_name() == Input.type_name()
                        or next_op.type_name() == Output.type_name()
                    ):
                        used_resources_ready_times[next_op] = current_time + 1
                    else:
                        used_resources_ready_times[next_op] = (
                            current_time + next_op.execution_time
                        )
                remaining_reads -= next_op.input_count

                remaining_ops = [
                    op_id for op_id in remaining_ops if op_id != next_op.graph_id
                ]
                schedule.start_times[next_op.graph_id] = current_time

                ready_ops_priority_table = self._get_ready_ops_priority_table(
                    sfg,
                    schedule.start_times,
                    current_time,
                    alap_start_times,
                    remaining_ops,
                    remaining_resources,
                    remaining_reads,
                )

            current_time += 1
            time_out_counter += 1
            if time_out_counter >= 100:
                raise TimeoutError(
                    "Algorithm did not schedule any operation for 10 time steps, "
                    "try relaxing constraints."
                )

            ready_ops_priority_table = self._get_ready_ops_priority_table(
                sfg,
                schedule.start_times,
                current_time,
                alap_start_times,
                remaining_ops,
                remaining_resources,
                remaining_reads,
            )
            # update available reads and operators
            remaining_reads = self._max_concurrent_reads
            for operation, ready_time in used_resources_ready_times.items():
                if ready_time == current_time:
                    remaining_resources[operation.type_name()] += 1

        current_time -= 1

        self._handle_outputs(schedule)

        if not schedule.cyclic:
            max_start_time = max(schedule.start_times.values())
            if current_time < max_start_time:
                current_time = max_start_time
            current_time = max(current_time, schedule.get_max_end_time())
            schedule.set_schedule_time(current_time)

        schedule.remove_delays()

        # schedule all dont cares ALAP
        for dc_op in sfg.find_by_type_name(DontCare.type_name()):
            dc_op = cast(DontCare, dc_op)
            schedule.start_times[dc_op.graph_id] = 0
            schedule.move_operation_alap(dc_op.graph_id)

    def _get_next_op_id(
        self, ready_ops_priority_table: list[tuple["GraphID", int, ...]]
    ) -> "GraphID":
        def sort_key(item):
            return tuple(
                (item[index] * (-1 if not asc else 1),)
                for index, asc in self.sort_indices
            )

        sorted_table = sorted(ready_ops_priority_table, key=sort_key)
        return sorted_table[0][0]

    def _get_ready_ops_priority_table(
        self,
        sfg: "SFG",
        start_times: dict["GraphID", int],
        current_time: int,
        alap_start_times: dict["GraphID", int],
        remaining_ops: list["GraphID"],
        remaining_resources: dict["GraphID", int],
        remaining_reads: int,
    ) -> list[tuple["GraphID", int, int, int]]:

        ready_ops = [
            op_id
            for op_id in remaining_ops
            if self._op_is_schedulable(
                start_times,
                sfg,
                sfg.find_by_id(op_id),
                current_time,
                remaining_resources,
                remaining_reads,
                self._max_concurrent_writes,
                remaining_ops,
            )
        ]

        deadlines = self._calculate_deadlines(sfg, alap_start_times)
        output_slacks = self._calculate_alap_output_slacks(
            current_time, alap_start_times
        )
        fan_outs = self._calculate_fan_outs(sfg, alap_start_times)

        ready_ops_priority_table = []
        for op_id in ready_ops:
            ready_ops_priority_table.append(
                (op_id, deadlines[op_id], output_slacks[op_id], fan_outs[op_id])
            )
        return ready_ops_priority_table

    def _calculate_deadlines(
        self, sfg, alap_start_times: dict["GraphID", int]
    ) -> dict["GraphID", int]:
        return {
            op_id: start_time + sfg.find_by_id(op_id).latency
            for op_id, start_time in alap_start_times.items()
        }

    def _calculate_alap_output_slacks(
        self, current_time: int, alap_start_times: dict["GraphID", int]
    ) -> dict["GraphID", int]:
        return {
            op_id: start_time - current_time
            for op_id, start_time in alap_start_times.items()
        }

    def _calculate_fan_outs(
        self, sfg: "SFG", alap_start_times: dict["GraphID", int]
    ) -> dict["GraphID", int]:
        return {
            op_id: len(sfg.find_by_id(op_id).output_signals)
            for op_id, start_time in alap_start_times.items()
        }

    @staticmethod
    def _op_is_schedulable(
        start_times: dict["GraphID"],
        sfg: "SFG",
        op: "Operation",
        current_time: int,
        remaining_resources: dict["GraphID", int],
        remaining_reads: int,
        max_concurrent_writes: int,
        remaining_ops: list["GraphID"],
    ) -> bool:
        if (
            op.type_name() in remaining_resources
            and remaining_resources[op.type_name()] == 0
        ):
            return False

        op_finish_time = current_time + op.latency
        future_ops = [
            sfg.find_by_id(item[0])
            for item in start_times.items()
            if item[1] + sfg.find_by_id(item[0]).latency == op_finish_time
        ]

        future_ops_writes = sum([op.input_count for op in future_ops])

        if (
            not op.graph_id.startswith("out")
            and future_ops_writes >= max_concurrent_writes
        ):
            return False

        read_counter = 0
        earliest_start_time = 0
        for op_input in op.inputs:
            source_op = op_input.signals[0].source.operation
            if isinstance(source_op, Delay) or isinstance(source_op, DontCare):
                continue

            source_op_graph_id = source_op.graph_id

            if source_op_graph_id in remaining_ops:
                return False

            if start_times[source_op_graph_id] != current_time - 1:
                # not a direct connection -> memory read required
                read_counter += 1

            if read_counter > remaining_reads:
                return False

            proceeding_op_start_time = start_times.get(source_op_graph_id)
            proceeding_op_finish_time = proceeding_op_start_time + source_op.latency
            earliest_start_time = max(earliest_start_time, proceeding_op_finish_time)

        return earliest_start_time <= current_time

    def _handle_outputs(
        self, schedule: "Schedule", non_schedulable_ops: Optional[list["GraphID"]] = []
    ) -> None:
        schedule.set_schedule_time(schedule.get_max_end_time())

        for output in schedule.sfg.find_by_type_name(Output.type_name()):
            output = cast(Output, output)
            if output.graph_id in self._output_delta_times:
                delta_time = self._output_delta_times[output.graph_id]
                if schedule.cyclic:
                    schedule.start_times[output.graph_id] = schedule.schedule_time
                    schedule.move_operation(output.graph_id, delta_time)
                else:
                    schedule.start_times[output.graph_id] = (
                        schedule.schedule_time + delta_time
                    )
