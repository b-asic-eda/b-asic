"""
B-ASIC Port Module.

Contains classes for managing the ports of operations.
"""

from abc import ABC, abstractmethod
from copy import copy
from typing import TYPE_CHECKING, Iterable, List, Optional

from b_asic.graph_component import Name
from b_asic.signal import Signal

if TYPE_CHECKING:
    from b_asic.operation import Operation


class Port(ABC):
    """
    Port interface.

    Ports serve as connection points for connecting signals between operations.
    They also store information about the latency of the corresponding
    calculations of the operation.

    Aside from connected signals, each port also provides a reference to the
    parent operation that "owns" it as well as the operation's port index at
    which the port resides.
    """

    @property
    @abstractmethod
    def operation(self) -> "Operation":
        """Return the connected operation."""
        raise NotImplementedError

    @property
    @abstractmethod
    def index(self) -> int:
        """Return the index of the port."""
        raise NotImplementedError

    @property
    @abstractmethod
    def latency_offset(self) -> int:
        """Get the latency_offset of the port."""
        raise NotImplementedError

    @latency_offset.setter
    @abstractmethod
    def latency_offset(self, latency_offset: int) -> None:
        """Set the latency_offset of the port to the integer specified value.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def signal_count(self) -> int:
        """Return the number of connected signals."""
        raise NotImplementedError

    @property
    @abstractmethod
    def signals(self) -> Iterable[Signal]:
        """Return all connected signals."""
        raise NotImplementedError

    @abstractmethod
    def add_signal(self, signal: Signal) -> None:
        """
        Connect this port to the entered signal. If the entered signal isn't connected to
        this port then connect the entered signal to the port as well.
        """
        raise NotImplementedError

    @abstractmethod
    def remove_signal(self, signal: Signal) -> None:
        """
        Remove the signal that was entered from the Ports signals.
        If the entered signal still is connected to this port then disconnect the
        entered signal from the port as well.

        Parameters
        ==========

        signal : Signal
            Signal to remove.
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """Removes all connected signals from the Port."""
        raise NotImplementedError


class AbstractPort(Port):
    """
    Generic abstract port base class.

    Concrete ports should normally derive from this to get the default
    behavior.
    """

    _operation: "Operation"
    _index: int
    _latency_offset: Optional[int]

    def __init__(
        self,
        operation: "Operation",
        index: int,
        latency_offset: Optional[int] = None,
    ):
        """Construct a port of the given operation at the given port index."""
        self._operation = operation
        self._index = index
        self._latency_offset = latency_offset

    @property
    def operation(self) -> "Operation":
        return self._operation

    @property
    def index(self) -> int:
        return self._index

    @property
    def latency_offset(self) -> int:
        return self._latency_offset

    @latency_offset.setter
    def latency_offset(self, latency_offset: int):
        self._latency_offset = latency_offset


class SignalSourceProvider(ABC):
    """
    Signal source provider interface.

    Signal source providers give access to a single output port that can be
    used to connect signals from.
    """

    @property
    @abstractmethod
    def source(self) -> "OutputPort":
        """Get the main source port provided by this object."""
        raise NotImplementedError


class InputPort(AbstractPort):
    """
    Input port.

    May have one or zero signals connected to it.
    """

    _source_signal: Optional[Signal]

    def __init__(self, operation: "Operation", index: int):
        """Construct an InputPort."""
        super().__init__(operation, index)
        self._source_signal = None

    @property
    def signal_count(self) -> int:
        return 0 if self._source_signal is None else 1

    @property
    def signals(self) -> Iterable[Signal]:
        return [] if self._source_signal is None else [self._source_signal]

    def add_signal(self, signal: Signal) -> None:
        assert (
            self._source_signal is None
        ), "Input port may have only one signal added."
        assert (
            signal is not self._source_signal
        ), "Attempted to add already connected signal."
        self._source_signal = signal
        signal.set_destination(self)

    def remove_signal(self, signal: Signal) -> None:
        assert (
            signal is self._source_signal
        ), "Attempted to remove signal that is not connected."
        self._source_signal = None
        signal.remove_destination()

    def clear(self) -> None:
        if self._source_signal is not None:
            self.remove_signal(self._source_signal)

    @property
    def connected_source(self) -> Optional["OutputPort"]:
        """
        Get the output port that is currently connected to this input port,
        or None if it is unconnected.
        """
        return (
            None if self._source_signal is None else self._source_signal.source
        )

    def connect(self, src: SignalSourceProvider, name: Name = "") -> Signal:
        """
        Connect the provided signal source to this input port by creating a new signal.
        Returns the new signal.
        """
        assert (
            self._source_signal is None
        ), "Attempted to connect already connected input port."
        # self._source_signal is set by the signal constructor.
        return Signal(source=src.source, destination=self, name=name)

    def __lshift__(self, src: SignalSourceProvider) -> Signal:
        """
        Overloads the left shift operator to make it connect the provided
        signal source to this input port. Returns the new signal.
        """
        return self.connect(src)


class OutputPort(AbstractPort, SignalSourceProvider):
    """
    Output port.

    May have zero or more signals connected to it.
    """

    _destination_signals: List[Signal]

    def __init__(self, operation: "Operation", index: int):
        """Construct an OutputPort."""
        super().__init__(operation, index)
        self._destination_signals = []

    @property
    def signal_count(self) -> int:
        return len(self._destination_signals)

    @property
    def signals(self) -> Iterable[Signal]:
        return self._destination_signals

    def add_signal(self, signal: Signal) -> None:
        assert (
            signal not in self._destination_signals
        ), "Attempted to add already connected signal."
        self._destination_signals.append(signal)
        signal.set_source(self)

    def remove_signal(self, signal: Signal) -> None:
        assert (
            signal in self._destination_signals
        ), "Attempted to remove signal that is not connected."
        self._destination_signals.remove(signal)
        signal.remove_source()

    def clear(self) -> None:
        for signal in copy(self._destination_signals):
            self.remove_signal(signal)

    @property
    def source(self) -> "OutputPort":
        return self
