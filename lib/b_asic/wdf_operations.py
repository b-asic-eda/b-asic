"""
B-ASIC WDF Operations Module.

Contains wave digital filter adaptors.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING

from b_asic.core_operations import (
    Addition,
    Constant,
    ConstantMultiplication,
    Negation,
    Subtraction,
    _zero_inputs,
)
from b_asic.graph_component import Name, TypeName
from b_asic.operation import AbstractOperation
from b_asic.port import SignalSourceProvider
from b_asic.types import Num

if TYPE_CHECKING:
    from b_asic.sfg import SFG


class _Adaptor(AbstractOperation):
    """Shared propagation hooks for stateless WDF adaptors."""

    __slots__ = ()

    def _constant_propagation(self) -> "SFG | None":
        folded = super()._constant_propagation()
        if folded is not None:
            return folded
        zeros = _zero_inputs(self)
        return self._arithmetic_sfg(zeros, set()) if zeros else None

    def _sink_propagation(self) -> "SFG | None":
        from b_asic.utility_operations import Sink  # noqa: PLC0415

        unused = {
            index
            for index, output in enumerate(self.outputs)
            if all(
                signal.destination is not None
                and isinstance(signal.destination.operation, Sink)
                for signal in output.signals
            )
        }
        if len(unused) == self.output_count:
            return super()._sink_propagation()
        return self._arithmetic_sfg(_zero_inputs(self), unused) if unused else None

    def _arithmetic_sfg(self, zeros: set[int], unused: set[int]) -> "SFG":
        from b_asic.sfg import SFG  # noqa: PLC0415
        from b_asic.special_operations import Input, Output  # noqa: PLC0415
        from b_asic.utility_operations import DontCare  # noqa: PLC0415

        inputs = [Input() for _ in self.inputs]
        sources = [
            Constant(0) if i in zeros else source for i, source in enumerate(inputs)
        ]
        results = self._arithmetic_outputs(sources, zeros, unused)
        replacement = SFG(
            inputs,
            [
                Output(DontCare() if index in unused else result)
                for index, result in enumerate(results)
            ],
        )
        # Simplify the generated arithmetic even for a target restricted to
        # adaptor operations, and discard computations for unused outputs.
        return replacement.constant_propagation()

    def _arithmetic_outputs(
        self,
        inputs: list[SignalSourceProvider],
        zeros: set[int],
        unused: set[int],
    ) -> list[SignalSourceProvider]:
        raise NotImplementedError


def _scale(value: Num, source: SignalSourceProvider) -> SignalSourceProvider:
    """Avoid adding a multiplier for trivial coefficients."""
    if value == 0:
        return Constant(0)
    if value == 1:
        return source
    if value == -1:
        return Negation(source)
    return ConstantMultiplication(value, source)


class SymmetricTwoportAdaptor(_Adaptor):
    r"""
    Wave digital filter symmetric twoport-adaptor operation.

    .. math::

        y_0 & = x_1 + \text{value}\times\left(x_1 - x_0\right)\\
        y_1 & = x_0 + \text{value}\times\left(x_1 - x_0\right)
    """

    __slots__ = (
        "_execution_time",
        "_in0",
        "_in1",
        "_latency",
        "_latency_offsets",
        "_name",
    )
    _in0: SignalSourceProvider | None
    _in1: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True
    is_swappable = True

    def __init__(
        self,
        value: Num = 0,
        in0: SignalSourceProvider | None = None,
        in1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
        """Construct a SymmetricTwoportAdaptor operation."""
        super().__init__(
            input_count=2,
            output_count=2,
            name=Name(name),
            input_sources=[in0, in1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.value = value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("sym2p")

    def evaluate(self, a, b, data_type=None) -> Num:
        tmp = self.value * (b - a)
        res = b + tmp, a + tmp
        return (
            self._cast_to_data_type(res[0], data_type),
            self._cast_to_data_type(res[1], data_type),
        )

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
            raise ValueError("value must be between -1 and 1 (inclusive)")

    def swap_io(self, force: bool = False) -> None:
        # Swap inputs and outputs and change sign of coefficient
        self._input_ports.reverse()
        for i, ip in enumerate(self._input_ports):
            ip._index = i
        self._output_ports.reverse()
        for i, op in enumerate(self._output_ports):
            op._index = i
        self.set_param("value", -self.value)

    def _constant_propagation(self) -> "SFG | None":
        folded = super()._constant_propagation()
        if folded is not None:
            return folded
        if self.value == 0:
            from b_asic.sfg import SFG  # noqa: PLC0415
            from b_asic.special_operations import Input, Output  # noqa: PLC0415

            inputs = [Input(), Input()]
            return SFG(inputs, [Output(inputs[1]), Output(inputs[0])])
        return None

    def _arithmetic_outputs(self, inputs, zeros, unused):
        a, b = inputs
        if 0 in zeros:
            tmp = _scale(self.value, b)
        elif 1 in zeros:
            tmp = _scale(-self.value, a)
        else:
            tmp = _scale(self.value, Subtraction(b, a))
        return [Addition(b, tmp), Addition(a, tmp)]


class SeriesTwoportAdaptor(_Adaptor):
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
        in0: SignalSourceProvider | None = None,
        in1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ):
        """Construct a SeriesTwoportAdaptor operation."""
        super().__init__(
            input_count=2,
            output_count=2,
            name=Name(name),
            input_sources=[in0, in1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.value = value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("ser2p")

    def evaluate(self, a, b, data_type=None):
        s = a + b
        val = self.value
        t = val * s
        y0 = a - t
        y1 = -(s + y0)
        return (
            self._cast_to_data_type(y0, data_type),
            self._cast_to_data_type(y1, data_type),
        )

    def _arithmetic_outputs(self, inputs, zeros, unused):
        a, b = inputs
        total = Addition(a, b)
        if 0 in zeros:
            y0 = _scale(-self.value, b)
        elif 1 in zeros:
            y0 = _scale(1 - self.value, a)
        else:
            y0 = Subtraction(a, _scale(self.value, total))
        if 0 not in unused:
            y1 = Negation(Addition(total, y0))
        elif 0 in zeros:
            y1 = _scale(self.value - 1, b)
        elif 1 in zeros:
            y1 = _scale(self.value - 2, a)
        else:
            y1 = Subtraction(b, _scale(2 - self.value, total))
        return [y0, y1]

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
            raise ValueError("value must be between 0 and 2 (inclusive)")

    def swap_io(self, force: bool = False) -> None:
        # Swap inputs and outputs and, hence, which port is dependent
        self._input_ports.reverse()
        for i, ip in enumerate(self._input_ports):
            ip._index = i
        self._output_ports.reverse()
        for i, op in enumerate(self._output_ports):
            op._index = i
        self.set_param("value", 2 - self.value)


class ParallelTwoportAdaptor(_Adaptor):
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
        in0: SignalSourceProvider | None = None,
        in1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ):
        """Construct a ParallelTwoportAdaptor operation."""
        super().__init__(
            input_count=2,
            output_count=2,
            name=Name(name),
            input_sources=[in0, in1],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.value = value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("par2p")

    def evaluate(self, a, b, data_type=None):
        s = b - a
        val = self.value
        t = val * s
        y1 = b - t
        y0 = y1 + s
        return (
            self._cast_to_data_type(y0, data_type),
            self._cast_to_data_type(y1, data_type),
        )

    def _arithmetic_outputs(self, inputs, zeros, unused):
        a, b = inputs
        if 0 in zeros:
            y1 = _scale(1 - self.value, b)
            y0 = Addition(y1, b)
        elif 1 in zeros:
            y1 = _scale(self.value, a)
            y0 = Subtraction(y1, a)
        else:
            difference = Subtraction(b, a)
            y1 = Subtraction(b, _scale(self.value, difference))
            y0 = Addition(y1, difference)
        return [y0, y1]

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
            raise ValueError("value must be between 0 and 2 (inclusive)")

    def swap_io(self, force: bool = False) -> None:
        # Swap inputs and outputs and, hence, which port is dependent
        self._input_ports.reverse()
        for i, ip in enumerate(self._input_ports):
            ip._index = i
        self._output_ports.reverse()
        for i, op in enumerate(self._output_ports):
            op._index = i
        self.set_param("value", 2 - self.value)


class SeriesThreeportAdaptor(_Adaptor):
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
        value: tuple[Num, Num] = (0, 0),
        in0: SignalSourceProvider | None = None,
        in1: SignalSourceProvider | None = None,
        in2: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ):
        """Construct a SeriesThreeportAdaptor operation."""
        super().__init__(
            input_count=3,
            output_count=3,
            name=Name(name),
            input_sources=[in0, in1, in2],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.value = value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("ser3p")

    def evaluate(self, a, b, c, data_type=None):
        s = a + b + c
        val0, val1 = self.value
        y0 = a - val0 * s
        y1 = b - val1 * s
        y2 = -(y0 + y1 + s)
        return (
            self._cast_to_data_type(y0, data_type),
            self._cast_to_data_type(y1, data_type),
            self._cast_to_data_type(y2, data_type),
        )

    def _arithmetic_outputs(self, inputs, zeros, unused):
        a, b, c = inputs
        total = Addition(Addition(a, b), c)
        val0, val1 = self.value
        y0 = Subtraction(a, _scale(val0, total))
        y1 = Subtraction(b, _scale(val1, total))
        y2 = (
            Subtraction(_scale(val0 + val1 - 1, total), Addition(a, b))
            if {0, 1} <= unused
            else Negation(Addition(Addition(y0, y1), total))
        )
        return [y0, y1, y2]

    @property
    def value(self) -> tuple[Num, Num]:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: tuple[Num, Num]) -> None:
        """Set the constant value of this operation."""
        if not all(0 <= v <= 2 for v in value):
            raise ValueError("each value must be between 0 and 2 (inclusive)")
        if 0 <= sum(value) <= 2:
            self.set_param("value", value)
        else:
            raise ValueError("sum of values must be between 0 and 2 (inclusive)")


class ReflectionFreeSeriesThreeportAdaptor(_Adaptor):
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
        in0: SignalSourceProvider | None = None,
        in1: SignalSourceProvider | None = None,
        in2: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ):
        """Construct a ReflectionFreeSeriesThreeportAdaptor operation."""
        super().__init__(
            input_count=3,
            output_count=3,
            name=Name(name),
            input_sources=[in0, in1, in2],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.value = value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("rfs3p")

    def evaluate(self, a, b, c, data_type=None):
        s = a + c
        y1 = -s
        y0 = a - self.value * (b + s)
        y2 = -(y0 + b)
        return (
            self._cast_to_data_type(y0, data_type),
            self._cast_to_data_type(y1, data_type),
            self._cast_to_data_type(y2, data_type),
        )

    def _arithmetic_outputs(self, inputs, zeros, unused):
        a, b, c = inputs
        total = Addition(a, c)
        y1 = Negation(total)
        product = _scale(self.value, Addition(b, total))
        y0 = Subtraction(a, product)
        y2 = (
            Subtraction(product, Addition(a, b))
            if 0 in unused
            else Negation(Addition(y0, b))
        )
        return [y0, y1, y2]

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
            raise ValueError("value must be between 0 and 1 (inclusive)")

    def inputs_required_for_output(self, output_index: int) -> Iterable[int]:
        """
        Get the input indices of all inputs in this operation whose values are
        required in order to evaluate the output at the given output index.
        """
        return {0: (0, 1, 2), 1: (0, 2), 2: (0, 1, 2)}
