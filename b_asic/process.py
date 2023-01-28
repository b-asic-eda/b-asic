"""
B-ASIC classes representing resource usage.
"""

from typing import Dict, Tuple

from b_asic.operation import Operation
from b_asic.port import InputPort, OutputPort


class Process:
    """
    Object for use in resource allocation. Has a start time and an execution
    time. Subclasses will in many cases contain additional information for
    resource assignment.

    Parameters
    ==========
    start_time : int
        Start time of process.
    execution_time : int
        Execution time (lifetime) of process.
    """

    def __init__(self, start_time: int, execution_time: int):
        self._start_time = start_time
        self._execution_time = execution_time

    def __lt__(self, other):
        return self._start_time < other.start_time or (
            self._start_time == other.start_time
            and self.execution_time > other.execution_time
        )

    @property
    def start_time(self) -> int:
        """Return the start time."""
        return self._start_time

    @property
    def execution_time(self) -> int:
        """Return the execution time."""
        return self._execution_time


class OperatorProcess(Process):
    """
    Object that corresponds to usage of an operator.

    Parameters
    ==========
    start_time : int
        Start time of process.
    operation : Operation
        Operation that the process corresponds to.
    """

    def __init__(self, start_time: int, operation: Operation):
        execution_time = operation.execution_time
        if execution_time is None:
            raise ValueError(
                "Operation {operation!r} does not have an execution time"
                " specified!"
            )
        super().__init__(start_time, execution_time)
        self._operation = operation


class MemoryVariable(Process):
    """
    Object that corresponds to a memory variable.

    Parameters
    ==========

    write_time : int
        Time when the memory variable is written.
    write_port : OutputPort
        The OutputPort that the memory variable originates from.
    reads : {InputPort: int, ...}
        Dictionary with the InputPorts that reads the memory variable and
        for how long after the *write_time* they will read.
    """

    def __init__(
        self,
        write_time: int,
        write_port: OutputPort,
        reads: Dict[InputPort, int],
    ):
        self._read_ports = tuple(reads.keys())
        self._life_times = tuple(reads.values())
        self._write_port = write_port
        super().__init__(
            start_time=write_time, execution_time=max(self._life_times)
        )

    @property
    def life_times(self) -> Tuple[int, ...]:
        return self._life_times

    @property
    def read_ports(self) -> Tuple[InputPort, ...]:
        return self._read_ports

    @property
    def write_port(self) -> OutputPort:
        return self._write_port


class PlainMemoryVariable(Process):
    """
    Object that corresponds to a memory variable which only use numbers for
    ports. This can be useful when only a plain memory variable is wanted with
    no connection to a schedule.

    Parameters
    ==========
    write_time : int
        The time the memory variable is written.
    write_port : int
        Identifier for the source of the memory variable.
    reads : {int: int, ...}
        Dictionary where the key is the destination identifier and the value
        is the time after *write_time* that the memory variable is read.
    """

    def __init__(
        self,
        write_time: int,
        write_port: int,
        reads: Dict[int, int],
    ):
        self._read_ports = tuple(reads.keys())
        self._life_times = tuple(reads.values())
        self._write_port = write_port
        super().__init__(
            start_time=write_time, execution_time=max(self._life_times)
        )

    @property
    def life_times(self) -> Tuple[int, ...]:
        return self._life_times

    @property
    def read_ports(self) -> Tuple[int, ...]:
        return self._read_ports

    @property
    def write_port(self) -> int:
        return self._write_port
