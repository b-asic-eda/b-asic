"""
B-ASIC Schedule Module.

Contains the schedule class for scheduling operations in an SFG.
"""

import io
import sys
from collections import defaultdict
from collections.abc import Sequence
from typing import cast

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import PathPatch, Polygon
from matplotlib.path import Path
from matplotlib.ticker import MaxNLocator

from b_asic import Signal
from b_asic._preferences import (
    EXECUTION_TIME_COLOR,
    LATENCY_COLOR,
    OPERATION_GAP,
    SCHEDULE_OFFSET,
    SIGNAL_COLOR,
    SIGNAL_LINEWIDTH,
    SPLINE_OFFSET,
)
from b_asic.core_operations import DontCare, Sink
from b_asic.graph_component import GraphID
from b_asic.operation import Operation
from b_asic.port import InputPort, OutputPort
from b_asic.process import MemoryVariable, OperatorProcess
from b_asic.resources import ProcessCollection
from b_asic.scheduler import Scheduler
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Delay, Input, Output
from b_asic.types import TypeName

# Need RGB from 0 to 1
_EXECUTION_TIME_COLOR: tuple[float, ...] = tuple(
    float(c / 255) for c in EXECUTION_TIME_COLOR
)
_LATENCY_COLOR: tuple[float, ...] = tuple(float(c / 255) for c in LATENCY_COLOR)
_SIGNAL_COLOR: tuple[float, ...] = tuple(float(c / 255) for c in SIGNAL_COLOR)


def _laps_default():
    """Default value for _laps. Cannot use lambda."""
    return 0


def _y_locations_default():
    """Default value for _y_locations. Cannot use lambda."""
    return None


class Schedule:
    """
    Schedule of an SFG with scheduled Operations.

    Parameters
    ----------
    sfg : :class:`~b_asic.signal_flow_graph.SFG`
        The signal flow graph to schedule.
    scheduler : Scheduler, default: None
        The automatic scheduler to be used.
    schedule_time : int, optional
        The schedule time. If not provided, it will be determined by the scheduling
        algorithm.
    cyclic : bool, default: False
        If the schedule is cyclic.
    start_times : dict, optional
        Dictionary with GraphIDs as keys and start times as values.
        Used when *algorithm* is 'provided'.
    laps : dict, optional
        Dictionary with GraphIDs as keys and laps as values.
        Used when *algorithm* is 'provided'.
    """

    _sfg: SFG
    _start_times: dict[GraphID, int]
    _laps: dict[GraphID, int]
    _schedule_time: int
    _cyclic: bool
    _y_locations: dict[GraphID, int | None]

    def __init__(
        self,
        sfg: SFG,
        scheduler: Scheduler | None = None,
        schedule_time: int | None = None,
        cyclic: bool = False,
        start_times: dict[GraphID, int] | None = None,
        laps: dict[GraphID, int] | None = None,
    ):
        """Construct a Schedule from an SFG."""
        if not isinstance(sfg, SFG):
            raise TypeError("An SFG must be provided")

        self._sfg = sfg
        self._start_times = {}
        self._laps = defaultdict(_laps_default)
        self._cyclic = cyclic
        self._y_locations = defaultdict(_y_locations_default)
        self._schedule_time = schedule_time

        if scheduler:
            self._scheduler = scheduler
            self._scheduler.apply_scheduling(self)
        elif start_times is None and laps is None:
            from b_asic.scheduler import ASAPScheduler

            self._scheduler = ASAPScheduler()
            self._scheduler.apply_scheduling(self)
        else:
            if start_times is None:
                raise ValueError("Must provide start_times when using 'provided'")
            if laps is None:
                raise ValueError("Must provide laps when using 'provided'")
            self._start_times = start_times
            self._laps.update(laps)
            self._remove_delays_no_laps()

        max_end_time = self.get_max_end_time()
        if not self._schedule_time:
            self._schedule_time = max_end_time

        self._validate_schedule()

    def __str__(self) -> str:
        """Return a string representation of this Schedule."""
        res: list[tuple[GraphID, int, int, int]] = [
            (
                op.graph_id,
                self.start_time_of_operation(op.graph_id),
                cast(int, self.backward_slack(op.graph_id)),
                self.forward_slack(op.graph_id),
            )
            for op in self._sfg.operations
        ]
        res.sort(key=lambda tup: tup[0])
        res_str = [
            (
                r[0],
                r[1],
                f"{r[2]}".rjust(8) if r[2] < sys.maxsize else "oo".rjust(8),
                f"{r[3]}".rjust(8) if r[3] < sys.maxsize else "oo".rjust(8),
            )
            for r in res
        ]

        string_io = io.StringIO()

        header = ["Graph ID", "Start time", "Backward slack", "Forward slack"]
        string_io.write("|".join(f"{col:^15}" for i, col in enumerate(header)) + "\n")
        string_io.write("-" * (15 * len(header) + len(header) - 1) + "\n")

        for r in res_str:
            row_str = "|".join(f"{item!s:^15}" for i, item in enumerate(r))
            string_io.write(row_str + "\n")

        return string_io.getvalue()

    def _validate_schedule(self) -> None:
        if self._schedule_time is None:
            raise ValueError("Schedule without set scheduling time detected.")
        if not isinstance(self._schedule_time, int):
            raise ValueError("Schedule with non-integer scheduling time detected.")

        ops = {op.graph_id for op in self._sfg.operations}
        missing_elems = ops - set(self._start_times)
        extra_elems = set(self._start_times) - ops
        if missing_elems:
            raise ValueError(
                f"Missing operations detected in start_times: {missing_elems}"
            )
        if extra_elems:
            raise ValueError(f"Extra operations detected in start_times: {extra_elems}")

        for graph_id, time in self._start_times.items():
            if self.forward_slack(graph_id) < 0:
                raise ValueError(
                    f"Negative forward slack detected in Schedule for operation: {graph_id}, "
                    f"slack: {self.forward_slack(graph_id)}."
                )
            if self.backward_slack(graph_id) < 0:
                raise ValueError(
                    f"Negative backward slack detected in Schedule for operation: {graph_id}, "
                    f"slack: {self.backward_slack(graph_id)}"
                )
            if time > self._schedule_time and not isinstance(
                self._sfg.find_by_id(graph_id), DontCare
            ):
                raise ValueError(
                    f"Start time larger than scheduling time detected in Schedule for operation {graph_id}"
                )

    def start_time_of_operation(self, graph_id: GraphID) -> int:
        """
        Return the start time of the operation with the specified by *graph_id*.

        Parameters
        ----------
        graph_id : GraphID
            The graph id of the operation to get the start time for.
        """
        if graph_id not in self._start_times:
            raise ValueError(f"No operation with graph_id {graph_id!r} in schedule")
        return self._start_times[graph_id]

    def get_max_end_time(self) -> int:
        """Return the current maximum end time among all operations."""
        max_end_time = 0
        for graph_id, op_start_time in self._start_times.items():
            operation = cast(Operation, self._sfg.find_by_id(graph_id))
            if isinstance(operation, Output):
                max_end_time = max(max_end_time, op_start_time)
            else:
                for outport in operation.outputs:
                    max_end_time = max(
                        max_end_time,
                        op_start_time + cast(int, outport.latency_offset),
                    )
        return max_end_time

    def get_max_non_io_end_time(self) -> int:
        """Return the current maximum end time among all non-IO operations."""
        max_end_time = 0
        for graph_id, op_start_time in self._start_times.items():
            operation = cast(Operation, self._sfg.find_by_id(graph_id))
            if isinstance(operation, Output):
                continue
            else:
                for outport in operation.outputs:
                    max_end_time = max(
                        max_end_time,
                        op_start_time + cast(int, outport.latency_offset),
                    )
        return max_end_time

    def forward_slack(self, graph_id: GraphID) -> int:
        """
        Return how much an operation can be moved forward in time.

        Parameters
        ----------
        graph_id : GraphID
            The graph id of the operation.

        Returns
        -------
        int
            The number of time steps the operation with *graph_id* can be moved
            forward in time.

        See Also
        --------
        backward_slack
        slacks
        """
        if graph_id not in self._start_times:
            raise ValueError(f"No operation with graph_id {graph_id!r} in schedule")
        output_slacks = self._forward_slacks(graph_id)
        return cast(
            int,
            min(
                sum(
                    (
                        list(signal_slacks.values())
                        for signal_slacks in output_slacks.values()
                    ),
                    [sys.maxsize],
                )
            ),
        )

    def _forward_slacks(
        self, graph_id: GraphID
    ) -> dict["OutputPort", dict["Signal", int]]:
        ret = {}
        start_time = self._start_times[graph_id]
        operation = cast(Operation, self._sfg.find_by_id(graph_id))
        for output_port in operation.outputs:
            ret[output_port] = self._output_slacks(output_port, start_time)
        return ret

    def _output_slacks(
        self, output_port: "OutputPort", start_time: int | None = None
    ) -> dict[Signal, int]:
        if start_time is None:
            start_time = self._start_times[output_port.operation.graph_id]
        output_slacks = {}
        available_time = start_time + cast(int, output_port.latency_offset)
        if available_time > self._schedule_time:
            available_time -= self._schedule_time
        for signal in output_port.signals:
            destination = cast(InputPort, signal.destination)
            usage_time = (
                cast(int, destination.latency_offset)
                + self._start_times[destination.operation.graph_id]
                + self._schedule_time * self._laps[signal.graph_id]
            )
            output_slacks[signal] = usage_time - available_time
        return output_slacks

    def backward_slack(self, graph_id: GraphID) -> int:
        """
        Return how much an operation can be moved backward in time.

        Parameters
        ----------
        graph_id : GraphID
            The graph id of the operation.

        Returns
        -------
        int
            The number of time steps the operation with *graph_id* can be moved
            backward in time.
        .. note:: The backward slack is positive, but a call to
            :func:`move_operation` should be negative to move the operation
            backward.

        See Also
        --------
        forward_slack
        slacks
        """
        if graph_id not in self._start_times:
            raise ValueError(f"No operation with graph_id {graph_id!r} in schedule")
        input_slacks = self._backward_slacks(graph_id)
        return cast(
            int,
            min(
                sum(
                    (
                        list(signal_slacks.values())
                        for signal_slacks in input_slacks.values()
                    ),
                    [sys.maxsize],
                )
            ),
        )

    def _backward_slacks(self, graph_id: GraphID) -> dict[InputPort, dict[Signal, int]]:
        ret = {}
        start_time = self._start_times[graph_id]
        operation = cast(Operation, self._sfg.find_by_id(graph_id))
        for input_port in operation.inputs:
            ret[input_port] = self._input_slacks(input_port, start_time)
        return ret

    def _input_slacks(
        self, input_port: InputPort, start_time: int | None = None
    ) -> dict[Signal, int]:
        if start_time is None:
            start_time = self._start_times[input_port.operation.graph_id]
        input_slacks = {}
        usage_time = start_time + cast(int, input_port.latency_offset)
        for signal in input_port.signals:
            source = cast(OutputPort, signal.source)
            if isinstance(source.operation, (DontCare, Delay)):
                available_time = 0
            else:
                if self._schedule_time is not None:
                    available_time = (
                        cast(int, source.latency_offset)
                        + self._start_times[source.operation.graph_id]
                    )
                    if available_time > self._schedule_time:
                        available_time -= self._schedule_time
                    available_time -= self._schedule_time * self._laps[signal.graph_id]
                else:
                    available_time = (
                        cast(int, source.latency_offset)
                        + self._start_times[source.operation.graph_id]
                    )

            input_slacks[signal] = usage_time - available_time
        return input_slacks

    def slacks(self, graph_id: GraphID) -> tuple[int, int]:
        """
        Return the backward and forward slacks of operation *graph_id*.

        That is, how much the operation can be moved backward and forward in time.

        Parameters
        ----------
        graph_id : GraphID
            The graph id of the operation.

        Returns
        -------
        tuple(int, int)
            The backward and forward slacks, respectively.
        .. note:: The backward slack is positive, but a call to :func:`move_operation`
            should be negative to move the operation backward.

        See Also
        --------
        backward_slack
        forward_slack
        """
        if graph_id not in self._start_times:
            raise ValueError(f"No operation with graph_id {graph_id!r} in schedule")
        return self.backward_slack(graph_id), self.forward_slack(graph_id)

    def print_slacks(self, order: int = 0, type_name: TypeName | None = None) -> None:
        """
        Print the slack times for all operations in the schedule.

        Parameters
        ----------
        order : int, default: 0
            Sorting order.

            * 0: alphabetical on Graph ID
            * 1: backward slack
            * 2: forward slack

        type_name : TypeName, optional
            If given, only the slack times for operations of this type will be printed.
        """
        if type_name is None:
            operations = self._sfg.operations
        else:
            operations = [
                op for op in self._sfg.operations if isinstance(op, type_name)
            ]

        res: list[tuple[GraphID, int, int]] = [
            (
                op.graph_id,
                cast(int, self.backward_slack(op.graph_id)),
                self.forward_slack(op.graph_id),
            )
            for op in operations
        ]
        res.sort(key=lambda tup: tup[order])
        res_str = [
            (
                r[0],
                f"{r[1]}".rjust(8) if r[1] < sys.maxsize else "oo".rjust(8),
                f"{r[2]}".rjust(8) if r[2] < sys.maxsize else "oo".rjust(8),
            )
            for r in res
        ]
        print("Graph ID | Backward |  Forward")
        print("---------|----------|---------")
        for r in res_str:
            print(f"{r[0]:8} | {r[1]} | {r[2]}")

    def set_schedule_time(self, time: int) -> "Schedule":
        """
        Set a new schedule time.

        Parameters
        ----------
        time : int
            The new schedule time. If it is too short, a ValueError will be raised.

        See Also
        --------
        get_max_time
        """
        max_end_time = self.get_max_end_time()
        if time < max_end_time:
            raise ValueError(
                f"New schedule time ({time}) too short, minimum: {max_end_time}."
            )

        # if updating the scheduling time -> update laps due to operations
        # reading and writing in different iterations (across the edge)
        if self._schedule_time is not None:
            for signal_id in self._laps:
                port = self._sfg.find_by_id(signal_id).destination

                source_port = port.signals[0].source
                source_op = source_port.operation
                source_port_start_time = self._start_times[source_op.graph_id]
                source_port_latency_offset = source_op.latency_offsets[
                    f"out{source_port.index}"
                ]
                if (
                    source_port_start_time + source_port_latency_offset
                    > self._schedule_time
                    and source_port_start_time + source_port_latency_offset <= time
                ):
                    self._laps[signal_id] += 1

        self._schedule_time = time
        return self

    def swap_io_of_operation(self, operation_id: GraphID) -> None:
        """
        Swap the inputs (and outputs) of operation.

        Parameters
        ----------
        operation_id : GraphID
            The GraphID of the operation to swap.
        """
        self._sfg.swap_io_of_operation(operation_id)

    @property
    def sfg(self) -> SFG:
        """The SFG corresponding to the current schedule."""
        reconstructed_sfg = self._reintroduce_delays()
        simplified_sfg = reconstructed_sfg.simplify_delay_element_placement()
        return simplified_sfg

    @property
    def start_times(self) -> dict[GraphID, int]:
        """The start times of the operations in the schedule."""
        return self._start_times

    @start_times.setter
    def start_times(self, start_times: dict[GraphID, int]) -> None:
        if not isinstance(start_times, dict):
            raise TypeError("start_times must be a dict")
        for key, value in start_times.items():
            if not isinstance(key, str) or not isinstance(value, int):
                raise TypeError("start_times must be a dict[GraphID, int]")
        self._start_times = start_times

    @property
    def laps(self) -> dict[GraphID, int]:
        """
        The number of laps for the start times of the operations in the schedule.
        """
        return self._laps

    @property
    def schedule_time(self) -> int:
        """The schedule time of the current schedule."""
        return self._schedule_time

    @property
    def cyclic(self) -> bool:
        """If the current schedule is cyclic."""
        return self._cyclic

    def edit(self, inplace=False) -> "Schedule":
        """
        Edit schedule in GUI and return new schedule.

        Parameters
        ----------
        inplace : bool, default: False
            If True, replace the current schedule.
        """
        from b_asic.scheduler_gui.main_window import start_scheduler

        new_schedule = start_scheduler(self)
        if inplace:
            self._start_times = new_schedule._start_times
            self._laps = new_schedule._laps
            self._schedule_time = new_schedule._schedule_time
            self._y_locations = new_schedule._y_locations
        return new_schedule

    def increase_time_resolution(self, factor: int) -> "Schedule":
        """
        Increase time resolution for a schedule.

        Parameters
        ----------
        factor : int
            The time resolution increment.
        """
        self._start_times = {k: factor * v for k, v in self._start_times.items()}
        for graph_id in self._start_times:
            cast(Operation, self._sfg.find_by_id(graph_id))._increase_time_resolution(
                factor
            )
        self._schedule_time *= factor
        return self

    def _get_all_times(self) -> list[int]:
        """
        Return a list of all times for the schedule.

        Used to check how the resolution can be modified.
        """
        # Local values
        ret = [self._schedule_time, *self._start_times.values()]
        # Loop over operations
        for graph_id in self._start_times:
            operation = cast(Operation, self._sfg.find_by_id(graph_id))
            ret += [
                cast(int, operation.execution_time),
                *operation.latency_offsets.values(),
            ]
        # Remove not set values (None)
        ret = [v for v in ret if v is not None]
        return ret

    def get_possible_time_resolution_decrements(self) -> list[int]:
        """Return a list with possible factors to reduce time resolution."""
        vals = self._get_all_times()
        max_loop = min(val for val in vals if val)
        if max_loop <= 1:
            return [1]
        ret = [1]
        for candidate in range(2, max_loop + 1):
            if not any(val % candidate for val in vals):
                ret.append(candidate)
        return ret

    def decrease_time_resolution(self, factor: int) -> "Schedule":
        """
        Decrease time resolution for a schedule.

        Parameters
        ----------
        factor : int
            The time resolution decrement.

        See Also
        --------
        get_possible_time_resolution_decrements
        """
        possible_values = self.get_possible_time_resolution_decrements()
        if factor not in possible_values:
            raise ValueError(
                f"Not possible to decrease resolution with {factor}. Possible"
                f" values are {possible_values}"
            )
        self._start_times = {k: v // factor for k, v in self._start_times.items()}
        for graph_id in self._start_times:
            cast(Operation, self._sfg.find_by_id(graph_id))._decrease_time_resolution(
                factor
            )
        self._schedule_time = self._schedule_time // factor
        return self

    def set_execution_time_of_type_name(
        self, type_name: TypeName, execution_time: int
    ) -> None:
        """
        Set the execution time of all operations with the given type name.

        Parameters
        ----------
        type_name : TypeName
            The type name of the operation. For example, obtained as
            ``Addition.type_name()``.
        execution_time : int
            The execution time of the operation.
        """
        self._sfg.set_execution_time_of_type_name(type_name, execution_time)

    def set_latency_of_type_name(
        self, type_name: TypeName | GraphID, latency: int
    ) -> None:
        """
        Set the latency of all operations with the given type name.

        Parameters
        ----------
        type_name : TypeName or GraphID
            The type name of the operation, e.g., obtained as
            ``Addition.type_name()`` or a specific GraphID of an operation.
        latency : int
            The latency of the operation.
        """
        passed = True
        for op in self._sfg.operations:
            if type_name in (op.type_name(), op.graph_id):
                change_in_latency = latency - op.latency
                if change_in_latency > (self.forward_slack(op.graph_id)):
                    passed = False
                    raise ValueError(
                        f"Error: Can't increase latency for all components. Try increasing forward slack time by rescheduling. "
                        f"Error in: {op.graph_id}"
                    )
                    break
        if change_in_latency < 0 or passed:
            for op in self._sfg.operations:
                if type_name in (op.type_name(), op.graph_id):
                    cast(Operation, op).set_latency(latency)

    def move_y_location(
        self, graph_id: GraphID, new_y: int, insert: bool = False
    ) -> None:
        """
        Move operation in y-direction and remove any empty rows.

        Parameters
        ----------
        graph_id : GraphID
            The GraphID of the operation to move.
        new_y : int
            The new y-position of the operation.
        insert : bool, optional
            If True, all operations on that y-position will be moved one position.
            The default is False.
        """
        if insert:
            for gid in self._y_locations:
                if self.get_y_location(gid) >= new_y:
                    self.set_y_location(gid, self.get_y_location(gid) + 1)
        self.set_y_location(graph_id, new_y)
        used_locations = {*self._y_locations.values()}
        possible_locations = set(range(round(max(used_locations)) + 1))
        if not possible_locations - used_locations:
            return
        remapping = {}
        offset = 0
        for loc in possible_locations:
            if loc in used_locations:
                remapping[loc] = loc - offset
            else:
                offset += 1

        for gid in self._y_locations:
            self._y_locations[gid] = remapping[self._y_locations[gid]]

    def get_y_location(self, graph_id: GraphID) -> int:
        """
        Get the y-position of the Operation with GraphID *graph_id*.

        Parameters
        ----------
        graph_id : GraphID
            The GraphID of the operation.

        Returns
        -------
        int
            The y-position of the operation.
        """
        return self._y_locations[graph_id]

    def set_y_location(self, graph_id: GraphID, y_location: int) -> None:
        """
        Set the y-position of the Operation with GraphID *graph_id* to *y_location*.

        Parameters
        ----------
        graph_id : GraphID
            The GraphID of the operation to move.
        y_location : int
            The new y-position of the operation.
        """
        self._y_locations[graph_id] = y_location

    def _get_minimum_height(
        self, operation_height: float = 1.0, operation_gap: float = OPERATION_GAP
    ):
        max_pos_graph_id = max(self._y_locations, key=self._y_locations.get)
        return self._get_y_plot_location(
            max_pos_graph_id, operation_height, operation_gap
        )

    def place_operation(
        self, op: Operation, time: int, op_laps: dict[GraphID, int]
    ) -> None:
        """Schedule the given operation in given time.

        Parameters
        ----------
        op : Operation
            Operation to schedule.
        time : int
            Time slot to schedule the operation in.
            If time > schedule_time -> schedule cyclically.
        op_laps : dict[GraphID, int]
            Laps of all scheduled operations.
        """
        start = time % self._schedule_time if self._schedule_time else time
        self._start_times[op.graph_id] = start

        if not self.schedule_time:
            return

        # update input laps
        for input_port in op.inputs:
            laps = 0
            if self._schedule_time is not None:
                current_lap = time // self._schedule_time
                source_port = source_op = input_port.signals[0].source
                source_op = source_port.operation

                if not isinstance(source_op, (Delay, DontCare)):
                    if op_laps[source_op.graph_id] < current_lap:
                        laps += current_lap - op_laps[source_op.graph_id]
                    source_available_time = (
                        self._start_times[source_op.graph_id]
                        + source_op.latency_offsets[f"out{source_port.index}"]
                    )
                    if source_available_time > self.schedule_time:
                        laps -= 1
            self._laps[input_port.signals[0].graph_id] = laps

        if (
            start == 0
            and isinstance(op, Output)
            and self._laps[op.input(0).signals[0].graph_id] != 0
        ):
            start = self._schedule_time
            self._laps[op.input(0).signals[0].graph_id] -= 1

        if (
            start == 0
            and isinstance(op, DontCare)
            and self._laps[op.output(0).signals[0].graph_id] == 0
        ):
            start = self._schedule_time
        if (
            time > self._schedule_time
            and isinstance(op, DontCare)
            and self._laps[op.output(0).signals[0].graph_id] == 0
        ):
            start = time % self._schedule_time

        self._start_times[op.graph_id] = start

    def move_operation(self, graph_id: GraphID, time: int) -> "Schedule":
        """
        Move an operation in the schedule.

        Parameters
        ----------
        graph_id : GraphID
            The graph id of the operation to move.
        time : int
            The time to move. If positive move forward, if negative move backward.
        """
        if graph_id not in self._start_times:
            raise ValueError(f"No operation with graph_id {graph_id!r} in schedule")

        if time == 0:
            return self
        (backward_slack, forward_slack) = self.slacks(graph_id)
        if not -backward_slack <= time <= forward_slack:
            raise ValueError(
                f"Operation {graph_id!r} got incorrect move: {time}. Must be"
                f" between {-backward_slack} and {forward_slack}."
            )

        old_start = self._start_times[graph_id]
        tmp_start = old_start + time
        new_start = tmp_start % self._schedule_time

        # Update input laps
        input_slacks = self._backward_slacks(graph_id)
        for in_port, signal_slacks in input_slacks.items():
            tmp_usage = tmp_start + cast(int, in_port.latency_offset)
            new_usage = tmp_usage % self._schedule_time
            for signal, signal_slack in signal_slacks.items():
                # New slack
                new_slack = signal_slack + time
                # Compute a lower limit on laps
                laps = new_slack // self._schedule_time
                # Compensate for cases where above is not correct
                tmp_prev_available = tmp_usage - new_slack
                prev_available = tmp_prev_available % self._schedule_time
                # If prev_available == 0 it will come from previous lap, unless it comes
                # from an Input
                source_op = signal.source_operation
                if prev_available == 0 and not isinstance(source_op, Input):
                    prev_available = self._schedule_time
                # Usage time (new_usage) < available time (prev_available) within a
                # schedule period
                if new_usage < prev_available:
                    laps += 1
                self._laps[signal.graph_id] = laps

        # Update output laps
        output_slacks = self._forward_slacks(graph_id)
        for out_port, signal_slacks in output_slacks.items():
            tmp_available = tmp_start + cast(int, out_port.latency_offset)
            new_available = tmp_available % self._schedule_time
            for signal, signal_slack in signal_slacks.items():
                # New slack
                new_slack = signal_slack - time
                # Compute a lower limit on laps
                laps = new_slack // self._schedule_time
                # Compensate for cases where above is not correct
                tmp_next_usage = tmp_available + new_slack
                next_usage = tmp_next_usage % self._schedule_time
                # Usage time (new_usage) < available time (prev_available) within a
                # schedule period
                if new_available == 0 and (new_slack > 0 or next_usage == 0):
                    new_available = self._schedule_time
                if (
                    next_usage < new_available
                    and self._start_times[signal.destination_operation.graph_id]
                    != self.schedule_time
                ):
                    laps += 1
                self._laps[signal.graph_id] = laps

        # Outputs should not start at 0, but at schedule time
        op = self._sfg.find_by_id(graph_id)
        if (
            new_start == 0
            and isinstance(op, Output)
            and self._laps[op.input(0).signals[0].graph_id] != 0
        ):
            new_start = self._schedule_time
            self._laps[op.input(0).signals[0].graph_id] -= 1
        if new_start == 0 and isinstance(op, Input):
            new_start = 0
            for signal in op.output(0).signals:
                if self._laps[signal.graph_id] != 0:
                    self._laps[signal.graph_id] -= 1
        # Set new start time
        self._start_times[graph_id] = new_start
        return self

    def move_operation_alap(self, graph_id: GraphID) -> "Schedule":
        """
        Move an operation as late as possible in the schedule.

        This is basically the same as::

            schedule.move_operation(graph_id, schedule.forward_slack(graph_id))

        but operations with no succeeding operation (Outputs) will only move to the end
        of the schedule.

        Parameters
        ----------
        graph_id : GraphID
            The graph id of the operation to move.
        """
        forward_slack = self.forward_slack(graph_id)
        if forward_slack == sys.maxsize:
            self.move_operation(
                graph_id, self.schedule_time - self._start_times[graph_id]
            )
        else:
            self.move_operation(graph_id, forward_slack)
        return self

    def move_operation_asap(self, graph_id: GraphID) -> "Schedule":
        """
        Move an operation as soon as possible in the schedule.

        This is basically the same as::

            schedule.move_operation(graph_id, -schedule.backward_slack(graph_id))

        but operations that do not have a preceding operation (Inputs and Constants)
        will only move to the start of the schedule.

        Parameters
        ----------
        graph_id : GraphID
            The graph id of the operation to move.
        """
        backward_slack = self.backward_slack(graph_id)
        if backward_slack == sys.maxsize:
            self.move_operation(graph_id, -self._start_times[graph_id])
        else:
            self.move_operation(graph_id, -backward_slack)
        return self

    def _remove_delays_no_laps(self) -> None:
        """Remove delay elements without updating laps. Used when loading schedule."""
        delay_list = self._sfg.find_by_type(Delay)
        while delay_list:
            delay_op = cast(Delay, delay_list[0])
            self._sfg = cast(SFG, self._sfg.remove_operation(delay_op.graph_id))
            delay_list = self._sfg.find_by_type(Delay)

    def remove_delays(self) -> None:
        """Remove delay elements and update laps. Used after scheduling algorithm."""
        delay_list = self._sfg.find_by_type(Delay)
        while delay_list:
            delay_op = cast(Delay, delay_list[0])
            delay_input_id = delay_op.input(0).signals[0].graph_id
            delay_output_ids = [sig.graph_id for sig in delay_op.output(0).signals]
            self._sfg = cast(SFG, self._sfg.remove_operation(delay_op.graph_id))
            for output_id in delay_output_ids:
                self._laps[output_id] += 1 + self._laps[delay_input_id]
            del self._laps[delay_input_id]
            delay_list = self._sfg.find_by_type(Delay)

    def _reintroduce_delays(self) -> SFG:
        """
        Reintroduce delay elements to each signal according to the ``_laps`` variable.
        """
        new_sfg = self._sfg()
        destination_laps = []
        for signal_id, lap in self._laps.items():
            port = new_sfg.find_by_id(signal_id).destination

            # if an operation lies across the scheduling time, place a delay after it
            source_port = port.signals[0].source
            source_op = source_port.operation
            source_port_start_time = self._start_times[source_op.graph_id]
            source_port_latency_offset = source_op.latency_offsets[
                f"out{source_port.index}"
            ]
            if (
                source_port_start_time + source_port_latency_offset
                > self._schedule_time
            ):
                lap += 1

            destination_laps.append((port.operation.graph_id, port.index, lap))

        for op, port, lap in destination_laps:
            for _ in range(lap):
                new_sfg = new_sfg.insert_operation_before(op, Delay(), port)
        return new_sfg()

    def _get_memory_variables_list(self) -> list[MemoryVariable]:
        ret: list[MemoryVariable] = []
        for graph_id, start_time in self._start_times.items():
            slacks = self._forward_slacks(graph_id)
            for outport, signals in slacks.items():
                if outport.name.startswith("dontcare"):
                    continue
                reads = {
                    cast(InputPort, signal.destination): slack
                    for signal, slack in signals.items()
                }
                ret.append(
                    MemoryVariable(
                        (start_time + cast(int, outport.latency_offset))
                        % self.schedule_time,
                        outport,
                        reads,
                        outport.name,
                    )
                )
        return ret

    def get_memory_variables(self) -> ProcessCollection:
        """
        Return a ProcessCollection containing all memory variables.

        Returns
        -------
        :class:`~b_asic.resources.ProcessCollection`
        """
        return ProcessCollection(
            set(self._get_memory_variables_list()), self.schedule_time
        )

    def get_operations(self) -> ProcessCollection:
        """
        Return a ProcessCollection containing all operations.

        Returns
        -------
        :class:`~b_asic.resources.ProcessCollection`
        """
        return ProcessCollection(
            {
                OperatorProcess(
                    start_time, cast(Operation, self._sfg.find_by_id(graph_id))
                )
                for graph_id, start_time in self._start_times.items()
                if not isinstance(self._sfg.find_by_id(graph_id), DontCare)
                and not isinstance(self._sfg.find_by_id(graph_id), Sink)
            },
            self.schedule_time,
            self.cyclic,
        )

    def get_used_type_names(self) -> list[TypeName]:
        """Get a list of all TypeNames used in the Schedule."""
        return self._sfg.get_used_type_names()

    def _get_y_plot_location(
        self, graph_id, operation_height=1.0, operation_gap=OPERATION_GAP
    ) -> float:
        y_location = self._y_locations[graph_id]
        if y_location is None:
            # Assign the lowest row number not yet in use
            used = {loc for loc in self._y_locations.values() if loc is not None}
            possible = set(range(len(self._start_times))) - used
            y_location = min(possible)
            self._y_locations[graph_id] = y_location
        return operation_gap + y_location * (operation_height + operation_gap)

    def sort_y_locations_on_start_times(self) -> None:
        """
        Sort the y-locations of the schedule based on start times of the operations.

        Inputs, outputs, dontcares, and sinks are located adjacent to the operations that
        they are connected to.

        See Also
        --------
        move_y_location
        set_y_location
        """

        def sort_key(graph_id):
            op = self._sfg.find_by_id(graph_id)
            return (
                self._start_times[op.graph_id],
                -self._sfg.find_by_id(graph_id).latency,
            )

        for i, graph_id in enumerate(sorted(self._start_times, key=sort_key)):
            self.set_y_location(graph_id, i)

        for graph_id in self._start_times:
            op = cast(Operation, self._sfg.find_by_id(graph_id))
            # Position Outputs and Sinks adjacent to the operation generating them
            if isinstance(op, (Output, Sink)):
                gen_op: Operation = op.preceding_operations[0]
                if (
                    gen_op.output_count == 1
                    or op.input(0).signals[0].source.index >= gen_op.output_count / 2
                ):
                    # Single output operation generating or lower half of outputs
                    # Put below
                    self.move_y_location(
                        graph_id,
                        self.get_y_location(gen_op.graph_id) + 1,
                        True,
                    )
                else:
                    # Put above
                    self.move_y_location(
                        graph_id,
                        self.get_y_location(gen_op.graph_id),
                        True,
                    )
            # Position DontCares and Inputs adjacent to the operation using them
            if isinstance(op, (DontCare, Input)):
                # Find the "top" connected operation (for DontCare there is always one, but use general case there as well)
                # TODO: Only check conconnected operations that do not have a lap
                dest_ops = {
                    sub_op: self.get_y_location(sub_op.graph_id)
                    for sub_op in op.subsequent_operations
                }
                dest_op = min(dest_ops, key=dest_ops.get)
                if (
                    dest_op.input_count == 1
                    or op.output(0).signals[0].destination.index
                    < dest_op.input_count / 2
                ):
                    # For single input operation consuming or upper half, position above
                    self.move_y_location(
                        graph_id,
                        self.get_y_location(dest_op.graph_id),
                        True,
                    )
                else:
                    # Position below
                    self.move_y_location(
                        graph_id,
                        self.get_y_location(dest_op.graph_id) + 1,
                        True,
                    )

    def _plot_schedule(self, ax: Axes, operation_gap: float = OPERATION_GAP) -> None:
        """Draw the schedule."""
        line_cache = []

        def _draw_arrow(
            start: Sequence[float], end: Sequence[float], name: str = "", laps: int = 0
        ) -> None:
            """Draw an arrow from *start* to *end*."""
            if end[0] > self.schedule_time:
                end[0] %= self.schedule_time
            if start[0] > self.schedule_time:
                start[0] %= self.schedule_time
            if end[0] < start[0] or laps > 0:  # Wrap around
                if start not in line_cache:
                    line = Line2D(
                        [start[0], self._schedule_time + SCHEDULE_OFFSET],
                        [start[1], start[1]],
                        color=_SIGNAL_COLOR,
                        lw=SIGNAL_LINEWIDTH,
                    )
                    ax.add_line(line)
                    ax.text(
                        self._schedule_time + SCHEDULE_OFFSET,
                        start[1],
                        name,
                        verticalalignment="center",
                    )
                line = Line2D(
                    [-SCHEDULE_OFFSET, end[0]],
                    [end[1], end[1]],
                    color=_SIGNAL_COLOR,
                    lw=SIGNAL_LINEWIDTH,
                )
                ax.add_line(line)
                ax.text(
                    -SCHEDULE_OFFSET,
                    end[1],
                    f"{name}: {laps}",
                    verticalalignment="center",
                    horizontalalignment="right",
                )
                line_cache.append(start)

            else:
                if end[0] == start[0]:
                    middle_points = [
                        [start[0] + SPLINE_OFFSET, start[1]],
                        [start[0] - SPLINE_OFFSET, end[1]],
                    ]
                else:
                    middle_points = [
                        [(start[0] + end[0]) / 2, start[1]],
                        [(start[0] + end[0]) / 2, end[1]],
                    ]

                path = Path(
                    [
                        start,
                        *middle_points,
                        end,
                    ],
                    [Path.MOVETO] + [Path.CURVE4] * 3,
                )
                path_patch = PathPatch(
                    path,
                    fc="none",
                    ec=_SIGNAL_COLOR,
                    lw=SIGNAL_LINEWIDTH,
                    zorder=10,
                )
                ax.add_patch(path_patch)

        def _draw_offset_arrow(
            start: Sequence[float],
            end: Sequence[float],
            start_offset: Sequence[float],
            end_offset: Sequence[float],
            name: str = "",
            laps: int = 0,
        ) -> None:
            """Draw an arrow from *start* to *end*, but with an offset."""
            _draw_arrow(
                [start[0] + start_offset[0], start[1] + start_offset[1]],
                [end[0] + end_offset[0], end[1] + end_offset[1]],
                name=name,
                laps=laps,
            )

        ytickpositions = []
        yticklabels = []
        ax.set_axisbelow(True)
        ax.grid()
        for graph_id, op_start_time in self._start_times.items():
            y_pos = self._get_y_plot_location(graph_id, operation_gap=operation_gap)
            operation = cast(Operation, self._sfg.find_by_id(graph_id))
            # Rewrite to make better use of NumPy
            (
                latency_coordinates,
                execution_time_coordinates,
            ) = operation.get_plot_coordinates()
            _x, _y = zip(*latency_coordinates, strict=True)
            x = np.array(_x)
            y = np.array(_y)
            xvalues = x + op_start_time
            xy = np.stack((xvalues, y + y_pos))
            ax.add_patch(Polygon(xy.T, fc=_LATENCY_COLOR))
            if any(xvalues > self.schedule_time) and not isinstance(operation, Output):
                xy = np.stack((xvalues - self.schedule_time, y + y_pos))
                ax.add_patch(Polygon(xy.T, fc=_LATENCY_COLOR))
            if isinstance(operation, Input):
                ax.annotate(
                    graph_id,
                    xy=(op_start_time - 0.48, y_pos + 0.7),
                    color="black",
                    size=10 - (0.05 * len(self._start_times)),
                )
            else:
                ax.annotate(
                    graph_id,
                    xy=(op_start_time + 0.03, y_pos + 0.7),
                    color="black",
                    size=10 - (0.05 * len(self._start_times)),
                )
            if execution_time_coordinates:
                _x, _y = zip(*execution_time_coordinates, strict=True)
                x = np.array(_x)
                y = np.array(_y)
                xvalues = x + op_start_time
                ax.plot(
                    xvalues,
                    y + y_pos,
                    color=_EXECUTION_TIME_COLOR,
                    linewidth=3,
                )
                if any(xvalues > self.schedule_time) and not isinstance(
                    operation, (Output, Sink)
                ):
                    ax.plot(
                        xvalues - self.schedule_time,
                        y + y_pos,
                        color=_EXECUTION_TIME_COLOR,
                        linewidth=3,
                    )

            ytickpositions.append(y_pos + 0.5)
            yticklabels.append(cast(Operation, self._sfg.find_by_id(graph_id)).name)

        for graph_id, op_start_time in self._start_times.items():
            operation = cast(Operation, self._sfg.find_by_id(graph_id))
            out_coordinates = operation.get_output_coordinates()
            source_y_pos = self._get_y_plot_location(
                graph_id, operation_gap=operation_gap
            )

            for output_port in operation.outputs:
                for output_signal in output_port.signals:
                    destination = cast(InputPort, output_signal.destination)
                    destination_op = destination.operation
                    destination_start_time = self._start_times[destination_op.graph_id]
                    destination_y_pos = self._get_y_plot_location(
                        destination_op.graph_id, operation_gap=operation_gap
                    )
                    destination_in_coordinates = (
                        destination.operation.get_input_coordinates()
                    )
                    _draw_offset_arrow(
                        out_coordinates[output_port.index],
                        destination_in_coordinates[destination.index],
                        [op_start_time, source_y_pos],
                        [destination_start_time, destination_y_pos],
                        name=graph_id,
                        laps=self._laps[output_signal.graph_id],
                    )

        ax.set_yticks(ytickpositions)
        ax.set_yticklabels(yticklabels)

        # Get operation with maximum position
        max_pos_graph_id = max(self._y_locations, key=self._y_locations.get)
        y_position_max = (
            self._get_y_plot_location(max_pos_graph_id, operation_gap=operation_gap)
            + 1
            + (OPERATION_GAP if operation_gap is None else operation_gap)
        )
        ax.axis([-0.8, self._schedule_time + 0.8, y_position_max, 0])  # Inverted y-axis
        ax.xaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=1))
        ax.axvline(
            0,
            linestyle="--",
            color="black",
        )
        ax.axvline(
            self._schedule_time,
            linestyle="--",
            color="black",
        )

    def reset_y_locations(self) -> None:
        """Reset all the y-locations in the schedule to None"""
        self._y_locations = defaultdict(_y_locations_default)

    def plot(self, ax: Axes, operation_gap: float = OPERATION_GAP) -> None:
        """
        Plot the schedule in a :class:`matplotlib.axes.Axes` or subclass.

        Parameters
        ----------
        ax : :class:`~matplotlib.axes.Axes`
            The :class:`matplotlib.axes.Axes` to plot in.
        operation_gap : float, optional
            The vertical distance between operations in the schedule. The height of
            the operation is always 1.
        """
        self._plot_schedule(ax, operation_gap=operation_gap)

    def show(
        self, operation_gap: float = OPERATION_GAP, title: str | None = None
    ) -> None:
        """
        Show the schedule. Will display based on the current Matplotlib backend.

        Parameters
        ----------
        operation_gap : float, optional
            The vertical distance between operations in the schedule. The height of
            the operation is always 1.
        title : str, optional
            Figure title.
        """
        fig = self._get_figure(operation_gap=operation_gap)
        if title:
            fig.suptitle(title)
        fig.show()

    def _get_figure(self, operation_gap: float = OPERATION_GAP) -> Figure:
        """
        Create a Figure and an Axes and plot schedule in the Axes.

        Parameters
        ----------
        operation_gap : float, optional
            The vertical distance between operations in the schedule. The height of
            the operation is always 1.

        Returns
        -------
        The Matplotlib Figure.
        """
        height = len(self._start_times) * 0.3 + 0.7
        fig, ax = plt.subplots(figsize=(12, height), layout="constrained")
        self._plot_schedule(ax, operation_gap=operation_gap)
        return fig

    def _repr_svg_(self) -> str:
        """
        Generate an SVG of the schedule. This is automatically displayed in e.g.
        Jupyter Qt console.
        """
        fig = self._get_figure()
        buffer = io.StringIO()
        fig.savefig(buffer, format="svg")

        return buffer.getvalue()

    # SVG is valid HTML. This is useful for e.g. sphinx-gallery
    _repr_html_ = _repr_svg_
