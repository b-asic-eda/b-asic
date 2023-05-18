"""B-ASIC classes representing resource usage."""

from typing import Any, Dict, List, Optional, Tuple, cast

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

    @property
    def read_times(self) -> Tuple[int, ...]:
        return (self.start_time + self.execution_time,)


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


class MemoryProcess(Process):
    """
    Intermediate class (abstract) for memory processes.

    Different from regular :class:`Process` objects, :class:`MemoryProcess` objects
    can contain multiple read accesses and can be split into two new
    :class:`MemoryProcess` objects based on these read times.

    Parameters
    ----------
    write_time : int
        Start time of process.
    life_times : list of int
        List of ints representing times after ``start_time`` this process is accessed.
    name : str, default=""
        Name of the process.
    """

    def __init__(
        self,
        write_time: int,
        life_times: List[int],
        name: str = "",
    ):
        pass
        self._life_times = life_times
        super().__init__(
            start_time=write_time,
            execution_time=max(self._life_times),
            name=name,
        )

    @property
    def read_times(self) -> List[int]:
        return list(self.start_time + read for read in self._life_times)

    @property
    def life_times(self) -> List[int]:
        return self._life_times

    @property
    def reads(self) -> Dict[Any, int]:
        raise NotImplementedError("MultiReadProcess should be derived from")

    @property
    def read_ports(self) -> List[Any]:
        raise NotImplementedError("MultiReadProcess should be derived from")

    @property
    def write_port(self) -> Any:
        raise NotImplementedError("MultiReadProcess should be derived from")

    def split_on_length(
        self,
        length: int = 0,
    ) -> Tuple[Optional["MemoryProcess"], Optional["MemoryProcess"]]:
        """
        Split this :class:`MemoryProcess` into two new :class:`MemoryProcess` objects,
        based on lifetimes of the read accesses.

        Parameters
        ----------
        length : int, default: 0
            The lifetime length to split on. Length is inclusive for the smaller
            process.

        Returns
        -------
        Two-tuple where the first element is a :class:`MemoryProcess` consisting
        of reads with read times smaller than or equal to ``length`` (or None if no such
        reads exists), and vice-versa for the other tuple element.
        """
        reads = self.reads
        short_reads = {k: v for k, v in filter(lambda t: t[1] <= length, reads.items())}
        long_reads = {k: v for k, v in filter(lambda t: t[1] > length, reads.items())}
        short_process = None
        long_process = None
        if short_reads:
            # Create a new Process of type self (which is a derived variant of
            # MultiReadProcess) by calling the self constructor
            short_process = type(self)(
                self.start_time,  # type: ignore
                self.write_port,  # type: ignore
                short_reads,  # type: ignore
                self.name,  # type: ignore
            )
        if long_reads:
            # Create a new Process of type self (which is a derived variant of
            # MultiReadProcess) by calling the self constructor
            long_process = type(self)(
                self.start_time,  # type: ignore
                self.write_port,  # type: ignore
                long_reads,  # type: ignore
                self.name,  # type: ignore
            )
        return short_process, long_process

    def _add_life_time(self, life_time: int):
        """
        Add a lifetime to this :class:`~b_asic.process.MultiReadProcess` set of
        lifetimes.

        If the lifetime specified by ``life_time`` is already in this
        :class:`~b_asic.process.MultiReadProcess`, nothing happens

        After adding a lifetime from this :class:`~b_asic.process.MultiReadProcess`,
        the execution time is re-evaluated.

        Parameters
        ----------
        life_time : int
            The lifetime to add to this :class:`~b_asic.process.MultiReadProcess`.
        """
        if life_time not in self.life_times:
            self._life_times.append(life_time)
            self._execution_time = max(self.life_times)

    def _remove_life_time(self, life_time: int):
        """
        Remove a lifetime from this :class:`~b_asic.process.MultiReadProcess`
        set of lifetimes.

        After removing a lifetime from this :class:`~b_asic.process.MultiReadProcess`,
        the execution time is re-evaluated.

        Raises :class:`KeyError` if the specified lifetime is not a lifetime of this
        :class:`~b_asic.process.MultiReadProcess`.

        Parameters
        ----------
        life_time : int
            The lifetime to remove from this :class:`~b_asic.process.MultiReadProcess`.
        """
        if life_time not in self.life_times:
            raise KeyError(
                f"Process {self.name}: {life_time} not in life_times: {self.life_times}"
            )
        else:
            self._life_times.remove(life_time)
            self._execution_time = max(self.life_times)


class MemoryVariable(MemoryProcess):
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
        self._read_ports = list(reads.keys())
        self._reads = reads
        self._write_port = write_port
        super().__init__(
            write_time=write_time,
            life_times=list(reads.values()),
            name=name,
        )

    @property
    def reads(self) -> Dict[InputPort, int]:
        return self._reads

    @property
    def read_ports(self) -> List[InputPort]:
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

    def split_on_length(
        self,
        length: int = 0,
    ) -> Tuple[Optional["MemoryVariable"], Optional["MemoryVariable"]]:
        """
        Split this :class:`MemoryVariable` into two new :class:`MemoryVariable` objects,
        based on lifetimes of read accesses.

        Parameters
        ----------
        length : int, default: 0
            The lifetime length to split on. Length is inclusive for the smaller
            process.

        Returns
        -------
        Two-tuple where the first element is a :class:`MemoryVariable` consisting
        of reads with read times smaller than or equal to ``length`` (or None if no such
        reads exists), and vice-versa for the other tuple element.
        """
        # This method exists only for documentation purposes and for generating correct
        # type annotations when calling it. Just call super().split_on_length() in here.
        short_process, long_process = super().split_on_length(length)
        return (
            cast(Optional["MemoryVariable"], short_process),
            cast(Optional["MemoryVariable"], long_process),
        )


class PlainMemoryVariable(MemoryProcess):
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
        self._read_ports = list(reads.keys())
        self._write_port = write_port
        self._reads = reads
        if name is None:
            name = f"Var. {PlainMemoryVariable._name_cnt}"
            PlainMemoryVariable._name_cnt += 1

        super().__init__(
            write_time=write_time,
            life_times=list(reads.values()),
            name=name,
        )

    @property
    def reads(self) -> Dict[int, int]:
        return self._reads

    @property
    def read_ports(self) -> List[int]:
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

    def split_on_length(
        self,
        length: int = 0,
    ) -> Tuple[Optional["PlainMemoryVariable"], Optional["PlainMemoryVariable"]]:
        """
        Split this :class:`PlainMemoryVariable` into two new
        :class:`PlainMemoryVariable` objects, based on lifetimes of read accesses.

        Parameters
        ----------
        length : int, default: 0
            The lifetime length to split on. Length is inclusive for the smaller
            process.

        Returns
        -------
        Two-tuple where the first element is a :class:`PlainMemoryVariable` consisting
        of reads with read times smaller than or equal to ``length`` (or None if no such
        reads exists), and vice-versa for the other tuple element.
        """
        # This method exists only for documentation purposes and for generating correct
        # type annotations when calling it. Just call super().split_on_length() in here.
        short_process, long_process = super().split_on_length(length)
        return (
            cast(Optional["PlainMemoryVariable"], short_process),
            cast(Optional["PlainMemoryVariable"], long_process),
        )

    # Static counter for default names
    _name_cnt = 0
