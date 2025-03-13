import copy
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, cast

import b_asic.logger as logger
from b_asic.core_operations import DontCare, Sink
from b_asic.port import OutputPort
from b_asic.special_operations import Delay, Output
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
        self._initialize_scheduler(schedule)

        if self._input_times:
            self._place_inputs_on_given_times()

        self._schedule_nonrecursive_ops()

        if self._output_delta_times:
            self._handle_outputs()

        if self._schedule.schedule_time is None:
            self._schedule.set_schedule_time(self._schedule.get_max_end_time())
        self._schedule.remove_delays()
        self._handle_dont_cares()
        self._schedule.sort_y_locations_on_start_times()
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
                pair[1]
                for pair in self._cached_latency_offsets[op_id].items()
                if pair[0].startswith("out")
            ]
            deadlines[op_id] = (
                start_time + min(output_offsets) if output_offsets else start_time
            )
        return deadlines

    def _calculate_alap_output_slacks(self) -> dict["GraphID", int]:
        return {
            op_id: start_time for op_id, start_time in self._alap_start_times.items()
        }

    def _calculate_fan_outs(self) -> dict["GraphID", int]:
        return {
            op_id: len(self._sfg.find_by_id(op_id).output_signals)
            for op_id in self._alap_start_times.keys()
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

    def _execution_times_in_time(self, op: "Operation", time: int) -> int:
        count = 0
        for other_op_id, start_time in self._schedule.start_times.items():
            if self._schedule.schedule_time is not None:
                start_time = start_time % self._schedule.schedule_time

            if time >= start_time:
                if time < start_time + max(
                    self._cached_execution_times[other_op_id], 1
                ):
                    if other_op_id.startswith(op.type_name()):
                        if other_op_id != op.graph_id:
                            count += 1
        return count

    def _op_satisfies_resource_constraints(self, op: "Operation") -> bool:
        if self._schedule.schedule_time is not None:
            time_slot = self._current_time % self._schedule.schedule_time
        else:
            time_slot = self._current_time
        count = self._execution_times_in_time(op, time_slot)
        return count < self._remaining_resources[op.type_name()]

    def _op_satisfies_concurrent_writes(self, op: "Operation") -> bool:
        tmp_used_writes = {}
        if not op.graph_id.startswith("out"):
            for i in range(len(op.outputs)):
                output_ready_time = (
                    self._current_time
                    + self._cached_latency_offsets[op.graph_id][f"out{i}"]
                )
                if self._schedule.schedule_time:
                    output_ready_time %= self._schedule.schedule_time

                writes_in_time = 0
                for item in self._schedule.start_times.items():
                    offsets = [
                        offset
                        for port_id, offset in self._cached_latency_offsets[
                            item[0]
                        ].items()
                        if port_id.startswith("out")
                    ]
                    write_times = [item[1] + offset for offset in offsets]
                    writes_in_time += write_times.count(output_ready_time)

                write_time = (
                    self._current_time
                    + self._cached_latency_offsets[op.graph_id][f"out{i}"]
                )
                if self._schedule.schedule_time:
                    write_time %= self._schedule.schedule_time

                if tmp_used_writes.get(write_time):
                    tmp_used_writes[write_time] += 1
                else:
                    tmp_used_writes[write_time] = 1

                if (
                    self._max_concurrent_writes
                    - writes_in_time
                    - tmp_used_writes[write_time]
                    < 0
                ):
                    return False
        return True

    def _op_satisfies_concurrent_reads(self, op: "Operation") -> bool:
        tmp_used_reads = {}
        for i, op_input in enumerate(op.inputs):
            source_op = op_input.signals[0].source.operation
            if isinstance(source_op, Delay) or isinstance(source_op, DontCare):
                continue
            if self._schedule.start_times[source_op.graph_id] != self._current_time - 1:
                input_read_time = (
                    self._current_time
                    + self._cached_latency_offsets[op.graph_id][f"in{i}"]
                )
                if self._schedule.schedule_time:
                    input_read_time %= self._schedule.schedule_time

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

            if isinstance(source_op, Delay) or isinstance(source_op, DontCare):
                continue

            source_op_graph_id = source_op.graph_id

            if source_op_graph_id in self._remaining_ops:
                return False

            if self._schedule.schedule_time is not None:
                available_time = (
                    self._schedule.start_times.get(source_op_graph_id)
                    + self._op_laps[source_op.graph_id] * self._schedule.schedule_time
                    + self._cached_latency_offsets[source_op.graph_id][
                        f"out{source_port.index}"
                    ]
                )
            else:
                available_time = (
                    self._schedule.start_times.get(source_op_graph_id)
                    + self._cached_latency_offsets[source_op.graph_id][
                        f"out{source_port.index}"
                    ]
                )

            required_time = (
                self._current_time
                + self._cached_latency_offsets[op.graph_id][f"in{op_input.index}"]
            )
            if available_time > required_time:
                return False
        return True

    def _op_is_schedulable(self, op: "Operation") -> bool:
        return (
            self._op_satisfies_resource_constraints(op)
            and self._op_satisfies_data_dependencies(op)
            and self._op_satisfies_concurrent_writes(op)
            and self._op_satisfies_concurrent_reads(op)
        )

    def _initialize_scheduler(self, schedule: "Schedule") -> None:
        self._schedule = schedule
        self._sfg = schedule._sfg

        for resource_type in self._max_resources.keys():
            if not self._sfg.find_by_type_name(resource_type):
                raise ValueError(
                    f"Provided max resource of type {resource_type} cannot be found in the provided SFG."
                )

        differing_elems = [
            resource
            for resource in self._sfg.get_used_type_names()
            if resource not in self._max_resources.keys()
            and resource != Delay.type_name()
            and resource != DontCare.type_name()
            and resource != Sink.type_name()
        ]
        for type_name in differing_elems:
            self._max_resources[type_name] = 1

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

        if self._schedule._cyclic and self._schedule.schedule_time is not None:
            iteration_period_bound = self._sfg.iteration_period_bound()
            if self._schedule.schedule_time < iteration_period_bound:
                raise ValueError(
                    f"Provided scheduling time {self._schedule.schedule_time} must be larger or equal to the"
                    f" iteration period bound: {iteration_period_bound}."
                )

        if self._schedule.schedule_time is not None:
            for resource_type, resource_amount in self._max_resources.items():
                if resource_amount < self._sfg.resource_lower_bound(
                    resource_type, self._schedule.schedule_time
                ):
                    raise ValueError(
                        f"Amount of resource: {resource_type} is not enough to "
                        f"realize schedule for scheduling time: {self._schedule.schedule_time}."
                    )

        alap_schedule = copy.copy(self._schedule)
        alap_schedule._schedule_time = None
        ALAPScheduler().apply_scheduling(alap_schedule)
        self._alap_start_times = alap_schedule.start_times
        self._schedule.start_times = {}
        for key in self._schedule._laps.keys():
            self._schedule._laps[key] = 0

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

        self._cached_latency_offsets = {
            op_id: self._sfg.find_by_id(op_id).latency_offsets
            for op_id in self._remaining_ops
        }
        self._cached_execution_times = {
            op_id: self._sfg.find_by_id(op_id).execution_time
            for op_id in self._remaining_ops
        }

        self._deadlines = self._calculate_deadlines()
        self._output_slacks = self._calculate_alap_output_slacks()
        self._fan_outs = self._calculate_fan_outs()

        self._schedule.start_times = {}
        self._used_reads = {0: 0}

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
                    (self._current_time) // self._schedule.schedule_time
                    if self._schedule.schedule_time
                    else 0
                )

                self._log_scheduled_op(next_op)

                prio_table = self._get_priority_table()

            self._current_time += 1
        self._current_time -= 1
        self._logger.debug("--- Non-Recursive Operation scheduling completed ---")

    def _log_scheduled_op(self, next_op: "Operation") -> None:
        if self._schedule.schedule_time is not None:
            self._logger.debug(f"  Op: {next_op.graph_id}, time: {self._current_time}")
        else:
            self._logger.debug(f"  Op: {next_op.graph_id}, time: {self._current_time}")

    def _update_port_reads(self, next_op: "Operation") -> None:
        for i, input_port in enumerate(next_op.inputs):
            source_op = input_port.signals[0].source.operation
            if (
                not isinstance(source_op, DontCare)
                and not isinstance(source_op, Delay)
                and self._schedule.start_times[source_op.graph_id]
                != self._current_time - 1
            ):
                time = (
                    self._current_time
                    + self._cached_latency_offsets[next_op.graph_id][f"in{i}"]
                )
                if self._schedule.schedule_time:
                    time %= self._schedule.schedule_time
                if self._used_reads.get(time):
                    self._used_reads[time] += 1
                else:
                    self._used_reads[time] = 1

    def _place_inputs_on_given_times(self) -> None:
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
                    self._schedule.place_operation(output, new_time, self._op_laps)
                else:
                    self._schedule.start_times[output.graph_id] = new_time

                count = -1
                for op_id, time in self._schedule.start_times.items():
                    if time == new_time and op_id.startswith("out"):
                        count += 1

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
        if min_slack != 0:
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

    def _handle_dont_cares(self) -> None:
        # schedule all dont cares ALAP
        for dc_op in self._sfg.find_by_type_name(DontCare.type_name()):
            self._schedule.start_times[dc_op.graph_id] = 0
            self._schedule.place_operation(
                dc_op, self._schedule.forward_slack(dc_op.graph_id), self._op_laps
            )


class RecursiveListScheduler(ListScheduler):
    def __init__(
        self,
        sort_order: tuple[tuple[int, bool], ...],
        max_resources: dict[TypeName, int] | None = None,
        max_concurrent_reads: int | None = None,
        max_concurrent_writes: int | None = None,
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
    ) -> None:
        super().__init__(
            sort_order=sort_order,
            max_resources=max_resources,
            max_concurrent_reads=max_concurrent_reads,
            max_concurrent_writes=max_concurrent_writes,
            input_times=input_times,
            output_delta_times=output_delta_times,
        )

    def apply_scheduling(self, schedule: "Schedule") -> None:
        self._logger.debug("--- Scheduler initializing ---")
        self._initialize_scheduler(schedule)

        if self._input_times:
            self._place_inputs_on_given_times()

        loops = self._sfg.loops
        if loops:
            self._schedule_recursive_ops(loops)

        self._schedule_nonrecursive_ops()

        if self._output_delta_times:
            self._handle_outputs()

        if self._schedule.schedule_time is None:
            self._schedule.set_schedule_time(self._schedule.get_max_end_time())
        self._schedule.remove_delays()
        self._handle_dont_cares()
        self._schedule.sort_y_locations_on_start_times()
        self._logger.debug("--- Scheduling completed ---")

    def _get_recursive_ops(self, loops: list[list["GraphID"]]) -> list["GraphID"]:
        recursive_ops = []
        seen = []
        for loop in loops:
            for op_id in loop:
                if op_id not in seen:
                    if not isinstance(self._sfg.find_by_id(op_id), Delay):
                        recursive_ops.append(op_id)
                        seen.append(op_id)
        return recursive_ops

    def _recursive_op_satisfies_data_dependencies(self, op: "Operation") -> bool:
        for input_port_index, op_input in enumerate(op.inputs):
            source_port = source_op = op_input.signals[0].source
            source_op = source_port.operation
            if isinstance(source_op, Delay) or isinstance(source_op, DontCare):
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

    def _schedule_recursive_ops(self, loops: list[list["GraphID"]]) -> None:
        saved_sched_time = self._schedule.schedule_time
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
                source_latency = self._cached_latency_offsets[source_op.graph_id][
                    f"out{source_port.index}"
                ]
                op_sched_time = max(op_sched_time, source_start_time + source_latency)

            exec_count = self._execution_times_in_time(op, op_sched_time)
            while exec_count >= self._remaining_resources[op.type_name()]:
                op_sched_time += 1
                exec_count = self._execution_times_in_time(op, op_sched_time)

            self._schedule.place_operation(op, op_sched_time, self._op_laps)
            self._op_laps[op.graph_id] = 0
            self._logger.debug(f"   Op: {op.graph_id} time: {op_sched_time}")
            self._remaining_recursive_ops.remove(op.graph_id)
            self._remaining_ops.remove(op.graph_id)
            prio_table = self._get_recursive_priority_table()

        self._schedule._schedule_time = self._schedule.get_max_end_time()
        if (
            saved_sched_time is not None
            and saved_sched_time < self._schedule.schedule_time
        ):
            raise ValueError(
                f"Requested schedule time {saved_sched_time} cannot be reached, increase to {self._schedule.schedule_time} or assign more resources."
            )
        self._logger.debug("--- Scheduling of recursive loops completed ---")

    def _get_next_recursive_op(
        self, priority_table: list[tuple["GraphID", int, ...]]
    ) -> "GraphID":
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
                # spotted a recursive operation -> check if ok
                op_available_time = (
                    self._current_time + op.latency_offsets[f"out{output_port.index}"]
                )
                usage_time = (
                    self._schedule.start_times[destination_op.graph_id]
                    + self._schedule.schedule_time
                    * self._schedule.laps[output_port.signals[0].graph_id]
                )
                if op_available_time > usage_time:
                    # constraint is not okay, move all recursive operations one lap by pipelining
                    # across the non-recursive to recursive edge
                    self._pipeline_input_to_recursive_sections()

        for op_input in op.inputs:
            source_port = op_input.signals[0].source
            source_op = source_port.operation
            if isinstance(source_op, Delay) or isinstance(source_op, DontCare):
                continue
            if source_op.graph_id in self._remaining_ops:
                return False
            if self._schedule.schedule_time is not None:
                available_time = (
                    self._schedule.start_times.get(source_op.graph_id)
                    + self._op_laps[source_op.graph_id] * self._schedule.schedule_time
                    + self._cached_latency_offsets[source_op.graph_id][
                        f"out{source_port.index}"
                    ]
                )
            else:
                available_time = (
                    self._schedule.start_times.get(source_op.graph_id)
                    + self._cached_latency_offsets[source_op.graph_id][
                        f"out{source_port.index}"
                    ]
                )
            required_time = (
                self._current_time
                + self._cached_latency_offsets[op.graph_id][f"in{op_input.index}"]
            )
            if available_time > required_time:
                return False
        return True
