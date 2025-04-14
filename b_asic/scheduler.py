import copy
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import TYPE_CHECKING, cast

import b_asic.logger as logger
from b_asic.core_operations import DontCare, Sink
from b_asic.port import OutputPort
from b_asic.special_operations import Delay, Input, Output
from b_asic.types import TypeName

if TYPE_CHECKING:
    from b_asic.operation import Operation
    from b_asic.schedule import Schedule
    from b_asic.types import GraphID


class Scheduler(ABC):
    def __init__(
        self,
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
        sort_y_direction: bool = True,
    ):
        self._logger = logger.getLogger("scheduler")
        self._op_laps = {}

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

        self._sort_y_direction = sort_y_direction

    @abstractmethod
    def apply_scheduling(self, schedule: "Schedule") -> None:
        """Applies the scheduling algorithm on the given Schedule.

        Parameters
        ----------
        schedule : Schedule
            Schedule to apply the scheduling algorithm on.
        """
        raise NotImplementedError

    def _place_inputs_on_given_times(self) -> None:
        self._logger.debug("--- Input placement starting ---")
        for input_id in self._input_times:
            self._schedule.start_times[input_id] = self._input_times[input_id]
            self._op_laps[input_id] = 0
            self._logger.debug(
                f"   {input_id} time: {self._schedule.start_times[input_id]}"
            )
        self._logger.debug("--- Input placement completed ---")

    def _place_outputs_asap(
        self, schedule: "Schedule", non_schedulable_ops: list["GraphID"] | None = []
    ) -> None:
        for output in schedule._sfg.find_by_type(Output):
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

    def _place_outputs_on_given_times(self) -> None:
        self._logger.debug("--- Output placement starting ---")
        if self._schedule._cyclic and isinstance(self, ListScheduler):
            end = self._schedule._schedule_time
        else:
            end = self._schedule.get_max_end_time()
        for output in self._sfg.find_by_type(Output):
            output = cast(Output, output)
            if output.graph_id in self._output_delta_times:
                delta_time = self._output_delta_times[output.graph_id]

                new_time = end + delta_time

                if (
                    self._schedule._cyclic
                    and self._schedule._schedule_time is not None
                    and isinstance(self, ListScheduler)
                ):
                    self._schedule.place_operation(output, new_time, self._op_laps)
                else:
                    self._schedule.start_times[output.graph_id] = new_time

                count = -1
                for op_id, time in self._schedule.start_times.items():
                    if time == new_time and isinstance(
                        self._sfg.find_by_id(op_id), Output
                    ):
                        count += 1

                modulo_time = (
                    new_time % self._schedule._schedule_time
                    if self._schedule._schedule_time
                    else new_time
                )
                self._logger.debug(f"   {output.graph_id} time: {modulo_time}")
        self._logger.debug("--- Output placement completed ---")

        self._logger.debug("--- Output placement optimization starting ---")
        min_slack = min(
            self._schedule.backward_slack(op.graph_id)
            for op in self._sfg.find_by_type(Output)
        )
        if min_slack != 0:
            for output in self._sfg.find_by_type(Output):
                if self._schedule._cyclic and self._schedule._schedule_time is not None:
                    self._schedule.move_operation(output.graph_id, -min_slack)
                else:
                    self._schedule.start_times[output.graph_id] = (
                        self._schedule.start_times[output.graph_id] - min_slack
                    )
                new_time = self._schedule.start_times[output.graph_id]
                if (
                    not self._schedule._cyclic
                    and self._schedule._schedule_time is not None
                    and new_time > self._schedule._schedule_time
                ):
                    raise ValueError(
                        f"Cannot place output {output.graph_id} at time {new_time} "
                        f"for scheduling time {self._schedule._schedule_time}. "
                        "Try to relax the scheduling time, change the output delta times or enable cyclic."
                    )
                self._logger.debug(
                    f"   {output.graph_id} moved {min_slack} time steps backwards to new time {new_time}"
                )
        self._logger.debug("--- Output placement optimization completed ---")


class ASAPScheduler(Scheduler):
    """Scheduler that implements the as-soon-as-possible (ASAP) algorithm."""

    def apply_scheduling(self, schedule: "Schedule") -> None:
        """Applies the scheduling algorithm on the given Schedule.

        Parameters
        ----------
        schedule : Schedule
            Schedule to apply the scheduling algorithm on.
        """
        self._schedule = schedule
        self._sfg = schedule._sfg
        prec_list = schedule.sfg.get_precedence_list()
        if len(prec_list) < 2:
            raise ValueError("Empty signal flow graph cannot be scheduled.")

        if self._input_times:
            self._place_inputs_on_given_times()

        # handle the first set in precedence graph (input and delays)
        non_schedulable_ops = []
        for outport in prec_list[0]:
            operation = outport.operation
            if operation.type_name() == Delay.type_name():
                non_schedulable_ops.append(operation.graph_id)
            elif operation.graph_id not in self._input_times:
                schedule.start_times[operation.graph_id] = 0

        # handle the remaining sets
        for outports in prec_list[1:]:
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

        self._place_outputs_asap(schedule, non_schedulable_ops)
        if self._input_times:
            self._place_outputs_on_given_times()
        schedule.remove_delays()

        max_end_time = schedule.get_max_end_time()

        if schedule._schedule_time is None:
            schedule.set_schedule_time(max_end_time)
        elif schedule._schedule_time < max_end_time:
            raise ValueError(f"Too short schedule time. Minimum is {max_end_time}.")

        if self._sort_y_direction:
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
        self._schedule = schedule
        self._sfg = schedule._sfg
        ASAPScheduler(
            self._input_times,
            self._output_delta_times,
            False,
        ).apply_scheduling(schedule)
        self._op_laps = {}

        if self._output_delta_times:
            self._place_outputs_on_given_times()

        for output in schedule.sfg.find_by_type(Input):
            output = cast(Output, output)
            self._op_laps[output.graph_id] = 0

        # move all outputs ALAP before operations
        for output in schedule.sfg.find_by_type(Output):
            output = cast(Output, output)
            self._op_laps[output.graph_id] = 0
            if output.graph_id in self._output_delta_times:
                continue
            schedule.move_operation_alap(output.graph_id)

        # move all operations ALAP
        for step in reversed(schedule.sfg.get_precedence_list()):
            for outport in step:
                op = outport.operation
                if not isinstance(op, Delay) and op.graph_id not in self._input_times:
                    new_unwrapped_start_time = schedule.start_times[
                        op.graph_id
                    ] + schedule.forward_slack(op.graph_id)
                    self._op_laps[op.graph_id] = (
                        new_unwrapped_start_time // schedule._schedule_time
                    )
                    schedule.move_operation_alap(op.graph_id)

        # adjust the scheduling time if empty time slots have appeared in the start
        slack = min(schedule.start_times.values())
        for op_id in schedule.start_times:
            schedule.move_operation(op_id, -slack)
        schedule.set_schedule_time(schedule._schedule_time - slack)

        if self._sort_y_direction:
            schedule.sort_y_locations_on_start_times()


class ListScheduler(Scheduler):
    """
    List-based scheduler that schedules the operations while complying to the given
    constraints.

    Parameters
    ----------
    sort_order : tuple[tuple[int, bool]]
        Specifies which columns in the priority table to sort on and in
        which order, where True is ascending order.
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
    """

    def __init__(
        self,
        sort_order: tuple[tuple[int, bool], ...],
        max_resources: dict[TypeName, int] | None = None,
        max_concurrent_reads: int | None = None,
        max_concurrent_writes: int | None = None,
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
        sort_y_locations: bool = True,
    ) -> None:
        super().__init__(input_times, output_delta_times, sort_y_locations)
        self._sort_order = sort_order

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

        if max_concurrent_reads is not None:
            if not isinstance(max_concurrent_reads, int):
                raise ValueError("Provided max_concurrent_reads must be an integer.")
            if max_concurrent_reads <= 0:
                raise ValueError("Provided max_concurrent_reads must be larger than 0.")
        self._max_concurrent_reads = max_concurrent_reads or 0

        if max_concurrent_writes is not None:
            if not isinstance(max_concurrent_writes, int):
                raise ValueError("Provided max_concurrent_writes must be an integer.")
            if max_concurrent_writes <= 0:
                raise ValueError(
                    "Provided max_concurrent_writes must be larger than 0."
                )
        self._max_concurrent_writes = max_concurrent_writes or 0

    def apply_scheduling(self, schedule: "Schedule") -> None:
        """Applies the scheduling algorithm on the given Schedule.

        Parameters
        ----------
        schedule : Schedule
            Schedule to apply the scheduling algorithm on.
        """
        self._logger.debug("--- Scheduler initializing ---")
        self._initialize_scheduler(schedule)

        if self._sfg.loops and self._schedule.cyclic:
            raise ValueError(
                "ListScheduler does not support cyclic scheduling of "
                "recursive algorithms. Use RecursiveListScheduler instead."
            )

        if self._input_times:
            self._place_inputs_on_given_times()
            self._remaining_ops = [
                op_id for op_id in self._remaining_ops if op_id not in self._input_times
            ]

        self._schedule_nonrecursive_ops()

        if self._output_delta_times:
            self._place_outputs_on_given_times()

        if self._schedule._schedule_time is None:
            self._schedule.set_schedule_time(self._schedule.get_max_end_time())
        self._schedule.remove_delays()
        self._handle_dont_cares()
        if self._sort_y_direction:
            schedule.sort_y_locations_on_start_times()
        self._logger.debug("--- Scheduling completed ---")

    def _get_next_op_id(
        self, priority_table: list[tuple["GraphID", int, ...]]
    ) -> "GraphID":
        def sort_key(item):
            return tuple(
                (item[index] * (-1 if not asc else 1),)
                for index, asc in self._sort_order
            )

        sorted_table = sorted(priority_table, key=sort_key)
        return sorted_table[0][0]

    def _get_priority_table(self) -> list[tuple["GraphID", int, int, int]]:
        ready_ops = [
            op_id
            for op_id in self._remaining_ops
            if self._op_is_schedulable(self._sfg.find_by_id(op_id))
        ]
        memory_reads = self._calculate_memory_reads(ready_ops)

        return [
            (
                op_id,
                self._deadlines[op_id],
                self._output_slacks[op_id],
                self._fan_outs[op_id],
                memory_reads[op_id],
            )
            for op_id in ready_ops
        ]

    def _calculate_deadlines(self) -> dict["GraphID", int]:
        deadlines = {}
        for op_id, start_time in self._alap_start_times.items():
            output_offsets = [
                output.latency_offset for output in self._sfg.find_by_id(op_id).outputs
            ]
            start_time += self._alap_op_laps[op_id] * self._alap_schedule_time
            deadlines[op_id] = start_time + min(output_offsets, default=0)
        return deadlines

    def _calculate_alap_output_slacks(self) -> dict["GraphID", int]:
        return {
            op_id: start_time + self._alap_op_laps[op_id] * self._alap_schedule_time
            for op_id, start_time in self._alap_start_times.items()
        }

    def _calculate_fan_outs(self) -> dict["GraphID", int]:
        return {
            op_id: len(self._sfg.find_by_id(op_id).output_signals)
            for op_id in self._alap_start_times
        }

    def _calculate_memory_reads(
        self, ready_ops: list["GraphID"]
    ) -> dict["GraphID", int]:
        op_reads = {}
        for op_id in ready_ops:
            reads = 0
            for op_input in self._sfg.find_by_id(op_id).inputs:
                source_op = op_input.signals[0].source.operation
                if isinstance(source_op, DontCare):
                    continue
                if isinstance(source_op, Delay):
                    reads += 1
                    continue
                if (
                    self._schedule.start_times[source_op.graph_id]
                    != self._current_time - 1
                ):
                    reads += 1
            op_reads[op_id] = reads
        return op_reads

    def _execution_times_in_time(self, op_type: "Operation", time: int) -> int:
        count = 0
        for other_op_id, start_time in self._schedule.start_times.items():
            if self._schedule._schedule_time is not None:
                start_time = start_time % self._schedule._schedule_time
            if (
                time >= start_time
                and time
                < start_time + max(self._cached_execution_times[other_op_id], 1)
                and isinstance(self._sfg.find_by_id(other_op_id), op_type)
            ):
                count += 1
        return count

    def _op_satisfies_resource_constraints(self, op: "Operation") -> bool:
        if self._schedule._schedule_time is not None:
            time_slot = self._current_time % self._schedule._schedule_time
        else:
            time_slot = self._current_time
        count = self._cached_execution_times_in_time[op.type_name()][time_slot]
        return count < self._remaining_resources[op.type_name()]

    def _op_satisfies_concurrent_writes(self, op: "Operation") -> bool:
        if self._max_concurrent_writes:
            tmp_used_writes = {}
            if not isinstance(op, Output):
                for output_port in op.outputs:

                    output_ready_time = self._current_time + output_port.latency_offset
                    if self._schedule._schedule_time:
                        output_ready_time %= self._schedule._schedule_time

                    writes_in_time = 0
                    for item in self._schedule.start_times.items():
                        offsets = [
                            output.latency_offset
                            for output in self._sfg.find_by_id(item[0]).outputs
                        ]
                        write_times = [item[1] + offset for offset in offsets]
                        writes_in_time += write_times.count(output_ready_time)

                    if tmp_used_writes.get(output_ready_time):
                        tmp_used_writes[output_ready_time] += 1
                    else:
                        tmp_used_writes[output_ready_time] = 1

                    if (
                        self._max_concurrent_writes
                        - writes_in_time
                        - tmp_used_writes[output_ready_time]
                        < 0
                    ):
                        return False
        return True

    def _op_satisfies_concurrent_reads(self, op: "Operation") -> bool:
        if self._max_concurrent_reads:
            tmp_used_reads = {}
            for i, op_input in enumerate(op.inputs):
                source_op = op_input.signals[0].source.operation
                if isinstance(source_op, (Delay, DontCare)):
                    continue
                if (
                    self._schedule.start_times[source_op.graph_id]
                    != self._current_time - 1
                ):
                    input_read_time = self._current_time + op_input.latency_offset
                    if self._schedule._schedule_time:
                        input_read_time %= self._schedule._schedule_time

                    if tmp_used_reads.get(input_read_time):
                        tmp_used_reads[input_read_time] += 1
                    else:
                        tmp_used_reads[input_read_time] = 1

                    prev_used = self._used_reads.get(input_read_time) or 0
                    if (
                        self._max_concurrent_reads
                        < prev_used + tmp_used_reads[input_read_time]
                    ):
                        return False
        return True

    def _op_satisfies_data_dependencies(self, op: "Operation") -> bool:
        for op_input in op.inputs:
            source_port = op_input.signals[0].source
            source_op = source_port.operation

            if isinstance(source_op, (Delay, DontCare)):
                continue

            if source_op.graph_id in self._remaining_ops:
                return False

            if self._schedule._schedule_time is not None:
                available_time = (
                    self._schedule.start_times[source_op.graph_id]
                    + self._op_laps[source_op.graph_id] * self._schedule._schedule_time
                    + source_port.latency_offset
                )
            else:
                available_time = (
                    self._schedule.start_times[source_op.graph_id]
                    + source_port.latency_offset
                )

            required_time = self._current_time + op_input.latency_offset
            if available_time > required_time:
                return False
        return True

    def _op_is_schedulable(self, op: "Operation") -> bool:
        return (
            self._op_satisfies_data_dependencies(op)
            and self._op_satisfies_resource_constraints(op)
            and self._op_satisfies_concurrent_writes(op)
            and self._op_satisfies_concurrent_reads(op)
        )

    def _initialize_scheduler(self, schedule: "Schedule") -> None:
        self._schedule = schedule
        self._sfg = schedule._sfg

        for resource_type in self._max_resources:
            if not self._sfg.find_by_type_name(resource_type):
                raise ValueError(
                    f"Provided max resource of type {resource_type} cannot be found in the provided SFG."
                )

        differing_elems = [
            resource
            for resource in self._sfg.get_used_type_names()
            if resource not in self._max_resources
            and resource != Delay.type_name()
            and resource != DontCare.type_name()
            and resource != Sink.type_name()
        ]
        for type_name in differing_elems:
            self._max_resources[type_name] = 1

        for key in self._input_times:
            if self._sfg.find_by_id(key) is None:
                raise ValueError(
                    f"Provided input time with GraphID {key} cannot be found in the provided SFG."
                )

        for key in self._output_delta_times:
            if self._sfg.find_by_id(key) is None:
                raise ValueError(
                    f"Provided output delta time with GraphID {key} cannot be found in the provided SFG."
                )

        if self._schedule._cyclic and self._schedule._schedule_time is not None:
            iteration_period_bound = self._sfg.iteration_period_bound()
            if self._schedule._schedule_time < iteration_period_bound:
                raise ValueError(
                    f"Provided scheduling time {self._schedule._schedule_time} must be larger or equal to the"
                    f" iteration period bound: {iteration_period_bound}."
                )

        if self._schedule._schedule_time is not None:
            for resource_type, resource_amount in self._max_resources.items():
                if resource_amount < self._sfg.resource_lower_bound(
                    resource_type, self._schedule._schedule_time
                ):
                    raise ValueError(
                        f"Amount of resource: {resource_type} is not enough to "
                        f"realize schedule for scheduling time: {self._schedule._schedule_time}."
                    )

        alap_schedule = copy.copy(self._schedule)
        alap_schedule._schedule_time = None
        alap_scheduler = ALAPScheduler(
            self._input_times, self._output_delta_times, False
        )
        alap_scheduler.apply_scheduling(alap_schedule)
        self._alap_start_times = alap_schedule.start_times
        self._alap_op_laps = alap_scheduler._op_laps
        self._alap_schedule_time = alap_schedule._schedule_time
        self._schedule.start_times = {}
        for key in self._schedule._laps:
            self._schedule._laps[key] = 0

        if (
            not self._schedule._cyclic
            and self._schedule.schedule_time
            and alap_schedule.schedule_time > self._schedule.schedule_time
        ):
            raise ValueError(
                f"Provided scheduling time {schedule.schedule_time} cannot be reached, "
                "try to enable the cyclic property or increase the time to at least "
                f"{alap_schedule.schedule_time}."
            )

        self._remaining_resources = self._max_resources.copy()

        self._remaining_ops = [op.graph_id for op in self._sfg.operations]
        self._cached_execution_times = {
            op_id: self._sfg.find_by_id(op_id).execution_time
            for op_id in self._remaining_ops
        }
        self._cached_execution_times_in_time = {
            op_type: defaultdict(int) for op_type in self._sfg.get_used_type_names()
        }
        self._remaining_ops = [
            op_id
            for op_id in self._remaining_ops
            if not isinstance(self._sfg.find_by_id(op_id), DontCare)
        ]
        self._remaining_ops = [
            op_id
            for op_id in self._remaining_ops
            if not isinstance(self._sfg.find_by_id(op_id), Delay)
        ]
        self._remaining_ops = [
            op_id
            for op_id in self._remaining_ops
            if not (
                isinstance(self._sfg.find_by_id(op_id), Output)
                and op_id in self._output_delta_times
            )
        ]

        for op_id in self._remaining_ops:
            if self._sfg.find_by_id(op_id).execution_time is None:
                raise ValueError(
                    "All operations in the SFG must have a specified execution time. "
                    f"Missing operation: {op_id}."
                )

        self._deadlines = self._calculate_deadlines()
        self._output_slacks = self._calculate_alap_output_slacks()
        self._fan_outs = self._calculate_fan_outs()

        self._schedule.start_times = {}
        self._used_reads = {0: 0}

        self._current_time = 0

    def _schedule_nonrecursive_ops(self) -> None:
        self._logger.debug("--- Non-Recursive Operation scheduling starting ---")
        while self._remaining_ops:
            prio_table = self._get_priority_table()
            while prio_table:
                next_op = self._sfg.find_by_id(self._get_next_op_id(prio_table))

                self._update_port_reads(next_op)

                self._remaining_ops = [
                    op_id for op_id in self._remaining_ops if op_id != next_op.graph_id
                ]

                self._schedule.place_operation(
                    next_op, self._current_time, self._op_laps
                )
                self._op_laps[next_op.graph_id] = (
                    (self._current_time) // self._schedule._schedule_time
                    if self._schedule._schedule_time
                    else 0
                )

                for i in range(max(1, next_op.execution_time)):
                    time_slot = (
                        (self._current_time + i) % self._schedule._schedule_time
                        if self._schedule._schedule_time
                        else self._current_time
                    )
                    self._cached_execution_times_in_time[next_op.type_name()][
                        time_slot
                    ] += 1

                self._log_scheduled_op(next_op)

                prio_table = self._get_priority_table()

            self._current_time += 1
        self._current_time -= 1
        self._logger.debug("--- Non-Recursive Operation scheduling completed ---")

    def _log_scheduled_op(self, next_op: "Operation") -> None:
        if self._schedule._schedule_time is not None:
            self._logger.debug(f"  Op: {next_op.graph_id}, time: {self._current_time}")
        else:
            self._logger.debug(f"  Op: {next_op.graph_id}, time: {self._current_time}")

    def _update_port_reads(self, next_op: "Operation") -> None:
        for input_port in next_op.inputs:
            source_op = input_port.signals[0].source.operation
            if (
                not isinstance(source_op, DontCare)
                and not isinstance(source_op, Delay)
                and self._schedule.start_times[source_op.graph_id]
                != self._current_time - 1
            ):
                time = self._current_time + input_port.latency_offset
                if self._schedule._schedule_time:
                    time %= self._schedule._schedule_time

                if self._used_reads.get(time):
                    self._used_reads[time] += 1
                else:
                    self._used_reads[time] = 1

    def _handle_dont_cares(self) -> None:
        # schedule all dont cares ALAP
        for dc_op in self._sfg.find_by_type(DontCare):
            self._schedule.start_times[dc_op.graph_id] = 0
            self._schedule.place_operation(
                dc_op, self._schedule.forward_slack(dc_op.graph_id), self._op_laps
            )


class RecursiveListScheduler(ListScheduler):
    def __init__(
        self,
        sort_order: tuple[tuple[int, bool], ...],
        max_resources: dict[TypeName, int] | None = None,
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
    ) -> None:
        super().__init__(
            sort_order=sort_order,
            max_resources=max_resources,
            input_times=input_times,
            output_delta_times=output_delta_times,
        )

    def apply_scheduling(self, schedule: "Schedule") -> None:
        self._logger.debug("--- Scheduler initializing ---")
        self._initialize_scheduler(schedule)

        if self._input_times:
            self._place_inputs_on_given_times()
            self._remaining_ops = [
                op_id for op_id in self._remaining_ops if op_id not in self._input_times
            ]

        loops = self._sfg.loops
        if loops:
            self._schedule_recursive_ops(loops)

        self._schedule_nonrecursive_ops()

        if self._output_delta_times:
            self._place_outputs_on_given_times()

        if self._schedule._schedule_time is None:
            self._schedule.set_schedule_time(self._schedule.get_max_end_time())
        period_bound = self._schedule._sfg.iteration_period_bound()
        self._schedule.remove_delays()
        if loops:
            self._retime_ops(period_bound)
        self._handle_dont_cares()
        if self._sort_y_direction:
            schedule.sort_y_locations_on_start_times()
        self._logger.debug("--- Scheduling completed ---")

    def _get_recursive_ops(self, loops: list[list["GraphID"]]) -> list["GraphID"]:
        recursive_ops = []
        for loop in loops:
            for op_id in loop:
                if op_id not in recursive_ops and not isinstance(
                    self._sfg.find_by_id(op_id), Delay
                ):
                    recursive_ops.append(op_id)
        return recursive_ops

    def _recursive_op_satisfies_data_dependencies(self, op: "Operation") -> bool:
        for op_input in op.inputs:
            source_port = source_op = op_input.signals[0].source
            source_op = source_port.operation
            if isinstance(source_op, (Delay, DontCare)):
                continue
            if (
                source_op.graph_id in self._recursive_ops
                and source_op.graph_id in self._remaining_ops
            ):
                return False
        return True

    def _get_recursive_priority_table(self):
        ready_ops = [
            op_id
            for op_id in self._remaining_recursive_ops
            if self._recursive_op_satisfies_data_dependencies(
                self._sfg.find_by_id(op_id)
            )
        ]
        return [(op_id, self._deadlines[op_id]) for op_id in ready_ops]

    def _retime_ops(self, period_bound: int) -> None:
        # calculate the time goal
        time_goal = period_bound
        for type_name, amount_of_resource in self._max_resources.items():
            if type_name in ("out", "in"):
                continue
            time_required = self._schedule._sfg.resource_lower_bound(
                type_name, time_goal
            )
            while (
                self._schedule._sfg.resource_lower_bound(type_name, time_required)
                > amount_of_resource
            ):
                time_required += 1
            time_goal = max(time_goal, time_required)

        # retiming loop
        time_out_counter = 100
        while self._schedule._schedule_time > time_goal and time_out_counter > 0:
            sorted_op_ids = sorted(
                self._schedule._start_times,
                key=self._schedule._start_times.get,
                reverse=True,
            )
            # move all operations forward to the next valid step and check if period can be reduced
            for op_id in sorted_op_ids:
                op = self._schedule._sfg.find_by_id(op_id)
                if self._schedule.forward_slack(op_id):
                    delta = 1
                    new_time = (
                        self._schedule._start_times[op_id] + delta
                    ) % self._schedule.schedule_time
                    exec_count = self._execution_times_in_time(type(op), new_time)
                    while exec_count >= self._remaining_resources[op.type_name()]:
                        delta += 1
                        new_time = (
                            self._schedule._start_times[op_id] + delta
                        ) % self._schedule.schedule_time
                        exec_count = self._execution_times_in_time(type(op), new_time)
                    if delta > self._schedule.forward_slack(op_id):
                        continue
                    self._schedule.move_operation(op_id, delta)

                # adjust time if a gap exists on the right side of the schedule
                self._schedule._schedule_time = min(
                    self._schedule._schedule_time, self._schedule.get_max_end_time()
                )

                # adjust time if a gap exists on the left side of the schedule
                slack = min(self._schedule._start_times.values())
                for other_op_id in sorted_op_ids:
                    op = self._schedule._sfg.find_by_id(other_op_id)
                    max_end_time = 0
                    op_start_time = self._schedule._start_times[other_op_id]
                    for outport in op.outputs:
                        max_end_time = max(
                            max_end_time,
                            op_start_time + cast(int, outport.latency_offset),
                        )
                    if max_end_time > self._schedule._schedule_time:
                        slack = min(slack, self._schedule.forward_slack(other_op_id))
                for op_id in self._schedule._start_times:
                    self._schedule._start_times[op_id] -= slack
                self._schedule._schedule_time = self._schedule._schedule_time - slack

            time_out_counter -= 1

    def _schedule_recursive_ops(self, loops: list[list["GraphID"]]) -> None:
        saved_sched_time = self._schedule._schedule_time
        self._schedule._schedule_time = None

        self._logger.debug("--- Scheduling of recursive loops starting ---")
        self._recursive_ops = self._get_recursive_ops(loops)
        self._remaining_recursive_ops = self._recursive_ops.copy()
        prio_table = self._get_recursive_priority_table()
        while prio_table:
            op = self._get_next_recursive_op(prio_table)
            op_sched_time = 0
            for input_port in op.inputs:
                source_port = input_port.signals[0].source
                source_op = source_port.operation
                if isinstance(source_op, Delay):
                    continue
                source_start_time = self._schedule.start_times.get(source_op.graph_id)
                if source_start_time is None:
                    continue
                op_sched_time = max(
                    op_sched_time, source_start_time + source_port.latency_offset
                )

            exec_count = self._execution_times_in_time(type(op), op_sched_time)
            while exec_count >= self._remaining_resources[op.type_name()]:
                op_sched_time += 1
                exec_count = self._execution_times_in_time(type(op), op_sched_time)

            self._schedule.place_operation(op, op_sched_time, self._op_laps)
            self._op_laps[op.graph_id] = 0
            self._logger.debug(f"   Op: {op.graph_id} time: {op_sched_time}")
            self._remaining_recursive_ops.remove(op.graph_id)
            self._remaining_ops.remove(op.graph_id)

            for i in range(max(1, op.execution_time)):
                time_slot = (
                    (self._current_time + i) % self._schedule._schedule_time
                    if self._schedule._schedule_time
                    else self._current_time
                )
                self._cached_execution_times_in_time[op.type_name()][time_slot] += 1

            prio_table = self._get_recursive_priority_table()

        self._schedule._schedule_time = self._schedule.get_max_end_time()

        if saved_sched_time and saved_sched_time > self._schedule._schedule_time:
            self._schedule._schedule_time = saved_sched_time
        self._logger.debug("--- Scheduling of recursive loops completed ---")

    def _get_next_recursive_op(
        self, priority_table: list[tuple["GraphID", int, ...]]
    ) -> "Operation":
        sorted_table = sorted(priority_table, key=lambda row: row[1])
        return self._sfg.find_by_id(sorted_table[0][0])

    def _pipeline_input_to_recursive_sections(self) -> None:
        for op_id in self._recursive_ops:
            op = self._sfg.find_by_id(op_id)
            for input_port in op.inputs:
                signal = input_port.signals[0]
                source_op = signal.source.operation
                if (
                    not isinstance(source_op, Delay)
                    and source_op.graph_id not in self._recursive_ops
                ):
                    # non-recursive to recursive edge found -> pipeline
                    self._schedule.laps[signal.graph_id] += 1

    def _op_satisfies_data_dependencies(self, op: "Operation") -> bool:
        for output_port in op.outputs:
            destination_port = output_port.signals[0].destination
            destination_op = destination_port.operation
            if destination_op.graph_id not in self._remaining_ops:
                if isinstance(destination_op, Delay):
                    continue
                # spotted a recursive operation -> check if ok
                op_available_time = (
                    self._current_time + op.latency_offsets[f"out{output_port.index}"]
                )
                usage_time = (
                    self._schedule.start_times[destination_op.graph_id]
                    + self._schedule._schedule_time
                    * self._schedule.laps[output_port.signals[0].graph_id]
                )
                if op_available_time > usage_time:
                    # constraint is not okay, move all recursive operations one lap by pipelining
                    # across the non-recursive to recursive edge
                    self._pipeline_input_to_recursive_sections()

        for op_input in op.inputs:
            source_port = op_input.signals[0].source
            source_op = source_port.operation
            if isinstance(source_op, (Delay, DontCare)):
                continue
            if source_op.graph_id in self._remaining_ops:
                return False
            if self._schedule._schedule_time is not None:
                available_time = (
                    self._schedule.start_times.get(source_op.graph_id)
                    + self._op_laps[source_op.graph_id] * self._schedule._schedule_time
                    + source_port.latency_offset
                )
            else:
                available_time = (
                    self._schedule.start_times.get(source_op.graph_id)
                    + source_port.latency_offset
                )
            required_time = self._current_time + op_input.latency_offset
            if available_time > required_time:
                return False
        return True
