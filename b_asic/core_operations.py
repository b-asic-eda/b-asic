"""@package docstring
B-ASIC Core Operations Module.
TODO: More info.
"""

from numbers import Number
from typing import Any
from numpy import conjugate, sqrt, abs as np_abs
from b_asic.port import InputPort, OutputPort
from b_asic.graph_id import GraphIDType
from b_asic.operation import AbstractOperation
from b_asic.graph_component import Name, TypeName


class Input(AbstractOperation):
    """Input operation.
    TODO: More info.
    """

    # TODO: Implement all functions.

    @property
    def type_name(self) -> TypeName:
        return "in"


class Constant(AbstractOperation):
    """Constant value operation.
    TODO: More info.
    """

    def __init__(self, value: Number = 0, name: Name = ""):
        super().__init__(name)

        self._output_ports = [OutputPort(0, self)]
        self._parameters["value"] = value

    def evaluate(self):
        return self.param("value")

    @property
    def type_name(self) -> TypeName:
        return "c"


class Addition(AbstractOperation):
    """Binary addition operation.
    TODO: More info.
    """

    def __init__(self, source1: OutputPort = None, source2: OutputPort = None, name: Name = ""):
        super().__init__(name)

        self._input_ports = [InputPort(0, self), InputPort(1, self)]
        self._output_ports = [OutputPort(0, self)]

        if source1 is not None:
            self._input_ports[0].connect(source1)
        if source2 is not None:
            self._input_ports[1].connect(source2)

    def evaluate(self, a, b):
        return a + b

    @property
    def type_name(self) -> TypeName:
        return "add"


class Subtraction(AbstractOperation):
    """Binary subtraction operation.
    TODO: More info.
    """

    def __init__(self, source1: OutputPort = None, source2: OutputPort = None, name: Name = ""):
        super().__init__(name)
        self._input_ports = [InputPort(0, self), InputPort(1, self)]
        self._output_ports = [OutputPort(0, self)]

        if source1 is not None:
            self._input_ports[0].connect(source1)
        if source2 is not None:
            self._input_ports[1].connect(source2)

    def evaluate(self, a, b):
        return a - b

    @property
    def type_name(self) -> TypeName:
        return "sub"


class Multiplication(AbstractOperation):
    """Binary multiplication operation.
    TODO: More info.
    """

    def __init__(self, source1: OutputPort = None, source2: OutputPort = None, name: Name = ""):
        super().__init__(name)
        self._input_ports = [InputPort(0, self), InputPort(1, self)]
        self._output_ports = [OutputPort(0, self)]

        if source1 is not None:
            self._input_ports[0].connect(source1)
        if source2 is not None:
            self._input_ports[1].connect(source2)

    def evaluate(self, a, b):
        return a * b

    @property
    def type_name(self) -> TypeName:
        return "mul"


class Division(AbstractOperation):
    """Binary division operation.
    TODO: More info.
    """

    def __init__(self, source1: OutputPort = None, source2: OutputPort = None, name: Name = ""):
        super().__init__(name)
        self._input_ports = [InputPort(0, self), InputPort(1, self)]
        self._output_ports = [OutputPort(0, self)]

        if source1 is not None:
            self._input_ports[0].connect(source1)
        if source2 is not None:
            self._input_ports[1].connect(source2)

    def evaluate(self, a, b):
        return a / b

    @property
    def type_name(self) -> TypeName:
        return "div"


class SquareRoot(AbstractOperation):
    """Unary square root operation.
    TODO: More info.
    """

    def __init__(self, source1: OutputPort = None, name: Name = ""):
        super().__init__(name)
        self._input_ports = [InputPort(0, self)]
        self._output_ports = [OutputPort(0, self)]

        if source1 is not None:
            self._input_ports[0].connect(source1)

    def evaluate(self, a):
        return sqrt((complex)(a))

    @property
    def type_name(self) -> TypeName:
        return "sqrt"


class ComplexConjugate(AbstractOperation):
    """Unary complex conjugate operation.
    TODO: More info.
    """

    def __init__(self, source1: OutputPort = None, name: Name = ""):
        super().__init__(name)
        self._input_ports = [InputPort(0, self)]
        self._output_ports = [OutputPort(0, self)]

        if source1 is not None:
            self._input_ports[0].connect(source1)

    def evaluate(self, a):
        return conjugate(a)

    @property
    def type_name(self) -> TypeName:
        return "conj"


class Max(AbstractOperation):
    """Binary max operation.
    TODO: More info.
    """

    def __init__(self, source1: OutputPort = None, source2: OutputPort = None, name: Name = ""):
        super().__init__(name)
        self._input_ports = [InputPort(0, self), InputPort(1, self)]
        self._output_ports = [OutputPort(0, self)]

        if source1 is not None:
            self._input_ports[0].connect(source1)
        if source2 is not None:
            self._input_ports[1].connect(source2)

    def evaluate(self, a, b):
        assert not isinstance(a, complex) and not isinstance(b, complex), \
            ("core_operations.Max does not support complex numbers.")
        return a if a > b else b

    @property
    def type_name(self) -> TypeName:
        return "max"


class Min(AbstractOperation):
    """Binary min operation.
    TODO: More info.
    """

    def __init__(self, source1: OutputPort = None, source2: OutputPort = None, name: Name = ""):
        super().__init__(name)
        self._input_ports = [InputPort(0, self), InputPort(1, self)]
        self._output_ports = [OutputPort(0, self)]

        if source1 is not None:
            self._input_ports[0].connect(source1)
        if source2 is not None:
            self._input_ports[1].connect(source2)

    def evaluate(self, a, b):
        assert not isinstance(a, complex) and not isinstance(b, complex), \
            ("core_operations.Min does not support complex numbers.")
        return a if a < b else b

    @property
    def type_name(self) -> TypeName:
        return "min"


class Absolute(AbstractOperation):
    """Unary absolute value operation.
    TODO: More info.
    """

    def __init__(self, source1: OutputPort = None, name: Name = ""):
        super().__init__(name)
        self._input_ports = [InputPort(0, self)]
        self._output_ports = [OutputPort(0, self)]

        if source1 is not None:
            self._input_ports[0].connect(source1)

    def evaluate(self, a):
        return np_abs(a)

    @property
    def type_name(self) -> TypeName:
        return "abs"


class ConstantMultiplication(AbstractOperation):
    """Unary constant multiplication operation.
    TODO: More info.
    """

    def __init__(self, coefficient: Number, source1: OutputPort = None, name: Name = ""):
        super().__init__(name)
        self._input_ports = [InputPort(0, self)]
        self._output_ports = [OutputPort(0, self)]
        self._parameters["coefficient"] = coefficient

        if source1 is not None:
            self._input_ports[0].connect(source1)

    def evaluate(self, a):
        return a * self.param("coefficient")

    @property
    def type_name(self) -> TypeName:
        return "cmul"


class ConstantAddition(AbstractOperation):
    """Unary constant addition operation.
    TODO: More info.
    """

    def __init__(self, coefficient: Number, source1: OutputPort = None, name: Name = ""):
        super().__init__(name)
        self._input_ports = [InputPort(0, self)]
        self._output_ports = [OutputPort(0, self)]
        self._parameters["coefficient"] = coefficient

        if source1 is not None:
            self._input_ports[0].connect(source1)

    def evaluate(self, a):
        return a + self.param("coefficient")

    @property
    def type_name(self) -> TypeName:
        return "cadd"


class ConstantSubtraction(AbstractOperation):
    """Unary constant subtraction operation.
    TODO: More info.
    """

    def __init__(self, coefficient: Number, source1: OutputPort = None, name: Name = ""):
        super().__init__(name)
        self._input_ports = [InputPort(0, self)]
        self._output_ports = [OutputPort(0, self)]
        self._parameters["coefficient"] = coefficient

        if source1 is not None:
            self._input_ports[0].connect(source1)

    def evaluate(self, a):
        return a - self.param("coefficient")

    @property
    def type_name(self) -> TypeName:
        return "csub"


class ConstantDivision(AbstractOperation):
    """Unary constant division operation.
    TODO: More info.
    """

    def __init__(self, coefficient: Number, source1: OutputPort = None, name: Name = ""):
        super().__init__(name)
        self._input_ports = [InputPort(0, self)]
        self._output_ports = [OutputPort(0, self)]
        self._parameters["coefficient"] = coefficient

        if source1 is not None:
            self._input_ports[0].connect(source1)

    def evaluate(self, a):
        return a / self.param("coefficient")

    @property
    def type_name(self) -> TypeName:
        return "cdiv"
