"""
B-ASIC FFT Operations Module.

Contains selected FFT butterfly operations.
"""

import math

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

        y_0 & = x_0 + x_1\\
        y_1 & = x_0 - x_1

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

    def evaluate(self, a, b, data_type=None) -> Num:
        res = a + b, a - b
        return (
            self._cast_to_data_type(res[0], data_type),
            self._cast_to_data_type(res[1], data_type),
        )


class R2DIFButterfly(AbstractOperation):
    r"""
    Radix-2 decimation-in-frequency butterfly operation for FFTs.

    Gives the result of adding its two inputs, as well as the result of subtracting the
    second input from the first one. This corresponds to a 2-point DFT.
    The second output is multiplied with the provided twiddle factor (TF).

    .. math::

        y_0 & = x_0 + x_1\\
        y_1 & = w(x_0 - x_1)

    Parameters
    ----------
    w : complex
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

    def evaluate(self, a, b, data_type=None) -> Num:
        res = a + b, self.w * (a - b)
        return (
            self._cast_to_data_type(res[0], data_type),
            self._cast_to_data_type(res[1], data_type),
        )

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

        y_0 & = x_0 + w*x_1\\
        y_1 & = x_0 - w*x_1

    Parameters
    ----------
    w : complex
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

    def evaluate(self, a, b, data_type=None) -> Num:
        tmp_b = self.w * b
        res = a + tmp_b, a - tmp_b
        return (
            self._cast_to_data_type(res[0], data_type),
            self._cast_to_data_type(res[1], data_type),
        )

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

        y_0 & = w_0(x_0 + x_1)\\
        y_1 & = w_1(x_0 - x_1)

    Parameters
    ----------
    w0 : complex
        Twiddle factor to multiply the first output with.
    w1 : complex
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

    def evaluate(self, a, b, data_type=None) -> Num:
        res = self.w0 * (a + b), self.w1 * (a - b)
        return (
            self._cast_to_data_type(res[0], data_type),
            self._cast_to_data_type(res[1], data_type),
        )

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

            s0 & = x_0 + x_2\\
            s1 & = x_1 + x_3\\
            s2 & = x_0 - x_2\\
            s3 & = -jx_1 + jx_3\\
            y0 & = s0 + s1\\
            y1 & = s2 + s3\\
            y2 & = s0 - s1\\
            y3 & = s2 - s3

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

    def evaluate(self, a, b, c, d, data_type=None) -> Num:
        s0 = a + c
        s1 = b + d
        s2 = a - c
        s3 = 1j * (d - b)

        y0 = s0 + s1  # y0 = a + b + c + d
        y1 = s2 + s3  # y1 = a -1j*b - c + 1j*d
        y2 = s0 - s1  # y2 = a - b + c - d
        y3 = s2 - s3  # y3 = a + 1j*b - c - 1j*d
        res = y0, y1, y2, y3
        return (
            self._cast_to_data_type(res[0], data_type),
            self._cast_to_data_type(res[1], data_type),
            self._cast_to_data_type(res[2], data_type),
            self._cast_to_data_type(res[3], data_type),
        )


class R3Winograd(AbstractOperation):
    r"""
    Three-point Winograd DFT.

    .. math::

            u & = -\frac{2 \pi}{3} \\
            c_{30} & = \cos(u) - 1 \\
            c_{31} & = j \sin(u) \\
            s_0 & = x_1 + x_2 \\
            s_1 & = x_1 - x_2 \\
            s_2 & = s_0 + x_0 \\
            m_0 & = c_{30} s_0 \\
            m_1 & = c_{31} s_1 \\
            s_3 & = s_2 + m_0 \\
            s_4 & = s_3 + m_1 \\
            s_5 & = s_3 - m_1 \\
            y_0 & = s_2 \\
            y_1 & = s_4 \\
            y_2 & = s_5

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

    def evaluate(self, a, b, c, data_type=None) -> Num:
        u = -2 * math.pi / 3
        c30 = -1.5  # cos(u) - 1
        c31 = 1j * math.sin(u)

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

        res = y0, y1, y2
        return (
            self._cast_to_data_type(res[0], data_type),
            self._cast_to_data_type(res[1], data_type),
            self._cast_to_data_type(res[2], data_type),
        )


class R5Winograd(AbstractOperation):
    r"""
    Five-point Winograd DFT.

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
        return TypeName("r5win")

    def evaluate(self, a, b, c, d, e, data_type=None) -> Num:
        # Fast Fourier Transform and Convolution Algorithms-Springer-Verlag
        # Berlin Heidelberg (1982). Page 146

        # Constants
        u = 2 * math.pi / 5
        shift1 = 1 / 4
        M2 = (math.cos(u) - math.cos(2 * u)) / 2
        M3 = math.sin(u)
        M4 = math.sin(u) + math.sin(2 * u)
        M5 = math.sin(u) - math.sin(2 * u)

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

        res = a7, a14, a16, a17, a15
        return (
            self._cast_to_data_type(res[0], data_type),
            self._cast_to_data_type(res[1], data_type),
            self._cast_to_data_type(res[2], data_type),
            self._cast_to_data_type(res[3], data_type),
            self._cast_to_data_type(res[4], data_type),
        )


class R7Winograd(AbstractOperation):
    r"""
    Seven-point Winograd DFT.


    Parameters
    ----------
    src0, src1, src2, src3, src4, src5, src6 : SignalSourceProvider, optional
        The seven signals to compute the 7-point DFT of.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if inputs have different arrival times or if the inputs should arrive
        after the operator has stared.
        For example, ``{"in0": 0, "in1": 1, "in2": 0, "in3": 0, "in4": 0, "in5": 0, "in6": 0,}`` which
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
        "_src5",
        "_src6",
    )
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _src2: SignalSourceProvider | None
    _src3: SignalSourceProvider | None
    _src4: SignalSourceProvider | None
    _src5: SignalSourceProvider | None
    _src6: SignalSourceProvider | None
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
        src5: SignalSourceProvider | None = None,
        src6: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
        """Construct a R7Winograd operation."""
        super().__init__(
            input_count=7,
            output_count=7,
            name=Name(name),
            input_sources=[src0, src1, src2, src3, src4, src5, src6],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("r7win")

    def evaluate(self, a, b, c, d, e, f, g, data_type=None) -> Num:
        # Constants
        u = -2 * math.pi / 7
        C70 = -((math.cos(u) + math.cos(2 * u) + math.cos(3 * u)) / 3 - 1)
        C71 = (2 * math.cos(u) - math.cos(2 * u) - math.cos(3 * u)) / 3
        C72 = (math.cos(u) - 2 * math.cos(2 * u) + math.cos(3 * u)) / 3
        C73 = (math.cos(u) + math.cos(2 * u) - 2 * math.cos(3 * u)) / 3
        C74 = -((math.sin(u) + math.sin(2 * u) - math.sin(3 * u)) / 3)
        C76 = -((2 * math.sin(u) - math.sin(2 * u) + math.sin(3 * u)) / 3)
        C77 = (math.sin(u) - 2 * math.sin(2 * u) - math.sin(3 * u)) / 3
        C78 = -((math.sin(u) + math.sin(2 * u) + 2 * math.sin(3 * u)) / 3)

        # Op 1
        s1 = g + b
        s2 = g - b

        # Op 2
        s3 = e + d
        s4 = e - d

        # Op 3
        s5 = c + f
        s6 = c - f

        # Op 4
        s7 = s1 + s3
        s10 = s1 - s3

        # Op 5
        # Type 3
        s11 = s3 - s5
        s12 = s1 - s5

        # Op 6
        s15 = s4 + s2
        s13 = s4 - s2

        # Op 7
        # ype 2
        s17 = s2 + s6
        s16 = s4 - s6

        # Op 8
        s8 = s7 + s5

        # Op 9
        s9 = s8 + a

        # Op 10
        s14 = s13 + s6

        # Multiplications
        # m0 = s9
        m1 = C70 * (s8)
        m2 = C71 * (s10)
        m3 = C72 * (s11)
        m4 = C73 * (s12)
        m5 = 1j * C74 * (s14)
        m6 = 1j * C76 * (s15)
        m7 = 1j * C77 * (s16)
        m8 = 1j * C78 * (s17)

        # Op 11
        s18 = s9 - m1

        # Op 12
        s27 = m5 + m6
        s25 = m5 - m6

        # Op 13
        # Type 2
        s29 = m5 + m7
        s26 = s25 - m7

        # Op 14
        s19 = s18 + m2
        s21 = s18 - m2

        # Op 15
        # Type 2
        s20 = s19 + m3
        s23 = s18 - m3

        # Op 16
        # Type 2
        s30 = s29 + m8
        s28 = s27 - m8

        # Op 17
        # Type 2
        s22 = s21 + m4
        s24 = s23 - m4

        # Op 18
        s32 = s20 + s26  # (m0+m1)+m2+m3-m5-m6-m7
        s31 = s20 - s26  # (m0+m1)+m2+m3+m5+m6+m7

        # Op 19
        s34 = s22 + s28  # (m0+m1)-m2-m4-m5+m6+m8
        s33 = s22 - s28  # (m0+m1)-m2-m4+m5-m6-m8

        # Op 20
        s36 = s24 + s30  # (m0+m1)-m3+m4-m5+m7-m8
        s35 = s24 - s30  # (m0+m1)-m3+m4+m5-m7+m8

        res = s9, s31, s33, s36, s35, s34, s32
        return (
            self._cast_to_data_type(res[0], data_type),
            self._cast_to_data_type(res[1], data_type),
            self._cast_to_data_type(res[2], data_type),
            self._cast_to_data_type(res[3], data_type),
            self._cast_to_data_type(res[4], data_type),
            self._cast_to_data_type(res[5], data_type),
            self._cast_to_data_type(res[6], data_type),
        )
