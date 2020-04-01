"""@package docstring
B-ASIC Operation Module.
TODO: More info.
"""

from abc import abstractmethod
from numbers import Number
from typing import List, Dict, Optional, Any, Set, TYPE_CHECKING
from collections import deque

from b_asic.graph_component import GraphComponent, AbstractGraphComponent, Name
from b_asic.simulation import SimulationState, OperationState
from b_asic.signal import Signal

if TYPE_CHECKING:
    from b_asic.port import InputPort, OutputPort


class Operation(GraphComponent):
    """Operation interface.
    TODO: More info.
    """

    @abstractmethod
    def inputs(self) -> "List[InputPort]":
        """Get a list of all input ports."""
        raise NotImplementedError

    @abstractmethod
    def outputs(self) -> "List[OutputPort]":
        """Get a list of all output ports."""
        raise NotImplementedError

    @abstractmethod
    def input_count(self) -> int:
        """Get the number of input ports."""
        raise NotImplementedError

    @abstractmethod
    def output_count(self) -> int:
        """Get the number of output ports."""
        raise NotImplementedError

    @abstractmethod
    def input(self, i: int) -> "InputPort":
        """Get the input port at index i."""
        raise NotImplementedError

    @abstractmethod
    def output(self, i: int) -> "OutputPort":
        """Get the output port at index i."""
        raise NotImplementedError

    @abstractmethod
    def params(self) -> Dict[str, Optional[Any]]:
        """Get a dictionary of all parameter values."""
        raise NotImplementedError

    @abstractmethod
    def param(self, name: str) -> Optional[Any]:
        """Get the value of a parameter.
        Returns None if the parameter is not defined.
        """
        raise NotImplementedError

    @abstractmethod
    def set_param(self, name: str, value: Any) -> None:
        """Set the value of a parameter.
        The parameter must be defined.
        """
        raise NotImplementedError

    @abstractmethod
    def evaluate_outputs(self, state: "SimulationState") -> List[Number]:
        """Simulate the circuit until its iteration count matches that of the simulation state,
        then return the resulting output vector.
        """
        raise NotImplementedError

    @abstractmethod
    def split(self) -> "List[Operation]":
        """Split the operation into multiple operations.
        If splitting is not possible, this may return a list containing only the operation itself.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def neighbors(self) -> "List[Operation]":
        """Return all operations that are connected by signals to this operation.
        If no neighbors are found, this returns an empty list.
        """
        raise NotImplementedError


class AbstractOperation(Operation, AbstractGraphComponent):
    """Generic abstract operation class which most implementations will derive from.
    TODO: More info.
    """

    _input_ports: List["InputPort"]
    _output_ports: List["OutputPort"]
    _parameters: Dict[str, Optional[Any]]

    def __init__(self, name: Name = ""):
        super().__init__(name)
        self._input_ports = []
        self._output_ports = []
        self._parameters = {}

    @abstractmethod
    def evaluate(self, *inputs) -> Any:  # pylint: disable=arguments-differ
        """Evaluate the operation and generate a list of output values given a
        list of input values.
        """
        raise NotImplementedError

    def inputs(self) -> List["InputPort"]:
        return self._input_ports.copy()

    def outputs(self) -> List["OutputPort"]:
        return self._output_ports.copy()

    def input_count(self) -> int:
        return len(self._input_ports)

    def output_count(self) -> int:
        return len(self._output_ports)

    def input(self, i: int) -> "InputPort":
        return self._input_ports[i]

    def output(self, i: int) -> "OutputPort":
        return self._output_ports[i]

    def params(self) -> Dict[str, Optional[Any]]:
        return self._parameters.copy()

    def param(self, name: str) -> Optional[Any]:
        return self._parameters.get(name)

    def set_param(self, name: str, value: Any) -> None:
        assert name in self._parameters  # TODO: Error message.
        self._parameters[name] = value

    def evaluate_outputs(self, state: SimulationState) -> List[Number]:
        # TODO: Check implementation.
        input_count: int = self.input_count()
        output_count: int = self.output_count()
        assert input_count == len(self._input_ports)  # TODO: Error message.
        assert output_count == len(self._output_ports)  # TODO: Error message.

        self_state: OperationState = state.operation_states[self]

        while self_state.iteration < state.iteration:
            input_values: List[Number] = [0] * input_count
            for i in range(input_count):
                source: Signal = self._input_ports[i].signal
                input_values[i] = source.operation.evaluate_outputs(state)[
                    source.port_index]

            self_state.output_values = self.evaluate(input_values)
            # TODO: Error message.
            assert len(self_state.output_values) == output_count
            self_state.iteration += 1
            for i in range(output_count):
                for signal in self._output_ports[i].signals():
                    destination: Signal = signal.destination
                    destination.evaluate_outputs(state)

        return self_state.output_values

    def split(self) -> List[Operation]:
        # TODO: Check implementation.
        results = self.evaluate(self._input_ports)
        if all(isinstance(e, Operation) for e in results):
            return results
        return [self]

    @property
    def neighbors(self) -> List[Operation]:
        neighbors: List[Operation] = []
        for port in self._input_ports:
            for signal in port.signals:
                neighbors.append(signal.source.operation)

        for port in self._output_ports:
            for signal in port.signals:
                neighbors.append(signal.destination.operation)

        return neighbors

    def traverse(self) -> Operation:
        """Traverse the operation tree and return a generator with start point in the operation."""
        return self._breadth_first_search()

    def _breadth_first_search(self) -> Operation:
        """Use breadth first search to traverse the operation tree."""
        visited: Set[Operation] = {self}
        queue = deque([self])
        while queue:
            operation = queue.popleft()
            yield operation
            for n_operation in operation.neighbors:
                if n_operation not in visited:
                    visited.add(n_operation)
                    queue.append(n_operation)

    def __add__(self, other):
        """Overloads the addition operator to make it return a new Addition operation
        object that is connected to the self and other objects. If other is a number then
        returns a ConstantAddition operation object instead.
        """
        # Import here to avoid circular imports.
        from b_asic.core_operations import Addition, ConstantAddition

        if isinstance(other, Operation):
            return Addition(self.output(0), other.output(0))
        elif isinstance(other, Number):
            return ConstantAddition(other, self.output(0))
        else:
            raise TypeError("Other type is not an Operation or a Number.")

    def __sub__(self, other):
        """Overloads the subtraction operator to make it return a new Subtraction operation
        object that is connected to the self and other objects. If other is a number then
        returns a ConstantSubtraction operation object instead.
        """
        # Import here to avoid circular imports.
        from b_asic.core_operations import Subtraction, ConstantSubtraction

        if isinstance(other, Operation):
            return Subtraction(self.output(0), other.output(0))
        elif isinstance(other, Number):
            return ConstantSubtraction(other, self.output(0))
        else:
            raise TypeError("Other type is not an Operation or a Number.")

    def __mul__(self, other):
        """Overloads the multiplication operator to make it return a new Multiplication operation
        object that is connected to the self and other objects. If other is a number then
        returns a ConstantMultiplication operation object instead.
        """
        # Import here to avoid circular imports.
        from b_asic.core_operations import Multiplication, ConstantMultiplication

        if isinstance(other, Operation):
            return Multiplication(self.output(0), other.output(0))
        elif isinstance(other, Number):
            return ConstantMultiplication(other, self.output(0))
        else:
            raise TypeError("Other type is not an Operation or a Number.")

    def __truediv__(self, other):
        """Overloads the division operator to make it return a new Division operation
        object that is connected to the self and other objects. If other is a number then
        returns a ConstantDivision operation object instead.
        """
        # Import here to avoid circular imports.
        from b_asic.core_operations import Division, ConstantDivision

        if isinstance(other, Operation):
            return Division(self.output(0), other.output(0))
        elif isinstance(other, Number):
            return ConstantDivision(other, self.output(0))
        else:
            raise TypeError("Other type is not an Operation or a Number.")

