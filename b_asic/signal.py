"""@package docstring
B-ASIC Signal Module.
"""
from typing import Optional, TYPE_CHECKING

from b_asic.graph_component import AbstractGraphComponent, TypeName, Name

if TYPE_CHECKING:
    from b_asic.port import InputPort, OutputPort


class Signal(AbstractGraphComponent):
    """A connection between two ports."""

    _source: "OutputPort"
    _destination: "InputPort"

    def __init__(self, source: Optional["OutputPort"] = None, \
                destination: Optional["InputPort"] = None, name: Name = ""):

        super().__init__(name)

        self._source = source
        self._destination = destination

        if source is not None:
            self.set_source(source)

        if destination is not None:
            self.set_destination(destination)

    @property
    def source(self) -> "OutputPort":
        """Return the source OutputPort of the signal."""
        return self._source

    @property
    def destination(self) -> "InputPort":
        """Return the destination "InputPort" of the signal."""
        return self._destination

    def set_source(self, src: "OutputPort") -> None:
        """Disconnect the previous source OutputPort of the signal and
        connect to the entered source OutputPort. Also connect the entered
        source port to the signal if it hasn't already been connected.

        Keyword arguments:
        - src: OutputPort to connect as source to the signal.
        """
        self.remove_source()
        self._source = src
        if self not in src.signals:
            # If the new source isn't connected to this signal then connect it.
            src.add_signal(self)

    def set_destination(self, dest: "InputPort") -> None:
        """Disconnect the previous destination InputPort of the signal and
        connect to the entered destination InputPort. Also connect the entered
        destination port to the signal if it hasn't already been connected.

        Keywords argments:
        - dest: InputPort to connect as destination to the signal.
        """
        self.remove_destination()
        self._destination = dest
        if self not in dest.signals:
            # If the new destination isn't connected to tis signal then connect it.
            dest.add_signal(self)

    @property
    def type_name(self) -> TypeName:
        return "s"

    def remove_source(self) -> None:
        """Disconnect the source OutputPort of the signal. If the source port
        still is connected to this signal then also disconnect the source port."""
        if self._source is not None:
            old_source: "OutputPort" = self._source
            self._source = None
            if self in old_source.signals:
                # If the old destination port still is connected to this signal, then disconnect it.
                old_source.remove_signal(self)

    def remove_destination(self) -> None:
        """Disconnect the destination InputPort of the signal."""
        if self._destination is not None:
            old_destination: "InputPort" = self._destination
            self._destination = None
            if self in old_destination.signals:
                # If the old destination port still is connected to this signal, then disconnect it.
                old_destination.remove_signal(self)

    def is_connected(self) -> bool:
        """Returns true if the signal is connected to both a source and a destination,
        else false."""
        return self._source is not None and self._destination is not None
