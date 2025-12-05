"""
B-ASIC Core Operations Module.

Contains some of the most commonly used mathematical operations.
"""

from typing import TYPE_CHECKING, Union

import apytypes as apy
from numpy import abs as np_abs
from numpy import conjugate, sqrt

from b_asic.graph_component import Name, TypeName
from b_asic.operation import AbstractOperation
from b_asic.port import SignalSourceProvider
from b_asic.types import Num, ShapeCoordinates
from b_asic.utils import float_to_csd

if TYPE_CHECKING:
    from b_asic.sfg import SFG


class Constant(AbstractOperation):
    r"""
    Constant value operation.

    Gives a specified value that remains constant for every iteration.

    .. math:: y = \text{value}

    Parameters
    ----------
    value : Number, default: 0
        The constant value.
    name : Name, optional
        Operation name.
    """

    __slots__ = ("_name", "_value")
    _value: Num
    _name: Name

    is_linear = True
    is_constant = True

    def __init__(self, value: Num = 0, name: Name = "") -> None:
        """
        Construct a Constant operation with the given value.
        """
        super().__init__(
            input_count=0,
            output_count=1,
            name=name,
            latency_offsets={"out0": 0},
            execution_time=1,
        )
        self.set_param("value", value)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("c")

    def evaluate(self, data_type=None) -> Num:
        if data_type is not None:
            return apy.fx(self.param("value"), data_type.wl[0], data_type.wl[1])
        return self.param("value")

    @property
    def value(self) -> Num:
        """
        Get the constant value of this operation.
        """
        return self.param("value")

    @value.setter
    def value(self, value: Num) -> None:
        """
        Set the constant value of this operation.
        """
        self.set_param("value", value)

    @property
    def latency(self) -> int:
        return 0

    def __repr__(self) -> str:
        return f"Constant({self.value})"

    def __str__(self) -> str:
        return f"{self.value}"

    def get_plot_coordinates(
        self,
    ) -> tuple[ShapeCoordinates, ShapeCoordinates]:
        # Doc-string inherited
        return (
            (
                (-0.5, 0),
                (-0.5, 1),
                (-0.25, 1),
                (0, 0.5),
                (-0.25, 0),
                (-0.5, 0),
            ),
            (
                (-0.5, 0),
                (-0.5, 1),
                (-0.25, 1),
                (0, 0.5),
                (-0.25, 0),
                (-0.5, 0),
            ),
        )

    def get_input_coordinates(self) -> ShapeCoordinates:
        # doc-string inherited
        return ()

    def get_output_coordinates(self) -> ShapeCoordinates:
        # doc-string inherited
        return ((0, 0.5),)


class Negation(AbstractOperation):
    """
    Negation operation.

    Gives the result of negating its input.

    .. math:: y = -x

    Parameters
    ----------
    src0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The signal to negate.
    name : Name, optional
        Operation name.
    latency : int, optional
        Operation latency (delay from input to output in time units).
    latency_offsets : dict[str, int], optional
        Used if input arrives later than when the operator starts, e.g.,
        ``{"in0": 0`` which corresponds to *src0* arriving one time unit after the
        operator starts. If not provided and *latency* is provided, set to zero.
    execution_time : int, optional
        Operation execution time (time units before operator can be
        reused).
    """

    __slots__ = ("_execution_time", "_latency", "_latency_offsets", "_name", "_src0")
    _src0: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True
    is_swappable = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
        """
        Construct a Negation operation.
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

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("neg")

    def evaluate(self, a, data_type=None) -> Num:
        if data_type is not None:
            return apy.fx(-a, data_type.wl[0], data_type.wl[1])
        return -a


class Addition(AbstractOperation):
    """
    Binary addition operation.

    Gives the result of adding two inputs.

    .. math:: y = x_0 + x_1

    Parameters
    ----------
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
    mul_j : bool, default: False
        If True, *src1* is multiplied by j before the addition.
    shift_output : int, default: 0
        Right-shift amount applied to the output result.

    See Also
    --------
    AddSub
    """

    __slots__ = (
        "_execution_time",
        "_latency",
        "_latency_offsets",
        "_mul_j",
        "_name",
        "_shift_output",
        "_src0",
        "_src1",
    )
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None
    _mul_j: bool
    _shift_output: int

    is_linear = True
    is_swappable = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
        mul_j: bool = False,
        shift_output: int = 0,
    ) -> None:
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
        self.set_param("mul_j", mul_j)
        self.set_param("shift_output", shift_output)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("add")

    @property
    def mul_j(self) -> bool:
        """
        Get if *src1* is multiplied by j before the addition.
        """
        return self.param("mul_j")

    @mul_j.setter
    def mul_j(self, mul_j: bool) -> None:
        """
        Set if *src1* is multiplied by j before the addition.

        Parameters
        ----------
        mul_j : bool
            Whether *src1* is multiplied by j before the addition.
        """
        self.set_param("mul_j", mul_j)

    @property
    def shift_output(self) -> int:
        """
        Get the right-shift amount applied to the output.
        """
        return self.param("shift_output")

    @shift_output.setter
    def shift_output(self, shift_output: int) -> None:
        """
        Set the right-shift amount applied to the output.

        Parameters
        ----------
        shift_output : int
            Right-shift amount for the output result.
        """
        if not isinstance(shift_output, int):
            raise TypeError("shift_output must be an int")
        if shift_output < 0:
            raise ValueError("shift_output must be non-negative")
        self.set_param("shift_output", shift_output)

    def evaluate(self, a, b, data_type=None) -> Num:
        if self.mul_j:
            b *= 1j
        res = a + b
        if self.shift_output != 0:
            if isinstance(res, (apy.APyFixed, apy.APyCFixed)):
                res = res >> self.shift_output
            else:
                res = res / (2**self.shift_output)
        return self._cast_to_data_type(res, data_type)

    def _rewrite_AddSub(self) -> "SFG":
        from b_asic.sfg import SFG  # noqa: PLC0415
        from b_asic.special_operations import Input, Output  # noqa: PLC0415

        in0 = Input()
        in1 = Input()
        out0 = Output()
        addsub = AddSub(
            is_add=True,
            src0=in0,
            src1=in1,
            name=self.name,
            latency_offsets=self.latency_offsets,
            execution_time=self.execution_time,
            mul_j=self.mul_j,
            shift_output=self.shift_output,
        )
        out0 <<= addsub
        return SFG([in0, in1], [out0])

    def _rewrite_ShiftAddSub(self) -> "SFG":
        from b_asic.sfg import SFG  # noqa: PLC0415
        from b_asic.special_operations import Input, Output  # noqa: PLC0415

        in0 = Input()
        in1 = Input()
        out0 = Output()
        addsub = ShiftAddSub(
            is_add=True,
            shift=0,
            src0=in0,
            src1=in1,
            name=self.name,
            latency_offsets=self.latency_offsets,
            execution_time=self.execution_time,
            mul_j=self.mul_j,
            shift_output=self.shift_output,
        )
        out0 <<= addsub
        return SFG([in0, in1], [out0])


class Subtraction(AbstractOperation):
    """
    Binary subtraction operation.

    Gives the result of subtracting the second input from the first one.

    .. math:: y = x_0 - x_1

    Parameters
    ----------
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
    mul_j : bool, default: False
        If True, *src1* is multiplied by j before the subtraction.
    shift_output : int, default: 0
        Right-shift amount applied to the output result.

    See Also
    --------
    AddSub
    """

    is_linear = True

    __slots__ = (
        "_execution_time",
        "_latency",
        "_latency_offsets",
        "_mul_j",
        "_name",
        "_shift_output",
        "_src0",
        "_src1",
    )
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None
    _mul_j: bool
    _shift_output: int

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
        mul_j: bool = False,
        shift_output: int = 0,
    ) -> None:
        """
        Construct a Subtraction operation.
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
        self.set_param("mul_j", mul_j)
        self.set_param("shift_output", shift_output)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("sub")

    @property
    def mul_j(self) -> bool:
        """
        Get if *src1* is multiplied by j before the subtraction.
        """
        return self.param("mul_j")

    @mul_j.setter
    def mul_j(self, mul_j: bool) -> None:
        """
        Set if *src1* is multiplied by j before the subtraction.

        Parameters
        ----------
        mul_j : bool
            Whether *src1* is multiplied by j before the subtraction.
        """
        self.set_param("mul_j", mul_j)

    @property
    def shift_output(self) -> int:
        """
        Get the right-shift amount applied to the output.
        """
        return self.param("shift_output")

    @shift_output.setter
    def shift_output(self, shift_output: int) -> None:
        """
        Set the right-shift amount applied to the output.

        Parameters
        ----------
        shift_output : int
            Right-shift amount for the output result.
        """
        if not isinstance(shift_output, int):
            raise TypeError("shift_output must be an int")
        if shift_output < 0:
            raise ValueError("shift_output must be non-negative")
        self.set_param("shift_output", shift_output)

    def evaluate(self, a, b, data_type=None) -> Num:
        if self.mul_j:
            b *= 1j
        res = a - b
        if self.shift_output != 0:
            if isinstance(res, (apy.APyFixed, apy.APyCFixed)):
                res = res >> self.shift_output
            else:
                res = res / (2**self.shift_output)
        return self._cast_to_data_type(res, data_type)

    def _rewrite_AddSub(self) -> "SFG":
        from b_asic.sfg import SFG  # noqa: PLC0415
        from b_asic.special_operations import Input, Output  # noqa: PLC0415

        in0 = Input()
        in1 = Input()
        out0 = Output()
        addsub = AddSub(
            is_add=False,
            src0=in0,
            src1=in1,
            name=self.name,
            latency_offsets=self.latency_offsets,
            execution_time=self.execution_time,
            mul_j=self.mul_j,
            shift_output=self.shift_output,
        )
        out0 <<= addsub
        return SFG([in0, in1], [out0])

    def _rewrite_ShiftAddSub(self) -> "SFG":
        from b_asic.sfg import SFG  # noqa: PLC0415
        from b_asic.special_operations import Input, Output  # noqa: PLC0415

        in0 = Input()
        in1 = Input()
        out0 = Output()
        addsub = ShiftAddSub(
            is_add=False,
            shift=0,
            src0=in0,
            src1=in1,
            name=self.name,
            latency_offsets=self.latency_offsets,
            execution_time=self.execution_time,
            mul_j=self.mul_j,
            shift_output=self.shift_output,
        )
        out0 <<= addsub
        return SFG([in0, in1], [out0])


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
    ----------
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
    mul_j : bool, default: False
        If True, *src1* is multiplied by j before the addition/subtraction.
    shift_output : int, default: 0
        Right-shift amount applied to the output result.

    See Also
    --------
    Addition, Subtraction, ShiftAddSub
    """

    __slots__ = (
        "_execution_time",
        "_is_add",
        "_latency",
        "_latency_offsets",
        "_mul_j",
        "_name",
        "_shift_output",
        "_src0",
        "_src1",
    )
    _is_add: bool
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None
    _mul_j: bool
    _shift_output: int

    is_linear = True

    def __init__(
        self,
        is_add: bool = True,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
        mul_j: bool = False,
        shift_output: int = 0,
    ) -> None:
        """
        Construct an Addition/Subtraction operation.
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
        self.set_param("is_add", is_add)
        self.set_param("mul_j", mul_j)
        self.set_param("shift_output", shift_output)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("addsub")

    def evaluate(self, a, b, data_type=None) -> Num:
        if self.mul_j:
            b *= 1j
        res = a + b if self.is_add else a - b
        if self.shift_output != 0:
            if isinstance(res, (apy.APyFixed, apy.APyCFixed)):
                res = res >> self.shift_output
            else:
                res = res / (2**self.shift_output)
        return self._cast_to_data_type(res, data_type)

    @property
    def is_add(self) -> bool:
        """
        Get if operation is an addition.
        """
        return self.param("is_add")

    @is_add.setter
    def is_add(self, is_add: bool) -> None:
        """
        Set if operation is an addition.

        Parameters
        ----------
        is_add : bool
            If True, operation is an addition. If False, operation is a subtraction.
        """
        self.set_param("is_add", is_add)

    @property
    def mul_j(self) -> bool:
        """
        Get if *src1* is multiplied by j before the addition/subtraction.
        """
        return self.param("mul_j")

    @mul_j.setter
    def mul_j(self, mul_j: bool) -> None:
        """
        Set if *src1* is multiplied by j before the addition/subtraction.

        Parameters
        ----------
        mul_j : bool
            Whether *src1* is multiplied by j before the addition/subtraction.
        """
        self.set_param("mul_j", mul_j)

    @property
    def shift_output(self) -> int:
        """
        Get the right-shift amount applied to the output.
        """
        return self.param("shift_output")

    @shift_output.setter
    def shift_output(self, shift_output: int) -> None:
        """
        Set the right-shift amount applied to the output.

        Parameters
        ----------
        shift_output : int
            Right-shift amount for the output result.
        """
        if not isinstance(shift_output, int):
            raise TypeError("shift_output must be an int")
        if shift_output < 0:
            raise ValueError("shift_output must be non-negative")
        self.set_param("shift_output", shift_output)

    @property
    def is_swappable(self) -> bool:
        return self.is_add

    def _rewrite_ShiftAddSub(self) -> "SFG":
        from b_asic.sfg import SFG  # noqa: PLC0415
        from b_asic.special_operations import Input, Output  # noqa: PLC0415

        in0 = Input()
        in1 = Input()
        out0 = Output()
        addsub = ShiftAddSub(
            is_add=self.is_add,
            shift=0,
            src0=in0,
            src1=in1,
            name=self.name,
            latency_offsets=self.latency_offsets,
            execution_time=self.execution_time,
            mul_j=self.mul_j,
            shift_output=self.shift_output,
        )
        out0 <<= addsub
        return SFG([in0, in1], [out0])


class ShiftAddSub(AbstractOperation):
    r"""
    Two-input addition or subtraction operation with right-shift for the second operand.

    .. math::
        y = \begin{cases}
        x_0 + x_1 \gg \text{shift},& \text{is_add} = \text{True}\\
        x_0 - x_1 \gg \text{shift},& \text{is_add} = \text{False}
        \end{cases}

    This is used to map additions and subtractions to the same
    operator.

    Parameters
    ----------
    src0, src1 : SignalSourceProvider, optional
        The two signals to add or subtract.
    is_add : bool, default: True
        If True, the operation is an addition, if False, a subtraction.
    shift : int, default: 0
        The right-shift amount.
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
    mul_j : bool, default: False
        If True, *src1* is multiplied by j before the addition/subtraction.
    shift_output : int, default: 0
        Right-shift amount applied to the output result.

    See Also
    --------
    Addition, Subtraction, AddSub
    """

    __slots__ = (
        "_execution_time",
        "_is_add",
        "_latency",
        "_latency_offsets",
        "_mul_j",
        "_name",
        "_shift",
        "_shift_output",
        "_src0",
        "_src1",
    )
    _is_add: bool
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None
    _shift: int
    _mul_j: bool
    _shift_output: int

    is_linear = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        is_add: bool = True,
        shift: int = 0,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
        mul_j: bool = False,
        shift_output: int = 0,
    ) -> None:
        """
        Construct an Addition/Subtraction operation.
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
        self.is_add = is_add
        self.shift = shift
        self.mul_j = mul_j
        self.shift_output = shift_output

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("shiftaddsub")

    def evaluate(self, a, b, data_type=None) -> Num:
        if self.mul_j:
            b *= 1j
        if isinstance(b, (apy.APyFixed, apy.APyCFixed)):
            if data_type is not None:
                b = self._cast_to_data_type(b >> self.shift, data_type)
            else:
                b = b >> self.shift
        else:
            b /= 2**self.shift
        res = a + b if self.is_add else a - b
        if self.shift_output != 0:
            if isinstance(res, (apy.APyFixed, apy.APyCFixed)):
                res = res >> self.shift_output
            else:
                res = res / (2**self.shift_output)
        return self._cast_to_data_type(res, data_type)

    @property
    def is_add(self) -> bool:
        """
        Get if operation is an addition.
        """
        return self.param("is_add")

    @property
    def shift(self) -> int:
        return self.param("shift")

    @property
    def mul_j(self) -> bool:
        """
        Get if *src1* is multiplied by j before the shift and addition/subtraction.
        """
        return self.param("mul_j")

    @property
    def shift_output(self) -> int:
        """
        Get the right-shift amount applied to the output.
        """
        return self.param("shift_output")

    @is_add.setter
    def is_add(self, is_add: bool) -> None:
        """
        Set if operation is an addition.

        Parameters
        ----------
        is_add : bool
            If True, operation is an addition. If False, operation is a subtraction.
        """
        if not isinstance(is_add, bool):
            raise TypeError("is_add must be a bool")
        self.set_param("is_add", is_add)

    @shift.setter
    def shift(self, shift: int) -> None:
        """
        Set the number of steps to shift *src1*.

        Parameters
        ----------
        shift : int
            The number of steps to shift *src1*.
        """
        if not isinstance(shift, int):
            raise TypeError("shift must be an int")
        if shift < 0:
            raise ValueError("shift must be non-negative")
        self.set_param("shift", shift)

    @mul_j.setter
    def mul_j(self, mul_j: bool) -> None:
        """
        Set if *src1* is multiplied by j before the shift and addition/subtraction.

        Parameters
        ----------
        mul_j : bool
            Whether *src1* is multiplied by j before the shift and addition/subtraction.
        """
        if not isinstance(mul_j, bool):
            raise TypeError("mul_j must be a bool")
        self.set_param("mul_j", mul_j)

    @shift_output.setter
    def shift_output(self, shift_output: int) -> None:
        """
        Set the right-shift amount applied to the output.

        Parameters
        ----------
        shift_output : int
            Right-shift amount for the output result.
        """
        if not isinstance(shift_output, int):
            raise TypeError("shift_output must be an int")
        if shift_output < 0:
            raise ValueError("shift_output must be non-negative")
        self.set_param("shift_output", shift_output)

    @property
    def is_swappable(self) -> bool:
        return self.is_add and self.shift == 0


class Multiplication(AbstractOperation):
    r"""
    Binary multiplication operation.

    Gives the result of multiplying two inputs.

    .. math:: y = x_0 \times x_1

    Parameters
    ----------
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
    --------
    ConstantMultiplication
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

    is_swappable = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
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

    def evaluate(self, a, b, data_type=None) -> Num:
        res = a * b
        return self._cast_to_data_type(res, data_type)

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
    ----------
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
    --------
    Reciprocal
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

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
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

    def evaluate(self, a, b, data_type=None) -> Num:
        res = float("inf") if b == 0 else a / b
        return self._cast_to_data_type(res, data_type)

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
    ----------
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
    --------
    Max
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

    is_swappable = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
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

    def evaluate(self, a, b, data_type=None) -> Num:
        if isinstance(a, complex) or isinstance(b, complex):
            raise ValueError("core_operations.Min does not support complex numbers.")
        res = min(a, b)
        return self._cast_to_data_type(res, data_type)


class Max(AbstractOperation):
    r"""
    Binary max operation.

    Gives the maximum value of two inputs.

    .. math:: y = \max\{x_0 , x_1\}

    .. note:: Only real-valued numbers are supported.

    Parameters
    ----------
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
    --------
    Min
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

    is_swappable = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
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

    def evaluate(self, a, b, data_type=None) -> Num:
        if isinstance(a, complex) or isinstance(b, complex):
            raise ValueError("core_operations.Max does not support complex numbers.")
        res = max(a, b)
        return self._cast_to_data_type(res, data_type)


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

    __slots__ = ("_execution_time", "_latency", "_latency_offsets", "_name", "_src0")
    _src0: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
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

    def evaluate(self, a, data_type=None) -> Num:
        res = sqrt(complex(a))
        return self._cast_to_data_type(res, data_type)


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

    __slots__ = ("_execution_time", "_latency", "_latency_offsets", "_name", "_src0")
    _src0: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
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

    def evaluate(self, a, data_type=None) -> Num:
        res = conjugate(a)
        return self._cast_to_data_type(res, data_type)


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

    __slots__ = ("_execution_time", "_latency", "_latency_offsets", "_name", "_src0")
    _src0: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
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

    def evaluate(self, a, data_type=None) -> Num:
        return self._cast_to_data_type(np_abs(a), data_type)


class ImaginaryMultiplication(AbstractOperation):
    r"""
    Imaginary multiplication operation.

    Gives the result of multiplying its input by the imaginary unit.

    .. math:: y = x_0 \times j

    Parameters
    ----------
    src0 : :class:`~b_asic.port.SignalSourceProvider`, optional
        The signal to multiply with the imaginary unit.
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

    __slots__ = (
        "_execution_time",
        "_latency",
        "_latency_offsets",
        "_name",
        "_src0",
    )
    _src0: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
        """Construct an ImaginaryMultiplication operation."""
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
        return TypeName("imul")

    def evaluate(self, a, data_type=None) -> Num:
        res = a * 1j
        return self._cast_to_data_type(res, data_type)

    def _join(self, other: "AbstractOperation") -> Union["SFG", None]:
        from b_asic.sfg import SFG  # noqa: PLC0415
        from b_asic.special_operations import Input, Output  # noqa: PLC0415

        if not isinstance(other, (Addition, Subtraction, AddSub, ShiftAddSub)):
            return None

        in0 = Input()
        in1 = Input()
        out0 = Output()
        if other.mul_j:
            in1 = -in1

        if isinstance(other, Addition):
            op = Addition(
                src0=in0,
                src1=in1,
                name=self.name,
                latency_offsets=self.latency_offsets,
                execution_time=self.execution_time,
                mul_j=not other.mul_j,
            )
        elif isinstance(other, Subtraction):
            op = Subtraction(
                src0=in0,
                src1=in1,
                name=self.name,
                latency_offsets=self.latency_offsets,
                execution_time=self.execution_time,
                mul_j=not other.mul_j,
            )
        elif isinstance(other, AddSub):
            op = AddSub(
                src0=in0,
                src1=in1,
                is_add=other.is_add,
                name=self.name,
                latency_offsets=self.latency_offsets,
                execution_time=self.execution_time,
                mul_j=not other.mul_j,
            )
        elif isinstance(other, ShiftAddSub):
            op = ShiftAddSub(
                src0=in0,
                src1=in1,
                is_add=other.is_add,
                shift=other.shift,
                name=self.name,
                latency_offsets=self.latency_offsets,
                execution_time=self.execution_time,
                mul_j=not other.mul_j,
            )
        out0 <<= op
        return SFG([in0, in1], [out0])


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

    __slots__ = (
        "_execution_time",
        "_latency",
        "_latency_offsets",
        "_name",
        "_src0",
        "_value",
    )
    _value: Num
    _src0: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True

    def __init__(
        self,
        value: Num = 0,
        src0: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
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

    def evaluate(self, a, data_type=None) -> Num:
        res = a * self.param("value")
        return self._cast_to_data_type(res, data_type)

    @property
    def value(self) -> Num:
        """Get the constant value of this operation."""
        return self.param("value")

    @value.setter
    def value(self, value: Num) -> None:
        """Set the constant value of this operation."""
        self.set_param("value", value)

    def _rewrite_ShiftAddSub(self) -> "SFG":
        from b_asic.sfg import SFG  # noqa: PLC0415
        from b_asic.special_operations import Input, Output  # noqa: PLC0415

        csd = float_to_csd(self.value)

        in0 = Input()
        out0 = Output()
        prev_op = in0

        if self.value < 0:
            prev_op = Negation(prev_op)

        bits = len(csd[0])
        frac_bits = csd[1]
        max_exp = bits - 1 - frac_bits

        if len(csd[0]) == 1:
            prev_op = Shift(frac_bits, prev_op)
        else:
            for i, digit in enumerate(csd[0]):
                if digit not in (-1, 0, 1):
                    raise ValueError("CSD representation can only contain -1, 0, and 1")
                if digit == 0:
                    continue

                exp = max_exp - i
                if exp == 0:
                    continue
                prev_op = ShiftAddSub(
                    is_add=digit == 1,
                    shift=-exp,
                    src0=prev_op,
                    src1=in0,
                )

        out0 <<= prev_op

        return SFG([in0], [out0])

    def _rewrite_Shift(self) -> "SFG":
        """Return a Shift and Add/Sub chain that implements the multiplication."""
        from b_asic.sfg import SFG  # noqa: PLC0415
        from b_asic.special_operations import Input, Output  # noqa: PLC0415

        csd = float_to_csd(self.value)

        in0 = Input()
        out0 = Output()
        prev_op = in0

        if self.value < 0:
            prev_op = Negation(prev_op)

        bits = len(csd[0])
        frac_bits = csd[1]
        max_exp = bits - 1 - frac_bits

        if len(csd[0]) == 1:
            prev_op = Shift(frac_bits, prev_op)
        else:
            for i, digit in enumerate(csd[0]):
                if digit not in (-1, 0, 1):
                    raise ValueError("CSD representation can only contain -1, 0, and 1")
                if digit == 0:
                    continue

                exp = max_exp - i
                if exp == 0:
                    continue

                shift = Shift(-exp, in0)
                if digit == 1:
                    prev_op = Addition(prev_op, shift)
                elif digit == -1:
                    prev_op = Subtraction(prev_op, shift)
        out0 <<= prev_op

        return SFG([in0], [out0])


class MAD(AbstractOperation):
    r"""
    Multiply-add operation.

    Gives the result of multiplying the first input by the second input and
    then adding the third input.

    .. math:: y = x_0 \times x_1 + x_2

    Parameters
    ----------
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

    __slots__ = (
        "_do_add",
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
    _do_add: bool

    is_swappable = True

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        src2: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
        do_add: bool = True,
    ) -> None:
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
        self.set_param("do_add", do_add)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("mad")

    def evaluate(self, a, b, c, data_type=None) -> Num:
        res = a * b + c if self.do_add else a * b
        return self._cast_to_data_type(res, data_type)

    @property
    def is_linear(self) -> bool:
        return (
            self.input(0).connected_source.operation.is_constant
            or self.input(1).connected_source.operation.is_constant
        )

    @property
    def do_add(self) -> bool:
        """Get whether the input to src2 is used when computing."""
        return self.param("do_add")

    @do_add.setter
    def do_add(self, do_add: bool) -> None:
        """Set whether the input to src2 is used when computing."""
        self.set_param("do_add", do_add)

    def swap_io(self) -> None:
        self._input_ports = [
            self._input_ports[1],
            self._input_ports[0],
            self._input_ports[2],
        ]
        for i, p in enumerate(self._input_ports):
            p._index = i


class MADS(AbstractOperation):
    __slots__ = (
        "_do_addsub",
        "_execution_time",
        "_is_add",
        "_latency",
        "_latency_offsets",
        "_name",
        "_src0",
        "_src1",
        "_src2",
    )
    _is_add: bool | None
    _src0: SignalSourceProvider | None
    _src1: SignalSourceProvider | None
    _src2: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None
    _do_addsub: bool

    is_swappable = True

    def __init__(
        self,
        is_add: bool | None = True,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
        src2: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
        do_addsub: bool = True,
    ) -> None:
        """Construct a MADS operation."""
        super().__init__(
            input_count=3,
            output_count=1,
            name=Name(name),
            input_sources=[src0, src1, src2],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        self.set_param("is_add", is_add)
        self.set_param("do_addsub", do_addsub)

    @classmethod
    def type_name(cls) -> TypeName:
        return TypeName("mads")

    def evaluate(self, a, b, c, data_type=None) -> Num:
        if self.is_add:
            res = a + b * c if self.do_addsub else b * c
        else:
            res = a - b * c if self.do_addsub else -b * c
        return self._cast_to_data_type(res, data_type)

    @property
    def is_add(self) -> bool:
        """Get whether to add or subtract with the product."""
        return self.param("is_add")

    @is_add.setter
    def is_add(self, is_add: bool) -> None:
        """Set whether to add or subtract with the product."""
        self.set_param("is_add", is_add)

    @property
    def do_addsub(self) -> bool:
        """Get whether the input to src0 is used when computing."""
        return self.param("do_addsub")

    @do_addsub.setter
    def do_addsub(self, do_addsub: bool) -> None:
        """Set whether the input to src0 is used when computing."""
        self.set_param("do_addsub", do_addsub)

    @property
    def is_linear(self) -> bool:
        return (
            self.input(1).connected_source.operation.is_constant
            or self.input(2).connected_source.operation.is_constant
        )

    def swap_io(self) -> None:
        self._input_ports = [
            self._input_ports[0],
            self._input_ports[2],
            self._input_ports[1],
        ]
        for i, p in enumerate(self._input_ports):
            p._index = i


class SymmetricTwoportAdaptor(AbstractOperation):
    r"""
    Wave digital filter symmetric twoport-adaptor operation.

    .. math::

        y_0 & = x_1 + \text{value}\times\left(x_1 - x_0\right)\\
        y_1 & = x_0 + \text{value}\times\left(x_1 - x_0\right)
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
    is_swappable = True

    def __init__(
        self,
        value: Num = 0,
        src0: SignalSourceProvider | None = None,
        src1: SignalSourceProvider | None = None,
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
            input_sources=[src0, src1],
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

    See Also
    --------
    Division
    """

    __slots__ = ("_execution_time", "_latency", "_latency_offsets", "_name", "_src0")
    _src0: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    def __init__(
        self,
        src0: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
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

    def evaluate(self, a, data_type=None) -> Num:
        res = float("inf") if a == 0 else 1 / a
        return self._cast_to_data_type(res, data_type)


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

    __slots__ = (
        "_execution_time",
        "_latency",
        "_latency_offsets",
        "_name",
        "_src0",
        "_value",
    )
    _value: Num
    _src0: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True

    def __init__(
        self,
        value: int = 0,
        src0: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
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

    def evaluate(self, a, data_type=None) -> Num:
        res = a * 2 ** (-self.param("value"))
        return self._cast_to_data_type(res, data_type)

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

    __slots__ = (
        "_execution_time",
        "_latency",
        "_latency_offsets",
        "_name",
        "_src0",
        "_value",
    )
    _value: Num
    _src0: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True

    def __init__(
        self,
        value: int = 0,
        src0: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
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

    def evaluate(self, a, data_type=None) -> Num:
        res = a * 2 ** (self.param("value"))
        return self._cast_to_data_type(res, data_type)

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

    __slots__ = (
        "_execution_time",
        "_latency",
        "_latency_offsets",
        "_name",
        "_src0",
        "_value",
    )
    _value: Num
    _src0: SignalSourceProvider | None
    _name: Name
    _latency: int | None
    _latency_offsets: dict[str, int] | None
    _execution_time: int | None

    is_linear = True

    def __init__(
        self,
        value: int = 0,
        src0: SignalSourceProvider | None = None,
        name: Name = Name(""),
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
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

    def evaluate(self, a, data_type=None) -> Num:
        if isinstance(a, (apy.APyFixed, apy.APyCFixed)):
            res = a >> self.param("value")
        else:
            res = a / 2 ** (self.param("value"))
        return self._cast_to_data_type(res, data_type)

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

    def _combine_Addition(self) -> "ShiftAddSub":
        from b_asic.core_operations import ShiftAddSub  # noqa: PLC0415

        if len(self.output(0).signals) != 1:
            raise ValueError("Output of Shift must only connect to one operation")
        dest_port = self.output(0).signals[0].destination
        add_op = dest_port.operation

        if not isinstance(add_op, Addition):
            raise TypeError("Output of Shift must connect to an Addition operation")

        if not dest_port.index == 1:
            raise ValueError(
                "Shift can only be combined with the second input of Addition"
            )

        return ShiftAddSub(
            shift=self.value,
            src0=self.input(0).connected_source,
            src1=add_op.input(1).connected_source,
        )

    def _combine_Subtraction(self) -> "ShiftAddSub":
        from b_asic.core_operations import ShiftAddSub  # noqa: PLC0415

        if len(self.output(0).signals) != 1:
            raise ValueError("Output of Shift must only connect to one operation")
        dest_port = self.output(0).signals[0].destination
        sub_op = dest_port.operation

        if not isinstance(sub_op, Subtraction):
            raise TypeError("Output of Shift must connect to a Subtraction operation")

        if not dest_port.index == 1:
            raise ValueError(
                "Shift can only be combined with the second input of Subtraction"
            )

        return ShiftAddSub(
            is_add=False,
            shift=self.value,
            src0=self.input(0).connected_source,
            src1=sub_op.input(1).connected_source,
        )

    def _combine_AddSub(self) -> "ShiftAddSub":
        from b_asic.core_operations import ShiftAddSub  # noqa: PLC0415

        if len(self.output(0).signals) != 1:
            raise ValueError("Output of Shift must only connect to one operation")
        dest_port = self.output(0).signals[0].destination
        addsub_op = dest_port.operation

        if not isinstance(addsub_op, ShiftAddSub):
            raise TypeError("Output of Shift must connect to a ShiftAddSub operation")

        if not dest_port.index == 1:
            raise ValueError(
                "Shift can only be combined with the second input of ShiftAddSub"
            )

        return ShiftAddSub(
            is_add=addsub_op.is_add,
            shift=self.value + addsub_op.shift,
            src0=self.input(0).connected_source,
            src1=addsub_op.input(1).connected_source,
        )
