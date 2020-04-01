"""@package docstring
B-ASIC Simulation Module.
TODO: More info.
"""

from numbers import Number
from typing import List


class OperationState:
    """Simulation state of an operation.
    TODO: More info.
    """

    output_values: List[Number]
    iteration: int

    def __init__(self):
        self.output_values = []
        self.iteration = 0


class SimulationState:
    """Simulation state.
    TODO: More info.
    """

    # operation_states: Dict[OperationId, OperationState]
    iteration: int

    def __init__(self):
        self.operation_states = {}
        self.iteration = 0

    # TODO: More stuff.
