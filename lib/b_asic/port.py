"""
B-ASIC Port Module.

Contains classes for managing the ports of operations.
"""

import copy
from abc import ABC, abstractmethod
from collections.abc import Sequence
from numbers import Number
from typing import TYPE_CHECKING, Optional, Union

from b_asic.graph_component import Name
from b_asic.signal import Signal
from b_asic.types import Num

if TYPE_CHECKING:
    from b_asic.core_operations import (
        Addition,
        ConstantMultiplication,
        Division,
        LeftShift,
        Multiplication,
        Reciprocal,
        RightShift,
        Shift,
        Subtraction,
    )
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
    def latency_offset(self) -> int | None:
        """Get the latency_offset of the port."""
        raise NotImplementedError

    @latency_offset.setter
    @abstractmethod
    def latency_offset(self, latency_offset: int) -> None:
        """Set the latency_offset of the port to the integer specified value."""
        raise NotImplementedError

    @property
    @abstractmethod
    def signal_count(self) -> int:
        """Return the number of connected signals."""
        raise NotImplementedError

    @property
    @abstractmethod
    def signals(self) -> Sequence[Signal]:
        """Return all connected signals."""
        raise NotImplementedError

    @abstractmethod
    def add_signal(self, signal: Signal) -> None:
        """
        Connect this port to the entered signal.

        If the entered signal is not connected to this port then connect the entered
        signal to the port as well.

        Parameters
        ----------
        signal : Signal
            Signal to add.
        """
        raise NotImplementedError

    @abstractmethod
    def remove_signal(self, signal: Signal) -> None:
        """
        Remove the signal that was entered from the Ports signals.

        If the entered signal still is connected to this port then disconnect the
        entered signal from the port as well.

        Parameters
        ----------
        signal : Signal
            Signal to remove.
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        """Remove all connected signals from the Port."""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return a name of the port.

        This name consists of *graph_id* of the related operation and the port number.
        """


class AbstractPort(Port):
    """
    Generic abstract port base class.

    Concrete ports should normally derive from this to get the default
    behavior.
    """

    __slots__ = ("_index", "_latency_offset", "_operation")
    _operation: "Operation"
    _index: int
    _latency_offset: int | None

    def __init__(
        self,
        operation: "Operation",
        index: int,
        latency_offset: int | None = None,
    ) -> None:
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
    def latency_offset(self) -> int | None:
        return self._latency_offset

    @latency_offset.setter
    def latency_offset(self, latency_offset: int | None) -> None:
        self._latency_offset = latency_offset

    @property
    def name(self) -> str:
        return f"{self.operation.graph_id}.{self.index}"


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

    def __add__(self, src: Union["SignalSourceProvider", Num]) -> "Addition":
        # Import here to avoid circular imports.
        from b_asic.core_operations import Addition, Constant

        if isinstance(src, Number):
            return Addition(self, Constant(src))
        else:
            return Addition(self, src)

    def __radd__(self, src: Union["SignalSourceProvider", Num]) -> "Addition":
        # Import here to avoid circular imports.
        from b_asic.core_operations import Addition, Constant

        return Addition(Constant(src) if isinstance(src, Number) else src, self)

    def __sub__(self, src: Union["SignalSourceProvider", Num]) -> "Subtraction":
        # Import here to avoid circular imports.
        from b_asic.core_operations import Constant, Subtraction

        return Subtraction(self, Constant(src) if isinstance(src, Number) else src)

    def __rsub__(self, src: Union["SignalSourceProvider", Num]) -> "Subtraction":
        # Import here to avoid circular imports.
        from b_asic.core_operations import Constant, Subtraction

        return Subtraction(Constant(src) if isinstance(src, Number) else src, self)

    def __mul__(
        self, src: Union["SignalSourceProvider", Num]
    ) -> Union["Multiplication", "ConstantMultiplication"]:
        # Import here to avoid circular imports.
        from b_asic.core_operations import ConstantMultiplication, Multiplication

        return (
            ConstantMultiplication(src, self)
            if isinstance(src, Number)
            else Multiplication(self, src)
        )

    def __rmul__(
        self, src: Union["SignalSourceProvider", Num]
    ) -> Union["Multiplication", "ConstantMultiplication"]:
        # Import here to avoid circular imports.
        from b_asic.core_operations import ConstantMultiplication, Multiplication

        return (
            ConstantMultiplication(src, self)
            if isinstance(src, Number)
            else Multiplication(src, self)
        )

    def __truediv__(self, src: Union["SignalSourceProvider", Num]) -> "Division":
        # Import here to avoid circular imports.
        from b_asic.core_operations import Constant, Division

        return Division(self, Constant(src) if isinstance(src, Number) else src)

    def __rtruediv__(
        self, src: Union["SignalSourceProvider", Num]
    ) -> Union["Division", "Reciprocal"]:
        # Import here to avoid circular imports.
        from b_asic.core_operations import Constant, Division, Reciprocal

        if isinstance(src, Number):
            if src == 1:
                return Reciprocal(self)
            else:
                return Division(Constant(src), self)
        return Division(src, self)

    def __lshift__(self, src: int) -> Union["LeftShift", "Shift"]:
        from b_asic.core_operations import LeftShift, Shift

        if not isinstance(src, int):
            raise TypeError("Can only shift with an int")
        if src >= 0:
            return LeftShift(src, self)
        return Shift(src, self)

    def __rshift__(self, src: int) -> Union["RightShift", "Shift"]:
        from b_asic.core_operations import RightShift, Shift

        if not isinstance(src, int):
            raise TypeError("Can only shift with an int")
        if src >= 0:
            return RightShift(src, self)
        return Shift(-src, self)


class InputPort(AbstractPort):
    """
    Input port.

    May have one or zero signals connected to it.
    """

    __slots__ = ("_source_signal",)
    _source_signal: Signal | None

    def __init__(self, operation: "Operation", index: int) -> None:
        """Construct an InputPort."""
        super().__init__(operation, index)
        self._source_signal = None

    @property
    def signal_count(self) -> int:
        return 0 if self._source_signal is None else 1

    @property
    def signals(self) -> Sequence[Signal]:
        return [] if self._source_signal is None else [self._source_signal]

    def add_signal(self, signal: Signal) -> None:
        if self._source_signal is not None:
            raise ValueError("Cannot add to already connected input port.")
        if signal is self._source_signal:
            raise ValueError("Cannot add same signal twice")
        self._source_signal = signal
        signal.set_destination(self)

    def remove_signal(self, signal: Signal) -> None:
        if signal is not self._source_signal:
            raise ValueError("Cannot remove signal that is not connected")
        self._source_signal = None
        signal.remove_destination()

    def clear(self) -> None:
        if self._source_signal is not None:
            self.remove_signal(self._source_signal)

    @property
    def connected_source(self) -> Optional["OutputPort"]:
        """
        Get the output port that is currently connected to this input port.

        Return None if it is unconnected.
        """
        return None if self._source_signal is None else self._source_signal.source

    def connect(self, src: SignalSourceProvider, name: Name = Name("")) -> Signal:
        """
        Connect the provided signal source to this input port by creating a new signal.

        Returns the new signal.
        """
        if self._source_signal is not None:
            raise ValueError("Cannot connect already connected input port.")
        if isinstance(src, Signal):
            src.set_destination(self)
            return src
        # self._source_signal is set by the signal constructor.
        return Signal(source=src.source, destination=self, name=Name(name))

    def __ilshift__(self, src: SignalSourceProvider) -> "InputPort":
        """
        Connect the provided signal source to this input port.

        Returns the new signal.
        """
        self.connect(src)
        return self

    def delay(self, number: int) -> "InputPort":
        """
        Insert *number* amount of delay elements before the input port.

        Returns the input port of the first delay element in the chain.
        """
        from b_asic.special_operations import Delay

        if not isinstance(number, int) or number < 0:
            raise TypeError("Number of delays must be a positive integer")
        tmp_signal = None
        if any(self.signals):
            tmp_signal = self.signals[0]
            tmp_signal.remove_destination()
        current = self
        for _ in range(number):
            d = Delay()
            current.connect(d)
            current = d.input(0)
        if tmp_signal is not None:
            tmp_signal.set_destination(current)
        return current


class OutputPort(AbstractPort, SignalSourceProvider):
    """
    Output port.

    May have zero or more signals connected to it.
    """

    __slots__ = ("_destination_signals",)
    _destination_signals: list[Signal]

    def __init__(self, operation: "Operation", index: int) -> None:
        """Construct an OutputPort."""
        super().__init__(operation, index)
        self._destination_signals = []

    @property
    def signal_count(self) -> int:
        return len(self._destination_signals)

    @property
    def signals(self) -> Sequence[Signal]:
        return self._destination_signals

    def add_signal(self, signal: Signal) -> None:
        if signal in self._destination_signals:
            raise ValueError("Cannot add same signal twice")
        self._destination_signals.append(signal)
        signal.set_source(self)

    def remove_signal(self, signal: Signal) -> None:
        if signal not in self._destination_signals:
            raise ValueError("Cannot remove signal that is not connected")
        self._destination_signals.remove(signal)
        signal.remove_source()

    def clear(self) -> None:
        for signal in copy.copy(self._destination_signals):
            self.remove_signal(signal)

    @property
    def source(self) -> "OutputPort":
        return self
