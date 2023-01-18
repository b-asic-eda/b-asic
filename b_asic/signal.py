"""
B-ASIC Signal Module.

Contains the class for representing the connections between operations.
"""
from typing import TYPE_CHECKING, Iterable, Optional

from b_asic.graph_component import (
    AbstractGraphComponent,
    GraphComponent,
    Name,
    TypeName,
)

if TYPE_CHECKING:
    from b_asic.port import InputPort, OutputPort


class Signal(AbstractGraphComponent):
    """A connection between two ports."""

    _source: Optional["OutputPort"]
    _destination: Optional["InputPort"]

    def __init__(
        self,
        source: Optional["OutputPort"] = None,
        destination: Optional["InputPort"] = None,
        bits: Optional[int] = None,
        name: Name = "",
    ):
        """Construct a Signal."""
        super().__init__(name)
        self._source = None
        self._destination = None
        if source is not None:
            self.set_source(source)
        if destination is not None:
            self.set_destination(destination)
        self.set_param("bits", bits)

    @classmethod
    def type_name(cls) -> TypeName:
        return "s"

    @property
    def neighbors(self) -> Iterable[GraphComponent]:
        return [
            p.operation
            for p in [self.source, self.destination]
            if p is not None
        ]

    @property
    def source(self) -> Optional["OutputPort"]:
        """Return the source OutputPort of the signal."""
        return self._source

    @property
    def destination(self) -> Optional["InputPort"]:
        """Return the destination "InputPort" of the signal."""
        return self._destination

    def set_source(self, src: "OutputPort") -> None:
        """Disconnect the previous source OutputPort of the signal and
        connect to the entered source OutputPort. Also connect the entered
        source port to the signal if it hasn't already been connected.

        Parameters
        ==========

        src : OutputPort
            OutputPort to connect as source to the signal.
        """
        if src is not self._source:
            self.remove_source()
            self._source = src
            if self not in src.signals:
                src.add_signal(self)

    def set_destination(self, dest: "InputPort") -> None:
        """
        Disconnect the previous destination InputPort of the signal and
        connect to the entered destination InputPort. Also connect the entered
        destination port to the signal if it hasn't already been connected.

        Parameters
        ==========

        dest : InputPort
            InputPort to connect as destination to the signal.
        """
        if dest is not self._destination:
            self.remove_destination()
            self._destination = dest
            if self not in dest.signals:
                dest.add_signal(self)

    def remove_source(self) -> None:
        """
        Disconnect the source OutputPort of the signal. If the source port
        still is connected to this signal then also disconnect the source port.
        """
        src = self._source
        if src is not None:
            self._source = None
            if self in src.signals:
                src.remove_signal(self)

    def remove_destination(self) -> None:
        """Disconnect the destination InputPort of the signal."""
        dest = self._destination
        if dest is not None:
            self._destination = None
            if self in dest.signals:
                dest.remove_signal(self)

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
        assert bits is None or (
            isinstance(bits, int) and bits >= 0
        ), "Bits must be non-negative."
        self.set_param("bits", bits)
