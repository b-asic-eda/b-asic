"""Comparison and conditional replacement operations for signal flow graphs."""

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

from b_asic.core_operations import (
    Absolute,
    Addition,
    Constant,
    Min,
    Multiplication,
    Subtraction,
    _RealValuedOperation,
)
from b_asic.operation import _ComplexPair
from b_asic.port import SignalSourceProvider
from b_asic.types import Name, Num, TypeName

if TYPE_CHECKING:
    from b_asic.utility_operations import Sink

__all__ = ["ReplaceZero"]


class ReplaceZero(_RealValuedOperation):
    r"""
    Replace an exactly zero input with a constant.

    .. math::

        y = \begin{cases} \text{value}, & x_0 = 0, \\ x_0, & x_0 \ne 0. \end{cases}

    Both signed zeros compare equal to zero. No tolerance is used. Complex
    inputs are zero only when both their real and imaginary parts are zero.
    Complex-to-real conversion requires a finite replacement unless
    ``real_valued=True``.

    Parameters
    ----------
    value : Number, default: 1
        Replacement constant, following the constant-first convention of
        :class:`~b_asic.core_operations.ConstantMultiplication`.
    in0 : SignalSourceProvider, optional
        Input signal.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency.
    latency_offsets : dict[str, int], optional
        Input and output latency offsets.
    execution_time : int, optional
        Time before the operation can be reused.
    real_valued : bool or None, default: None
        Use only the real input part. The replacement must then be real.
    """

    def __init__(
        self,
        value: Num = 1,
        in0: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
        real_valued: bool | None = None,
    ) -> None:
        """Construct a ReplaceZero operation."""
        super().__init__(
            input_count=1,
            output_count=1,
            name=Name(name),
            input_sources=[in0],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.real_valued = real_valued
        self.value = value

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("replacezero")

    @property
    def value(self) -> Num:
        """Get the replacement constant."""
        return self.param("value")

    @value.setter
    def value(self, value: Num) -> None:
        """Set the replacement constant."""
        if self.real_valued and value.imag != 0:
            raise ValueError("real_valued ReplaceZero requires a real replacement")
        self.set_param("value", value)

    def evaluate(self, a, data_type=None) -> Num:
        if self.real_valued:
            a = a.real
        value = self.value.real if self.real_valued else self.value
        return self._cast_to_data_type(value if a == 0 else a, data_type)

    def _complex_to_real(
        self, inputs: Sequence[_ComplexPair], sinks: list["Sink"], **kwargs
    ) -> Sequence[_ComplexPair]:
        """Preserve the joint zero test when splitting a complex input."""
        from b_asic.complex_conversion import _real_valued  # noqa: PLC0415

        if self.real_valued:
            return _real_valued(self, inputs, sinks)
        if not (math.isfinite(self.value.real) and math.isfinite(self.value.imag)):
            raise NotImplementedError(
                "Complex ReplaceZero conversion requires a finite replacement"
            )
        a, b = inputs[0].re, inputs[0].im

        def zero_indicator(component):
            # Bounding each component avoids underflow and infinity subtraction.
            # The numeric first operand also makes a NaN component nonzero.
            magnitude = Min(Constant(1), Absolute(component, real_valued=True))
            return Subtraction(ReplaceZero(1, magnitude, real_valued=True), magnitude)

        is_zero = Multiplication(zero_indicator(a), zero_indicator(b))
        return [
            _ComplexPair(
                Addition(a, Multiplication(Constant(self.value.real), is_zero)),
                Addition(b, Multiplication(Constant(self.value.imag), is_zero)),
            )
        ]
