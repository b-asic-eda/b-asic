"""
B-ASIC Core Operations Module.

Contains some of the most commonly used mathematical operations.
"""

from numbers import Number
from typing import Dict, Optional

from numpy import abs as np_abs
from numpy import conjugate, sqrt

from b_asic.graph_component import Name, TypeName
from b_asic.operation import AbstractOperation
from b_asic.port import SignalSourceProvider


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

    def __init__(self, value: Number = 0, name: Name = Name("")):
        """Construct a Constant operation with the given value."""
        super().__init__(
            input_count=0,
            output_count=1,
            name=Name(name),
            latency_offsets={"out0": 0},
        )
        self.set_param("value", value)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("c")

    def evaluate(self):
        return self.param("value")

    @property
    def value(self) -> Number:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: Number) -> None:
        """Set the constant value of this operation."""
        self.set_param("value", value)


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
    def is_add(self) -> Number:
        """Get if operation is add."""
        return self.param("is_add")

    @is_add.setter
    def is_add(self, is_add: bool) -> None:
        """Set if operation is add."""
        self.set_param("is_add", is_add)


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
    ConstantMultiplication

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


class Division(AbstractOperation):
    r"""
    Binary division operation.

    Gives the result of dividing the first input by the second one.

    .. math:: y = \frac{x_0}{x_1}

    See also
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


class Min(AbstractOperation):
    r"""
    Binary min operation.

    Gives the minimum value of two inputs.

    .. math:: y = \min\{x_0 , x_1\}

    .. note:: Only real-valued numbers are supported.

    See also
    ========
    Max
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
            raise ValueError(
                "core_operations.Min does not support complex numbers."
            )
        return a if a < b else b


class Max(AbstractOperation):
    r"""
    Binary max operation.

    Gives the maximum value of two inputs.

    .. math:: y = \max\{x_0 , x_1\}

    .. note:: Only real-valued numbers are supported.

    See also
    ========
    Min
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
            raise ValueError(
                "core_operations.Max does not support complex numbers."
            )
        return a if a > b else b


class SquareRoot(AbstractOperation):
    r"""
    Square root operation.

    Gives the square root of its input.

    .. math:: y = \sqrt{x}
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
    """

    def __init__(
        self,
        value: Number = 0,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a ConstantMultiplication operation with the given value.
        """
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
    def value(self) -> Number:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: Number) -> None:
        """Set the constant value of this operation."""
        self.set_param("value", value)


class Butterfly(AbstractOperation):
    r"""
    Radix-2 Butterfly operation.

    Gives the result of adding its two inputs, as well as the result of
    subtracting the second input from the first one.

    .. math::
        \begin{eqnarray}
        y_0 & = & x_0 + x_1\\
        y_1 & = & x_0 - x_1
        \end{eqnarray}
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
    """

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


class SymmetricTwoportAdaptor(AbstractOperation):
    r"""
    Symmetric twoport-adaptor operation.

    .. math::
        \begin{eqnarray}
        y_0 & = & x_1 + \text{value}\times\left(x_1 - x_0\right)\\
        y_1 & = & x_0 + \text{value}\times\left(x_1 - x_0\right)
        \end{eqnarray}
    """

    def __init__(
        self,
        value: Number = 0,
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
        self.set_param("value", value)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("sym2p")

    def evaluate(self, a, b):
        tmp = self.value * (b - a)
        return b + tmp, a + tmp

    @property
    def value(self) -> Number:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: Number) -> None:
        """Set the constant value of this operation."""
        self.set_param("value", value)


class Reciprocal(AbstractOperation):
    r"""
    Reciprocal operation.

    Gives the reciprocal of its input.

    .. math:: y = \frac{1}{x}

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
        """Construct an Reciprocal operation."""
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
