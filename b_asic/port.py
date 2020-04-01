"""@package docstring
B-ASIC Port Module.
TODO: More info.
"""

from abc import ABC, abstractmethod
from typing import NewType, Optional, List

from b_asic.operation import Operation
from b_asic.signal import Signal

PortIndex = NewType("PortIndex", int)

class Port(ABC):
    """Port Interface.

    TODO: More documentaiton?
    """

    @property
    @abstractmethod
    def operation(self) -> Operation:
        """Return the connected operation."""
        raise NotImplementedError

    @property
    @abstractmethod
    def index(self) -> PortIndex:
        """Return the unique PortIndex."""
        raise NotImplementedError

    @property
    @abstractmethod
    def signals(self) -> List[Signal]:
        """Return a list of all connected signals."""
        raise NotImplementedError

    @abstractmethod
    def signal(self, i: int = 0) -> Signal:
        """Return the connected signal at index i.

        Keyword argumens:
        i: integer index of the signal requsted.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def connected_ports(self) -> List["Port"]:
        """Return a list of all connected Ports."""
        raise NotImplementedError

    @abstractmethod
    def signal_count(self) -> int:
        """Return the number of connected signals."""
        raise NotImplementedError

    @abstractmethod
    def connect(self, port: "Port") -> Signal:
        """Create and return a signal that is connected to this port and the entered
        port and connect this port to the signal and the entered port to the signal."""
        raise NotImplementedError

    @abstractmethod
    def add_signal(self, signal: Signal) -> None:
        """Connect this port to the entered signal. If the entered signal isn't connected to
        this port then connect the entered signal to the port aswell."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self, port: "Port") -> None:
        """Disconnect the entered port from the port by removing it from the ports signal.
        If the entered port is still connected to this ports signal then disconnect the entered
        port from the signal aswell."""
        raise NotImplementedError

    @abstractmethod
    def remove_signal(self, signal: Signal) -> None:
        """Remove the signal that was entered from the Ports signals.
        If the entered signal still is connected to this port then disconnect the
        entered signal from the port aswell.

        Keyword arguments:
        - signal: Signal to remove.
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """Removes all connected signals from the Port."""
        raise NotImplementedError


class AbstractPort(Port):
    """Abstract port class.

    Handles functionality for port id and saves the connection to the parent operation.
    """

    _index: int
    _operation: Operation

    def __init__(self, index: int, operation: Operation):
        self._index = index
        self._operation = operation

    @property
    def operation(self) -> Operation:
        return self._operation

    @property
    def index(self) -> PortIndex:
        return self._index


class InputPort(AbstractPort):
    """Input port.
    TODO: More info.
    """

    _source_signal: Optional[Signal]

    def __init__(self, port_id: PortIndex, operation: Operation):
        super().__init__(port_id, operation)
        self._source_signal = None

    @property
    def signals(self) -> List[Signal]:
        return [] if self._source_signal is None else [self._source_signal]

    def signal(self, i: int = 0) -> Signal:
        assert 0 <= i < self.signal_count(), "Signal index out of bound."
        assert self._source_signal is not None, "No Signal connect to InputPort."
        return self._source_signal

    @property
    def connected_ports(self) -> List[Port]:
        return [] if self._source_signal is None or self._source_signal.source is None \
            else [self._source_signal.source]

    def signal_count(self) -> int:
        return 0 if self._source_signal is None else 1

    def connect(self, port: "OutputPort") -> Signal:
        assert self._source_signal is None, "Connecting new port to already connected input port."
        return Signal(port, self)        # self._source_signal is set by the signal constructor

    def add_signal(self, signal: Signal) -> None:
        assert self._source_signal is None, "Connecting new port to already connected input port."
        self._source_signal: Signal = signal
        if self is not signal.destination:
            # Connect this inputport as destination for this signal if it isn't already.
            signal.set_destination(self)

    def disconnect(self, port: "OutputPort") -> None:
        assert self._source_signal.source is port, "The entered port is not connected to this port."
        self._source_signal.remove_source()

    def remove_signal(self, signal: Signal) -> None:
        old_signal: Signal = self._source_signal
        self._source_signal = None
        if self is old_signal.destination:
            # Disconnect the dest of the signal if this inputport currently is the dest
            old_signal.remove_destination()

    def clear(self) -> None:
        self.remove_signal(self._source_signal)

class OutputPort(AbstractPort):
    """Output port.
    TODO: More info.
    """

    _destination_signals: List[Signal]

    def __init__(self, port_id: PortIndex, operation: Operation):
        super().__init__(port_id, operation)
        self._destination_signals = []

    @property
    def signals(self) -> List[Signal]:
        return self._destination_signals.copy()

    def signal(self, i: int = 0) -> Signal:
        assert 0 <= i < self.signal_count(), "Signal index out of bounds."
        return self._destination_signals[i]

    @property
    def connected_ports(self) -> List[Port]:
        return [signal.destination for signal in self._destination_signals \
            if signal.destination is not None]

    def signal_count(self) -> int:
        return len(self._destination_signals)

    def connect(self, port: InputPort) -> Signal:
        return Signal(self, port)      # Signal is added to self._destination_signals in signal constructor

    def add_signal(self, signal: Signal) -> None:
        assert signal not in self.signals, \
                "Attempting to connect to Signal already connected."
        self._destination_signals.append(signal)
        if self is not signal.source:
            # Connect this outputport to the signal if it isn't already
            signal.set_source(self)

    def disconnect(self, port: InputPort) -> None:
        assert port in self.connected_ports, "Attempting to disconnect port that isn't connected."
        for sig in self._destination_signals:
            if sig.destination is port:
                sig.remove_destination()
                break

    def remove_signal(self, signal: Signal) -> None:
        i: int = self._destination_signals.index(signal)
        old_signal: Signal = self._destination_signals[i]
        del self._destination_signals[i]
        if self is old_signal.source:
            old_signal.remove_source()

    def clear(self) -> None:
        for signal in self._destination_signals:
            self.remove_signal(signal)
