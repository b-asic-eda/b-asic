from enum import Enum
from typing import TYPE_CHECKING, cast

from b_asic.operation import Operation
from b_asic.port import OutputPort
from b_asic.special_operations import Delay, Output

if TYPE_CHECKING:
    from b_asic.schedule import Schedule


class SchedulingAlgorithm(Enum):
    ASAP = "ASAP"
    ALAP = "ALAP"
    EARLIEST_DEADLINE = "earliest_deadline"
    # LEAST_SLACK = "least_slack" # to be implemented
    PROVIDED = "provided"


class Scheduler:
    def __init__(self, schedule: "Schedule") -> None:
        self.schedule = schedule

    def schedule_asap(self) -> None:
        """Schedule the operations using as-soon-as-possible scheduling."""
        sched = self.schedule
        prec_list = sched.sfg.get_precedence_list()
        if len(prec_list) < 2:
            raise ValueError("Empty signal flow graph cannot be scheduled.")

        # handle the first set in precedence graph (input and delays)
        non_schedulable_ops = set()
        for outport in prec_list[0]:
            operation = outport.operation
            if operation.type_name() == Delay.type_name():
                non_schedulable_ops.add(operation.graph_id)
            # elif operation.graph_id not in sched._start_times:
            else:
                sched._start_times[operation.graph_id] = 0

        # handle second set in precedence graph (first operations)
        for outport in prec_list[1]:
            operation = outport.operation
            # if operation.graph_id not in sched._start_times:
            sched._start_times[operation.graph_id] = 0

        # handle the remaining sets
        for outports in prec_list[2:]:
            for outport in outports:
                operation = outport.operation
                if operation.graph_id not in sched._start_times:
                    op_start_time = 0
                    for current_input in operation.inputs:
                        if len(current_input.signals) != 1:
                            raise ValueError(
                                "Error in scheduling, dangling input port detected."
                            )
                        if current_input.signals[0].source is None:
                            raise ValueError(
                                "Error in scheduling, signal with no source detected."
                            )
                        source_port = current_input.signals[0].source

                        if source_port.operation.graph_id in non_schedulable_ops:
                            source_end_time = 0
                        else:
                            source_op_time = sched._start_times[
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

                    sched._start_times[operation.graph_id] = op_start_time

        self._handle_outputs_and_delays(non_schedulable_ops)

    def schedule_alap(self) -> None:
        """Schedule the operations using as-late-as-possible scheduling."""
        self.schedule_asap()
        sched = self.schedule
        max_end_time = sched.get_max_end_time()

        if sched.schedule_time is None:
            sched.set_schedule_time(max_end_time)
        elif sched.schedule_time < max_end_time:
            raise ValueError(f"Too short schedule time. Minimum is {max_end_time}.")

        # move all outputs ALAP before operations
        for output in sched.sfg.find_by_type_name(Output.type_name()):
            output = cast(Output, output)
            sched.move_operation_alap(output.graph_id)

        # move all operations ALAP
        for step in reversed(sched.sfg.get_precedence_list()):
            for outport in step:
                if not isinstance(outport.operation, Delay):
                    sched.move_operation_alap(outport.operation.graph_id)

    def schedule_earliest_deadline(
        self, process_elements: dict[Operation, int]
    ) -> None:
        """Schedule the operations using earliest deadline scheduling."""

        # ACT BASED ON THE NUMBER OF PEs!

        sched = self.schedule
        prec_list = sched.sfg.get_precedence_list()
        if len(prec_list) < 2:
            raise ValueError("Empty signal flow graph cannot be scheduled.")

        # handle the first set in precedence graph (input and delays)
        non_schedulable_ops = set()
        for outport in prec_list[0]:
            operation = outport.operation
            if operation.type_name() == Delay.type_name():
                non_schedulable_ops.add(operation.graph_id)
            elif operation.graph_id not in sched._start_times:
                sched._start_times[operation.graph_id] = 0

        current_time = 0
        sorted_outports = sorted(
            prec_list[1], key=lambda outport: outport.operation.latency
        )
        for outport in sorted_outports:
            op = outport.operation
            sched._start_times[op.graph_id] = current_time
            current_time += 1

        for outports in prec_list[2:]:
            # try all remaining operations for one time step
            candidates = []
            current_time -= 1
            while len(candidates) == 0:
                current_time += 1
                for outport in outports:
                    remaining_op = outport.operation
                    op_is_ready_to_be_scheduled = True
                    for op_input in remaining_op.inputs:
                        source_op = op_input.signals[0].source.operation
                        source_op_time = sched.start_times[source_op.graph_id]
                        source_end_time = source_op_time + source_op.latency
                        if source_end_time > current_time:
                            op_is_ready_to_be_scheduled = False
                    if op_is_ready_to_be_scheduled:
                        candidates.append(remaining_op)
                        # sched._start_times[remaining_op.graph_id] = current_time
            sorted_candidates = sorted(
                candidates, key=lambda candidate: candidate.latency
            )
            # schedule the best candidate to current time
            sched._start_times[sorted_candidates[0].graph_id] = current_time

        self._handle_outputs_and_delays(non_schedulable_ops)

    def _handle_outputs_and_delays(self, non_schedulable_ops) -> None:
        sched = self.schedule
        for output in sched._sfg.find_by_type_name(Output.type_name()):
            output = cast(Output, output)
            source_port = cast(OutputPort, output.inputs[0].signals[0].source)
            if source_port.operation.graph_id in non_schedulable_ops:
                sched._start_times[output.graph_id] = 0
            else:
                if source_port.latency_offset is None:
                    raise ValueError(
                        f"Output port {source_port.index} of operation"
                        f" {source_port.operation.graph_id} has no"
                        " latency-offset."
                    )
                sched._start_times[output.graph_id] = sched._start_times[
                    source_port.operation.graph_id
                ] + cast(int, source_port.latency_offset)
        sched._remove_delays()
