"""
B-ASIC Utility Operations Module.

Contains some operations that are not really operations, but needed for other reasons.
"""

import random
from collections.abc import Sequence

from b_asic.graph_component import Name, TypeName
from b_asic.operation import AbstractOperation, _ComplexPair
from b_asic.port import SignalSourceProvider
from b_asic.types import Num, ShapeCoordinates


class ComplexToReal(AbstractOperation):
    """
    Split a complex signal into its real and imaginary parts.

    Output 0 is the real part and output 1 is the imaginary part. Both outputs
    are real signals. Used at complex SFG interfaces by
    :meth:`~b_asic.sfg.SFG.complex_to_real` with ``split_io=False``.

    Parameters
    ----------
    in0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        Complex input signal.
    name : :data:`~b_asic.types.Name`, optional
        Operation name.
    """

    __slots__ = ()

    def __init__(
        self, in0: SignalSourceProvider | None = None, name: Name = ""
    ) -> None:
        super().__init__(
            input_count=1,
            output_count=2,
            input_sources=[in0],
            name=name,
            latency=0,
            execution_time=0,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("c2r")

    def evaluate(self, a, data_type=None) -> tuple[Num, Num]:
        if isinstance(a, SignalSourceProvider):
            raise TypeError("ComplexToReal requires a numeric input")
        return (
            self._cast_to_data_type(a.real, data_type),
            self._cast_to_data_type(a.imag, data_type),
        )

    def _complex_to_real(
        self, inputs: Sequence[_ComplexPair], sinks: list["Sink"], **kwargs
    ) -> Sequence[_ComplexPair]:
        from b_asic.core_operations import Constant  # noqa: PLC0415

        return [
            _ComplexPair(inputs[0].re, Constant(0)),
            _ComplexPair(inputs[0].im, Constant(0)),
        ]


class RealToComplex(AbstractOperation):
    """
    Join real and imaginary signals into a complex signal.

    Both inputs must be real. Input 0 supplies the real part and input 1 the
    imaginary part. Used at complex SFG interfaces by
    :meth:`~b_asic.sfg.SFG.complex_to_real` with ``split_io=False``.

    Parameters
    ----------
    in0, in1 : :class:`~b_asic.port.SignalSourceProvider`, optional
        Real and imaginary input signals, respectively.
    name : :data:`~b_asic.types.Name`, optional
        Operation name.
    """

    __slots__ = ()

    def __init__(
        self,
        in0: SignalSourceProvider | None = None,
        in1: SignalSourceProvider | None = None,
        name: Name = "",
    ) -> None:
        super().__init__(
            input_count=2,
            output_count=1,
            input_sources=[in0, in1],
            name=name,
            latency=0,
            execution_time=0,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("r2c")

    def evaluate(self, a, b, data_type=None) -> Num:
        return self._cast_to_data_type(complex(float(a), float(b)), data_type)

    def _complex_to_real(
        self, inputs: Sequence[_ComplexPair], sinks: list["Sink"], **kwargs
    ) -> Sequence[_ComplexPair]:
        sinks.extend((Sink(inputs[0].im), Sink(inputs[1].im)))
        return [_ComplexPair(inputs[0].re, inputs[1].re)]


class DontCare(AbstractOperation):
    """
    Dont-care operation.

    Used for ignoring the input to another operation and thus avoiding dangling input nodes.

    Parameters
    ----------
    name : :data:`~b_asic.types.Name`, optional
        Operation name.
    """

    __slots__ = ("_name",)
    _name: Name

    is_linear = True

    def __init__(self, name: Name = "") -> None:
        """Construct a DontCare operation."""
        super().__init__(
            input_count=0,
            output_count=1,
            name=name,
            latency_offsets={"out0": 0},
            execution_time=0,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("dontcare")

    def evaluate(self, data_type=None) -> float:
        # Evaluate to random to flush out errors
        res = random.random()
        return self._cast_to_data_type(res, data_type)

    @property
    def latency(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "DontCare()"

    def __str__(self) -> str:
        return "dontcare"

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

    def _complex_to_real(
        self, inputs: Sequence[_ComplexPair], sinks: list["Sink"], **kwargs
    ) -> Sequence[_ComplexPair]:
        """Build real and imaginary output pairs for this operation."""
        from b_asic.complex_conversion import _componentwise  # noqa: PLC0415

        return _componentwise(self, inputs, sinks)


class Sink(AbstractOperation):
    """
    Sink operation.

    Used for ignoring the output from another operation to avoid dangling output nodes.

    Parameters
    ----------
    in0 : SignalSourceProvider, optional
        Source of the unused output. A string is accepted as a positional name
        for compatibility with earlier versions.
    name : :data:`~b_asic.types.Name`, optional
        Operation name.
    """

    __slots__ = ("_name",)
    _name: Name

    is_linear = True

    def __init__(
        self,
        in0: SignalSourceProvider | Name | None = None,
        name: Name = "",
    ) -> None:
        """Construct a Sink operation."""
        if isinstance(in0, str):
            name, in0 = in0, None
        super().__init__(
            input_count=1,
            output_count=0,
            name=name,
            input_sources=[in0],
            latency_offsets={"in0": 0},
            execution_time=0,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("sink")

    def evaluate(self) -> None:
        raise NotImplementedError

    @property
    def latency(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "Sink()"

    def __str__(self) -> str:
        return "sink"

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

    def _complex_to_real(
        self, inputs: Sequence[_ComplexPair], sinks: list["Sink"], **kwargs
    ) -> Sequence[_ComplexPair]:
        """Build real and imaginary output pairs for this operation."""
        sinks.extend((Sink(inputs[0].re), Sink(inputs[0].im)))
        return []
