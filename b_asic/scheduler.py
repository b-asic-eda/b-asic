import copy
import sys
from abc import ABC, abstractmethod
from math import ceil
from typing import TYPE_CHECKING, cast

import b_asic.logger as logger
from b_asic.core_operations import DontCare
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
        self, schedule: "Schedule", non_schedulable_ops: list["GraphID"] | None = []
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

        max_end_time = schedule.get_max_end_time()

        if schedule.schedule_time is None:
            schedule.set_schedule_time(max_end_time)
        elif schedule.schedule_time < max_end_time:
            raise ValueError(f"Too short schedule time. Minimum is {max_end_time}.")

        schedule.sort_y_locations_on_start_times()


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

        # move all outputs ALAP before operations
        for output in schedule.sfg.find_by_type_name(Output.type_name()):
            output = cast(Output, output)
            schedule.move_operation_alap(output.graph_id)

        # move all operations ALAP
        for step in reversed(schedule.sfg.get_precedence_list()):
            for outport in step:
                if not isinstance(outport.operation, Delay):
                    schedule.move_operation_alap(outport.operation.graph_id)

        schedule.sort_y_locations_on_start_times()


class ListScheduler(Scheduler, ABC):
    """
    List-based scheduler that schedules the operations while complying to the given
    constraints.

    Parameters
    ----------
    max_resources : dict[TypeName, int] | None, optional
        Max resources available to realize the schedule, by default None
    max_concurrent_reads : int | None, optional
        Max number of conccurent reads, by default None
    max_concurrent_writes : int | None, optional
        Max number of conccurent writes, by default None
    input_times : dict[GraphID, int] | None, optional
        Specified input times, by default None
    output_delta_times : dict[GraphID, int] | None, optional
        Specified output delta times, by default None
    cyclic : bool | None, optional
        If the scheduler is allowed to schedule cyclically (modulo), by default False
    sort_order : tuple[tuple[int, bool]]
        Specifies which columns in the priority table to sort on and in which order, where True is ascending order.
    """

    def __init__(
        self,
        max_resources: dict[TypeName, int] | None = None,
        max_concurrent_reads: int | None = None,
        max_concurrent_writes: int | None = None,
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
        sort_order=tuple[tuple[int, bool], ...],
    ) -> None:
        super()
        self._logger = logger.getLogger("list_scheduler")

        if max_resources is not None:
            if not isinstance(max_resources, dict):
                raise ValueError("Provided max_resources must be a dictionary.")
            for key, value in max_resources.items():
                if not isinstance(key, str):
                    raise ValueError("Provided max_resources keys must be strings.")
                if not isinstance(value, int):
                    raise ValueError("Provided max_resources values must be integers.")
            self._max_resources = max_resources
        else:
            self._max_resources = {}

        if Input.type_name() not in self._max_resources:
            self._max_resources[Input.type_name()] = 1
        if Output.type_name() not in self._max_resources:
            self._max_resources[Output.type_name()] = 1

        if max_concurrent_reads is not None:
            if not isinstance(max_concurrent_reads, int):
                raise ValueError("Provided max_concurrent_reads must be an integer.")
            if max_concurrent_reads <= 0:
                raise ValueError("Provided max_concurrent_reads must be larger than 0.")
        self._max_concurrent_reads = max_concurrent_reads or sys.maxsize

        if max_concurrent_writes is not None:
            if not isinstance(max_concurrent_writes, int):
                raise ValueError("Provided max_concurrent_writes must be an integer.")
            if max_concurrent_writes <= 0:
                raise ValueError(
                    "Provided max_concurrent_writes must be larger than 0."
                )
        self._max_concurrent_writes = max_concurrent_writes or sys.maxsize

        if input_times is not None:
            if not isinstance(input_times, dict):
                raise ValueError("Provided input_times must be a dictionary.")
            for key, value in input_times.items():
                if not isinstance(key, str):
                    raise ValueError("Provided input_times keys must be strings.")
                if not isinstance(value, int):
                    raise ValueError("Provided input_times values must be integers.")
            if any(time < 0 for time in input_times.values()):
                raise ValueError("Provided input_times values must be non-negative.")
            self._input_times = input_times
        else:
            self._input_times = {}

        if output_delta_times is not None:
            if not isinstance(output_delta_times, dict):
                raise ValueError("Provided output_delta_times must be a dictionary.")
            for key, value in output_delta_times.items():
                if not isinstance(key, str):
                    raise ValueError(
                        "Provided output_delta_times keys must be strings."
                    )
                if not isinstance(value, int):
                    raise ValueError(
                        "Provided output_delta_times values must be integers."
                    )
            if any(time < 0 for time in output_delta_times.values()):
                raise ValueError(
                    "Provided output_delta_times values must be non-negative."
                )
            self._output_delta_times = output_delta_times
        else:
            self._output_delta_times = {}

        self._sort_order = sort_order

    def apply_scheduling(self, schedule: "Schedule") -> None:
        """Applies the scheduling algorithm on the given Schedule.

        Parameters
        ----------
        schedule : Schedule
            Schedule to apply the scheduling algorithm on.
        """
        self._logger.debug("--- Scheduler initializing ---")

        self._schedule = schedule
        self._sfg = schedule.sfg

        for resource_type in self._max_resources.keys():
            if not self._sfg.find_by_type_name(resource_type):
                raise ValueError(
                    f"Provided max resource of type {resource_type} cannot be found in the provided SFG."
                )

        for key in self._input_times.keys():
            if self._sfg.find_by_id(key) is None:
                raise ValueError(
                    f"Provided input time with GraphID {key} cannot be found in the provided SFG."
                )

        for key in self._output_delta_times.keys():
            if self._sfg.find_by_id(key) is None:
                raise ValueError(
                    f"Provided output delta time with GraphID {key} cannot be found in the provided SFG."
                )

        if self._schedule._cyclic and self._schedule.schedule_time is None:
            raise ValueError("Scheduling time must be provided when cyclic = True.")

        for resource_type, resource_amount in self._max_resources.items():
            total_exec_time = sum(
                [op.execution_time for op in self._sfg.find_by_type_name(resource_type)]
            )
            if self._schedule.schedule_time is not None:
                resource_lower_bound = ceil(
                    total_exec_time / self._schedule.schedule_time
                )
                if resource_amount < resource_lower_bound:
                    raise ValueError(
                        f"Amount of resource: {resource_type} is not enough to "
                        f"realize schedule for scheduling time: {self._schedule.schedule_time}."
                    )

        alap_schedule = copy.copy(self._schedule)
        alap_schedule._schedule_time = None
        ALAPScheduler().apply_scheduling(alap_schedule)
        alap_start_times = alap_schedule.start_times
        self._schedule.start_times = {}

        if not self._schedule._cyclic and self._schedule.schedule_time:
            if alap_schedule.schedule_time > self._schedule.schedule_time:
                raise ValueError(
                    f"Provided scheduling time {schedule.schedule_time} cannot be reached, "
                    "try to enable the cyclic property or increase the time to at least "
                    f"{alap_schedule.schedule_time}."
                )

        self._remaining_resources = self._max_resources.copy()

        self._remaining_ops = self._sfg.operations
        self._remaining_ops = [op.graph_id for op in self._remaining_ops]

        self._cached_latencies = {
            op_id: self._sfg.find_by_id(op_id).latency for op_id in self._remaining_ops
        }
        self._cached_execution_times = {
            op_id: self._sfg.find_by_id(op_id).execution_time
            for op_id in self._remaining_ops
        }

        self._deadlines = self._calculate_deadlines(alap_start_times)
        self._output_slacks = self._calculate_alap_output_slacks(alap_start_times)
        self._fan_outs = self._calculate_fan_outs(alap_start_times)

        self._schedule.start_times = {}
        self.remaining_reads = self._max_concurrent_reads

        self._current_time = 0
        self._op_laps = {}

        self._remaining_ops = [
            op for op in self._remaining_ops if not op.startswith("dontcare")
        ]
        self._remaining_ops = [
            op for op in self._remaining_ops if not op.startswith("t")
        ]
        self._remaining_ops = [
            op
            for op in self._remaining_ops
            if not (op.startswith("out") and op in self._output_delta_times)
        ]

        if self._input_times:
            self._logger.debug("--- Input placement starting ---")
            for input_id in self._input_times:
                self._schedule.start_times[input_id] = self._input_times[input_id]
                self._op_laps[input_id] = 0
                self._logger.debug(
                    f"   {input_id} time: {self._schedule.start_times[input_id]}"
                )
            self._remaining_ops = [
                elem for elem in self._remaining_ops if not elem.startswith("in")
            ]
            self._logger.debug("--- Input placement completed ---")

        self._logger.debug("--- Operation scheduling starting ---")
        while self._remaining_ops:
            ready_ops_priority_table = self._get_ready_ops_priority_table()
            while ready_ops_priority_table:
                next_op = self._sfg.find_by_id(
                    self._get_next_op_id(ready_ops_priority_table)
                )

                self.remaining_reads -= next_op.input_count

                self._remaining_ops = [
                    op_id for op_id in self._remaining_ops if op_id != next_op.graph_id
                ]

                self._schedule.place_operation(next_op, self._current_time)
                self._op_laps[next_op.graph_id] = (
                    (self._current_time) // self._schedule.schedule_time
                    if self._schedule.schedule_time
                    else 0
                )

                if self._schedule.schedule_time is not None:
                    self._logger.debug(
                        f"  Op: {next_op.graph_id}, time: {self._current_time % self._schedule.schedule_time}"
                    )
                else:
                    self._logger.debug(
                        f"  Op: {next_op.graph_id}, time: {self._current_time}"
                    )

                ready_ops_priority_table = self._get_ready_ops_priority_table()

            self._current_time += 1
            self.remaining_reads = self._max_concurrent_reads

        self._logger.debug("--- Operation scheduling completed ---")

        self._current_time -= 1

        if self._output_delta_times:
            self._handle_outputs()

        if self._schedule.schedule_time is None:
            self._schedule.set_schedule_time(self._schedule.get_max_end_time())

        self._schedule.remove_delays()

        # schedule all dont cares ALAP
        for dc_op in self._sfg.find_by_type_name(DontCare.type_name()):
            dc_op = cast(DontCare, dc_op)
            self._schedule.start_times[dc_op.graph_id] = 0
            self._schedule.move_operation_alap(dc_op.graph_id)

        self._schedule.sort_y_locations_on_start_times()
        self._logger.debug("--- Scheduling completed ---")

    def _get_next_op_id(
        self, ready_ops_priority_table: list[tuple["GraphID", int, ...]]
    ) -> "GraphID":
        def sort_key(item):
            return tuple(
                (item[index] * (-1 if not asc else 1),)
                for index, asc in self._sort_order
            )

        sorted_table = sorted(ready_ops_priority_table, key=sort_key)
        return sorted_table[0][0]

    def _get_ready_ops_priority_table(self) -> list[tuple["GraphID", int, int, int]]:
        ready_ops = [
            op_id
            for op_id in self._remaining_ops
            if self._op_is_schedulable(self._sfg.find_by_id(op_id))
        ]

        return [
            (
                op_id,
                self._deadlines[op_id],
                self._output_slacks[op_id],
                self._fan_outs[op_id],
            )
            for op_id in ready_ops
        ]

    def _calculate_deadlines(
        self, alap_start_times: dict["GraphID", int]
    ) -> dict["GraphID", int]:
        return {
            op_id: start_time + self._cached_latencies[op_id]
            for op_id, start_time in alap_start_times.items()
        }

    def _calculate_alap_output_slacks(
        self, alap_start_times: dict["GraphID", int]
    ) -> dict["GraphID", int]:
        return {op_id: start_time for op_id, start_time in alap_start_times.items()}

    def _calculate_fan_outs(
        self, alap_start_times: dict["GraphID", int]
    ) -> dict["GraphID", int]:
        return {
            op_id: len(self._sfg.find_by_id(op_id).output_signals)
            for op_id, start_time in alap_start_times.items()
        }

    def _op_satisfies_resource_constraints(self, op: "Operation") -> bool:
        if self._schedule.schedule_time is not None:
            time_slot = self._current_time % self._schedule.schedule_time
        else:
            time_slot = self._current_time

        count = 0
        for op_id, start_time in self._schedule.start_times.items():
            if self._schedule.schedule_time is not None:
                start_time = start_time % self._schedule.schedule_time

            if time_slot >= start_time:
                if time_slot < start_time + max(self._cached_execution_times[op_id], 1):
                    if op_id.startswith(op.type_name()):
                        if op.graph_id != op_id:
                            count += 1

        return count < self._remaining_resources[op.type_name()]

    def _op_is_schedulable(self, op: "Operation") -> bool:
        if not self._op_satisfies_resource_constraints(op):
            return False

        op_finish_time = self._current_time + self._cached_latencies[op.graph_id]
        future_ops = [
            self._sfg.find_by_id(item[0])
            for item in self._schedule.start_times.items()
            if item[1] + self._cached_latencies[item[0]] == op_finish_time
        ]

        future_ops_writes = sum([op.input_count for op in future_ops])

        if (
            not op.graph_id.startswith("out")
            and future_ops_writes >= self._max_concurrent_writes
        ):
            return False

        read_counter = 0
        earliest_start_time = 0
        for op_input in op.inputs:
            source_op = op_input.signals[0].source.operation
            if isinstance(source_op, Delay) or isinstance(source_op, DontCare):
                continue

            source_op_graph_id = source_op.graph_id

            if source_op_graph_id in self._remaining_ops:
                return False

            if self._schedule.start_times[source_op_graph_id] != self._current_time - 1:
                # not a direct connection -> memory read required
                read_counter += 1

            if read_counter > self.remaining_reads:
                return False

            if self._schedule.schedule_time is not None:
                proceeding_op_start_time = (
                    self._schedule.start_times.get(source_op_graph_id)
                    + self._op_laps[source_op.graph_id] * self._schedule.schedule_time
                )
                proceeding_op_finish_time = (
                    proceeding_op_start_time
                    + self._cached_latencies[source_op.graph_id]
                )
            else:
                proceeding_op_start_time = self._schedule.start_times.get(
                    source_op_graph_id
                )
                proceeding_op_finish_time = (
                    proceeding_op_start_time
                    + self._cached_latencies[source_op.graph_id]
                )
            earliest_start_time = max(earliest_start_time, proceeding_op_finish_time)

        return earliest_start_time <= self._current_time

    def _handle_outputs(self) -> None:
        self._logger.debug("--- Output placement starting ---")
        if self._schedule._cyclic:
            end = self._schedule.schedule_time
        else:
            end = self._schedule.get_max_end_time()
        for output in self._sfg.find_by_type_name(Output.type_name()):
            output = cast(Output, output)
            if output.graph_id in self._output_delta_times:
                delta_time = self._output_delta_times[output.graph_id]

                new_time = end + delta_time

                if self._schedule._cyclic and self._schedule.schedule_time is not None:
                    self._schedule.place_operation(output, new_time)
                else:
                    self._schedule.start_times[output.graph_id] = new_time

                count = -1
                for op_id, time in self._schedule.start_times.items():
                    if time == new_time and op_id.startswith("out"):
                        count += 1

                self._remaining_resources = self._max_resources
                self._remaining_resources[Output.type_name()] -= count

                self._current_time = new_time
                if not self._op_is_schedulable(output):
                    raise ValueError(
                        "Cannot schedule outputs according to the provided output_delta_times. "
                        f"Failed output: {output.graph_id}, "
                        f"at time: { self._schedule.start_times[output.graph_id]}, "
                        "try relaxing the constraints."
                    )

                modulo_time = (
                    new_time % self._schedule.schedule_time
                    if self._schedule.schedule_time
                    else new_time
                )
                self._logger.debug(f"   {output.graph_id} time: {modulo_time}")
        self._logger.debug("--- Output placement completed ---")

        self._logger.debug("--- Output placement optimization starting ---")
        min_slack = min(
            self._schedule.backward_slack(op.graph_id)
            for op in self._sfg.find_by_type_name(Output.type_name())
        )
        if min_slack > 0:
            for output in self._sfg.find_by_type_name(Output.type_name()):
                if self._schedule._cyclic and self._schedule.schedule_time is not None:
                    self._schedule.move_operation(output.graph_id, -min_slack)
                else:
                    self._schedule.start_times[output.graph_id] = (
                        self._schedule.start_times[output.graph_id] - min_slack
                    )
                new_time = self._schedule.start_times[output.graph_id]
                if (
                    not self._schedule._cyclic
                    and self._schedule.schedule_time is not None
                ):
                    if new_time > self._schedule.schedule_time:
                        raise ValueError(
                            f"Cannot place output {output.graph_id} at time {new_time} "
                            f"for scheduling time {self._schedule.schedule_time}. "
                            "Try to relax the scheduling time, change the output delta times or enable cyclic."
                        )
                self._logger.debug(
                    f"   {output.graph_id} moved {min_slack} time steps backwards to new time {new_time}"
                )
        self._logger.debug("--- Output placement optimization completed ---")
