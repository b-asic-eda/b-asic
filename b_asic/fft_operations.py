"""
B-ASIC FFT Operations Module.

Contains selected FFT butterfly operations.
"""

from b_asic.graph_component import Name, TypeName
from b_asic.operation import AbstractOperation
from b_asic.port import SignalSourceProvider
from b_asic.types import Num


class R2Butterfly(AbstractOperation):
    r"""
    Radix-2 butterfly operation for FFTs.

    Gives the result of adding its two inputs, as well as the result of subtracting the
    second input from the first one. This corresponds to a 2-point DFT.

    .. math::
        \begin{eqnarray}
        y_0 & = & x_0 + x_1\\
        y_1 & = & x_0 - x_1
        \end{eqnarray}

    Parameters
    ----------
    src0, src1 : SignalSourceProvider, optional
        The two signals to compute the 2-point DFT of.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if inputs have different arrival times or if the inputs should arrive
        after the operator has stared. For example, ``{"in0": 0, "in1": 1}`` which
        corresponds to *src1* arriving one time unit later than *src0* and one time
        unit later than the operator starts. If not provided and *latency* is provided,
        set to zero. Hence, the previous example can be written as ``{"in1": 1}``
        only.
    execution_time : int, optional
        Operation execution time (time units before operator can be reused).
    """

    __slots__ = (
        "_execution_time",
        "_latency",
        "_latency_offsets",
        "_name",
        "_src0",
        "_src1",
    )
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
        """Construct a R2Butterfly operation."""
        super().__init__(
            input_count=2,
            output_count=2,
            name=Name(name),
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("r2bfly")

    def evaluate(self, a, b) -> Num:
        return a + b, a - b


class R2DIFButterfly(AbstractOperation):
    r"""
    Radix-2 decimation-in-frequency butterfly operation for FFTs.

    Gives the result of adding its two inputs, as well as the result of subtracting the
    second input from the first one. This corresponds to a 2-point DFT.
    The second output is multiplied with the provided twiddle factor (TF).

    .. math::
        \begin{eqnarray}
        y_0 & = & x_0 + x_1\\
        y_1 & = & w(x_0 - x_1)
        \end{eqnarray}

    Parameters
    ----------
    w: complex
        Twiddle factor to multiply the second output with.
    src0, src1 : SignalSourceProvider, optional
        The two signals to compute the 2-point DFT of.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if inputs have different arrival times or if the inputs should arrive
        after the operator has stared. For example, ``{"in0": 0, "in1": 1}`` which
        corresponds to *src1* arriving one time unit later than *src0* and one time
        unit later than the operator starts. If not provided and *latency* is provided,
        set to zero. Hence, the previous example can be written as ``{"in1": 1}``
        only.
    execution_time : int, optional
        Operation execution time (time units before operator can be reused).
    """

    __slots__ = (
        "_execution_time",
        "_latency",
        "_latency_offsets",
        "_name",
        "_src0",
        "_src1",
        "_w",
    )
    _w: complex
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True

    def __init__(
        self,
        w: complex,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
        """Construct a R2DIFButterfly operation."""
        super().__init__(
            input_count=2,
            output_count=2,
            name=Name(name),
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.set_param("w", w)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("r2difbfly")

    def evaluate(self, a, b) -> Num:
        return a + b, self.w * (a - b)

    @property
    def w(self) -> complex:
        """Get the twiddle factor."""
        return self.param("w")

    @w.setter
    def w(self, w: complex) -> None:
        """Set the twiddle factor."""
        self.set_param("w", w)


class R2DITButterfly(AbstractOperation):
    r"""
    Radix-2 decimation-in-time butterfly operation for FFTs.

    Gives the result of adding its two inputs, as well as the result of subtracting the
    second input from the first one. This corresponds to a 2-point DFT.
    The second input is multiplied with the provided twiddle factor (TF).

    .. math::
        \begin{eqnarray}
        y_0 & = & x_0 + w*x_1\\
        y_1 & = & x_0 - w*x_1
        \end{eqnarray}

    Parameters
    ----------
    w: complex
        Twiddle factor to multiply the second input with.
    src0, src1 : SignalSourceProvider, optional
        The two signals to compute the 2-point DFT of.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if inputs have different arrival times or if the inputs should arrive
        after the operator has stared. For example, ``{"in0": 0, "in1": 1}`` which
        corresponds to *src1* arriving one time unit later than *src0* and one time
        unit later than the operator starts. If not provided and *latency* is provided,
        set to zero. Hence, the previous example can be written as ``{"in1": 1}``
        only.
    execution_time : int, optional
        Operation execution time (time units before operator can be reused).
    """

    __slots__ = (
        "_execution_time",
        "_latency",
        "_latency_offsets",
        "_name",
        "_src0",
        "_src1",
        "_w",
    )
    _w: complex
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True

    def __init__(
        self,
        w: complex,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
        """Construct a R2DITButterfly operation."""
        super().__init__(
            input_count=2,
            output_count=2,
            name=Name(name),
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.set_param("w", w)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("r2ditbfly")

    def evaluate(self, a, b) -> Num:
        tmp_b = self.w * b
        return a + tmp_b, a - tmp_b

    @property
    def w(self) -> complex:
        """Get the twiddle factor."""
        return self.param("w")

    @w.setter
    def w(self, w: complex) -> None:
        """Set the twiddle factor."""
        self.set_param("w", w)
