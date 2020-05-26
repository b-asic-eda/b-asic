"""B-ASIC Schema Module.

Contains the schema class for scheduling operations in an SFG.
"""

from typing import Dict, List, Optional

from b_asic.signal_flow_graph import SFG
from b_asic.graph_component import GraphID
from b_asic.operation import Operation


class Schema:
    """Schema of an SFG with scheduled Operations."""

    _sfg: SFG
    _start_times: Dict[GraphID, int]
    _laps: Dict[GraphID, List[int]]
    _schedule_time: int
    _cyclic: bool
    _resolution: int

    def __init__(self, sfg: SFG, schedule_time: Optional[int] = None, cyclic: bool = False, resolution: int = 1, scheduling_alg: str = "ASAP"):
        """Construct a Schema from an SFG."""
        self._sfg = sfg
        self._start_times = dict()
        self._laps = dict()
        self._cyclic = cyclic
        self._resolution = resolution

        if scheduling_alg == "ASAP":
            self._schedule_asap()
        else:
            raise NotImplementedError(
                f"No algorithm with name: {scheduling_alg} defined.")

        max_end_time = 0
        for op_id, op_start_time in self._start_times.items():
            op = self._sfg.find_by_id(op_id)
            for outport in op.outputs:
                max_end_time = max(
                    max_end_time, op_start_time + outport.latency_offset)

        if not self._cyclic:
            if schedule_time is None:
                self._schedule_time = max_end_time
            elif schedule_time < max_end_time:
                raise ValueError(
                    "Too short schedule time for non-cyclic Schedule entered.")
            else:
                self._schedule_time = schedule_time

    def start_time_of_operation(self, op_id: GraphID) -> int:
        """Get the start time of the operation with the specified by the op_id."""
        assert op_id in self._start_times, "No operation with the specified op_id in this schema."
        return self._start_times[op_id]

    def forward_slack(self, op_id: GraphID) -> int:
        raise NotImplementedError

    def backward_slack(self, op_id: GraphID) -> int:
        raise NotImplementedError

    def print_slacks(self) -> None:
        raise NotImplementedError

    def _schedule_asap(self) -> None:
        pl = self._sfg.get_precedence_list()

        if len(pl) < 2:
            print("Empty signal flow graph cannot be scheduled.")
            return

        non_schedulable_ops = set((outp.operation.graph_id for outp in pl[0]))

        for outport in pl[1]:
            op = outport.operation
            if op not in self._start_times:
                # Set start time of all operations in the first iter to 0
                self._start_times[op.graph_id] = 0

        for outports in pl[2:]:
            for outport in outports:
                op = outport.operation
                if op.graph_id not in self._start_times:
                    # Schedule the operation if it doesn't have a start time yet.
                    op_start_time = 0
                    for inport in op.inputs:
                        print(inport.operation.graph_id)
                        assert len(
                            inport.signals) == 1, "Error in scheduling, dangling input port detected."
                        assert inport.signals[0].source is not None, "Error in scheduling, signal with no source detected."
                        source_port = inport.signals[0].source

                        source_end_time = None
                        if source_port.operation.graph_id in non_schedulable_ops:
                            source_end_time = 0
                        else:
                            source_op_time = self._start_times[source_port.operation.graph_id]

                            assert source_port.latency_offset is not None, f"Output port: {source_port.index} of operation: \
                                    {source_port.operation.graph_id} has no latency-offset."
                            assert inport.latency_offset is not None, f"Input port: {inport.index} of operation: \
                                    {inport.operation.graph_id} has no latency-offset."

                            source_end_time = source_op_time + source_port.latency_offset

                        op_start_time_from_in = source_end_time - inport.latency_offset
                        op_start_time = max(
                            op_start_time, op_start_time_from_in)

                    self._start_times[op.graph_id] = op_start_time
