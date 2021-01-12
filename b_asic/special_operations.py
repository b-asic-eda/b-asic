"""B-ASIC Special Operations Module.

Contains operations with special purposes that may be treated differently from
normal operations in an SFG.
"""

from numbers import Number
from typing import Optional, Sequence, Tuple, List

from b_asic.operation import AbstractOperation, ResultKey, DelayMap, MutableResultMap, MutableDelayMap
from b_asic.graph_component import Name, TypeName
from b_asic.port import SignalSourceProvider


class Input(AbstractOperation):
    """Input operation.

    Marks an input port to an SFG.
    Its value will be updated on each iteration when simulating the SFG.
    """

    def __init__(self, name: Name = ""):
        """Construct an Input operation."""
        super().__init__(input_count=0, output_count=1, name=name, latency_offsets={'out0' : 0})
        self.set_param("value", 0)

    @classmethod
    def type_name(cls) -> TypeName:
        return "in"

    def evaluate(self):
        return self.param("value")

    @property
    def value(self) -> Number:
        """Get the current value of this input."""
        return self.param("value")

    @value.setter
    def value(self, value: Number) -> None:
        """Set the current value of this input."""
        self.set_param("value", value)

    def get_plot_coordinates(self) -> Tuple[List[List[Number]], List[List[Number]]]:
        return ([[-0.5, 0], [-0.5, 1], [-0.25, 1], [0, 0.5], [-0.25, 0], [-0.5, 0]],
                [[-0.5, 0], [-0.5, 1], [-0.25, 1], [0, 0.5], [-0.25, 0], [-0.5, 0]])

    def get_io_coordinates(self) -> Tuple[List[List[Number]], List[List[Number]]]:
        return ([], [[0, 0.5]])


class Output(AbstractOperation):
    """Output operation.

    Marks an output port to an SFG.
    The SFG will forward its input to the corresponding output signal
    destinations.
    """

    def __init__(self, src0: Optional[SignalSourceProvider] = None, name: Name = ""):
        """Construct an Output operation."""
        super().__init__(input_count=1, output_count=0,
                         name=name, input_sources=[src0], latency_offsets={'in0' : 0})

    @classmethod
    def type_name(cls) -> TypeName:
        return "out"

    def evaluate(self, _):
        return None

    def get_plot_coordinates(self) -> Tuple[List[List[Number]], List[List[Number]]]:
        return ([[0, 0], [0, 1], [0.25, 1], [0.5, 0.5], [0.25, 0], [0, 0]],
                [[0, 0], [0, 1], [0.25, 1], [0.5, 0.5], [0.25, 0], [0, 0]])

    def get_io_coordinates(self) -> Tuple[List[List[Number]], List[List[Number]]]:
        return ([[0, 0.5]], [])


class Delay(AbstractOperation):
    """Unit delay operation.

    Represents one unit of delay in a circuit, typically a clock cycle.
    Can be thought of as a register or a D flip-flop.
    """

    def __init__(self, src0: Optional[SignalSourceProvider] = None, initial_value: Number = 0, name: Name = ""):
        """Construct a Delay operation."""
        super().__init__(input_count=1, output_count=1,
                         name=name, input_sources=[src0])
        self.set_param("initial_value", initial_value)

    @classmethod
    def type_name(cls) -> TypeName:
        return "t"

    def evaluate(self, a):
        return self.param("initial_value")

    def current_output(self, index: int, delays: Optional[DelayMap] = None, prefix: str = "") -> Optional[Number]:
        if delays is not None:
            return delays.get(self.key(index, prefix), self.param("initial_value"))
        return self.param("initial_value")

    def evaluate_output(self, index: int, input_values: Sequence[Number], results: Optional[MutableResultMap] = None, delays: Optional[MutableDelayMap] = None, prefix: str = "", bits_override: Optional[int] = None, truncate: bool = True) -> Number:
        if index != 0:
            raise IndexError(
                f"Output index out of range (expected 0-0, got {index})")
        if len(input_values) != 1:
            raise ValueError(
                f"Wrong number of inputs supplied to SFG for evaluation (expected 1, got {len(input_values)})")

        key = self.key(index, prefix)
        value = self.param("initial_value")
        if delays is not None:
            value = delays.get(key, value)
            delays[key] = self.truncate_inputs(input_values, bits_override)[
                0] if truncate else input_values[0]
        if results is not None:
            results[key] = value
        return value

    @property
    def initial_value(self) -> Number:
        """Get the initial value of this delay."""
        return self.param("initial_value")

    @initial_value.setter
    def initial_value(self, value: Number) -> None:
        """Set the initial value of this delay."""
        self.set_param("initial_value", value)
