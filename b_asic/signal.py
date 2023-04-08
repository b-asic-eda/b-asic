"""
B-ASIC Signal Module.

Contains the class for representing the connections between operations.
"""
from typing import TYPE_CHECKING, Iterable, Optional, Union

from b_asic.graph_component import AbstractGraphComponent, GraphComponent
from b_asic.types import Name, TypeName

if TYPE_CHECKING:
    from b_asic.operation import Operation
    from b_asic.port import InputPort, OutputPort


class Signal(AbstractGraphComponent):
    """
    A connection between two ports.

    .. note:: If a Signal is provided as *source* or *destination*, the
              connected port is used. Hence, if the argument signal is later
              changed, it will not affect the current Signal.

    Parameters
    ==========

    source : OutputPort, Signal, or Operation, optional
        OutputPort, Signal, or Operation to connect as source to the signal.
    destination : InputPort, Signal, or Operation, optional
        InputPort, Signal, or Operation to connect as destination to the signal.
    bits : int, optional
        The word length of the signal.
    name : Name, default: ""
        The signal name.

    See also
    ========
    set_source, set_destination
    """

    _source: Optional["OutputPort"]
    _destination: Optional["InputPort"]

    def __init__(
        self,
        source: Optional[Union["OutputPort", "Signal", "Operation"]] = None,
        destination: Optional[Union["InputPort", "Signal", "Operation"]] = None,
        bits: Optional[int] = None,
        name: Name = Name(""),
    ):
        """Construct a Signal."""
        super().__init__(Name(name))
        self._source = None
        self._destination = None
        if source is not None:
            self.set_source(source)
        if destination is not None:
            self.set_destination(destination)
        self.set_param("bits", bits)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("s")

    @property
    def neighbors(self) -> Iterable[GraphComponent]:
        """Return a list of the (up to) two operations connected to this signal."""
        return [p.operation for p in [self.source, self.destination] if p is not None]

    @property
    def source(self) -> Optional["OutputPort"]:
        """Return the source OutputPort of the signal."""
        return self._source

    @property
    def destination(self) -> Optional["InputPort"]:
        """Return the destination InputPort of the signal."""
        return self._destination

    @property
    def source_operation(self) -> Optional["Operation"]:
        """Return the source Operation of the signal."""
        if self._source is not None:
            return self._source.operation
        return None

    @property
    def destination_operation(self) -> Optional["Operation"]:
        """Return the destination Operation of the signal."""
        if self._destination is not None:
            return self._destination.operation
        return None

    def set_source(self, source: Union["OutputPort", "Signal", "Operation"]) -> None:
        """
        Connect to the entered source OutputPort.

        Also, disconnect the previous source OutputPort of the signal and
        connect the entered source port to the signal if it has not
        already been connected.

        Parameters
        ----------
        source : OutputPort, Signal, or Operation
            OutputPort, Signal, or Operation to connect as source to the signal.
            If Signal, it will connect to the source of the signal, so later on
            changing the source of the argument Signal will not affect this Signal.
            If Operation, it must have a single output, otherwise a TypeError is
            raised. That output is used to extract the OutputPort.
        """
        # import here to avoid cyclic imports
        from b_asic.operation import Operation

        if isinstance(source, (Signal, Operation)):
            # Signal or Operation
            new_source = source.source
        else:
            new_source = source

        if new_source is not self._source:
            self.remove_source()
            self._source = new_source
            if self not in new_source.signals:
                new_source.add_signal(self)

    def set_destination(
        self, destination: Union["InputPort", "Signal", "Operation"]
    ) -> None:
        """
        Connect to the entered *destination* InputPort.

        Also, disconnect the previous destination InputPort of the signal and
        connect the entered destination port to the signal if it has not already
        been connected.

        Parameters
        ----------
        destination : InputPort, Signal, or Operation
            InputPort, Signal, or Operation to connect as destination to the signal.
            If Signal, it will connect to the destination of the signal, so later on
            changing the destination of the argument Signal will not affect this Signal.
            If Operation, it must have a single input, otherwise a TypeError
            is raised.

        """
        # import here to avoid cyclic imports
        from b_asic.operation import Operation

        if isinstance(destination, (Signal, Operation)):
            # Signal or Operation
            new_destination = destination.destination
        else:
            new_destination = destination

        if new_destination is not self._destination:
            self.remove_destination()
            self._destination = new_destination
            if self not in new_destination.signals:
                new_destination.add_signal(self)

    def remove_source(self) -> None:
        """
        Disconnect the source OutputPort of the signal.

        If the source port still is connected to this signal then also disconnect
        the source port.
        """
        source = self._source
        if source is not None:
            self._source = None
            if self in source.signals:
                source.remove_signal(self)

    def remove_destination(self) -> None:
        """Disconnect the destination InputPort of the signal."""
        destination = self._destination
        if destination is not None:
            self._destination = None
            if self in destination.signals:
                destination.remove_signal(self)

    def dangling(self) -> bool:
        """
        Return True if the signal is missing either a source or a destination.
        """
        return self._source is None or self._destination is None

    @property
    def bits(self) -> Optional[int]:
        """
        Get the number of bits that this operation using this signal as an
        input should quantize received values to.
        None = unlimited.
        """
        return self.param("bits")

    @bits.setter
    def bits(self, bits: Optional[int]) -> None:
        """
        Set the number of bits that operations using this signal as an input
        should quantize received values to.
        None = unlimited.
        """
        if bits is not None:
            if not isinstance(bits, int):
                raise TypeError(f"Bits must be an int, not {type(bits)}: {bits!r}")
            if bits < 0:
                raise ValueError("Bits cannot be negative")
        self.set_param("bits", bits)

    @property
    def is_constant(self) -> bool:
        """
        Return True if the value of the signal (source) is constant.
        """
        if self.source is None:
            raise ValueError("Signal source not set")
        return self.source.operation.is_constant
