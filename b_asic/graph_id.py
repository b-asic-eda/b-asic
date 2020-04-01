"""@package docstring
B-ASIC Graph ID module for handling IDs of different objects in a graph.
TODO: More info
"""

from collections import defaultdict
from typing import NewType, DefaultDict

GraphID = NewType("GraphID", str)
GraphIDType = NewType("GraphIDType", str)
GraphIDNumber = NewType("GraphIDNumber", int)


class GraphIDGenerator:
    """A class that generates Graph IDs for objects."""

    _next_id_number: DefaultDict[GraphIDType, GraphIDNumber]

    def __init__(self):
        self._next_id_number = defaultdict(lambda: 1)       # Initalises every key element to 1

    def get_next_id(self, graph_id_type: GraphIDType) -> GraphID:
        """Return the next graph id for a certain graph id type."""
        graph_id = graph_id_type + str(self._next_id_number[graph_id_type])
        self._next_id_number[graph_id_type] += 1            # Increase the current id number
        return graph_id
