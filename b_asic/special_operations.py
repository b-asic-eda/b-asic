"""
B-ASIC Special Operations Module.

Contains operations with special purposes that may be treated differently from
normal operations in an SFG.
"""

from typing import Optional, Sequence, Tuple

from b_asic.operation import (
    AbstractOperation,
    DelayMap,
    MutableDelayMap,
    MutableResultMap,
)
from b_asic.port import SignalSourceProvider
from b_asic.types import Name, Num, TypeName


class Input(AbstractOperation):
    """
    Input operation.

    Represents an input port to an SFG.
    Its value will be updated on each iteration when simulating the SFG.

    Parameters
    ==========
    name : Name, optional
        Operation name.
    """

    is_linear = True
    is_constant = False

    def __init__(self, name: Name = ""):
        """Construct an Input operation."""
        super().__init__(
            input_count=0,
            output_count=1,
            name=name,
            latency_offsets={"out0": 0},
            execution_time=0,
        )
        self.set_param("value", 0)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("in")

    def evaluate(self):
        return self.param("value")

    @property
    def latency(self) -> int:
        return self.latency_offsets["out0"]

    @property
    def value(self) -> Num:
        """Get the current value of this input."""
        return self.param("value")

    @value.setter
    def value(self, value: Num) -> None:
        """Set the current value of this input."""
        self.set_param("value", value)

    def get_plot_coordinates(
        self,
    ) -> Tuple[Tuple[Tuple[float, float], ...], Tuple[Tuple[float, float], ...]]:
        # Doc-string inherited
        return (
            (
                (-0.5, 0),
                (-0.5, 1),
                (-0.25, 1),
                (0, 0.5),
                (-0.25, 0),
                (-0.5, 0),
            ),
            (
                (-0.5, 0),
                (-0.5, 1),
                (-0.25, 1),
                (0, 0.5),
                (-0.25, 0),
                (-0.5, 0),
            ),
        )

    def get_input_coordinates(self) -> Tuple[Tuple[float, float], ...]:
        # doc-string inherited
        return tuple()

    def get_output_coordinates(self) -> Tuple[Tuple[float, float], ...]:
        # doc-string inherited
        return ((0, 0.5),)


class Output(AbstractOperation):
    """
    Output operation.

    Represents an output port to an SFG.
    The SFG will forward its input to the corresponding output signal
    destinations.

    Parameters
    ==========

    src0 : SignalSourceProvider, optional
        The signal connected to the Output operation.
    name : Name, optional
        Operation name.
    """

    is_linear = True

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
    ):
        """Construct an Output operation."""
        super().__init__(
            input_count=1,
            output_count=0,
            name=Name(name),
            input_sources=[src0],
            latency_offsets={"in0": 0},
            execution_time=0,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("out")

    def evaluate(self, _):
        return None

    def get_plot_coordinates(
        self,
    ) -> Tuple[Tuple[Tuple[float, float], ...], Tuple[Tuple[float, float], ...]]:
        # Doc-string inherited
        return (
            ((0, 0), (0, 1), (0.25, 1), (0.5, 0.5), (0.25, 0), (0, 0)),
            ((0, 0), (0, 1), (0.25, 1), (0.5, 0.5), (0.25, 0), (0, 0)),
        )

    def get_input_coordinates(self) -> Tuple[Tuple[float, float], ...]:
        # doc-string inherited
        return ((0, 0.5),)

    def get_output_coordinates(self) -> Tuple[Tuple[float, float], ...]:
        # doc-string inherited
        return tuple()

    @property
    def latency(self) -> int:
        return self.latency_offsets["in0"]


class Delay(AbstractOperation):
    """
    Unit delay operation.

    Represents a delay of one iteration.
    The initial value is zero unless otherwise specified.

    Parameters
    ----------
    src0 : SignalSourceProvider, optional
        The node to be delayed.
    initial_value : Number, default: 0
        Initial value of the delay.
    name : Name, default ""
        Name.
    """

    is_linear = True

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        initial_value: Num = 0,
        name: Name = Name(""),
    ):
        """Construct a Delay operation."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=Name(name),
            input_sources=[src0],
        )
        self.set_param("initial_value", initial_value)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("t")

    def evaluate(self, a):
        return self.param("initial_value")

    def current_output(
        self, index: int, delays: Optional[DelayMap] = None, prefix: str = ""
    ) -> Optional[Num]:
        if delays is not None:
            return delays.get(self.key(index, prefix), self.param("initial_value"))
        return self.param("initial_value")

    def evaluate_output(
        self,
        index: int,
        input_values: Sequence[Num],
        results: Optional[MutableResultMap] = None,
        delays: Optional[MutableDelayMap] = None,
        prefix: str = "",
        bits_override: Optional[int] = None,
        quantize: bool = True,
    ) -> Num:
        if index != 0:
            raise IndexError(f"Output index out of range (expected 0-0, got {index})")
        if len(input_values) != 1:
            raise ValueError(
                "Wrong number of inputs supplied to SFG for evaluation"
                f" (expected 1, got {len(input_values)})"
            )

        key = self.key(index, prefix)
        value = self.param("initial_value")
        if delays is not None:
            value = delays.get(key, value)
            delays[key] = (
                self.quantize_inputs(input_values, bits_override)[0]
                if quantize
                else input_values[0]
            )
        if results is not None:
            results[key] = value
        return value

    @property
    def initial_value(self) -> Num:
        """Get the initial value of this delay."""
        return self.param("initial_value")

    @initial_value.setter
    def initial_value(self, value: Num) -> None:
        """Set the initial value of this delay."""
        self.set_param("initial_value", value)
