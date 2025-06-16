"""
B-ASIC FFT Operations Module.

Contains selected FFT butterfly operations.
"""

from math import cos, pi, sin

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


class R2TFButterfly(AbstractOperation):
    r"""
    Radix-2 butterfly operation for FFTs with twiddle factor (TF) multiplications at both outputs.

    Gives the result of adding its two inputs, as well as the result of subtracting the
    second input from the first one. This corresponds to a 2-point DFT.
    Both outputs are multiplied with the provided TFs.

    .. math::
        \begin{eqnarray}
        y_0 & = & w_0(x_0 + x_1)\\
        y_1 & = & w_1(x_0 - x_1)
        \end{eqnarray}

    Parameters
    ----------
    w0: complex
        Twiddle factor to multiply the first output with.
    w1: complex
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
        "_w0",
        "_w1",
    )
    _w0: complex
    _w1: complex
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True

    def __init__(
        self,
        w0: complex,
        w1: complex,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
        """Construct a R2TFButterfly operation."""
        super().__init__(
            input_count=2,
            output_count=2,
            name=Name(name),
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.set_param("w0", w0)
        self.set_param("w1", w1)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("r2tfbfly")

    def evaluate(self, a, b) -> Num:
        return self.w0 * (a + b), self.w1 * (a - b)

    @property
    def w0(self) -> complex:
        """Get the twiddle factor that the first output is multiplied with."""
        return self.param("w0")

    @w0.setter
    def w0(self, w0: complex) -> None:
        """Set the twiddle factor that the first output is multiplied with."""
        self.set_param("w0", w0)

    @property
    def w1(self) -> complex:
        """Get the twiddle factor that the second output is multiplied with."""
        return self.param("w1")

    @w1.setter
    def w1(self, w1: complex) -> None:
        """Set the twiddle factor that the second output is multiplied with."""
        self.set_param("w1", w1)


class R4Butterfly(AbstractOperation):
    r"""
    Radix-4 butterfly operation for FFTs.

    This corresponds to a 4-point DFT.

    .. math::
        \begin{eqnarray}
            s0 & = & x_0 + x_2\\
            s1 & = & x_1 + x_3\\
            s2 & = & x_0 - x_2\\
            s3 & = & -j*x_1 + j*x_3\\
            y0 & = & s0 + s1\\
            y1 & = & s2 + s3\\
            y2 & = & s0 - s1\\
            y3 & = & s2 - s3
        \end{eqnarray}

    Parameters
    ----------
    src0, src1, src2, src3 : SignalSourceProvider, optional
        The four signals to compute the 4-point DFT of.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if inputs have different arrival times or if the inputs should arrive
        after the operator has stared. For example, ``{"in0": 0, "in1": 1, "in2": 0, "in3": 0}`` which
        corresponds to *src1* arriving one time unit later than the other inputs and one time
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
        "_src2",
        "_src3",
    )
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _src2: SignalSourceProvider | None
    _src3: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        src2: SignalSourceProvider | None = None,
        src3: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
        """Construct a R4Butterfly operation."""
        super().__init__(
            input_count=4,
            output_count=4,
            name=Name(name),
            input_sources=[src0, src1, src2, src3],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("r4bfly")

    def evaluate(self, a, b, c, d) -> Num:
        s0 = a + c
        s1 = b + d
        s2 = a - c
        s3 = -1j * b + 1j * d

        y0 = s0 + s1  # y0 = a + b + c + d
        y1 = s2 + s3  # y1 = a -1j*b - c + 1j*d
        y2 = s0 - s1  # y2 = a - b + c - d
        y3 = s2 - s3  # y3 = a + 1j*b - c - 1j*d
        return y0, y1, y2, y3


class R3Winograd(AbstractOperation):
    r"""
    Three-point Winograd DFT.

    .. math::
        \begin{eqnarray}
            u = -2 * pi / 3
            c_{30} = cos(u) - 1
            c_{31} = j * sin(u)
            s_0 = x_1 + x_2
            s_1 = x_1 - x_2
            s_2 = s_0 + x_0
            m_0 = c_{30} * s_0
            m_1 = c_{31} * s_1
            s_3 = s_2 + m_0
            s_4 = s_3 + m_1
            s_5 = s_3 - m_1
            y_0 = s_2
            y_1 = s_4
            y_2 = s_5
        \end{eqnarray}

    Parameters
    ----------
    src0, src1, src2 : SignalSourceProvider, optional
        The three signals to compute the 3-point DFT of.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if inputs have different arrival times or if the inputs should arrive
        after the operator has stared. For example, ``{"in0": 0, "in1": 1, "in2": 0}`` which
        corresponds to *src1* arriving one time unit later than the other inputs and one time
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
        "_src2",
    )
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _src2: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        src2: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
        """Construct a R3Winograd operation."""
        super().__init__(
            input_count=3,
            output_count=3,
            name=Name(name),
            input_sources=[src0, src1, src2],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("r3win")

    def evaluate(self, a, b, c) -> Num:
        u = -2 * pi / 3
        c30 = cos(u) - 1
        c31 = 1j * sin(u)

        s0 = b + c
        s1 = b - c
        s2 = s0 + a
        m0 = c30 * s0
        m1 = c31 * s1
        s3 = s2 + m0
        s4 = s3 + m1
        s5 = s3 - m1

        y0 = s2
        y1 = s4
        y2 = s5

        return y0, y1, y2


class R5Winograd(AbstractOperation):
    r"""
    Five-point Winograd DFT.

    .. math::
        \begin{eqnarray}
        \end{eqnarray}

    Parameters
    ----------
    src0, src1, src2, src3, src4 : SignalSourceProvider, optional
        The five signals to compute the 5-point DFT of.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if inputs have different arrival times or if the inputs should arrive
        after the operator has stared.
        For example, ``{"in0": 0, "in1": 1, "in2": 0, "in3": 0, "in4": 0,}`` which
        corresponds to *src1* arriving one time unit later than the other inputs and one time
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
        "_src2",
        "_src3",
        "_src4",
    )
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _src2: SignalSourceProvider | None
    _src3: SignalSourceProvider | None
    _src4: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        src2: SignalSourceProvider | None = None,
        src3: SignalSourceProvider | None = None,
        src4: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
        """Construct a R5Winograd operation."""
        super().__init__(
            input_count=5,
            output_count=5,
            name=Name(name),
            input_sources=[src0, src1, src2, src3, src4],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("r3win")

    def evaluate(self, a, b, c, d, e) -> Num:
        # % Fast Fourier Transform and Convolution Algorithms-Springer-Verlag
        # % Berlin Heidelberg (1982). Page 146

        # Constants
        u = 2 * pi / 5
        shift1 = 1 / 4
        M2 = (cos(u) - cos(2 * u)) / 2
        M3 = sin(u)
        M4 = sin(u) + sin(2 * u)
        M5 = sin(u) - sin(2 * u)

        # Op 1
        a1 = b + e
        a2 = b - e

        # Op 2
        a3 = c + d
        a4 = c - d

        # Op 3
        a5 = a1 + a3
        a6 = a1 - a3

        # Op 4
        a7 = a + a5
        a8 = a - shift1 * a5

        # Op 5
        a9 = a4 - a2

        # Multiplications
        M2out = M2 * a6
        M3out = 1j * M3 * a9
        M4out = 1j * M4 * a4
        M5out = 1j * M5 * a2

        # Op 6
        a10 = a8 + M2out
        a11 = a8 - M2out

        # Op 7 - Type 2
        a13 = M5out + M3out
        a12 = M4out - M3out

        # Op 8
        a15 = a10 + a12
        a14 = a10 - a12

        # Op 9
        a16 = a11 + a13
        a17 = a11 - a13

        return a7, a14, a16, a17, a15
