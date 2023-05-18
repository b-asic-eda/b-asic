"""
B-ASIC Core Operations Module.

Contains some of the most commonly used mathematical operations.
"""

from typing import Dict, Optional

from numpy import abs as np_abs
from numpy import conjugate, sqrt

from b_asic.graph_component import Name, TypeName
from b_asic.operation import AbstractOperation
from b_asic.port import SignalSourceProvider
from b_asic.types import Num


class Constant(AbstractOperation):
    r"""
    Constant value operation.

    Gives a specified value that remains constant for every iteration.

    .. math:: y = \text{value}

    Parameters
    ==========

    value : Number, default: 0
        The constant value.
    name : Name, optional
        Operation name.
    """

    _execution_time = 0
    is_linear = True
    is_constant = True

    def __init__(self, value: Num = 0, name: Name = ""):
        """Construct a Constant operation with the given value."""
        super().__init__(
            input_count=0,
            output_count=1,
            name=name,
            latency_offsets={"out0": 0},
        )
        self.set_param("value", value)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("c")

    def evaluate(self):
        return self.param("value")

    @property
    def value(self) -> Num:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: Num) -> None:
        """Set the constant value of this operation."""
        self.set_param("value", value)

    @property
    def latency(self) -> int:
        return self.latency_offsets["out0"]

    def __repr__(self) -> str:
        return f"Constant({self.value})"

    def __str__(self) -> str:
        return f"{self.value}"


class Addition(AbstractOperation):
    """
    Binary addition operation.

    Gives the result of adding two inputs.

    .. math:: y = x_0 + x_1

    Parameters
    ==========

    src0, src1 : SignalSourceProvider, optional
        The two signals to add.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if inputs have different arrival times, e.g.,
        ``{"in0": 0, "in1": 1}`` which corresponds to *src1* arriving one
        time unit later than *src0*. If not provided and *latency* is
        provided, set to zero if not explicitly provided. So the previous
        example can be written as ``{"in1": 1}`` only.
    execution_time : int, optional
        Operation execution time (time units before operator can be
        reused).

    See also
    ========
    AddSub
    """

    is_linear = True
    is_swappable = True

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """
        Construct an Addition operation.
        """
        super().__init__(
            input_count=2,
            output_count=1,
            name=Name(name),
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("add")

    def evaluate(self, a, b):
        return a + b


class Subtraction(AbstractOperation):
    """
    Binary subtraction operation.

    Gives the result of subtracting the second input from the first one.

    .. math:: y = x_0 - x_1

    Parameters
    ==========

    src0, src1 : SignalSourceProvider, optional
        The two signals to subtract.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if inputs have different arrival times, e.g.,
        ``{"in0": 0, "in1": 1}`` which corresponds to *src1* arriving one
        time unit later than *src0*. If not provided and *latency* is
        provided, set to zero if not explicitly provided. So the previous
        example can be written as ``{"in1": 1}`` only.
    execution_time : int, optional
        Operation execution time (time units before operator can be
        reused).

    See also
    ========
    AddSub
    """

    is_linear = True

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a Subtraction operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=Name(name),
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("sub")

    def evaluate(self, a, b):
        return a - b


class AddSub(AbstractOperation):
    r"""
    Two-input addition or subtraction operation.

    Gives the result of adding or subtracting two inputs.

    .. math::
        y = \begin{cases}
        x_0 + x_1,& \text{is_add} = \text{True}\\
        x_0 - x_1,& \text{is_add} = \text{False}
        \end{cases}

    This is used to later map additions and subtractions to the same
    operator.

    Parameters
    ==========

    is_add : bool, default: True
        If True, the operation is an addition, if False, a subtraction.
    src0, src1 : SignalSourceProvider, optional
        The two signals to add or subtract.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if inputs have different arrival times, e.g.,
        ``{"in0": 0, "in1": 1}`` which corresponds to *src1* arriving one
        time unit later than *src0*. If not provided and *latency* is
        provided, set to zero if not explicitly provided. So the previous
        example can be written as ``{"in1": 1}`` only.
    execution_time : int, optional
        Operation execution time (time units before operator can be
        reused).

    See also
    ========
    Addition, Subtraction
    """
    is_linear = True

    def __init__(
        self,
        is_add: bool = True,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct an Addition/Subtraction operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=Name(name),
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.set_param("is_add", is_add)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("addsub")

    def evaluate(self, a, b):
        return a + b if self.is_add else a - b

    @property
    def is_add(self) -> bool:
        """Get if operation is an addition."""
        return self.param("is_add")

    @is_add.setter
    def is_add(self, is_add: bool) -> None:
        """Set if operation is an addition."""
        self.set_param("is_add", is_add)

    @property
    def is_swappable(self) -> bool:
        return self.is_add


class Multiplication(AbstractOperation):
    r"""
    Binary multiplication operation.

    Gives the result of multiplying two inputs.

    .. math:: y = x_0 \times x_1

    Parameters
    ==========

    src0, src1 : SignalSourceProvider, optional
        The two signals to multiply.
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

    See Also
    ========
    ConstantMultiplication
    """
    is_swappable = True

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a Multiplication operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=Name(name),
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("mul")

    def evaluate(self, a, b):
        return a * b

    @property
    def is_linear(self) -> bool:
        return any(
            input_.connected_source.operation.is_constant for input_ in self.inputs
        )


class Division(AbstractOperation):
    r"""
    Binary division operation.

    Gives the result of dividing the first input by the second one.

    .. math:: y = \frac{x_0}{x_1}

    Parameters
    ==========

    src0, src1 : SignalSourceProvider, optional
        The two signals to divide.
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

    See Also
    ========
    Reciprocal
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a Division operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=Name(name),
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("div")

    def evaluate(self, a, b):
        return a / b

    @property
    def is_linear(self) -> bool:
        return self.input(1).connected_source.operation.is_constant


class Min(AbstractOperation):
    r"""
    Binary min operation.

    Gives the minimum value of two inputs.

    .. math:: y = \min\{x_0 , x_1\}

    .. note:: Only real-valued numbers are supported.

    Parameters
    ==========

    src0, src1 : SignalSourceProvider, optional
        The two signals to determine the min of.
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

    See Also
    ========
    Max
    """
    is_swappable = True

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a Min operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=Name(name),
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("min")

    def evaluate(self, a, b):
        if isinstance(a, complex) or isinstance(b, complex):
            raise ValueError("core_operations.Min does not support complex numbers.")
        return a if a < b else b


class Max(AbstractOperation):
    r"""
    Binary max operation.

    Gives the maximum value of two inputs.

    .. math:: y = \max\{x_0 , x_1\}

    .. note:: Only real-valued numbers are supported.

    Parameters
    ==========

    src0, src1 : SignalSourceProvider, optional
        The two signals to determine the min of.
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

    See Also
    ========
    Min
    """
    is_swappable = True

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a Max operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=Name(name),
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("max")

    def evaluate(self, a, b):
        if isinstance(a, complex) or isinstance(b, complex):
            raise ValueError("core_operations.Max does not support complex numbers.")
        return a if a > b else b


class SquareRoot(AbstractOperation):
    r"""
    Square root operation.

    Gives the square root of its input.

    .. math:: y = \sqrt{x}

    Parameters
    ----------
    src0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The signal to compute the square root of.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if input arrives later than when the operator starts, e.g.,
        ``{"in0": 0`` which corresponds to *src0* arriving one time unit after the
        operator starts. If not provided and *latency* is provided, set to zero.
    execution_time : int, optional
        Operation execution time (time units before operator can be reused).
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a SquareRoot operation."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=Name(name),
            input_sources=[src0],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("sqrt")

    def evaluate(self, a):
        return sqrt(complex(a))


class ComplexConjugate(AbstractOperation):
    """
    Complex conjugate operation.

    Gives the complex conjugate of its input.

    .. math:: y = x^*

    Parameters
    ----------
    src0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The signal to compute the complex conjugate of.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if input arrives later than when the operator starts, e.g.,
        ``{"in0": 0`` which corresponds to *src0* arriving one time unit after the
        operator starts. If not provided and *latency* is provided, set to zero.
    execution_time : int, optional
        Operation execution time (time units before operator can be reused).
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a ComplexConjugate operation."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=Name(name),
            input_sources=[src0],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("conj")

    def evaluate(self, a):
        return conjugate(a)


class Absolute(AbstractOperation):
    """
    Absolute value operation.

    Gives the absolute value of its input.

    .. math:: y = |x|

    Parameters
    ----------
    src0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The signal to compute the absolute value of.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if input arrives later than when the operator starts, e.g.,
        ``{"in0": 0`` which corresponds to *src0* arriving one time unit after the
        operator starts. If not provided and *latency* is provided, set to zero.
    execution_time : int, optional
        Operation execution time (time units before operator can be reused).
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct an Absolute operation."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=Name(name),
            input_sources=[src0],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("abs")

    def evaluate(self, a):
        return np_abs(a)


class ConstantMultiplication(AbstractOperation):
    r"""
    Constant multiplication operation.

    Gives the result of multiplying its input by a specified value.

    .. math:: y = x_0 \times \text{value}

    Parameters
    ----------
    value : int
        Value to multiply with.
    src0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The signal to multiply.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if input arrives later than when the operator starts, e.g.,
        ``{"in0": 0`` which corresponds to *src0* arriving one time unit after the
        operator starts. If not provided and *latency* is provided, set to zero.
    execution_time : int, optional
        Operation execution time (time units before operator can be reused).

    See Also
    --------
    Multiplication
    """
    is_linear = True

    def __init__(
        self,
        value: Num = 0,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a ConstantMultiplication operation with the given value."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=Name(name),
            input_sources=[src0],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.set_param("value", value)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("cmul")

    def evaluate(self, a):
        return a * self.param("value")

    @property
    def value(self) -> Num:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: Num) -> None:
        """Set the constant value of this operation."""
        self.set_param("value", value)


class Butterfly(AbstractOperation):
    r"""
    Radix-2 Butterfly operation for FFTs.

    Gives the result of adding its two inputs, as well as the result of subtracting the
    second input from the first one. This corresponds to a 2-point DFT.

    .. math::
        \begin{eqnarray}
        y_0 & = & x_0 + x_1\\
        y_1 & = & x_0 - x_1
        \end{eqnarray}

    Parameters
    ==========

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
    is_linear = True

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a Butterfly operation."""
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
        return TypeName("bfly")

    def evaluate(self, a, b):
        return a + b, a - b


class MAD(AbstractOperation):
    r"""
    Multiply-add operation.

    Gives the result of multiplying the first input by the second input and
    then adding the third input.

    .. math:: y = x_0 \times x_1 + x_2

    Parameters
    ==========

    src0, src1, src2 : SignalSourceProvider, optional
        The three signals to determine the multiply-add operation of.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if inputs have different arrival times or if the inputs should arrive
        after the operator has stared. For example, ``{"in0": 0, "in1": 0, "in2": 2}``
        which corresponds to *src2*, i.e., the term to be added, arriving two time
        units later than *src0* and *src1*. If not provided and *latency* is provided,
        set to zero. Hence, the previous example can be written as ``{"in1": 1}``
        only.
    execution_time : int, optional
        Operation execution time (time units before operator can be reused).

    See Also
    --------
    Multiplication
    Addition
    """
    is_swappable = True

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        src2: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a MAD operation."""
        super().__init__(
            input_count=3,
            output_count=1,
            name=Name(name),
            input_sources=[src0, src1, src2],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("mad")

    def evaluate(self, a, b, c):
        return a * b + c

    @property
    def is_linear(self) -> bool:
        return (
            self.input(0).connected_source.operation.is_constant
            or self.input(1).connected_source.operation.is_constant
        )

    def swap_io(self) -> None:
        self._input_ports = [
            self._input_ports[1],
            self._input_ports[0],
            self._input_ports[2],
        ]
        for i, p in enumerate(self._input_ports):
            p._index = i


class SymmetricTwoportAdaptor(AbstractOperation):
    r"""
    Wave digital filter symmetric twoport-adaptor operation.

    .. math::
        \begin{eqnarray}
        y_0 & = & x_1 + \text{value}\times\left(x_1 - x_0\right)\\
        y_1 & = & x_0 + \text{value}\times\left(x_1 - x_0\right)
        \end{eqnarray}
    """
    is_linear = True
    is_swappable = True

    def __init__(
        self,
        value: Num = 0,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a SymmetricTwoportAdaptor operation."""
        super().__init__(
            input_count=2,
            output_count=2,
            name=Name(name),
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.value = value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("sym2p")

    def evaluate(self, a, b):
        tmp = self.value * (b - a)
        return b + tmp, a + tmp

    @property
    def value(self) -> Num:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: Num) -> None:
        """Set the constant value of this operation."""
        if -1 <= value <= 1:
            self.set_param("value", value)
        else:
            raise ValueError('value must be between -1 and 1 (inclusive)')

    def swap_io(self) -> None:
        # Swap inputs and outputs and change sign of coefficient
        self._input_ports.reverse()
        for i, p in enumerate(self._input_ports):
            p._index = i
        self._output_ports.reverse()
        for i, p in enumerate(self._output_ports):
            p._index = i
        self.set_param("value", -self.value)


class Reciprocal(AbstractOperation):
    r"""
    Reciprocal operation.

    Gives the reciprocal of its input.

    .. math:: y = \frac{1}{x}

    Parameters
    ----------
    src0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The signal to compute the reciprocal of.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if input arrives later than when the operator starts, e.g.,
        ``{"in0": 0`` which corresponds to *src0* arriving one time unit after the
        operator starts. If not provided and *latency* is provided, set to zero.
    execution_time : int, optional
        Operation execution time (time units before operator can be reused).

    See also
    ========
    Division
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a Reciprocal operation."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=Name(name),
            input_sources=[src0],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("rec")

    def evaluate(self, a):
        return 1 / a


class RightShift(AbstractOperation):
    r"""
    Arithmetic right-shift operation.

    Shifts the input to the right assuming a fixed-point representation, so
    a multiplication by a power of two.

    .. math:: y = x \gg \text{value} = 2^{-\text{value}}x \text{ where value} \geq 0

    Parameters
    ----------
    value : int
        Number of bits to shift right.
    src0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The signal to shift right.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if input arrives later than when the operator starts, e.g.,
        ``{"in0": 0`` which corresponds to *src0* arriving one time unit after the
        operator starts. If not provided and *latency* is provided, set to zero.
    execution_time : int, optional
        Operation execution time (time units before operator can be reused).

    See Also
    --------
    LeftShift
    Shift
    """

    is_linear = True

    def __init__(
        self,
        value: int = 0,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a RightShift operation with the given value."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=Name(name),
            input_sources=[src0],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.value = value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("rshift")

    def evaluate(self, a):
        return a * 2 ** (-self.param("value"))

    @property
    def value(self) -> int:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: int) -> None:
        """Set the constant value of this operation."""
        if not isinstance(value, int):
            raise TypeError("value must be an int")
        if value < 0:
            raise ValueError("value must be non-negative")
        self.set_param("value", value)


class LeftShift(AbstractOperation):
    r"""
    Arithmetic left-shift operation.

    Shifts the input to the left assuming a fixed-point representation, so
    a multiplication by a power of two.

    .. math:: y = x \ll \text{value} = 2^{\text{value}}x \text{ where value} \geq 0

    Parameters
    ----------
    value : int
        Number of bits to shift left.
    src0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The signal to shift left.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if input arrives later than when the operator starts, e.g.,
        ``{"in0": 0`` which corresponds to *src0* arriving one time unit after the
        operator starts. If not provided and *latency* is provided, set to zero.
    execution_time : int, optional
        Operation execution time (time units before operator can be reused).

    See Also
    --------
    RightShift
    Shift
    """

    is_linear = True

    def __init__(
        self,
        value: int = 0,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a RightShift operation with the given value."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=Name(name),
            input_sources=[src0],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.value = value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("lshift")

    def evaluate(self, a):
        return a * 2 ** (self.param("value"))

    @property
    def value(self) -> int:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: int) -> None:
        """Set the constant value of this operation."""
        if not isinstance(value, int):
            raise TypeError("value must be an int")
        if value < 0:
            raise ValueError("value must be non-negative")
        self.set_param("value", value)


class Shift(AbstractOperation):
    r"""
    Arithmetic shift operation.

    Shifts the input to the left or right assuming a fixed-point representation, so
    a multiplication by a power of two. By definition a positive value is a shift to
    the left.

    .. math:: y = x \ll \text{value} = 2^{\text{value}}x

    Parameters
    ----------
    value : int
        Number of bits to shift. Positive *value* shifts to the left.
    src0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The signal to shift.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if input arrives later than when the operator starts, e.g.,
        ``{"in0": 0`` which corresponds to *src0* arriving one time unit after the
        operator starts. If not provided and *latency* is provided, set to zero.
    execution_time : int, optional
        Operation execution time (time units before operator can be reused).

    See Also
    --------
    LeftShift
    RightShift
    """

    is_linear = True

    def __init__(
        self,
        value: int = 0,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a Shift operation with the given value."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=Name(name),
            input_sources=[src0],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.value = value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("shift")

    def evaluate(self, a):
        return a * 2 ** (self.param("value"))

    @property
    def value(self) -> int:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: int) -> None:
        """Set the constant value of this operation."""
        if not isinstance(value, int):
            raise TypeError("value must be an int")
        self.set_param("value", value)
