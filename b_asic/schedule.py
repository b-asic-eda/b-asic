"""
B-ASIC Schedule Module.

Contains the schedule class for scheduling operations in an SFG.
"""

import io
import math
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from matplotlib.ticker import MaxNLocator
import numpy as np

from b_asic import OutputPort, Signal
from b_asic.graph_component import GraphID
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Delay, Output


class Schedule:
    """Schedule of an SFG with scheduled Operations."""

    _sfg: SFG
    _start_times: Dict[GraphID, int]
    _laps: Dict[GraphID, List[int]]
    _schedule_time: int
    _cyclic: bool

    def __init__(
        self,
        sfg: SFG,
        schedule_time: Optional[int] = None,
        cyclic: bool = False,
        scheduling_alg: str = "ASAP",
    ):
        """Construct a Schedule from an SFG."""
        self._sfg = sfg
        self._start_times = {}
        self._laps = defaultdict(lambda: 0)
        self._cyclic = cyclic
        if scheduling_alg == "ASAP":
            self._schedule_asap()
        else:
            raise NotImplementedError(
                f"No algorithm with name: {scheduling_alg} defined."
            )

        max_end_time = self.get_max_end_time()

        if schedule_time is None:
            self._schedule_time = max_end_time
        elif schedule_time < max_end_time:
            raise ValueError(
                f"Too short schedule time. Minimum is {max_end_time}."
            )
        else:
            self._schedule_time = schedule_time

    def start_time_of_operation(self, op_id: GraphID) -> int:
        """Get the start time of the operation with the specified by the op_id.
        """
        assert (
            op_id in self._start_times
        ), "No operation with the specified op_id in this schedule."
        return self._start_times[op_id]

    def get_max_end_time(self) -> int:
        """Returns the current maximum end time among all operations."""
        max_end_time = 0
        for op_id, op_start_time in self._start_times.items():
            op = self._sfg.find_by_id(op_id)
            for outport in op.outputs:
                max_end_time = max(
                    max_end_time, op_start_time + outport.latency_offset
                )
        return max_end_time

    def forward_slack(self, op_id: GraphID) -> int:
        assert (
            op_id in self._start_times
        ), "No operation with the specified op_id in this schedule."
        slack = sys.maxsize
        output_slacks = self._forward_slacks(op_id)
        # Make more pythonic
        for signal_slacks in output_slacks.values():
            for signal_slack in signal_slacks.values():
                slack = min(slack, signal_slack)
        return slack

    def _forward_slacks(
        self, op_id: GraphID
    ) -> Dict["OutputPort", Dict["Signal", int]]:
        ret = {}
        start_time = self._start_times[op_id]
        op = self._sfg.find_by_id(op_id)
        for output_port in op.outputs:
            output_slacks = {}
            available_time = start_time + output_port.latency_offset

            for signal in output_port.signals:
                usage_time = (
                    signal.destination.latency_offset
                    + self._start_times[signal.destination.operation.graph_id]
                    + self._schedule_time * self._laps[signal.graph_id]
                )
                output_slacks[signal] = usage_time - available_time
            ret[output_port] = output_slacks
        return ret

    def backward_slack(self, op_id: GraphID) -> int:
        assert (
            op_id in self._start_times
        ), "No operation with the specified op_id in this schedule."
        slack = sys.maxsize
        input_slacks = self._backward_slacks(op_id)
        # Make more pythonic
        for signal_slacks in input_slacks.values():
            for signal_slack in signal_slacks.values():
                slack = min(slack, signal_slack)
        return slack

    def _backward_slacks(
        self, op_id: GraphID
    ) -> Dict["OutputPort", Dict["Signal", int]]:
        ret = {}
        start_time = self._start_times[op_id]
        op = self._sfg.find_by_id(op_id)
        for input_port in op.inputs:
            input_slacks = {}
            usage_time = start_time + input_port.latency_offset

            for signal in input_port.signals:
                available_time = (
                    signal.source.latency_offset
                    + self._start_times[signal.source.operation.graph_id]
                    - self._schedule_time * self._laps[signal.graph_id]
                )
                input_slacks[signal] = usage_time - available_time
            ret[input_port] = input_slacks
        return ret

    def slacks(self, op_id: GraphID) -> Tuple[int, int]:
        assert (
            op_id in self._start_times
        ), "No operation with the specified op_id in this schedule."
        return self.backward_slack(op_id), self.forward_slack(op_id)

    def print_slacks(self) -> None:
        raise NotImplementedError

    def set_schedule_time(self, time: int) -> "Schedule":
        assert self.get_max_end_time() <= time, "New schedule time to short."
        self._schedule_time = time
        return self

    @property
    def sfg(self) -> SFG:
        return self._sfg

    @property
    def start_times(self) -> Dict[GraphID, int]:
        return self._start_times

    @property
    def laps(self) -> Dict[GraphID, List[int]]:
        return self._laps

    @property
    def schedule_time(self) -> int:
        return self._schedule_time

    @property
    def cyclic(self) -> bool:
        return self._cyclic

    def increase_time_resolution(self, factor: int) -> "Schedule":
        """
        Increase time resolution for a schedule.

        Parameters
        ==========

        factor : int
            The time resolution increment.
        """
        self._start_times = {
            k: factor * v for k, v in self._start_times.items()
        }
        for op_id in self._start_times:
            self._sfg.find_by_id(op_id)._increase_time_resolution(factor)
        self._schedule_time *= factor
        return self

    def _get_all_times(self) -> List[int]:
        """
        Return a list of all times for the schedule. Used to check how the
        resolution can be modified.
        """
        # Local values
        ret = [self._schedule_time, *self._start_times.values()]
        # Loop over operations
        for op_id in self._start_times:
            op = self._sfg.find_by_id(op_id)
            ret += [op.execution_time, *op.latency_offsets.values()]
        # Remove not set values (None)
        ret = [v for v in ret if v is not None]
        return ret

    def get_possible_time_resolution_decrements(self) -> List[int]:
        """Return a list with possible factors to reduce time resolution."""
        vals = self._get_all_times()
        maxloop = min(val for val in vals if val)
        if maxloop <= 1:
            return [1]
        ret = [1]
        for candidate in range(2, maxloop + 1):
            if not any(val % candidate for val in vals):
                ret.append(candidate)
        return ret

    def decrease_time_resolution(self, factor: int) -> "Schedule":
        """
        Decrease time resolution for a schedule.

        Parameters
        ==========

        factor : int
            The time resolution decrement.
        """
        possible_values = self.get_possible_time_resolution_decrements()
        if factor not in possible_values:
            raise ValueError(
                f"Not possible to decrease resolution with {factor}. Possible"
                f" values are {possible_values}"
            )
        self._start_times = {
            k: v // factor for k, v in self._start_times.items()
        }
        for op_id, _ in self._start_times.items():
            self._sfg.find_by_id(op_id)._decrease_time_resolution(factor)
        self._schedule_time = self._schedule_time // factor
        return self

    def move_operation(self, op_id: GraphID, time: int) -> "Schedule":
        assert (
            op_id in self._start_times
        ), "No operation with the specified op_id in this schedule."

        (backward_slack, forward_slack) = self.slacks(op_id)
        if not -backward_slack <= time <= forward_slack:
            raise ValueError

        tmp_start = self._start_times[op_id] + time
        new_start = tmp_start % self._schedule_time

        # Update input laps
        input_slacks = self._backward_slacks(op_id)
        for in_port, signal_slacks in input_slacks.items():
            tmp_usage = tmp_start + in_port.latency_offset
            new_usage = tmp_usage % self._schedule_time
            for signal, signal_slack in signal_slacks.items():
                new_slack = signal_slack + time
                old_laps = self._laps[signal.graph_id]
                tmp_prev_available = tmp_usage - new_slack
                prev_available = tmp_prev_available % self._schedule_time
                laps = new_slack // self._schedule_time
                if new_usage < prev_available:
                    laps += 1
                print(
                    [
                        signal_slack,
                        new_slack,
                        old_laps,
                        laps,
                        new_usage,
                        prev_available,
                        tmp_usage,
                        tmp_prev_available,
                    ]
                )
                self._laps[signal.graph_id] = laps

        # Update output laps
        output_slacks = self._forward_slacks(op_id)
        for out_port, signal_slacks in output_slacks.items():
            tmp_available = tmp_start + out_port.latency_offset
            new_available = tmp_available % self._schedule_time
            for signal, signal_slack in signal_slacks.items():
                new_slack = signal_slack - time
                tmp_next_usage = tmp_available + new_slack
                next_usage = tmp_next_usage % self._schedule_time
                laps = new_slack // self._schedule_time
                if next_usage < new_available:
                    laps += 1
                if new_available == 0 and new_slack > 0:
                    laps += 1
                self._laps[signal.graph_id] = laps

        # Set new start time
        self._start_times[op_id] = new_start
        return self

    def _remove_delays(self) -> None:
        delay_list = self._sfg.find_by_type_name(Delay.type_name())
        while delay_list:
            delay_op = delay_list[0]
            delay_input_id = delay_op.input(0).signals[0].graph_id
            delay_output_ids = [
                sig.graph_id for sig in delay_op.output(0).signals
            ]
            self._sfg = self._sfg.remove_operation(delay_op.graph_id)
            for output_id in delay_output_ids:
                self._laps[output_id] += 1 + self._laps[delay_input_id]
            del self._laps[delay_input_id]
            delay_list = self._sfg.find_by_type_name(Delay.type_name())

    def _schedule_asap(self) -> None:
        pl = self._sfg.get_precedence_list()

        if len(pl) < 2:
            print("Empty signal flow graph cannot be scheduled.")
            return

        non_schedulable_ops = set()
        for outport in pl[0]:
            op = outport.operation
            if op.type_name() not in [Delay.type_name()]:
                if op.graph_id not in self._start_times:
                    # Set start time of all operations in the first iter to 0
                    self._start_times[op.graph_id] = 0
            else:
                non_schedulable_ops.add(op.graph_id)

        for outport in pl[1]:
            op = outport.operation
            if op.graph_id not in self._start_times:
                # Set start time of all operations in the first iter to 0
                self._start_times[op.graph_id] = 0

        for outports in pl[2:]:
            for outport in outports:
                op = outport.operation
                if op.graph_id not in self._start_times:
                    # Schedule the operation if it doesn't have a start time yet.
                    op_start_time = 0
                    for inport in op.inputs:
                        assert (
                            len(inport.signals) == 1
                        ), "Error in scheduling, dangling input port detected."
                        assert inport.signals[0].source is not None, (
                            "Error in scheduling, signal with no source"
                            " detected."
                        )
                        source_port = inport.signals[0].source

                        source_end_time = None
                        if (
                            source_port.operation.graph_id
                            in non_schedulable_ops
                        ):
                            source_end_time = 0
                        else:
                            source_op_time = self._start_times[
                                source_port.operation.graph_id
                            ]

                            assert source_port.latency_offset is not None, (
                                f"Output port: {source_port.index} of"
                                " operation:                                  "
                                f"   {source_port.operation.graph_id} has no"
                                " latency-offset."
                            )
                            assert inport.latency_offset is not None, (
                                f"Input port: {inport.index} of operation:    "
                                "                                "
                                f" {inport.operation.graph_id} has no"
                                " latency-offset."
                            )

                            source_end_time = (
                                source_op_time + source_port.latency_offset
                            )

                        op_start_time_from_in = (
                            source_end_time - inport.latency_offset
                        )
                        op_start_time = max(
                            op_start_time, op_start_time_from_in
                        )

                    self._start_times[op.graph_id] = op_start_time
        for output in self._sfg.find_by_type_name(Output.type_name()):
            source_port = output.inputs[0].signals[0].source
            if source_port.operation.graph_id in non_schedulable_ops:
                self._start_times[output.graph_id] = 0
            else:
                self._start_times[output.graph_id] = (
                    self._start_times[source_port.operation.graph_id]
                    + source_port.latency_offset
                )
        self._remove_delays()

    def _plot_schedule(self, ax):
        def _draw_arrow(start, end, name="", laps=0):
            if end[0] < start[0] or laps > 0:  # Wrap around
                ax.add_line(
                    Line2D(
                        [start[0], self._schedule_time + 0.2],
                        [start[1], start[1]],
                        color="black",
                    )
                )
                ax.add_line(
                    Line2D([-0.2, end[0]], [end[1], end[1]], color="black")
                )
                ax.text(
                    self._schedule_time + 0.2,
                    start[1],
                    name,
                    verticalalignment="center",
                )
                ax.text(
                    -0.2,
                    end[1],
                    f"{name}: {laps}",
                    verticalalignment="center",
                    horizontalalignment="right",
                )

            elif end[0] == start[0]:
                p = Path(
                    [
                        start,
                        [start[0] + 0.2, start[1]],
                        [start[0] + 0.2, (start[1] + end[1]) / 2],
                        [start[0], (start[1] + end[1]) / 2],
                        [start[0] - 0.2, (start[1] + end[1]) / 2],
                        [start[0] - 0.2, end[1]],
                        end,
                    ],
                    [
                        Path.MOVETO,
                        Path.CURVE4,
                        Path.CURVE4,
                        Path.CURVE4,
                        Path.CURVE4,
                        Path.CURVE4,
                        Path.CURVE4,
                    ],
                )
                pp = PathPatch(p, fc='none')
                ax.add_patch(pp)
            else:
                p = Path(
                    [
                        start,
                        [(start[0] + end[0]) / 2, start[1]],
                        [(start[0] + end[0]) / 2, end[1]],
                        end,
                    ],
                    [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4],
                )
                pp = PathPatch(p, fc='none')
                ax.add_patch(pp)

        def _draw_offset_arrow(
            start, end, start_offset, end_offset, name="", laps=0
        ):
            _draw_arrow(
                [start[0] + start_offset[0], start[1] + start_offset[1]],
                [end[0] + end_offset[0], end[1] + end_offset[1]],
                name=name,
                laps=laps,
            )

        ypos = 0.5
        ytickpositions = []
        yticklabels = []
        ax.grid(zorder=0.5)
        ypositions = {}
        for op_id, op_start_time in self._start_times.items():
            op = self._sfg.find_by_id(op_id)
            latency_coords, execution_time_coords = op.get_plot_coordinates()
            _x, _y = zip(*latency_coords)
            x = np.array(_x)
            y = np.array(_y)
            ax.fill(x + op_start_time, y + ypos)
            if execution_time_coords:
                _x, _y = zip(*execution_time_coords)
                x = np.array(_x)
                y = np.array(_y)
                ax.plot(
                    x + op_start_time,
                    y + ypos,
                    color="black",
                    linewidth=3,
                    alpha=0.5,
                )
            ytickpositions.append(ypos + 0.5)
            yticklabels.append(self._sfg.find_by_id(op_id).name)
            ypositions[op_id] = ypos
            ypos += 1.5

        for op_id, op_start_time in self._start_times.items():
            op = self._sfg.find_by_id(op_id)
            _, out_coords = op.get_io_coordinates()
            source_ypos = ypositions[op_id]
            for output_port in op.outputs:
                for output_signal in output_port.signals:
                    dest_op = output_signal.destination.operation
                    dest_start_time = self._start_times[dest_op.graph_id]
                    dest_ypos = ypositions[dest_op.graph_id]
                    (
                        dest_in_coords,
                        _,
                    ) = (
                        output_signal.destination.operation.get_io_coordinates()
                    )
                    _draw_offset_arrow(
                        out_coords[output_port.index],
                        dest_in_coords[output_signal.destination.index],
                        [op_start_time, source_ypos],
                        [dest_start_time, dest_ypos],
                        name=op_id,
                        laps=self._laps[output_signal.graph_id],
                    )

        ax.set_yticks(ytickpositions)
        ax.set_yticklabels(yticklabels)
        ax.axis([-1, self._schedule_time + 1, 0, ypos])
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.add_line(Line2D([0, 0], [0, ypos], linestyle="--", color="black"))
        ax.add_line(
            Line2D(
                [self._schedule_time, self._schedule_time],
                [0, ypos],
                linestyle="--",
                color="black",
            )
        )

    def plot_schedule(self) -> None:
        fig, ax = plt.subplots()
        self._plot_schedule(ax)
        fig.show()

    def _repr_svg_(self):
        fig, ax = plt.subplots()
        self._plot_schedule(ax)
        f = io.StringIO()
        fig.savefig(f, format="svg")

        return f.getvalue()
