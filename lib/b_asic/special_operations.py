"""
B-ASIC Special Operations Module.

Contains operations with special purposes that may be treated differently from
normal operations in an SFG.
"""

import apytypes as apy

from b_asic.data_type import NumRepresentation
from b_asic.operation import (
    AbstractOperation,
    DelayMap,
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

    def evaluate(self, data_type=None) -> Num:
        if data_type is None:
            return self._value
        if data_type.num_repr == NumRepresentation.FIXED_POINT:
            return apy.fx(self._value, data_type.wl[0], data_type.wl[1])
        return apy.fp(self._value, data_type.wl[0], data_type.wl[1])

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

    def evaluate(self, _, data_type) -> None:
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

    def evaluate(self, a, data_type, delays=None) -> Num:
        if data_type and data_type.is_complex:
            self.initial_value = complex(self.initial_value)
        if delays is not None:
            res = delays.get(self.graph_id, self.param("initial_value"))
        else:
            res = self.param("initial_value")
        return self._cast_to_data_type(res, data_type)

    def current_output(
        self, index: int, delays: DelayMap | None = None, prefix: str = ""
    ) -> Num | None:
        if delays is not None:
            return delays.get(self.key(index, prefix), self.param("initial_value"))
        return self.param("initial_value")

    @property
    def initial_value(self) -> Num:
        """Get the initial value of this delay."""
        return self.param("initial_value")

    @initial_value.setter
    def initial_value(self, value: Num) -> None:
        """Set the initial value of this delay."""
        self.set_param("initial_value", value)
