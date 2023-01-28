"""
B-ASIC Signal Module.

Contains the class for representing the connections between operations.
"""
from typing import TYPE_CHECKING, Iterable, Optional, Union

from b_asic.graph_component import (
    AbstractGraphComponent,
    GraphComponent,
    Name,
    TypeName,
)

if TYPE_CHECKING:
    from b_asic.port import InputPort, OutputPort
    from b_asic.operation import Operation


class Signal(AbstractGraphComponent):
    """
    A connection between two ports.

    Parameters
    ==========

    source : OutputPort or Operation, optional
        OutputPort or Operation to connect as source to the signal.
    destination : InputPort or Operation, optional
        InputPort or Operation to connect as destination to the signal.
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
        source: Optional[Union["OutputPort", "Operation"]] = None,
        destination: Optional[Union["InputPort", "Operation"]] = None,
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
        return [
            p.operation
            for p in [self.source, self.destination]
            if p is not None
        ]

    @property
    def source(self) -> Optional["OutputPort"]:
        """The source OutputPort of the signal."""
        return self._source

    @property
    def destination(self) -> Optional["InputPort"]:
        """The destination InputPort of the signal."""
        return self._destination

    def set_source(self, source: Union["OutputPort", "Operation"]) -> None:
        """
        Disconnect the previous source OutputPort of the signal and
        connect to the entered source OutputPort. Also connect the entered
        source port to the signal if it has not already been connected.

        Parameters
        ==========

        source : OutputPort or Operation, optional
            OutputPort or Operation to connect as source to the signal. If
            Operation, it must have a single output, otherwise a TypeError is
            raised. That output is used to extract the OutputPort.
        """
        from b_asic.operation import Operation

        if isinstance(source, Operation):
            if source.output_count != 1:
                raise TypeError(
                    "Can only connect operations with a single output."
                    f" {source.type_name()} has {source.output_count} outputs."
                    " Use the output port directly instead."
                )
            source = source.output(0)

        if source is not self._source:
            self.remove_source()
            self._source = source
            if self not in source.signals:
                source.add_signal(self)

    def set_destination(self, destination: "InputPort") -> None:
        """
        Disconnect the previous destination InputPort of the signal and
        connect to the entered destination InputPort. Also connect the entered
        destination port to the signal if it has not already been connected.

        Parameters
        ==========

        destination : InputPort or Operation
            InputPort or Operation to connect as destination to the signal.
            If Operation, it must have a single input, otherwise a TypeError
            is raised.

        """
        from b_asic.operation import Operation

        if isinstance(destination, Operation):
            if destination.input_count != 1:
                raise TypeError(
                    "Can only connect operations with a single input."
                    f" {destination.type_name()} has"
                    f" {destination.input_count} outputs. Use the input port"
                    " directly instead."
                )
            destination = destination.input(0)

        if destination is not self._destination:
            self.remove_destination()
            self._destination = destination
            if self not in destination.signals:
                destination.add_signal(self)

    def remove_source(self) -> None:
        """
        Disconnect the source OutputPort of the signal. If the source port
        still is connected to this signal then also disconnect the source port.
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
        Returns True if the signal is missing either a source or a destination,
        else False.
        """
        return self._source is None or self._destination is None

    @property
    def bits(self) -> Optional[int]:
        """
        Get the number of bits that this operation using this signal as an
        input should truncate received values to.
        None = unlimited.
        """
        return self.param("bits")

    @bits.setter
    def bits(self, bits: Optional[int]) -> None:
        """
        Set the number of bits that operations using this signal as an input
        should truncate received values to.
        None = unlimited.
        """
        if bits is not None:
            if not isinstance(bits, int):
                raise TypeError(
                    f"Bits must be an int, not {type(bits)}: {bits!r}"
                )
            if bits < 0:
                raise ValueError("Bits cannot be negative")
        self.set_param("bits", bits)
