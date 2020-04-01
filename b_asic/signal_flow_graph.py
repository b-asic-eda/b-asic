"""@package docstring
B-ASIC Signal Flow Graph Module.
TODO: More info.
"""

from typing import List, Dict, Optional, DefaultDict
from collections import defaultdict

from b_asic.operation import Operation
from b_asic.operation import AbstractOperation
from b_asic.signal import Signal
from b_asic.graph_id import GraphIDGenerator, GraphID
from b_asic.graph_component import GraphComponent, Name, TypeName


class SFG(AbstractOperation):
    """Signal flow graph.
    TODO: More info.
    """

    _graph_components_by_id: Dict[GraphID, GraphComponent]
    _graph_components_by_name: DefaultDict[Name, List[GraphComponent]]
    _graph_id_generator: GraphIDGenerator

    def __init__(self, input_signals: List[Signal] = None, output_signals: List[Signal] = None, \
                ops: List[Operation] = None, **kwds):
        super().__init__(**kwds)
        if input_signals is None:
            input_signals = []
        if output_signals is None:
            output_signals = []
        if ops is None:
            ops = []

        self._graph_components_by_id = dict() # Maps Graph ID to objects
        self._graph_components_by_name = defaultdict(list) # Maps Name to objects
        self._graph_id_generator = GraphIDGenerator()

        for operation in ops:
            self._add_graph_component(operation)

        for input_signal in input_signals:
            self._add_graph_component(input_signal)

        # TODO: Construct SFG based on what inputs that were given
        # TODO: Traverse the graph between the inputs/outputs and add to self._operations.
        # TODO: Connect ports with signals with appropriate IDs.

    def evaluate(self, *inputs) -> list:
        return [] # TODO: Implement

    def _add_graph_component(self, graph_component: GraphComponent) -> GraphID:
        """Add the entered graph component to the SFG's dictionary of graph objects and
         return a generated GraphID for it.

        Keyword arguments:
        graph_component: Graph component to add to the graph.
        """
        # Add to name dict
        self._graph_components_by_name[graph_component.name].append(graph_component)

        # Add to ID dict
        graph_id: GraphID = self._graph_id_generator.get_next_id(graph_component.type_name)
        self._graph_components_by_id[graph_id] = graph_component
        return graph_id

    def find_by_id(self, graph_id: GraphID) -> Optional[GraphComponent]:
        """Find a graph object based on the entered Graph ID and return it. If no graph
        object with the entered ID was found then return None.

        Keyword arguments:
        graph_id: Graph ID of the wanted object.
        """
        if graph_id in self._graph_components_by_id:
            return self._graph_components_by_id[graph_id]

        return None

    def find_by_name(self, name: Name) -> List[GraphComponent]:
        """Find all graph objects that have the entered name and return them
        in a list. If no graph object with the entered name was found then return an
        empty list.

        Keyword arguments:
        name: Name of the wanted object.
        """
        return self._graph_components_by_name[name]

    @property
    def type_name(self) -> TypeName:
        return "sfg"
