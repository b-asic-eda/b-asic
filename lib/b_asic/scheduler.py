"""
B-ASIC Scheduler Module.

Contains classes for automatic scheduling of SFGs.
"""

import copy
import math
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from typing import TYPE_CHECKING, cast

import pulp

import b_asic.logger
from b_asic._ilp_utils import _solve_ilp_problem
from b_asic.operation import Operation
from b_asic.port import InputPort, OutputPort
from b_asic.special_operations import Delay, Input, Output
from b_asic.types import TypeName
from b_asic.utility_operations import DontCare, Sink

if TYPE_CHECKING:
    from cpmpy.solvers.solver_interface import SolverInterface

    from b_asic.schedule import Schedule
    from b_asic.types import GraphID

log = b_asic.logger.getLogger()

PriorityTableType = list[tuple["GraphID", int, int, int, int]]


class Scheduler(ABC):
    """
    Scheduler base class.

    Parameters
    ----------
    input_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The times when inputs arrive.
    output_delta_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The relative times when outputs should be produced.
    output_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The times when outputs should be produced.
    sort_y_location : bool, default: True
        If the y-location should be sorted based on start time of operations.
    """

    __slots__ = (
        "_input_times",
        "_op_laps",
        "_output_delta_times",
        "_output_times",
        "_schedule",
        "_sort_y_location",
    )

    _schedule: "Schedule"
    _op_laps: dict["GraphID", int]

    def __init__(
        self,
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
        output_times: dict["GraphID", int] | None = None,
        sort_y_location: bool = True,
    ) -> None:
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

        if output_times is not None:
            if not isinstance(output_times, dict):
                raise ValueError(
                    f"Provided output_times must be a dictionary, not {type(output_times)} {output_times}."
                )
            for key, value in output_times.items():
                if not isinstance(key, str):
                    raise ValueError("Provided output_times keys must be strings.")
                if not isinstance(value, int):
                    raise ValueError("Provided output_times values must be integers.")
            if any(time < 0 for time in output_times.values()):
                raise ValueError("Provided output_times values must be non-negative.")
            self._output_times = output_times
        else:
            self._output_times = {}

        self._sort_y_location = sort_y_location

    @abstractmethod
    def apply_scheduling(self, schedule: "Schedule") -> None:
        """
        Apply the scheduling algorithm on the given Schedule.

        Parameters
        ----------
        schedule : :class:`~b_asic.schedule.Schedule`
            Schedule to apply the scheduling algorithm on.
        """
        raise NotImplementedError

    def _place_inputs_on_given_times(self) -> None:
        log.debug("Input placement starting")
        for input_id in self._input_times:
            self._schedule.start_times[input_id] = self._input_times[input_id]
            self._op_laps[input_id] = 0
            log.debug(
                "Input %s at time: %d", input_id, self._schedule.start_times[input_id]
            )
        log.debug("Input placement completed")

    def _place_outputs_asap(
        self, schedule: "Schedule", non_schedulable_ops: list["GraphID"] | None
    ) -> None:
        if non_schedulable_ops is None:
            non_schedulable_ops = []
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
        log.debug("Output placement starting")

        # Calculate the maximum end time of non-output operations
        max_non_output_end = 0
        for op_id, start_time in self._schedule.start_times.items():
            op = self._schedule._sfg.find_by_id(op_id)
            if not isinstance(op, Output):
                op = cast(Operation, op)
                for output_port in op.outputs:
                    if output_port.latency_offset is not None:
                        op_end = start_time + output_port.latency_offset
                        if (
                            self._schedule._cyclic
                            and self._schedule._schedule_time is not None
                        ):
                            # Account for lap number in cyclic scheduling
                            lap = self._op_laps.get(op_id, 0)
                            op_end += lap * self._schedule._schedule_time
                        max_non_output_end = max(max_non_output_end, op_end)

        end = (
            max_non_output_end
            if max_non_output_end > 0
            else (self._schedule._schedule_time or self._schedule.get_max_end_time())
        )

        for output in self._schedule._sfg.find_by_type(Output):
            output = cast(Output, output)
            if output.graph_id in self._output_delta_times:
                delta_time = self._output_delta_times[output.graph_id]

                new_time = end + delta_time

                if (
                    self._schedule._cyclic
                    and self._schedule._schedule_time is not None
                    and isinstance(self, ListScheduler)
                ):
                    # Calculate lap number to maintain absolute time relationships
                    lap_number = new_time // self._schedule._schedule_time
                    self._op_laps[output.graph_id] = lap_number
                    self._schedule._place_operation(output, new_time, self._op_laps)
                else:
                    self._schedule.start_times[output.graph_id] = new_time

                count = -1
                for op_id, time in self._schedule.start_times.items():
                    if time == new_time and isinstance(
                        self._schedule._sfg.find_by_id(op_id), Output
                    ):
                        count += 1

                modulo_time = (
                    new_time % self._schedule._schedule_time
                    if self._schedule._schedule_time
                    else new_time
                )
                log.debug(
                    "Output %s at time: %d (lap: %d)",
                    output.graph_id,
                    modulo_time,
                    self._op_laps.get(output.graph_id, 0),
                )
        log.debug("Output placement completed")

        log.debug("Output placement optimization starting")

        # Calculate minimum slack across ALL outputs
        all_outputs = list(self._schedule._sfg.find_by_type(Output))
        if all_outputs:
            min_slack = min(
                self._schedule.backward_slack(op.graph_id) for op in all_outputs
            )
            if min_slack > 0:
                # Move all outputs back by the minimum slack to reduce latency
                for output in all_outputs:
                    if (
                        self._schedule._cyclic
                        and self._schedule._schedule_time is not None
                    ):
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
                    log.debug(
                        "Output %s moved %d time steps backwards to new time %d",
                        output.graph_id,
                        min_slack,
                        new_time,
                    )
        log.debug("Output placement optimization completed")

    def _handle_utility_operations(self) -> None:
        for dc_op in self._schedule._sfg.find_by_type(DontCare):
            log.debug("Scheduling DontCare operation %s ALAP", dc_op.graph_id)
            self._schedule.start_times[dc_op.graph_id] = 0
            self._schedule.move_operation_alap(dc_op.graph_id)

        for sink_op in self._schedule._sfg.find_by_type(Sink):
            log.debug("Scheduling Sink operation %s ASAP", sink_op.graph_id)
            self._schedule.start_times[sink_op.graph_id] = self._schedule._schedule_time
            self._schedule.move_operation_asap(sink_op.graph_id)


class ASAPScheduler(Scheduler):
    """
    Scheduler that implements the as-soon-as-possible (ASAP) algorithm.

    Parameters
    ----------
    input_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The times when inputs arrive.
    output_delta_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The relative times when outputs should be produced.
    output_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The times when outputs should be produced.
    sort_y_location : bool, default: True
        If the y-location should be sorted based on start time of operations.
    """

    def apply_scheduling(self, schedule: "Schedule") -> None:
        # Doc-string inherited
        self._schedule = schedule
        prec_list = schedule._sfg.get_precedence_list()
        if len(prec_list) < 2:
            raise ValueError("Empty signal flow graph cannot be scheduled.")

        if self._input_times:
            self._place_inputs_on_given_times()

        log.debug("ASAP scheduling starting")

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
                        source_port = cast(OutputPort, current_input.signals[0].source)

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

        log.debug("ASAP scheduling completed")
        self._place_outputs_asap(schedule, non_schedulable_ops)
        if self._output_delta_times:
            self._place_outputs_on_given_times()
        schedule.remove_delays()

        max_end_time = schedule.get_max_end_time()

        if schedule._schedule_time is None:
            schedule.set_schedule_time(max_end_time)
        elif schedule._schedule_time < max_end_time:
            raise ValueError(f"Too short schedule time. Minimum is {max_end_time}.")

        self._handle_utility_operations()

        if self._sort_y_location:
            schedule.sort_y_locations_on_start_times()


class ALAPScheduler(Scheduler):
    """
    Scheduler that implements the as-late-as-possible (ALAP) algorithm.

    Parameters
    ----------
    input_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The times when inputs arrive.
    output_delta_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The relative times when outputs should be produced.
    output_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The times when outputs should be produced.
    sort_y_location : bool, default: True
        If the y-location should be sorted based on start time of operations.
    """

    def apply_scheduling(self, schedule: "Schedule") -> None:
        # Doc-string inherited
        self._schedule = schedule
        ASAPScheduler(
            input_times=self._input_times,
            output_delta_times=self._output_delta_times,
            sort_y_location=False,
        ).apply_scheduling(schedule)
        self._op_laps = {}

        if self._output_times:
            for output_id, output_time in self._output_times.items():
                self._schedule.move_operation(
                    output_id,
                    output_time - self._schedule.start_time_of_operation(output_id),
                )

        for input_op in schedule.sfg.find_by_type(Input):
            input_op = cast(Input, input_op)
            self._op_laps[input_op.graph_id] = 0

        log.debug("ALAP scheduling starting")
        # move all outputs ALAP before operations
        for output in schedule.sfg.find_by_type(Output):
            output = cast(Output, output)
            self._op_laps[output.graph_id] = 0
            if (
                output.graph_id in self._output_delta_times
                or output.graph_id in self._output_times
            ):
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

        log.debug("ALAP scheduling completed")
        # adjust the scheduling time if empty time slots have appeared in the start
        if schedule.schedule_time is None:
            slack = min(schedule.start_times.values())
            for op_id in schedule.start_times:
                schedule.move_operation(op_id, -slack)
            schedule.set_schedule_time(schedule._schedule_time - slack)

        self._handle_utility_operations()

        if self._sort_y_location:
            schedule.sort_y_locations_on_start_times()


class ListScheduler(Scheduler):
    """
    List-based scheduler with optional constraints.

    .. admonition:: Important

       Only works on non-recursive SFGs.
       For recursive SFGs use :class:`RecursiveListScheduler` instead.

    Parameters
    ----------
    sort_order : tuple(tuple(int, bool))
        Specifies which columns in the priority table to sort on and in
        which order, where True is ascending order.
        There are five columns::

            0 - GraphID of the operation.
            1 - Deadline, i.e., the clock cycle that the data is required in the ALAP schedule.
            2 - Output slack, i.e., the start time of the operation in the ALAP schedule when sorted on.
            3 - Fan-out, i.e., the number of operations reading from the output of the operation.
            4 - Memory reads, i.e., the number of memory reads required if operation is scheduled in the
                current time slot.
    max_resources : dict[:data:`~b_asic.types.TypeName`, int], optional
        Max resources available to realize the schedule.
    max_concurrent_reads : int, optional
        Max number of concurrent reads.
    max_concurrent_writes : int, optional
        Max number of concurrent writes.
    input_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The times when inputs arrive.
    output_delta_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The relative times when outputs should be produced.
    output_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The times when outputs should be produced.
    sort_y_location : bool, default: True
        If the y-location should be sorted based on start time of operations.
    """

    __slots__ = (
        "_alap_op_laps",
        "_alap_schedule_time",
        "_alap_start_times",
        "_cached_execution_times",
        "_cached_execution_times_in_time",
        "_current_time",
        "_deadlines",
        "_fan_outs",
        "_max_concurrent_reads",
        "_max_concurrent_writes",
        "_max_resources",
        "_output_slacks",
        "_remaining_ops",
        "_remaining_ops_set",
        "_remaining_resources",
        "_sort_order",
        "_used_reads",
    )
    _remaining_ops: list["GraphID"]
    _deadlines: dict["GraphID", int]
    _output_slacks: dict["GraphID", int]
    _fan_outs: dict["GraphID", int]
    _current_time: int
    _cached_execution_times_in_time: dict[type[Operation], defaultdict[int, int]]
    _alap_start_times: dict["GraphID", int]
    _alap_op_laps: dict["GraphID", int]
    _alap_schedule_time: int
    _used_reads: defaultdict[int, int]
    _cached_execution_times: dict["GraphID", int]

    def __init__(
        self,
        sort_order: tuple[tuple[int, bool], ...],
        max_resources: dict[TypeName, int] | None = None,
        max_concurrent_reads: int | None = None,
        max_concurrent_writes: int | None = None,
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
        output_times: dict["GraphID", int] | None = None,
        sort_y_location: bool = True,
    ) -> None:
        super().__init__(
            input_times=input_times,
            output_delta_times=output_delta_times,
            output_times=output_times,
            sort_y_location=sort_y_location,
        )
        self._sort_order = sort_order

        if max_resources is not None:
            if not isinstance(max_resources, dict):
                raise ValueError("Provided max_resources must be a dictionary.")
            normalized: dict[TypeName, int] = {}
            for key, value in max_resources.items():
                if isinstance(key, type) and hasattr(key, "type_name"):
                    key = key.type_name()
                if not isinstance(key, str):
                    raise ValueError(
                        "Provided max_resources keys must be strings or operation types."
                    )
                if not isinstance(value, int):
                    raise ValueError("Provided max_resources values must be integers.")
                normalized[TypeName(key)] = value
            self._max_resources = normalized
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
        # Doc-string inherited
        log.debug("Scheduler initializing")
        self._initialize_scheduler(schedule)

        if self._input_times:
            self._place_inputs_on_given_times()
            self._remaining_ops = [
                op_id for op_id in self._remaining_ops if op_id not in self._input_times
            ]
            self._remaining_ops_set = set(self._remaining_ops)

        self._schedule_nonrecursive_ops()

        if self._output_delta_times:
            self._place_outputs_on_given_times()

        if self._schedule._schedule_time is None:
            self._schedule.set_schedule_time(self._schedule.get_max_end_time())
        self._schedule.remove_delays()
        self._handle_utility_operations()
        if self._sort_y_location:
            schedule.sort_y_locations_on_start_times()
        self._validate_constraints()
        log.debug("Scheduling completed")

    def _validate_constraints(self) -> None:
        for time_slot in range(self._schedule._schedule_time):
            for op_type, constraint in self._remaining_resources.items():
                if (
                    self._schedule._execution_times_in_time(op_type, time_slot)
                    > constraint
                ):
                    raise ValueError(
                        "Derived schedule breaches resource constraints for:",
                        op_type,
                        " at time slot",
                        time_slot,
                    )
            if self._max_concurrent_reads:
                _, mem_vars = self._schedule.get_memory_variables().split_on_length()
                if mem_vars.read_ports_bound() > self._max_concurrent_reads:
                    raise ValueError(
                        "Derived schedule breaches concurrent read constraints for time slot:",
                        time_slot,
                    )
            if self._max_concurrent_writes:
                _, mem_vars = self._schedule.get_memory_variables().split_on_length()
                if mem_vars.write_ports_bound() > self._max_concurrent_writes:
                    raise ValueError(
                        "Derived schedule breaches concurrent write constraints for time slot:",
                        time_slot,
                    )

    def _get_next_op_id(self, priority_table: PriorityTableType) -> "GraphID":
        def sort_key(item):
            return tuple(
                (item[index] * (-1 if not asc else 1),)
                for index, asc in self._sort_order
            )

        sorted_table = sorted(priority_table, key=sort_key)
        return sorted_table[0][0]

    def _get_priority_table(self, candidate_ids) -> PriorityTableType:
        schedule_time = (
            self._schedule._schedule_time
            if self._schedule._schedule_time is not None
            else 0
        )
        ready_ops = [
            op_id
            for op_id in candidate_ids
            if self._op_is_schedulable(
                cast(Operation, self._schedule._sfg.find_by_id(op_id)), schedule_time
            )
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
            op = cast(Operation, self._schedule._sfg.find_by_id(op_id))
            output_offsets = [cast(int, output.latency_offset) for output in op.outputs]
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
            op_id: len(
                cast(Operation, self._schedule._sfg.find_by_id(op_id)).output_signals
            )
            for op_id in self._alap_start_times
        }

    def _calculate_memory_reads(
        self, ready_ops: list["GraphID"]
    ) -> dict["GraphID", int]:
        op_reads = {}
        for op_id in ready_ops:
            reads = 0
            op = cast(Operation, self._schedule._sfg.find_by_id(op_id))
            for op_input in op.inputs:
                source_port = cast(OutputPort, op_input.signals[0].source)
                source_op = source_port.operation
                if isinstance(source_op, DontCare):
                    continue
                if isinstance(source_op, Delay):
                    reads += 1
                    continue
                if self._schedule.start_times[source_op.graph_id] + cast(
                    int, source_port.latency_offset
                ) != self._current_time + cast(int, op_input.latency_offset):
                    reads += 1
            op_reads[op_id] = reads
        return op_reads

    def _op_satisfies_resource_constraints(self, op: Operation) -> bool:
        op_type = type(op)
        if self._schedule._schedule_time is None:
            for i in range(max(1, op.execution_time)):
                time_slot = self._current_time + i
                count = self._cached_execution_times_in_time[op_type][time_slot]
                if count >= self._remaining_resources[op_type]:
                    return False
        else:
            for i in range(max(1, cast(int, op.execution_time))):
                time_slot = (self._current_time + i) % self._schedule._schedule_time
                count = self._cached_execution_times_in_time[op_type][time_slot]
                if count >= self._remaining_resources[op_type]:
                    return False
        return True

    def _op_satisfies_concurrent_writes(self, op: Operation) -> bool:
        if self._max_concurrent_writes:
            tmp_used_writes: defaultdict[int, int] = defaultdict(int)
            if not isinstance(op, Output):
                for output_port in op.outputs:
                    output_ready_time = self._current_time + cast(
                        int, output_port.latency_offset
                    )
                    if self._schedule._schedule_time:
                        output_ready_time %= self._schedule._schedule_time

                    writes_in_time = 0
                    for op_id, start_time in self._schedule.start_times.items():
                        tmp_op = cast(Operation, self._schedule._sfg.find_by_id(op_id))
                        offsets = [
                            cast(int, output.latency_offset)
                            for output in tmp_op.outputs
                        ]
                        write_times = [start_time + offset for offset in offsets]
                        writes_in_time += write_times.count(output_ready_time)

                    tmp_used_writes[output_ready_time] += 1

                    if (
                        self._max_concurrent_writes
                        - writes_in_time
                        - tmp_used_writes[output_ready_time]
                        < 0
                    ):
                        return False
        return True

    def _op_satisfies_concurrent_reads(self, op: Operation) -> bool:
        if self._max_concurrent_reads:
            tmp_used_reads: defaultdict[int, int] = defaultdict(int)
            for op_input in op.inputs:
                source_port = cast(OutputPort, op_input.signals[0].source)
                source_op = source_port.operation
                if isinstance(source_op, (Delay, DontCare)):
                    continue
                input_read_time = self._current_time + cast(
                    int, op_input.latency_offset
                )
                if (
                    self._schedule.start_times[source_op.graph_id]
                    + cast(int, source_port.latency_offset)
                    != input_read_time
                ):
                    if self._schedule._schedule_time:
                        input_read_time %= self._schedule._schedule_time

                    tmp_used_reads[input_read_time] += 1

                    if (
                        self._max_concurrent_reads
                        < self._used_reads[input_read_time]
                        + tmp_used_reads[input_read_time]
                    ):
                        return False
        return True

    def _op_satisfies_data_dependencies(
        self, op: Operation, schedule_time: int
    ) -> bool:
        for op_input in op.inputs:
            source_port = cast(OutputPort, op_input.signals[0].source)
            source_op = source_port.operation

            if isinstance(source_op, (Delay, DontCare)):
                continue

            if source_op.graph_id in self._remaining_ops_set:
                return False

            available_time = (
                self._schedule.start_times[source_op.graph_id]
                + self._op_laps[source_op.graph_id] * schedule_time
                + cast(int, source_port.latency_offset)
            )

            required_time = self._current_time + cast(int, op_input.latency_offset)
            if available_time > required_time:
                return False
        return True

    def _op_is_schedulable(self, op: Operation, schedule_time: int) -> bool:
        return (
            self._op_satisfies_resource_constraints(op)
            and self._op_satisfies_data_dependencies(op, schedule_time)
            and self._op_satisfies_concurrent_writes(op)
            and self._op_satisfies_concurrent_reads(op)
        )

    def _initialize_scheduler(self, schedule: "Schedule") -> None:
        self._schedule = schedule

        for resource_type in self._max_resources:
            if not self._schedule._sfg.find_by_type_name(resource_type):
                raise ValueError(
                    f"Provided max resource of type {resource_type} cannot be found in the provided SFG."
                )

        differing_elems = [
            resource
            for resource in self._schedule._sfg.get_used_type_names()
            if resource not in self._max_resources
            and resource != Delay.type_name()
            and resource != DontCare.type_name()
            and resource != Sink.type_name()
        ]
        for type_name in differing_elems:
            self._max_resources[type_name] = 1

        for key in self._input_times:
            if self._schedule._sfg.find_by_id(key) is None:
                raise ValueError(
                    f"Provided input time with GraphID {key} cannot be found in the provided SFG."
                )

        for key in self._output_delta_times:
            if self._schedule._sfg.find_by_id(key) is None:
                raise ValueError(
                    f"Provided output delta time with GraphID {key} cannot be found in the provided SFG."
                )

        if self._schedule._cyclic and self._schedule._schedule_time is not None:
            iteration_period_bound = self._schedule._sfg.iteration_period_bound()
            if self._schedule._schedule_time < iteration_period_bound:
                raise ValueError(
                    f"Provided scheduling time {self._schedule._schedule_time} must be larger or equal to the"
                    f" iteration period bound: {iteration_period_bound}."
                )

        if self._schedule._schedule_time is not None:
            for resource_type, resource_amount in self._max_resources.items():
                if resource_amount < self._schedule._sfg.resource_lower_bound(
                    resource_type, self._schedule._schedule_time
                ):
                    raise ValueError(
                        f"Amount of resource: {resource_type} is not enough to "
                        f"realize schedule for scheduling time: {self._schedule._schedule_time}."
                    )

        alap_schedule = copy.copy(self._schedule)
        alap_schedule._schedule_time = None
        alap_scheduler = ALAPScheduler(
            input_times=self._input_times,
            output_delta_times=self._output_delta_times,
            sort_y_location=False,
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

        used_op_types = self._schedule._sfg.get_used_operation_types()

        def find_type_from_type_name(type_name: TypeName) -> type[Operation]:
            for op_type in used_op_types:
                if op_type.type_name() == type_name:
                    return op_type
            raise ValueError(f"Internal bug: {type_name} not in schedule.")

        self._remaining_resources = {
            find_type_from_type_name(type_name): cnt
            for type_name, cnt in self._max_resources.items()
        }

        self._remaining_ops = [op.graph_id for op in self._schedule._sfg.operations]
        self._cached_execution_times = {
            op_id: cast(Operation, self._schedule._sfg.find_by_id(op_id)).execution_time
            for op_id in self._remaining_ops
        }
        self._cached_execution_times_in_time = {
            op_type: defaultdict(int) for op_type in used_op_types
        }
        self._remaining_ops = [
            op_id
            for op_id in self._remaining_ops
            if not isinstance(self._schedule._sfg.find_by_id(op_id), (Delay, DontCare))
        ]
        self._remaining_ops = [
            op_id
            for op_id in self._remaining_ops
            if not (
                isinstance(self._schedule._sfg.find_by_id(op_id), Output)
                and op_id in self._output_delta_times
            )
        ]

        for op_id in self._remaining_ops:
            op = cast(Operation, self._schedule._sfg.find_by_id(op_id))
            if op.execution_time is None:
                raise ValueError(
                    "All operations in the SFG must have a specified execution time. "
                    f"Missing operation: {op_id}."
                )

        self._remaining_ops_set = set(self._remaining_ops)
        self._deadlines = self._calculate_deadlines()
        self._output_slacks = self._calculate_alap_output_slacks()
        self._fan_outs = self._calculate_fan_outs()

        self._schedule.start_times = {}
        self._used_reads = defaultdict(int)

        self._current_time = 0

    def _schedule_nonrecursive_ops(self) -> None:
        log.debug("Non-recursive operation scheduling starting")
        while self._remaining_ops:
            prio_table = self._get_priority_table(self._remaining_ops)
            while prio_table:
                next_op_id = self._get_next_op_id(prio_table)
                next_op = self._schedule._sfg.find_by_id(next_op_id)
                next_op = cast(Operation, next_op)

                self._update_port_reads(next_op)

                self._remaining_ops = [
                    op_id for op_id in self._remaining_ops if op_id != next_op_id
                ]
                self._remaining_ops_set.remove(next_op_id)

                self._schedule._place_operation(
                    next_op, self._current_time, self._op_laps
                )
                self._op_laps[next_op_id] = (
                    (self._current_time) // self._schedule._schedule_time
                    if self._schedule._schedule_time
                    else 0
                )

                if self._schedule._schedule_time is None:
                    for i in range(max(1, next_op.execution_time)):
                        time_slot = self._current_time + i
                        self._cached_execution_times_in_time[type(next_op)][
                            time_slot
                        ] += 1
                else:
                    for i in range(max(1, cast(int, next_op.execution_time))):
                        time_slot = (
                            self._current_time + i
                        ) % self._schedule._schedule_time
                        self._cached_execution_times_in_time[type(next_op)][
                            time_slot
                        ] += 1

                log.debug(
                    "Schedule operation: %s at time: %d",
                    next_op.graph_id,
                    self._current_time,
                )

                prio_table = self._get_priority_table(self._remaining_ops)

            self._current_time += 1
        self._current_time -= 1
        log.debug("Non-recursive operation scheduling completed")

    def _update_port_reads(self, next_op: Operation) -> None:
        for input_port in next_op.inputs:
            source_port = cast(OutputPort, input_port.signals[0].source)
            source_op = source_port.operation
            time = self._current_time + cast(int, input_port.latency_offset)
            if (
                not isinstance(source_op, (DontCare, Delay))
                and self._schedule.start_times[source_op.graph_id]
                + cast(int, source_port.latency_offset)
                != time
            ):
                if self._schedule._schedule_time:
                    time %= self._schedule._schedule_time

                self._used_reads[time] += 1


class RecursiveListScheduler(ListScheduler):
    """
    List-based scheduler for recursive algorithms with optional constraints.

    .. admonition:: Info

       If the SFG does not have any recursive parts, use :class:`ListScheduler` instead.

    Parameters
    ----------
    sort_order : tuple(tuple(int, bool))
        Specifies which columns in the priority table to sort on and in
        which order, where True is ascending order.
        There are five columns::

            0 - GraphID of the operation.
            1 - Deadline, i.e., the clock cycle that the data is required in the ALAP schedule.
            2 - Output slack, i.e., the start time of the operation in the ALAP schedule when sorted on.
            3 - Fan-out, i.e., the number of operations reading from the output of the operation.
            4 - Memory reads, i.e., the number of memory reads required if operation is scheduled in the
                current time slot.
    max_resources : dict[:data:`~b_asic.types.TypeName`, int], optional
        Max resources available to realize the schedule.
    input_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The times when inputs arrive.
    output_delta_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The relative times when outputs should be produced.
    output_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The times when outputs should be produced.
    sort_y_location : bool, default: True
        If the y-location should be sorted based on start time of operations.
    """

    __slots__ = ("_recursive_ops", "_recursive_ops_set", "_remaining_recursive_ops")

    def __init__(
        self,
        sort_order: tuple[tuple[int, bool], ...],
        max_resources: dict[TypeName, int] | None = None,
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
        output_times: dict["GraphID", int] | None = None,
        sort_y_location: bool = True,
    ) -> None:
        super().__init__(
            sort_order=sort_order,
            max_resources=max_resources,
            input_times=input_times,
            output_delta_times=output_delta_times,
            output_times=output_times,
            sort_y_location=sort_y_location,
        )

    def apply_scheduling(self, schedule: "Schedule") -> None:
        log.debug("Scheduler initializing")
        self._initialize_scheduler(schedule)

        if self._input_times:
            self._place_inputs_on_given_times()
            self._remaining_ops = [
                op_id for op_id in self._remaining_ops if op_id not in self._input_times
            ]
            self._remaining_ops_set = set(self._remaining_ops)

        loops = self._schedule._sfg.loops
        if loops:
            log.debug("Scheduling recursive operations")
            self._schedule_recursive_ops(loops)

        log.debug("Scheduling non-recursive operations")
        self._schedule_nonrecursive_ops()

        if self._output_delta_times:
            self._place_outputs_on_given_times()

        if self._schedule._schedule_time is None:
            self._schedule.set_schedule_time(self._schedule.get_max_end_time())
        period_bound = self._schedule._sfg.iteration_period_bound()
        self._schedule.remove_delays()
        if loops:
            if int(period_bound) != period_bound:
                log.warning("Rational iteration period bound: %d", period_bound)
            log.debug("Retiming operations")
            self._retime_ops(math.ceil(period_bound))
        self._handle_utility_operations()
        if self._sort_y_location:
            schedule.sort_y_locations_on_start_times()
        self._validate_constraints()
        log.debug("Scheduling completed")

    def _get_recursive_ops(self, loops: list[list["GraphID"]]) -> list["GraphID"]:
        recursive_ops = []
        for loop in loops:
            for op_id in loop:
                if op_id not in recursive_ops and not isinstance(
                    self._schedule._sfg.find_by_id(op_id), Delay
                ):
                    recursive_ops.append(op_id)
        return recursive_ops

    def _recursive_op_satisfies_data_dependencies(self, op: Operation) -> bool:
        for op_input in op.inputs:
            source_port = cast(OutputPort, op_input.signals[0].source)
            source_op = source_port.operation
            if isinstance(source_op, (Delay, DontCare)):
                continue
            if (
                source_op.graph_id in self._recursive_ops
                and source_op.graph_id in self._remaining_ops
            ):
                return False
        return True

    def _get_recursive_priority_table(self) -> list[tuple["GraphID", int]]:
        ready_ops = [
            op_id
            for op_id in self._remaining_recursive_ops
            if self._recursive_op_satisfies_data_dependencies(
                self._schedule._sfg.find_by_id(op_id)
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
                    delta_start_time = self._schedule._start_times[op_id] + delta
                    new_times = (
                        (delta_start_time + time) % self._schedule.schedule_time
                        for time in range(self._cached_execution_times[op_id])
                    )

                    op_type = type(op)
                    exec_counts = (
                        self._schedule._execution_times_in_time(op_type, new_time)
                        for new_time in new_times
                    )
                    while any(
                        count >= self._remaining_resources[op_type]
                        for count in exec_counts
                    ):
                        delta += 1
                        if delta >= self._schedule._schedule_time:
                            break
                        delta_start_time = self._schedule._start_times[op_id] + delta
                        new_times = (
                            (delta_start_time + time) % self._schedule.schedule_time
                            for time in range(self._cached_execution_times[op_id])
                        )
                        exec_counts = (
                            self._schedule._execution_times_in_time(op_type, new_time)
                            for new_time in new_times
                        )
                    if delta > self._schedule.forward_slack(op_id):
                        continue
                    log.debug("Moving operation %s %d time units", op_id, delta)
                    self._schedule.move_operation(op_id, delta)

                # adjust time if a gap exists on the right side of the schedule
                self._schedule._schedule_time = min(
                    self._schedule._schedule_time, self._schedule.get_max_end_time()
                )

                # adjust time if a gap exists on the left side of the schedule
                slack = min(self._schedule._start_times.values())
                for other_op_id in sorted_op_ids:
                    op = cast(Operation, self._schedule._sfg.find_by_id(other_op_id))
                    max_end_time = 0
                    op_start_time = self._schedule._start_times[other_op_id]
                    for outport in op.outputs:
                        max_end_time = max(
                            max_end_time,
                            op_start_time + cast(int, outport.latency_offset),
                        )
                    if max_end_time > self._schedule._schedule_time:
                        slack = min(slack, self._schedule.forward_slack(other_op_id))
                if slack > 0:
                    log.debug("Reducing schedule time by %d", slack)
                    for inner_op_id in self._schedule._start_times:
                        self._schedule._start_times[inner_op_id] -= slack

                    self._schedule._schedule_time = (
                        self._schedule._schedule_time - slack
                    )

                if self._schedule._schedule_time <= time_goal:
                    break

            time_out_counter -= 1

    def _schedule_recursive_ops(self, loops: list[list["GraphID"]]) -> None:
        saved_sched_time = self._schedule._schedule_time
        self._schedule._schedule_time = None

        log.debug("Scheduling of recursive loops starting")
        self._recursive_ops = self._get_recursive_ops(loops)
        self._recursive_ops_set = set(self._recursive_ops)
        self._remaining_recursive_ops = self._recursive_ops.copy()
        log.debug("Generating initial recursive priority table")
        prio_table = self._get_recursive_priority_table()
        while prio_table:
            op = self._get_next_recursive_op(prio_table)
            op_sched_time = 0
            for input_port in op.inputs:
                source_port = cast(OutputPort, input_port.signals[0].source)
                source_op = source_port.operation
                if isinstance(source_op, Delay):
                    continue
                source_start_time = self._schedule.start_times.get(source_op.graph_id)
                if source_start_time is None:
                    continue
                op_sched_time = max(
                    op_sched_time, source_start_time + source_port.latency_offset
                )

            op_type = type(op)
            exec_count = self._schedule._execution_times_in_time(op_type, op_sched_time)
            while exec_count >= self._remaining_resources[op_type]:
                op_sched_time += 1
                exec_count = self._schedule._execution_times_in_time(
                    op_type, op_sched_time
                )

            self._schedule._place_operation(op, op_sched_time, self._op_laps)
            self._op_laps[op.graph_id] = 0
            log.debug("Schedule operation: %s at time: %d", op.graph_id, op_sched_time)
            self._remaining_recursive_ops.remove(op.graph_id)
            self._remaining_ops.remove(op.graph_id)
            self._remaining_ops_set.remove(op.graph_id)

            for i in range(max(1, cast(int, op.execution_time))):
                time_slot = op_sched_time + i
                self._cached_execution_times_in_time[op_type][time_slot] += 1

            prio_table = self._get_recursive_priority_table()

        self._schedule._schedule_time = self._schedule.get_max_end_time()

        if saved_sched_time and saved_sched_time > self._schedule._schedule_time:
            self._schedule._schedule_time = saved_sched_time
        log.debug("Scheduling of recursive loops completed")

    def _get_next_recursive_op(self, priority_table: PriorityTableType) -> Operation:
        sorted_table = sorted(priority_table, key=lambda row: row[1])
        return cast(Operation, self._schedule._sfg.find_by_id(sorted_table[0][0]))

    def _pipeline_input_to_recursive_sections(self) -> None:
        for op_id in self._recursive_ops:
            op = cast(Operation, self._schedule._sfg.find_by_id(op_id))
            for input_port in op.inputs:
                signal = input_port.signals[0]
                source_op = cast(OutputPort, signal.source).operation
                if (
                    not isinstance(source_op, Delay)
                    and source_op.graph_id not in self._recursive_ops_set
                ):
                    # non-recursive to recursive edge found -> pipeline
                    self._schedule.laps[signal.graph_id] += 1

    def _op_satisfies_data_dependencies(
        self, op: Operation, schedule_time: int
    ) -> bool:
        for output_port in op.outputs:
            destination_port = cast(InputPort, output_port.signals[0].destination)
            destination_op = destination_port.operation
            if destination_op.graph_id not in self._remaining_ops_set:
                if isinstance(destination_op, (Delay, Output, Sink)):
                    continue
                # spotted a recursive operation -> check if ok
                op_available_time = self._current_time + cast(
                    int, output_port.latency_offset
                )
                usage_time = (
                    self._schedule.start_times[destination_op.graph_id]
                    + schedule_time
                    * self._schedule.laps[output_port.signals[0].graph_id]
                )
                if op_available_time > usage_time:
                    # constraint is not okay, move all recursive operations one lap by pipelining
                    # across the non-recursive to recursive edge
                    self._pipeline_input_to_recursive_sections()

        for op_input in op.inputs:
            source_port = cast(OutputPort, op_input.signals[0].source)
            source_op = source_port.operation
            if isinstance(source_op, (Delay, DontCare)):
                continue
            if source_op.graph_id in self._remaining_ops_set:
                return False
            available_time = (
                self._schedule.start_times[source_op.graph_id]
                + self._op_laps[source_op.graph_id] * schedule_time
                + cast(int, source_port.latency_offset)
            )
            required_time = self._current_time + cast(int, op_input.latency_offset)
            if available_time > required_time:
                return False
        return True


class _OptimizationScheduler(Scheduler):
    """Shared timing bounds and schedule extraction for optimizing schedulers."""

    def _get_asap_start_times(
        self,
        schedule: "Schedule",
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
    ) -> tuple[dict["GraphID", int], int]:
        asap_schedule = copy.copy(schedule)
        asap_schedule._schedule_time = None
        asap_scheduler = ASAPScheduler(
            sort_y_location=False,
            input_times=input_times,
            output_delta_times=output_delta_times,
        )
        asap_scheduler.apply_scheduling(asap_schedule)
        for key in schedule._laps:
            schedule._laps[key] = 0
        return copy.copy(asap_schedule.start_times), asap_schedule.schedule_time

    def _get_alap_start_times(
        self,
        schedule: "Schedule",
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
        max_time: int | None = None,
    ) -> dict["GraphID", int]:
        alap_schedule = copy.copy(schedule)
        if max_time is not None:
            alap_schedule._schedule_time = max_time
        alap_scheduler = ALAPScheduler(
            sort_y_location=False,
            input_times=input_times,
            output_delta_times=output_delta_times,
        )
        alap_scheduler.apply_scheduling(alap_schedule)
        for key in schedule._laps:
            schedule._laps[key] = 0
        upper_bounds = copy.copy(alap_schedule.start_times)
        if output_delta_times:
            # ALAP leaves the relative output group at its ASAP placement.
            # Translate its bounds to use the available horizon. Only the
            # specified outputs determine the group end; unspecified outputs
            # may already be at the horizon.
            horizon = alap_schedule.schedule_time
            slack = horizon - max(upper_bounds[key] for key in output_delta_times)
            for key, time in upper_bounds.items():
                if not input_times or key not in input_times:
                    upper_bounds[key] = min(time + slack, horizon)
        return upper_bounds

    def _finish_schedule(self, schedule: "Schedule", Ts: int) -> None:
        self._handle_utility_operations()
        schedule.remove_delays()

        if self._max_time is not None and self._max_time > Ts:
            schedule._schedule_time = self._max_time
            diff = self._max_time - Ts
            move_order = {
                port.operation.graph_id: level
                for level, step in enumerate(schedule.sfg.get_precedence_list())
                for port in step
            }
            # Move operations ahead in time so that they wrap
            for time in reversed(range(Ts, self._max_time + 1)):
                ops_to_move = set()
                # Find operations to move
                for op_id, op_time in schedule.start_times.items():
                    if op_time == time:
                        ops_to_move.add(op_id)
                # Move consumers first when operations share a start time,
                # so moving their producers does not violate dependencies.
                for op_id in sorted(
                    ops_to_move,
                    key=lambda op_id: move_order.get(op_id, len(move_order)),
                    reverse=True,
                ):
                    schedule.move_operation(op_id, diff)
            # Move any outputs at the schedule edge
            for op_id, op_time in schedule.start_times.items():
                # Any operations still at max_time will be Outputs or Sinks
                # Move back to new schedule time
                if op_time == self._max_time:
                    schedule.move_operation(op_id, -diff)

            # Folded operations may finish after the period boundary. Allow
            # this when their cyclic dependencies remain valid.
            schedule.set_schedule_time(Ts, allow_cyclic_wrap=schedule.cyclic)

        if self._sort_y_location:
            schedule.sort_y_locations_on_start_times()


class ILPScheduler(_OptimizationScheduler):
    """
    ILP-based scheduler that minimizes the sum of per-type resource counts.

    Resource occupancy is determined by execution time. For cyclic schedules,
    occupancy includes overlap between successive iterations.

    Parameters
    ----------
    solver : :class:`~pulp.LpSolver`, optional
        .. code-block:: python

            import pulp

            print(pulp.listSolvers(onlyAvailable=True))

    input_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The times when inputs arrive.
    output_delta_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        Output offsets relative to a common time chosen by the solver. The
        outputs may move together within the scheduling horizon.
    output_times : dict(:data:`~b_asic.types.GraphID`, int), optional
        The times when outputs should be produced.
    max_time : int, optional
        The time horizon to schedule for in cyclic scheduling.
    sort_y_location : bool, default: True
        If the y-location should be sorted based on start time of operations.
    """

    def __init__(
        self,
        solver: pulp.LpSolver | None = None,
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
        output_times: dict["GraphID", int] | None = None,
        max_time: int | None = None,
        sort_y_location: bool = True,
    ) -> None:
        self._solver = solver
        super().__init__(
            input_times=input_times,
            output_delta_times=output_delta_times,
            output_times=output_times,
            sort_y_location=sort_y_location,
        )
        self._max_time = max_time

    def apply_scheduling(self, schedule: "Schedule") -> None:
        # Inspired by K.K. Parhi https://doi.org/10.1109/CICC.1993.590480

        Ts = schedule.schedule_time

        self._schedule = schedule
        LB, asap_max_time = self._get_asap_start_times(
            schedule,
            input_times=self._input_times,
            output_delta_times=self._output_delta_times,
        )
        if not self._schedule.cyclic and asap_max_time > self._schedule.schedule_time:
            raise ValueError(
                f"Shortest possible schedule time, {asap_max_time}, is longer than requested schedule time {self._schedule.schedule_time}. Use cyclic scheduling or increase schedule time."
            )
        UB = self._get_alap_start_times(
            schedule,
            input_times=self._input_times,
            output_delta_times=self._output_delta_times,
            max_time=self._max_time,
        )

        if self._max_time:
            time_slots = range(max(self._max_time, Ts) + 1)
        else:
            time_slots = range(Ts + 1)

        ops = [
            op
            for op in schedule._sfg.operations
            if not isinstance(op, (Delay, DontCare, Sink))
        ]
        op_types = list({op.type_name() for op in ops})

        problem = pulp.LpProblem()
        X = problem.add_variable_dicts("X", (ops, time_slots), cat=pulp.LpBinary)
        R_used = problem.add_variable_dicts("R_used", op_types, cat=pulp.LpInteger)

        # I/O timing constraints already determine resource requirements.
        # Partial timing maps give lower bounds; complete maps give exact
        # counts. Relative output offsets have translation-invariant overlap.
        fixed_output_times = self._output_times
        if not schedule.cyclic:
            fixed_output_times = {}
            for output_id, output_time in self._output_times.items():
                starts = [
                    time
                    for time in range(LB[output_id], UB[output_id] + 1)
                    if time % Ts == output_time
                ]
                if len(starts) == 1:
                    fixed_output_times[output_id] = starts[0]
        for io_type, timing_maps in (
            (Input, (self._input_times,)),
            (Output, (fixed_output_times, self._output_delta_times)),
        ):
            io_ops = [op for op in ops if isinstance(op, io_type)]
            if not io_ops:
                continue
            resource = R_used[io_type.type_name()]
            for timings in timing_maps:
                if not timings:
                    continue
                io_occupancy = Counter(
                    (timings[op.graph_id] + offset) % Ts
                    if schedule.cyclic
                    else timings[op.graph_id] + offset
                    for op in io_ops
                    if op.graph_id in timings
                    for offset in range(op.execution_time)
                )
                required = max(io_occupancy.values(), default=0)
                resource.lowBound = max(resource.lowBound or 0, required)
                if all(op.graph_id in timings for op in io_ops):
                    resource.upBound = min(
                        resource.upBound if resource.upBound is not None else required,
                        required,
                    )

        initial_start_times = LB.copy()
        if self._output_delta_times and not schedule.cyclic:
            # Keep the computation ASAP but place outputs at the end of the
            # horizon. Shift all outputs together, including unspecified ones,
            # to preserve their spacing and avoid increasing output resources.
            outputs = [op for op in ops if isinstance(op, Output)]
            output_shift = min(UB[op.graph_id] - LB[op.graph_id] for op in outputs)
            for op in outputs:
                initial_start_times[op.graph_id] += output_shift
        initial_values = {
            X[op][time]: int(time == initial_start_times[op.graph_id])
            for op in ops
            for time in time_slots
        }

        # w - Stage difference between operations (i.e. number of Delays between)
        W = {}
        for op in ops:
            tmp = {}
            for input_port in op.inputs:
                depth = 0
                source_op = input_port.connected_source.operation
                while isinstance(source_op, Delay):
                    source_op = source_op.inputs[0].connected_source.operation
                    depth += 1
                tmp[source_op.graph_id] = depth
            W[op.graph_id] = tmp

        # Minimize the amount of concurrent processes and I/O
        problem += pulp.lpSum(R_used[op_type] for op_type in op_types)

        # (1) - Each operation should have one and only one start time
        for op in ops:
            # Variables outside the ASAP/ALAP window must not be selected when
            # extracting start times, or contribute to resource constraints.
            for time in time_slots:
                if not LB[op.graph_id] <= time <= UB[op.graph_id]:
                    X[op][time].upBound = 0
            problem += (
                pulp.lpSum(
                    X[op][j] for j in range(LB[op.graph_id], UB[op.graph_id] + 1)
                )
                == 1
            )

        if self._output_delta_times:
            # Keep the output offsets relative to a movable common origin.
            # Bounds alone do not enforce the relative output times.
            output_origin = problem.add_variable(
                "output_origin", lowBound=0, cat=pulp.LpInteger
            )
            output_id = next(iter(self._output_delta_times))
            initial_values[output_origin] = (
                initial_start_times[output_id] - self._output_delta_times[output_id]
            )
            for output_id, delta_time in self._output_delta_times.items():
                output_op = schedule._sfg.find_by_id(output_id)
                problem += (
                    pulp.lpSum(
                        time * X[output_op][time]
                        for time in range(LB[output_id], UB[output_id] + 1)
                    )
                    == output_origin + delta_time
                )

        if self._input_times:
            for input_id, input_time in self._input_times.items():
                input_op = schedule._sfg.find_by_id(input_id)
                X[input_op][input_time].setInitialValue(1)
                X[input_op][input_time].fixValue()

        if self._output_times:
            for output_id, output_time in self._output_times.items():
                output_op = schedule._sfg.find_by_id(output_id)
                for t in time_slots:
                    if t % Ts != output_time:
                        X[output_op][t].setInitialValue(0)
                        X[output_op][t].fixValue()

        # (2) - At most R_used[resource_type] can be used in each time slot for every resource type
        resource_slots = range(Ts) if schedule.cyclic else time_slots
        for op_type in op_types:
            occupancy = {time: [] for time in resource_slots}
            for op in ops:
                if op.type_name() != op_type:
                    continue
                for start_time in range(LB[op.graph_id], UB[op.graph_id] + 1):
                    # Count every occupied slot, including repeated visits if
                    # execution_time exceeds the period. Latency determines
                    # data availability, not resource occupancy.
                    for offset in range(op.execution_time):
                        time = start_time + offset
                        if schedule.cyclic:
                            time %= Ts
                        if time in occupancy:
                            occupancy[time].append(X[op][start_time])
            for terms in occupancy.values():
                problem += pulp.lpSum(terms) <= R_used[op_type]
            initial_values[R_used[op_type]] = max(
                (
                    sum(initial_values[var] for var in terms)
                    for terms in occupancy.values()
                ),
                default=0,
            )

        # (3) - Ensure that all timing constraints are met
        for op in ops:
            for input_port in op.inputs:
                source_port = input_port.connected_source
                source_op = source_port.operation
                if isinstance(source_op, DontCare):
                    continue
                while isinstance(source_op, Delay):
                    source_port = source_op.inputs[0].connected_source
                    source_op = source_port.operation
                a = set(
                    range(
                        LB[source_op.graph_id],
                        UB[source_op.graph_id] + source_op.latency,
                    )
                )
                b = set(
                    range(
                        LB[op.graph_id] + Ts * W[op.graph_id][source_op.graph_id],
                        UB[op.graph_id] + Ts * W[op.graph_id][source_op.graph_id] + 1,
                    )
                )
                for j in list(a & b):
                    problem += (
                        pulp.lpSum(
                            X[source_op][j2]
                            for j2 in range(
                                LB[source_op.graph_id] + input_port.latency_offset,
                                UB[source_op.graph_id] + 1,
                            )
                            if j2 >= j - source_port.latency_offset + 1
                        )
                        + pulp.lpSum(
                            X[op][j1]
                            for j1 in range(LB[op.graph_id], UB[op.graph_id] + 1)
                            if j1 <= j - W[op.graph_id][source_op.graph_id] * Ts
                        )
                        <= 1
                    )

        # Check the ASAP candidate against the complete model before passing
        # it to the solver. Fixed output times or additional resource limits
        # may rule it out even when its data dependencies are satisfied.
        warm_start = all(
            (var.lowBound is None or value >= var.lowBound)
            and (var.upBound is None or value <= var.upBound)
            for var, value in initial_values.items()
        )
        if warm_start:
            for constraint in problem.constraints():
                residual = constraint.constant + sum(
                    coefficient * initial_values[var]
                    for var, coefficient in constraint.items()
                )
                if (
                    constraint.sense == pulp.LpConstraintEQ and residual != 0
                ) or residual * constraint.sense < 0:
                    warm_start = False
                    break
        if warm_start:
            for var, value in initial_values.items():
                var.setInitialValue(value)

        stats = _solve_ilp_problem(problem, self._solver, warm_start=warm_start)

        if not stats.has_solution:
            raise ValueError("Solution could not be found via ILP, use another method.")

        for op in ops:
            for time in range(LB[op.graph_id], UB[op.graph_id] + 1):
                if round(pulp.value(X[op][time])) == 1:
                    schedule.start_times[op.graph_id] = time
                    break

        self._finish_schedule(schedule, Ts)


class CPScheduler(_OptimizationScheduler):
    """
    Constraint programming scheduler minimizing concurrent operations and I/O.

    Minimizes the sum of peak resource counts for each operation type, including
    I/O. For cyclic schedules, resource constraints count overlap between
    successive iterations.

    Requires the optional ``cp`` dependencies (``pip install b-asic[cp]``).

    Parameters
    ----------
    solver : str or :class:`~cpmpy.solvers.solver_interface.SolverInterface`, optional
        CPMpy solver name (default: ``"ortools"``) or a fresh solver instance.
        Constraints and the objective are added to supplied instances in place,
        preserving native solver settings.
    input_times : dict(GraphID, int), optional
        The times when inputs arrive.
    output_delta_times : dict(GraphID, int), optional
        The relative times when outputs should be produced.
    output_times : dict(GraphID, int), optional
        The times when outputs should be produced. For cyclic schedules these
        specify the time within the schedule period.
    max_time : int, optional
        The time horizon to schedule for in cyclic scheduling. The iteration
        period is specified by the Schedule's ``schedule_time`` parameter.
    sort_y_location : bool, default: True
        If the y-location should be sorted based on start time of operations.
    **kwargs : Any
        Options passed to the CPMpy solver's ``solve()`` method, for example
        ``time_limit=60`` or, for OR-Tools, ``num_search_workers=4``.

    Examples
    --------
    Schedule an SFG with a given schedule time:

    .. code-block:: python

        from b_asic import CPScheduler, Schedule

        schedule = Schedule(sfg, CPScheduler(), schedule_time=20)
    """

    def __init__(
        self,
        solver: "str | SolverInterface | None" = None,
        input_times: dict["GraphID", int] | None = None,
        output_delta_times: dict["GraphID", int] | None = None,
        output_times: dict["GraphID", int] | None = None,
        max_time: int | None = None,
        sort_y_location: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(
            input_times=input_times,
            output_delta_times=output_delta_times,
            output_times=output_times,
            sort_y_location=sort_y_location,
        )
        if max_time is not None and (not isinstance(max_time, int) or max_time <= 0):
            raise ValueError("max_time must be a positive integer.")
        self._solver = solver
        self._max_time = max_time
        self._solver_options = kwargs

    def apply_scheduling(self, schedule: "Schedule") -> None:
        # Keep CPMpy optional for users of the other schedulers.
        try:
            import cpmpy as cp  # noqa: PLC0415
            from cpmpy.solvers.solver_interface import SolverInterface  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("CPScheduler requires CPMpy; install b-asic[cp]") from exc

        if self._solver is not None and not isinstance(
            self._solver, (str, SolverInterface)
        ):
            raise TypeError("CPScheduler requires a CPMpy solver name or instance")

        self._schedule = schedule
        lower, asap_time = self._get_asap_start_times(
            schedule, self._input_times, self._output_delta_times
        )
        Ts = schedule.schedule_time
        if Ts is None:
            Ts = asap_time
            schedule._schedule_time = Ts
        if Ts <= 0:
            raise ValueError("CPScheduler requires a positive schedule time.")
        if not schedule.cyclic and asap_time > Ts:
            raise ValueError(
                f"Shortest possible schedule time, {asap_time}, is longer than requested schedule time {Ts}. Use cyclic scheduling or increase schedule time."
            )
        if self._max_time is not None and not schedule.cyclic:
            raise ValueError("max_time is only supported for cyclic scheduling.")
        horizon = max(Ts, self._max_time or Ts)
        upper = self._get_alap_start_times(
            schedule,
            self._input_times,
            self._output_delta_times,
            max_time=horizon,
        )
        ops = [
            op
            for op in schedule._sfg.operations
            if not isinstance(op, (Delay, DontCare, Sink))
        ]
        model = cp.Model()
        starts = {}
        groups = defaultdict(list)
        for op in ops:
            op_id = op.graph_id
            if lower[op_id] > upper[op_id]:
                raise ValueError(
                    "Solution could not be found via CP, use another method."
                )
            if op.execution_time is None:
                raise ValueError(f"Operation {op_id} has no execution time.")
            starts[op_id] = cp.intvar(lower[op_id], upper[op_id], name=op_id)
            # Include isolated and zero-duration operations in the solver model.
            model += starts[op_id] >= lower[op_id]
            groups[op.type_name()].append(op)

        for op_id, time in self._input_times.items():
            model += starts[op_id] == time
        if self._output_delta_times:
            output_base = cp.intvar(0, horizon, name="output_base")
            for op_id, delta in self._output_delta_times.items():
                model += starts[op_id] == output_base + delta
        for op_id, time in self._output_times.items():
            if schedule.cyclic:
                model += starts[op_id] % Ts == time % Ts
                model += time <= Ts
                if time == Ts:
                    model += starts[op_id] > 0
            else:
                model += starts[op_id] == time

        stages = {
            op.graph_id: (
                cp.max([starts[op.graph_id] - 1, 0]) // Ts
                if isinstance(op, Output)
                else starts[op.graph_id] // Ts
            )
            for op in ops
        }
        # Follow each input separately: parallel edges may have different delays
        # and different latency offsets even when their source operation agrees.
        for op in ops:
            for port in op.inputs:
                source = port.connected_source
                depth = 0
                while isinstance(source.operation, Delay):
                    source = source.operation.input(0).connected_source
                    depth += 1
                if isinstance(source.operation, DontCare):
                    continue
                model += (
                    starts[source.operation.graph_id] + source.latency_offset
                    <= starts[op.graph_id] + port.latency_offset + depth * Ts
                )
                if schedule.cyclic:
                    source_id = source.operation.graph_id
                    source_phase = starts[source_id] - stages[source_id] * Ts
                    model += (
                        depth
                        + stages[op.graph_id]
                        - stages[source_id]
                        - (source_phase + source.latency_offset > Ts)
                        >= 0
                    )

        capacities = []
        for op_type, group in groups.items():
            capacity = cp.intvar(
                0,
                sum(max(1, math.ceil(op.execution_time / Ts)) for op in group),
                name=f"resources_{op_type}",
            )
            capacities.append(capacity)
            if schedule.cyclic:
                # Count busy instances from all iterations, including execution
                # intervals that cross the period boundary or span full periods.
                for time in range(Ts):
                    model += (
                        cp.sum(
                            [
                                op.execution_time // Ts
                                + (
                                    (
                                        time
                                        + (horizon // Ts + 1) * Ts
                                        - starts[op.graph_id]
                                    )
                                    % Ts
                                    < op.execution_time % Ts
                                )
                                for op in group
                            ]
                        )
                        <= capacity
                    )
            else:
                busy = [op for op in group if op.execution_time > 0]
                if busy:
                    model += cp.Cumulative(
                        [starts[op.graph_id] for op in busy],
                        [op.execution_time for op in busy],
                        [starts[op.graph_id] + op.execution_time for op in busy],
                        [1] * len(busy),
                        capacity,
                    )
        objective = cp.sum(capacities)
        model.minimize(objective)
        solver = self._solver or "ortools"
        if isinstance(solver, str):
            solved = model.solve(solver=solver, **self._solver_options)
        else:
            solver += model.constraints
            solver.minimize(objective)
            solved = solver.solve(**self._solver_options)
        if not solved:
            raise ValueError("Solution could not be found via CP, use another method.")
        for op_id, start in starts.items():
            schedule.start_times[op_id] = int(start.value())
        if schedule.cyclic:
            self._finish_cyclic_schedule(schedule, Ts, horizon)
        else:
            self._finish_schedule(schedule, Ts)

    def _finish_cyclic_schedule(
        self, schedule: "Schedule", period: int, horizon: int
    ) -> None:
        # Place utility operations in absolute time before folding the schedule.
        schedule._schedule_time = horizon
        self._handle_utility_operations()
        schedule.remove_delays()
        stages = {}
        for op in schedule._sfg.operations:
            time = schedule.start_times[op.graph_id]
            phase = time % period
            if phase == 0 and time > 0 and isinstance(op, (Output, Sink)):
                phase = period
            stages[op.graph_id] = (time - phase) // period
            schedule.start_times[op.graph_id] = phase
        for op in schedule._sfg.operations:
            for port in op.inputs:
                source = port.connected_source
                source_id = source.operation.graph_id
                wrapped = (
                    schedule.start_times[source_id] + source.latency_offset > period
                )
                schedule.laps[port.signals[0].graph_id] += (
                    stages[op.graph_id] - stages[source_id] - int(wrapped)
                )
        schedule._schedule_time = period
        if self._sort_y_location:
            schedule.sort_y_locations_on_start_times()
