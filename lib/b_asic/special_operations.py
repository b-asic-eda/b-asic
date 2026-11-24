"""
B-ASIC Special Operations Module.

Contains operations with special purposes that may be treated differently from
normal operations in an SFG.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from b_asic.core_operations import _RealValuedOperation
from b_asic.operation import (
    AbstractOperation,
    DelayMap,
    _ComplexPair,
)
from b_asic.port import SignalSourceProvider
from b_asic.types import Name, Num, ShapeCoordinates, TypeName

if TYPE_CHECKING:
    from b_asic.sfg import SFG
    from b_asic.utility_operations import Sink


class Input(_RealValuedOperation):
    """
    Input operation.

    Represents an input port to an SFG.
    Its value will be updated on each iteration when simulating the SFG.

    Parameters
    ----------
    name : :data:`~b_asic.types.Name`, optional
        Operation name.
    real_valued : bool or None, default: None
        Mark the interface as real-valued. Complex-to-real conversion discards
        the imaginary input and uses a zero constant for its imaginary signal.
    """

    is_linear = True
    is_constant = False

    def __init__(self, name: Name = "", real_valued: bool | None = None) -> None:
        """Construct an Input operation."""
        super().__init__(
            input_count=0,
            output_count=1,
            name=name,
            latency_offsets={"out0": 0},
            execution_time=1,
        )
        self.real_valued = real_valued
        self._value = 0

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("in")

    def evaluate(self, data_type=None) -> Num:
        return self._cast_to_data_type(self._value, data_type)

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


class Output(_RealValuedOperation):
    """
    Output operation.

    Represents an output port to an SFG.
    The SFG will forward its input to the corresponding output signal
    destinations.

    Parameters
    ----------
    in0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The signal connected to the Output operation.
    name : :data:`~b_asic.types.Name`, optional
        Operation name.
    real_valued : bool or None, default: None
        Mark the interface as real-valued. Complex-to-real conversion terminates
        the incoming imaginary signal at a Sink and emits an imaginary zero.
    """

    is_linear = True

    def __init__(
        self,
        in0: SignalSourceProvider | None = None,
        name: Name = Name(""),
        real_valued: bool | None = None,
    ) -> None:
        """Construct an Output operation."""
        super().__init__(
            input_count=1,
            output_count=0,
            name=Name(name),
            input_sources=[in0],
            latency_offsets={"in0": 0},
            execution_time=1,
        )
        self.real_valued = real_valued

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("out")

    def _expr(self, recursive: bool = False) -> str:
        inputs = self._get_input_representations(recursive, wrap_expressions=False)
        return inputs[0]

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


class MemoryRead(Input):
    """
    Read a value from a memory address.

    Behaves as an :class:`Input` with an address and an optional memory name.
    During simulation, values are supplied through the SFG input mechanism.
    The address and memory name identify the memory location symbolically.

    Parameters
    ----------
    address : int, default: 0
        Read address.
    memory_name : :data:`~b_asic.types.Name`, optional
        Memory name. An empty name denotes the default memory.
    name : :data:`~b_asic.types.Name`, optional
        Operation name.
    latency : int, default: 0
        Cycles between presenting the read address and obtaining the value.
        The operation starts when the address is presented, and its value output
        has this latency offset.
    real_valued : bool or None, default: None
        Mark the stored input as real-valued, as for :class:`Input`.
    """

    def __init__(
        self,
        address: int = 0,
        memory_name: Name = "",
        name: Name = "",
        latency: int = 0,
        real_valued: bool | None = None,
    ) -> None:
        super().__init__(name=name, real_valued=real_valued)
        self.address = address
        self.memory_name = memory_name
        self.set_latency(latency)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("read")

    @property
    def latency(self) -> int:
        """Get the latency from the read address to the value output."""
        return self.output_latency_offsets[0]

    @property
    def address(self) -> int:
        """Get the read address."""
        return self.param("address")

    @address.setter
    def address(self, address: int) -> None:
        """Set the read address."""
        self.set_param("address", address)

    @property
    def memory_name(self) -> Name:
        """Get the name of the memory to read from."""
        return self.param("memory_name")

    @memory_name.setter
    def memory_name(self, memory_name: Name) -> None:
        """Set the name of the memory to read from."""
        self.set_param("memory_name", memory_name)


class MemoryWrite(Output):
    """
    Write a value to a memory address.

    Behaves as an :class:`Output` with an address and an optional memory name.
    During simulation, values are collected through the SFG output mechanism.
    The address and memory name identify the memory location symbolically.

    Parameters
    ----------
    address : int, default: 0
        Write address.
    in0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The signal to write.
    memory_name : :data:`~b_asic.types.Name`, optional
        Memory name. An empty name denotes the default memory.
    name : :data:`~b_asic.types.Name`, optional
        Operation name.
    real_valued : bool or None, default: None
        Mark the stored output as real-valued, as for :class:`Output`.
    """

    def __init__(
        self,
        address: int = 0,
        in0: SignalSourceProvider | None = None,
        memory_name: Name = "",
        name: Name = "",
        real_valued: bool | None = None,
    ) -> None:
        super().__init__(in0=in0, name=name, real_valued=real_valued)
        self.address = address
        self.memory_name = memory_name

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("write")

    @property
    def address(self) -> int:
        """Get the write address."""
        return self.param("address")

    @address.setter
    def address(self, address: int) -> None:
        """Set the write address."""
        self.set_param("address", address)

    @property
    def memory_name(self) -> Name:
        """Get the name of the memory to write to."""
        return self.param("memory_name")

    @memory_name.setter
    def memory_name(self, memory_name: Name) -> None:
        """Set the name of the memory to write to."""
        self.set_param("memory_name", memory_name)


class Delay(AbstractOperation):
    """
    Unit delay operation.

    Represents a delay of one iteration.
    The initial value is zero unless otherwise specified.

    Parameters
    ----------
    in0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The node to be delayed.
    initial_value : Number, default: 0
        Initial value of the delay.
    name : :data:`~b_asic.types.Name`, default ""
        Name.
    """

    is_linear = True

    def __init__(
        self,
        in0: SignalSourceProvider | None = None,
        initial_value: Num = 0,
        name: Name = Name(""),
    ) -> None:
        """Construct a Delay operation."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=Name(name),
            input_sources=[in0],
            latency=0,
        )
        self.initial_value = initial_value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("t")

    def _expr(self, recursive: bool = False) -> str:
        inputs = self._get_input_representations(recursive, wrap_expressions=False)
        if self.initial_value != 0:
            return f"{inputs[0]}, init={self.initial_value}"
        return inputs[0]

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

    def _constant_propagation(self) -> "SFG | None":
        from b_asic.core_operations import (  # noqa: PLC0415
            Constant,
            _simplified_sfg,
        )

        source = self.input(0).connected_source
        if (
            source is not None
            and isinstance(source.operation, Constant)
            and source.operation.value == self.initial_value
        ):
            value = source.operation.value
            return _simplified_sfg(self, lambda inputs: Constant(value))
        return None

    def _complex_to_real(
        self, inputs: Sequence[_ComplexPair], sinks: list["Sink"], **kwargs
    ) -> Sequence[_ComplexPair]:
        """Build real and imaginary output pairs for this operation."""
        value = self.initial_value
        return [
            _ComplexPair(
                Delay(inputs[0].re, initial_value=value.real, name=self.name),
                Delay(inputs[0].im, initial_value=value.imag, name=self.name),
            )
        ]


class _RateChange(AbstractOperation):
    """Base for symbolic operations that change the number of samples."""

    is_linear = True
    is_constant = False

    def __init__(
        self,
        factor: int = 2,
        in0: SignalSourceProvider | None = None,
        name: Name = "",
        *,
        phase: int = 0,
    ) -> None:
        if not isinstance(factor, int) or isinstance(factor, bool):
            raise TypeError("factor must be an integer")
        if factor < 1:
            raise ValueError("factor must be positive")
        if not isinstance(phase, int) or isinstance(phase, bool):
            raise TypeError("phase must be an integer")
        if not 0 <= phase < factor:
            raise ValueError("phase must satisfy 0 <= phase < factor")
        super().__init__(
            input_count=1,
            output_count=1,
            input_sources=[in0],
            name=name,
            latency=0,
            execution_time=0,
        )
        self.set_param("factor", factor)
        self.set_param("phase", phase)

    @property
    def factor(self) -> int:
        """Get the integer sample-rate conversion factor."""
        return self.param("factor")

    @property
    def phase(self) -> int:
        """Get the retained or nonzero phase."""
        return self.param("phase")

    def _expr(self, recursive: bool = False) -> str:
        source = self._get_input_representations(recursive)[0]
        return f"{type(self).__name__}({self.factor}, {source}, phase={self.phase})"

    def evaluate(self, *inputs, data_type=None):
        raise ValueError(
            "Rate-changing operations require stream evaluation. "
            "Use Simulation or SFG.to_single_rate()."
        )

    def split(self):
        return [self]

    def to_sfg(self) -> "SFG":
        from b_asic.sfg import SFG  # noqa: PLC0415

        source = Input()
        operation = self.copy()
        operation.input(0).connect(source)
        return SFG(source, Output(operation))

    def _constant_propagation(self) -> "SFG | None":
        # In particular, expanding a nonzero constant does not produce a
        # constant stream. Simplify after the phases have been made explicit.
        return None

    def _complex_to_real(
        self, inputs: Sequence[_ComplexPair], sinks: list["Sink"], **kwargs
    ) -> Sequence[_ComplexPair]:
        """Build real and imaginary output pairs for this operation."""
        from b_asic.complex_conversion import _componentwise  # noqa: PLC0415

        return _componentwise(self, inputs, sinks)


class Expansion(_RateChange):
    r"""
    Increase the sample rate by an integer *factor* using zero insertion.

    The output is ``y[factor * n + phase] = x[n]``; all other samples are zero.
    Filtering, when needed, is represented by separate operations.

    Parameters
    ----------
    factor : int, default: 2
        Positive integer expansion factor.
    in0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        Input stream.
    name : :data:`~b_asic.types.Name`, optional
        Operation name.
    phase : int, default: 0
        Nonzero phase, in the range ``0 <= phase < factor``.

    Notes
    -----
    Simulate graphs containing this operation with :class:`~b_asic.simulation.Simulation`.
    Use :meth:`~b_asic.sfg.SFG.to_single_rate` before scheduling.
    """

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("expand")


class Compression(_RateChange):
    r"""
    Reduce the sample rate by retaining every *factor*:th sample.

    The output is ``y[n] = x[factor * n + phase]``.

    Parameters
    ----------
    factor : int, default: 2
        Positive integer compression factor.
    in0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        Input stream.
    name : :data:`~b_asic.types.Name`, optional
        Operation name.
    phase : int, default: 0
        Retained phase, in the range ``0 <= phase < factor``.

    Notes
    -----
    Simulate graphs containing this operation with :class:`~b_asic.simulation.Simulation`.
    Use :meth:`~b_asic.sfg.SFG.to_single_rate` before scheduling.
    """

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("compress")
