"""
B-ASIC Special Operations Module.

Contains operations with special purposes that may be treated differently from
normal operations in an SFG.
"""

from collections.abc import Sequence

from b_asic.operation import (
    AbstractOperation,
    DelayMap,
    MutableDelayMap,
    MutableResultMap,
)
from b_asic.port import SignalSourceProvider
from b_asic.types import Name, Num, ShapeCoordinates, TypeName


class Input(AbstractOperation):
    """
    Input operation.

    Represents an input port to an SFG.
    Its value will be updated on each iteration when simulating the SFG.

    Parameters
    ----------
    name : Name, optional
        Operation name.
    """

    is_linear = True
    is_constant = False

    def __init__(self, name: Name = "") -> None:
        """Construct an Input operation."""
        super().__init__(
            input_count=0,
            output_count=1,
            name=name,
            latency_offsets={"out0": 0},
            execution_time=1,
        )
        self._value = 0

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("in")

    def evaluate(self) -> Num:
        return self._value

    @property
    def latency(self) -> int:
        return 0

    @property
    def value(self) -> Num:
        """Get the current value of this input."""
        return self._value

    @value.setter
    def value(self, value: Num) -> None:
        """Set the current value of this input."""
        self._value = value

    def get_plot_coordinates(
        self,
    ) -> tuple[ShapeCoordinates, ShapeCoordinates]:
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

    def get_input_coordinates(self) -> ShapeCoordinates:
        # doc-string inherited
        return ()

    def get_output_coordinates(self) -> ShapeCoordinates:
        # doc-string inherited
        return ((0, 0.5),)


class Output(AbstractOperation):
    """
    Output operation.

    Represents an output port to an SFG.
    The SFG will forward its input to the corresponding output signal
    destinations.

    Parameters
    ----------
    src0 : SignalSourceProvider, optional
        The signal connected to the Output operation.
    name : Name, optional
        Operation name.
    """

    is_linear = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        name: Name = Name(""),
    ) -> None:
        """Construct an Output operation."""
        super().__init__(
            input_count=1,
            output_count=0,
            name=Name(name),
            input_sources=[src0],
            latency_offsets={"in0": 0},
            execution_time=1,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("out")

    def evaluate(self, _) -> None:
        return None

    def get_plot_coordinates(
        self,
    ) -> tuple[ShapeCoordinates, ShapeCoordinates]:
        # Doc-string inherited
        return (
            ((0, 0), (0, 1), (0.25, 1), (0.5, 0.5), (0.25, 0), (0, 0)),
            ((0, 0), (0, 1), (0.25, 1), (0.5, 0.5), (0.25, 0), (0, 0)),
        )

    def get_input_coordinates(self) -> ShapeCoordinates:
        # doc-string inherited
        return ((0, 0.5),)

    def get_output_coordinates(self) -> ShapeCoordinates:
        # doc-string inherited
        return ()

    @property
    def latency(self) -> int:
        return 0


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
        src0: SignalSourceProvider | None = None,
        initial_value: Num = 0,
        name: Name = Name(""),
    ) -> None:
        """Construct a Delay operation."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=Name(name),
            input_sources=[src0],
            latency=0,
        )
        self.initial_value = initial_value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("t")

    def evaluate(self, a) -> Num:
        return self.param("initial_value")

    def current_output(
        self, index: int, delays: DelayMap | None = None, prefix: str = ""
    ) -> Num | None:
        if delays is not None:
            return delays.get(self.key(index, prefix), self.param("initial_value"))
        return self.param("initial_value")

    def evaluate_output(
        self,
        index: int,
        input_values: Sequence[Num],
        results: MutableResultMap | None = None,
        delays: MutableDelayMap | None = None,
        prefix: str = "",
        bits_override: int | None = None,
        quantize: bool = True,
    ) -> Num:
        if index != 0:
            raise IndexError(f"Output index out of range (expected 0-0, got {index})")
        if len(input_values) != 1:
            raise ValueError(
                "Wrong number of inputs supplied to Delay for evaluation"
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
