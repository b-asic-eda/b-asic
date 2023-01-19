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
    """
    Constant value operation.

    Gives a specified value that remains constant for every iteration.

    output(0): self.param("value")
    """

    _execution_time = 0

    def __init__(self, value: Number = 0, name: Name = ""):
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
        return "c"

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

    output(0): input(0) + input(1)
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct an Addition operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=name,
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return "add"

    def evaluate(self, a, b):
        return a + b


class Subtraction(AbstractOperation):
    """
    Binary subtraction operation.

    Gives the result of subtracting the second input from the first one.

    output(0): input(0) - input(1)
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct a Subtraction operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=name,
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return "sub"

    def evaluate(self, a, b):
        return a - b


class AddSub(AbstractOperation):
    """
    Two-input addition or subtraction operation.

    Gives the result of adding or subtracting two inputs.

    output(0): input(0) + input(1) if is_add = True
    output(0): input(0) - input(1) if is_add = False
    """

    def __init__(
        self,
        is_add: bool = True,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct an Addition operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=name,
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
        )
        self.set_param("is_add", is_add)

    @classmethod
    def type_name(cls) -> TypeName:
        return "addsub"

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
    """
    Binary multiplication operation.

    Gives the result of multiplying two inputs.

    output(0): input(0) * input(1)
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct a Multiplication operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=name,
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return "mul"

    def evaluate(self, a, b):
        return a * b


class Division(AbstractOperation):
    """
    Binary division operation.

    Gives the result of dividing the first input by the second one.

    output(0): input(0) / input(1)
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct a Division operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=name,
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return "div"

    def evaluate(self, a, b):
        return a / b


class Min(AbstractOperation):
    """
    Binary min operation.

    Gives the minimum value of two inputs.
    NOTE: Non-real numbers are not supported.

    output(0): min(input(0), input(1))
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct a Min operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=name,
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return "min"

    def evaluate(self, a, b):
        if isinstance(a, complex) or isinstance(b, complex):
            raise ValueError(
                "core_operations.Min does not support complex numbers.")
        return a if a < b else b


class Max(AbstractOperation):
    """
    Binary max operation.

    Gives the maximum value of two inputs.
    NOTE: Non-real numbers are not supported.

    output(0): max(input(0), input(1))
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct a Max operation."""
        super().__init__(
            input_count=2,
            output_count=1,
            name=name,
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return "max"

    def evaluate(self, a, b):
        if isinstance(a, complex) or isinstance(b, complex):
            raise ValueError(
                "core_operations.Max does not support complex numbers.")
        return a if a > b else b


class SquareRoot(AbstractOperation):
    """
    Square root operation.

    Gives the square root of its input.

    output(0): sqrt(input(0))
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct a SquareRoot operation."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=name,
            input_sources=[src0],
            latency=latency,
            latency_offsets=latency_offsets,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return "sqrt"

    def evaluate(self, a):
        return sqrt(complex(a))


class ComplexConjugate(AbstractOperation):
    """
    Complex conjugate operation.

    Gives the complex conjugate of its input.

    output(0): conj(input(0))
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct a ComplexConjugate operation."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=name,
            input_sources=[src0],
            latency=latency,
            latency_offsets=latency_offsets,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return "conj"

    def evaluate(self, a):
        return conjugate(a)


class Absolute(AbstractOperation):
    """
    Absolute value operation.

    Gives the absolute value of its input.

    output(0): abs(input(0))
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct an Absolute operation."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=name,
            input_sources=[src0],
            latency=latency,
            latency_offsets=latency_offsets,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return "abs"

    def evaluate(self, a):
        return np_abs(a)


class ConstantMultiplication(AbstractOperation):
    """
    Constant multiplication operation.

    Gives the result of multiplying its input by a specified value.

    output(0): self.param("value") * input(0)
    """

    def __init__(
        self,
        value: Number = 0,
        src0: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct a ConstantMultiplication operation with the given value.
        """
        super().__init__(
            input_count=1,
            output_count=1,
            name=name,
            input_sources=[src0],
            latency=latency,
            latency_offsets=latency_offsets,
        )
        self.set_param("value", value)

    @classmethod
    def type_name(cls) -> TypeName:
        return "cmul"

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
    """
    Butterfly operation.

    Gives the result of adding its two inputs, as well as the result of
    subtracting the second input from the first one.

    output(0): input(0) + input(1)
    output(1): input(0) - input(1)
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct a Butterfly operation."""
        super().__init__(
            input_count=2,
            output_count=2,
            name=name,
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return "bfly"

    def evaluate(self, a, b):
        return a + b, a - b


class MAD(AbstractOperation):
    """
    Multiply-add operation.

    Gives the result of multiplying the first input by the second input and
    then adding the third input.

    output(0): (input(0) * input(1)) + input(2)
    """

    def __init__(
        self,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        src2: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct a MAD operation."""
        super().__init__(
            input_count=3,
            output_count=1,
            name=name,
            input_sources=[src0, src1, src2],
            latency=latency,
            latency_offsets=latency_offsets,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        return "mad"

    def evaluate(self, a, b, c):
        return a * b + c


class SymmetricTwoportAdaptor(AbstractOperation):
    """
    Symmetric twoport-adaptor operation.

    output(0): input(1) + value*(input(1) - input(0)
    output(1): input(0) + value*(input(1) - input(0)
    """

    def __init__(
        self,
        value: Number = 0,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        name: Name = "",
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
    ):
        """Construct a Butterfly operation."""
        super().__init__(
            input_count=2,
            output_count=2,
            name=name,
            input_sources=[src0, src1],
            latency=latency,
            latency_offsets=latency_offsets,
        )
        self.set_param("value", value)

    @classmethod
    def type_name(cls) -> TypeName:
        return "sym2p"

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
