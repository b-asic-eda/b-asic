"""@package docstring
B-ASIC Operation Module.
TODO: More info.
"""

from abc import ABC, abstractmethod
from typing import NewType

Name = NewType("Name", str)
TypeName = NewType("TypeName", str)


class GraphComponent(ABC):
    """Graph component interface.
    TODO: More info.
    """

    @property
    @abstractmethod
    def type_name(self) -> TypeName:
        """Return the type name of the graph component"""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> Name:
        """Return the name of the graph component."""
        raise NotImplementedError

    @name.setter
    @abstractmethod
    def name(self, name: Name) -> None:
        """Set the name of the graph component to the entered name."""
        raise NotImplementedError


class AbstractGraphComponent(GraphComponent):
    """Abstract Graph Component class which is a component of a signal flow graph.

    TODO: More info.
    """

    _name: Name

    def __init__(self, name: Name = ""):
        self._name = name

    @property
    def name(self) -> Name:
        return self._name

    @name.setter
    def name(self, name: Name) -> None:
        self._name = name
