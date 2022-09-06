"""B-ASIC Graph Component Module.

Contains the base for all components with an ID in a signal flow graph.
"""

from abc import ABC, abstractmethod
from collections import deque
from copy import copy, deepcopy
from typing import Any, Dict, Generator, Iterable, Mapping, NewType

Name = NewType("Name", str)
TypeName = NewType("TypeName", str)
GraphID = NewType("GraphID", str)
GraphIDNumber = NewType("GraphIDNumber", int)


class GraphComponent(ABC):
    """Graph component interface.

    Each graph component has a type name, a name and a unique ID.
    Graph components also contain parameters and provide an interface for
    copying that automatically copies each parameter in its default
    implementation.

    Graph components also provide an interface for traversing connected graph
    components and accessing their direct neighbors.
    """

    @classmethod
    @abstractmethod
    def type_name(cls) -> TypeName:
        """Get the type name of this graph component"""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> Name:
        """Get the name of this graph component."""
        raise NotImplementedError

    @name.setter
    @abstractmethod
    def name(self, name: Name) -> None:
        """Set the name of this graph component to the given name."""
        raise NotImplementedError

    @property
    @abstractmethod
    def graph_id(self) -> GraphID:
        """Get the graph id of this graph component."""
        raise NotImplementedError

    @graph_id.setter
    @abstractmethod
    def graph_id(self, graph_id: GraphID) -> None:
        """Set the graph id of this graph component to the given id.
        Note that this id will be ignored if this component is used to create a new graph,
        and that a new local id will be generated for it instead."""
        raise NotImplementedError

    @property
    @abstractmethod
    def params(self) -> Mapping[str, Any]:
        """Get a dictionary of all parameter values."""
        raise NotImplementedError

    @abstractmethod
    def param(self, name: str) -> Any:
        """Get the value of a parameter.
        Returns None if the parameter is not defined.
        """
        raise NotImplementedError

    @abstractmethod
    def set_param(self, name: str, value: Any) -> None:
        """Set the value of a parameter.
        Adds the parameter if it is not already defined.
        """
        raise NotImplementedError

    @abstractmethod
    def copy_component(self, *args, **kwargs) -> "GraphComponent":
        """Get a new instance of this graph component type with the same name, id and parameters."""
        raise NotImplementedError

    @property
    @abstractmethod
    def neighbors(self) -> Iterable["GraphComponent"]:
        """Get all components that are directly connected to this operation."""
        raise NotImplementedError

    @abstractmethod
    def traverse(self) -> Generator["GraphComponent", None, None]:
        """Get a generator that recursively iterates through all components that are connected to this operation,
        as well as the ones that they are connected to.
        """
        raise NotImplementedError


class AbstractGraphComponent(GraphComponent):
    """Generic abstract graph component base class.

    Concrete graph components should normally derive from this to get the
    default behavior.
    """

    _name: Name
    _graph_id: GraphID
    _parameters: Dict[str, Any]

    def __init__(self, name: Name = ""):
        """Construct a graph component."""
        self._name = name
        self._graph_id = ""
        self._parameters = {}

    def __str__(self) -> str:
        """Get a string representation of this graph component."""
        return (
            f"id: {self.graph_id if self.graph_id else 'no_id'}, \tname:"
            f" {self.name if self.name else 'no_name'}"
            + "".join(
                (
                    f", \t{key}: {str(param)}"
                    for key, param in self._parameters.items()
                )
            )
        )

    @property
    def name(self) -> Name:
        return self._name

    @name.setter
    def name(self, name: Name) -> None:
        self._name = name

    @property
    def graph_id(self) -> GraphID:
        return self._graph_id

    @graph_id.setter
    def graph_id(self, graph_id: GraphID) -> None:
        self._graph_id = graph_id

    @property
    def params(self) -> Mapping[str, Any]:
        return self._parameters.copy()

    def param(self, name: str) -> Any:
        return self._parameters.get(name)

    def set_param(self, name: str, value: Any) -> None:
        self._parameters[name] = value

    def copy_component(self, *args, **kwargs) -> GraphComponent:
        new_component = self.__class__(*args, **kwargs)
        new_component.name = copy(self.name)
        new_component.graph_id = copy(self.graph_id)
        for name, value in self.params.items():
            new_component.set_param(
                copy(name), deepcopy(value)
            )  # pylint: disable=no-member
        return new_component

    def traverse(self) -> Generator[GraphComponent, None, None]:
        # Breadth first search.
        visited = {self}
        fontier = deque([self])
        while fontier:
            component = fontier.popleft()
            yield component
            for neighbor in component.neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    fontier.append(neighbor)
