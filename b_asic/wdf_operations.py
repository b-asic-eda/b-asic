"""
B-ASIC Core Operations Module.

Contains wave digital filter adaptors.
"""
from typing import Dict, Iterable, Optional, Tuple

from b_asic.graph_component import Name, TypeName
from b_asic.operation import AbstractOperation
from b_asic.port import SignalSourceProvider
from b_asic.types import Num


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


class SeriesTwoportAdaptor(AbstractOperation):
    r"""
    Wave digital filter series twoport-adaptor operation.

    .. math::
        \begin{eqnarray}
        y_0 & = & x_0 - \text{value}\times\left(x_0 + x_1\right)\\
        y_1 & = & x_1 - (2-\text{value})\times\left(x_0 + x_1\right)\\
            & = & -2x_0 - x_1  + \text{value}\times\left(x_0 + x_1\right)
        \end{eqnarray}

    Port 1 is the dependent port.
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
        """Construct a SeriesTwoportAdaptor operation."""
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
        return TypeName("ser2p")

    def evaluate(self, a, b):
        s = a + b
        val = self.value
        t = val * a
        y0 = a - t
        y1 = -(s + y0)
        return y0, y1

    @property
    def value(self) -> Num:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: Num) -> None:
        """Set the constant value of this operation."""
        if 0 <= value <= 2:
            self.set_param("value", value)
        else:
            raise ValueError('value must be between 0 and 2 (inclusive)')

    def swap_io(self) -> None:
        # Swap inputs and outputs and, hence, which port is dependent
        self._input_ports.reverse()
        for i, p in enumerate(self._input_ports):
            p._index = i
        self._output_ports.reverse()
        for i, p in enumerate(self._output_ports):
            p._index = i
        self.set_param("value", 2 - self.value)


class ParallelTwoportAdaptor(AbstractOperation):
    r"""
    Wave digital filter parallel twoport-adaptor operation.

    .. math::
        \begin{eqnarray}
        y_0 & = & - x_0 + \text{value}\times x_0 + (2 - \text{value}) \times x_1\\
            & = & 2x_1 - x_0 + \text{value}\times \left(x_0 - x_1\right)
        y_1 & = & - x_1 + \text{value}\times x_0 + (2 - \text{value}) \times x_1\\
            & = & x_1 + \text{value}\times\left(x_0 - x_1\right)
        \end{eqnarray}

    Port 1 is the dependent port.
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
        """Construct a ParallelTwoportAdaptor operation."""
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
        return TypeName("par2p")

    def evaluate(self, a, b):
        s = b - a
        val = self.value
        t = val * s
        y1 = b - t
        y0 = y1 + s
        return y0, y1

    @property
    def value(self) -> Num:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: Num) -> None:
        """Set the constant value of this operation."""
        if 0 <= value <= 2:
            self.set_param("value", value)
        else:
            raise ValueError('value must be between 0 and 2 (inclusive)')

    def swap_io(self) -> None:
        # Swap inputs and outputs and, hence, which port is dependent
        self._input_ports.reverse()
        for i, p in enumerate(self._input_ports):
            p._index = i
        self._output_ports.reverse()
        for i, p in enumerate(self._output_ports):
            p._index = i
        self.set_param("value", 2 - self.value)


class SeriesThreeportAdaptor(AbstractOperation):
    r"""
    Wave digital filter series threeport-adaptor operation.

    .. math::
        \begin{eqnarray}
        y_0 & = & x_0 - \text{value}_0\times\left(x_0 + x_1 + x_2\right)\\
        y_1 & = & x_1 - \text{value}_1\times\left(x_0 + x_1 + x_2\right)\\
        y_2 & = & x_2 - \left(2 - \text{value}_0 - \text{value}_1\right)\times\left(x_0
                + x_1 + x_2\right)
        \end{eqnarray}

    Port 2 is the dependent port.

    """
    is_linear = True
    is_swappable = True

    def __init__(
        self,
        value: Tuple[Num, Num] = (0, 0),
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        src2: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a SeriesThreeportAdaptor operation."""
        super().__init__(
            input_count=3,
            output_count=3,
            name=Name(name),
            input_sources=[src0, src1, src2],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.value = value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("ser3p")

    def evaluate(self, a, b, c):
        s = a + b + c
        val0, val1 = self.value
        y0 = a - val0 * s
        y1 = b - val1 * s
        y2 = -(y0 + y1 + s)
        return y0, y1, y2

    @property
    def value(self) -> Tuple[Num, Num]:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: Tuple[Num, Num]) -> None:
        """Set the constant value of this operation."""
        if not all(0 <= v <= 2 for v in value):
            raise ValueError('each value must be between 0 and 2 (inclusive)')
        if 0 <= sum(value) <= 2:
            self.set_param("value", value)
        else:
            raise ValueError('sum of values must be between 0 and 2 (inclusive)')


class ReflectionFreeSeriesThreeportAdaptor(AbstractOperation):
    r"""
    Wave digital filter reflection free series threeport-adaptor operation.

    .. math::
        \begin{eqnarray}
        y_0 & = & x_0 - \text{value}\times\left(x_0 + x_1 + x_2\right)\\
        y_1 & = & -x_0 - x_2\\
        y_2 & = & x_2 - \left(1 - \text{value}\right)\times\left(x_0
                + x_1 + x_2\right) \\
            & = & -x_0 - x_1 + \text{value}\times\left(x_0
                    + x_1 + x_2\right)
        \end{eqnarray}

    Port 1 is the reflection-free port and port 2 is the dependent port.
    """
    is_linear = True
    is_swappable = True

    def __init__(
        self,
        value: Num = 0,
        src0: Optional[SignalSourceProvider] = None,
        src1: Optional[SignalSourceProvider] = None,
        src2: Optional[SignalSourceProvider] = None,
        name: Name = Name(""),
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """Construct a ReflectionFreeSeriesThreeportAdaptor operation."""
        super().__init__(
            input_count=3,
            output_count=3,
            name=Name(name),
            input_sources=[src0, src1, src2],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.value = value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("rfs3p")

    def evaluate(self, a, b, c):
        s = a + c
        y1 = -s
        y0 = a - self.value * (b + s)
        y2 = -(y0 + b)
        return y0, y1, y2

    @property
    def value(self) -> Num:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: Num) -> None:
        """Set the constant value of this operation."""
        if 0 <= value <= 1:
            self.set_param("value", value)
        else:
            raise ValueError('value must be between 0 and 1 (inclusive)')

    def inputs_required_for_output(self, output_index: int) -> Iterable[int]:
        """
        Get the input indices of all inputs in this operation whose values are
        required in order to evaluate the output at the given output index.
        """
        return {0: (0, 1, 2), 1: (0, 2), 2: (0, 1, 2)}
