"""B-ASIC classes representing resource usage."""

from typing import Dict, Optional, Tuple

from b_asic.operation import Operation
from b_asic.port import InputPort, OutputPort
from b_asic.types import TypeName


class Process:
    """
    Object for use in resource allocation.

    Has a start time and an execution time. Subclasses will in many cases
    contain additional information for resource assignment.

    Parameters
    ==========
    start_time : int
        Start time of process.
    execution_time : int
        Execution time (lifetime) of process.
    name : str, default: ""
        The name of the process.
    """

    def __init__(self, start_time: int, execution_time: int, name: str = ""):
        self._start_time = start_time
        self._execution_time = execution_time
        self._name = name

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

    @property
    def name(self) -> str:
        return self._name

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return f"Process({self.start_time}, {self.execution_time}, {self.name!r})"


class OperatorProcess(Process):
    """
    Object that corresponds to usage of an operator.

    Parameters
    ==========
    start_time : int
        Start time of process.
    operation : :class:`~b_asic.operation.Operation`
        Operation that the process corresponds to.
    name : str, optional
        The name of the process.
    """

    def __init__(
        self,
        start_time: int,
        operation: Operation,
        name: Optional[str] = None,
    ):
        execution_time = operation.execution_time
        if execution_time is None:
            raise ValueError(
                f"Operation {operation!r} does not have an execution time specified!"
            )
        super().__init__(
            start_time,
            execution_time,
            name=name or operation.name or operation.graph_id,
        )
        self._operation = operation

    @property
    def operation(self) -> Operation:
        """The Operation that the OperatorProcess corresponds to."""
        return self._operation

    @property
    def type_name(self) -> TypeName:
        return self._operation.type_name()

    def __repr__(self) -> str:
        return f"OperatorProcess({self.start_time}, {self.operation}, {self.name!r})"


class MemoryVariable(Process):
    """
    Object that corresponds to a memory variable.

    Parameters
    ==========

    write_time : int
        Time when the memory variable is written.
    write_port : :class:`~b_asic.port.OutputPort`
        The OutputPort that the memory variable originates from.
    reads : dict
        Dictionary with :class:`~b_asic.port.InputPort` that reads the memory variable
        as key and for how long after the *write_time* it will read.
    name : str, optional
        The name of the process.
    """

    def __init__(
        self,
        write_time: int,
        write_port: OutputPort,
        reads: Dict[InputPort, int],
        name: Optional[str] = None,
    ):
        self._read_ports = tuple(reads.keys())
        self._life_times = tuple(reads.values())
        self._reads = reads
        self._write_port = write_port
        super().__init__(
            start_time=write_time,
            execution_time=max(self._life_times),
            name=name,
        )

    @property
    def reads(self) -> Dict[InputPort, int]:
        return self._reads

    @property
    def life_times(self) -> Tuple[int, ...]:
        return self._life_times

    @property
    def read_ports(self) -> Tuple[InputPort, ...]:
        return self._read_ports

    @property
    def write_port(self) -> OutputPort:
        return self._write_port

    def __repr__(self) -> str:
        reads = {k: v for k, v in zip(self._read_ports, self._life_times)}
        return (
            f"MemoryVariable({self.start_time}, {self.write_port},"
            f" {reads!r}, {self.name!r})"
        )


class PlainMemoryVariable(Process):
    """
    Object that corresponds to a memory variable which only use numbers for ports.

    This can be useful when only a plain memory variable is wanted with
    no connection to a schedule.

    Parameters
    ==========
    write_time : int
        The time the memory variable is written.
    write_port : int
        Identifier for the source of the memory variable.
    reads : {int: int, ...}
        Dictionary where the key is the destination identifier and the value
        is the time after *write_time* that the memory variable is read, i.e., the
        lifetime of the variable.
    name : str, optional
        The name of the process.
    """

    def __init__(
        self,
        write_time: int,
        write_port: int,
        reads: Dict[int, int],
        name: Optional[str] = None,
    ):
        self._read_ports = tuple(reads.keys())
        self._life_times = tuple(reads.values())
        self._write_port = write_port
        self._reads = reads
        if name is None:
            name = f"Var. {PlainMemoryVariable._name_cnt}"
            PlainMemoryVariable._name_cnt += 1

        super().__init__(
            start_time=write_time,
            execution_time=max(self._life_times),
            name=name,
        )

    @property
    def reads(self) -> Dict[int, int]:
        return self._reads

    @property
    def life_times(self) -> Tuple[int, ...]:
        return self._life_times

    @property
    def read_ports(self) -> Tuple[int, ...]:
        return self._read_ports

    @property
    def write_port(self) -> int:
        return self._write_port

    def __repr__(self) -> str:
        reads = {k: v for k, v in zip(self._read_ports, self._life_times)}
        return (
            f"PlainMemoryVariable({self.start_time}, {self.write_port},"
            f" {reads!r}, {self.name!r})"
        )

    # Static counter for default names
    _name_cnt = 0
