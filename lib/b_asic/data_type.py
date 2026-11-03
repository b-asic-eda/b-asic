"""
B-ASIC Data Type Module.
"""

from enum import Enum, auto
from typing import Self

from b_asic.quantization import OverflowMode, QuantizationMode


class NumRepresentation(Enum):
    """
    Type of number representation.
    """

    FIXED_POINT = auto()
    FLOATING_POINT = auto()


def _format_wl(
    wl: int | tuple[int, int], num_repr: NumRepresentation
) -> tuple[int, int]:
    if isinstance(wl, int):
        if num_repr == NumRepresentation.FLOATING_POINT:
            raise TypeError(
                "Both exponent and mantissa word lengths must be provided for floating-point."
            )
        return (1, wl - 1)
    return wl


def _count_bits(wl: tuple[int, int], num_repr: NumRepresentation) -> int:
    return sum(wl) + (1 if num_repr == NumRepresentation.FLOATING_POINT else 0)


class DataType:
    """
    Data type specification.

    All arguments are keyword only.

    The number of bits can be specified in two few different ways.

    +-------------------------------------------+----------------------------------------------------+---------------------------------+
    | *num_repr*                                | int                                                | (int, int)                      |
    +===========================================+====================================================+=================================+
    | :attr:`~NumRepresentation.FIXED_POINT`    | (1, *wl* -1), one integer bits, *wl* bits in total | (integer bits, fractional bits) |
    +-------------------------------------------+----------------------------------------------------+---------------------------------+
    | :attr:`~NumRepresentation.FLOATING_POINT` | N/A                                                | (exponent bits, mantissa bits)  |
    +-------------------------------------------+----------------------------------------------------+---------------------------------+



    If *input_wl* or *output_wl* are not provided, they are assumed to be the same as *wl*.

    Parameters
    ----------
    wl : int or (int, int)
        Number of bits for data type used in computations.
    input_wl : int or (int, int), optional
        Number of bits for input data type.
    output_wl : int or (int, int), optional
        Number of bits for output data type.
    num_repr : :class:`~b_asic.data_type.NumRepresentation`, default: :attr:`~b_asic.data_type.NumRepresentation.FIXED_POINT`
        Type of number representation to use.
    is_signed : bool, default: True
        If the number representation is signed.
    is_complex : bool, default: False
        If the number representation is complex-valued.
    quantization_mode : :class:`~b_asic.quantization.QuantizationMode`, default: :attr:`~b_asic.quantization.QuantizationMode.TRUNCATION`
        Type of quantization to use.
    overflow_mode : :class:`~b_asic.quantization.OverflowMode`, default: :attr:`~b_asic.quantization.OverflowMode.WRAPPING`
        Type of overflow to use.
    """

    def __init__(
        self,
        wl: int | tuple[int, int],
        input_wl: int | tuple[int, int] | None = None,
        output_wl: int | tuple[int, int] | None = None,
        num_repr: NumRepresentation = NumRepresentation.FIXED_POINT,
        is_signed: bool = True,
        is_complex: bool = False,
        quantization_mode: QuantizationMode = QuantizationMode.TRUNCATION,
        overflow_mode: OverflowMode = OverflowMode.WRAPPING,
    ):
        wl = _format_wl(wl, num_repr)
        input_wl = _format_wl(input_wl, num_repr) if input_wl is not None else wl
        output_wl = _format_wl(output_wl, num_repr) if output_wl is not None else wl
        self.wl = wl
        self.input_wl = input_wl
        self.output_wl = output_wl
        self.num_repr = num_repr
        self.is_signed = is_signed
        self.is_complex = is_complex
        self.quantization_mode = quantization_mode
        self.overflow_mode = overflow_mode

    @property
    def bits(self) -> int:
        """
        Number of bits used for computations.

        Returns
        -------
        int
            Total number of bits used for computations.
        """
        return _count_bits(self.wl, self.num_repr)

    @property
    def high(self) -> int:
        """
        Index of most significant bit.

        Returns
        -------
        int
            Zero-based index of the most significant computation bit.
        """
        return self.bits - 1

    @property
    def low(self) -> int:
        """
        Index of least significant bit.

        Returns
        -------
        int
            Zero-based index of the least significant bit, always 0.
        """
        return 0

    @property
    def input_bits(self) -> int:
        """
        Number of bits used for input.

        Returns
        -------
        int
            Total number of bits used for input values.
        """
        return _count_bits(self.input_wl, self.num_repr)

    @property
    def input_high(self) -> int:
        """
        Index of most significant bit for input.

        Returns
        -------
        int
            Zero-based index of the most significant input bit.
        """
        return self.input_bits - 1

    @property
    def output_bits(self) -> int:
        """
        Number of bits used for output.

        Returns
        -------
        int
            Total number of bits used for output values.
        """
        return _count_bits(self.output_wl, self.num_repr)

    @property
    def output_high(self) -> int:
        """
        Index of most significant bit for output.

        Returns
        -------
        int
            Zero-based index of the most significant output bit.
        """
        return self.output_bits - 1

    @property
    def int_bits(self) -> int:
        """
        Number of integer bits. Only valid for fixed-point types.

        Returns
        -------
        int
            Number of integer bits in the fixed-point representation.
        """
        if self.num_repr != NumRepresentation.FIXED_POINT:
            raise TypeError("Only fixed-point data types have integer bits")
        return self.wl[0]

    @property
    def frac_bits(self) -> int:
        """
        Number of fractional bits. Only valid for fixed-point types.

        Returns
        -------
        int
            Number of fractional bits in the fixed-point representation.
        """
        if self.num_repr != NumRepresentation.FIXED_POINT:
            raise TypeError("Only fixed-point data types have fractional bits")
        return self.wl[1]

    @property
    def exp_bits(self) -> int:
        """
        Number of exponent bits. Only valid for floating-point types.

        Returns
        -------
        int
            Number of exponent bits in the floating-point representation.
        """
        if self.num_repr != NumRepresentation.FLOATING_POINT:
            raise TypeError("Only floating-point data types have exponent bits")
        return self.wl[0]

    @property
    def man_bits(self) -> int:
        """
        Number of mantissa bits. Only valid for floating-point types.

        Returns
        -------
        int
            Number of mantissa bits in the floating-point representation.
        """
        if self.num_repr != NumRepresentation.FLOATING_POINT:
            raise TypeError("Only floating-point data types have mantissa bits")
        return self.wl[1]

    @classmethod
    def from_DataType(cls, other: "DataType") -> Self:
        """
        Create DataType subclass from other subclass.

        Parameters
        ----------
        other : :class:`~b_asic.data_type.DataType`
            The DataType to base new object on.
        """
        return cls(**other.__dict__)


class _VhdlDataType(DataType):
    """
    Internal VHDL-specific data type.

    Created by :class:`~b_asic.code_printer.VhdlPrinter` from a :class:`DataType`.
    Extends :class:`DataType` with VHDL string representations and index conventions.

    Parameters
    ----------
    vhdl_2008 : bool, default: False
        If True, use ``fixed_pkg`` for fixed-point values and ``float_pkg`` for
        floating-point values.
    """

    def __init__(
        self,
        wl: int | tuple[int, int],
        input_wl: int | tuple[int, int] | None = None,
        output_wl: int | tuple[int, int] | None = None,
        num_repr: NumRepresentation = NumRepresentation.FIXED_POINT,
        is_signed: bool = True,
        is_complex: bool = False,
        quantization_mode: QuantizationMode = QuantizationMode.TRUNCATION,
        overflow_mode: OverflowMode = OverflowMode.WRAPPING,
        vhdl_2008: bool = False,
    ):
        super().__init__(
            wl,
            input_wl,
            output_wl,
            num_repr,
            is_signed,
            is_complex,
            quantization_mode,
            overflow_mode,
        )
        self.vhdl_2008 = vhdl_2008

    @property
    def high(self) -> int:
        # Doc-string inherited
        if self.vhdl_2008 and not self.is_complex:
            return self.wl[0] - 1
        return super().high

    @property
    def low(self) -> int:
        # Doc-string inherited
        if self.vhdl_2008 and not self.is_complex:
            return -self.wl[1]
        return 0

    @property
    def type_str(self) -> str:
        # Doc-string inherited
        if self.is_complex:
            return "complex"
        return self._real_type_str(self.is_signed, self.vhdl_2008)

    @property
    def init_val(self) -> str:
        if self.is_complex:
            return "(re => (others => '0'), im => (others => '0'))"
        else:
            return "(others => '0')"

    @property
    def dontcare_str(self) -> str:
        if self.is_complex:
            return "(re => (others => '-'), im => (others => '-'))"
        else:
            return "(others => '-')"

    @property
    def scalar_type_str(self) -> str:
        if not self.is_complex:
            return self.type_str
        return self._real_type_str(self.is_signed, self.vhdl_2008)

    @property
    def slv_type_str(self) -> str:
        return f"std_logic_vector({self.bits - 1} downto 0)"

    @property
    def input_type_str(self) -> str:
        return f"std_logic_vector({self.input_bits - 1} downto 0)"

    @property
    def output_type_str(self) -> str:
        return f"std_logic_vector({self.output_bits - 1} downto 0)"

    def get_input_port_declaration(
        self, entity_name: str, signal_suffix: str = ""
    ) -> list[str]:
        if self.is_complex:
            return [
                f"{entity_name}_0_in_re{signal_suffix} : in {self.input_type_str}",
                f"{entity_name}_0_in_im{signal_suffix} : in {self.input_type_str}",
            ]
        else:
            return [f"{entity_name}_0_in{signal_suffix} : in {self.input_type_str}"]

    def get_output_port_declaration(
        self, entity_name: str, signal_suffix: str = ""
    ) -> list[str]:
        if self.is_complex:
            return [
                f"{entity_name}_0_out_re{signal_suffix} : out {self.output_type_str}",
                f"{entity_name}_0_out_im{signal_suffix} : out {self.output_type_str}",
            ]
        else:
            return [f"{entity_name}_0_out{signal_suffix} : out {self.output_type_str}"]

    def get_input_port_mapping(
        self, entity_name: str, signal_suffix: str = ""
    ) -> list[str]:
        if self.is_complex:
            return [
                f"p_0_in_re => {entity_name}_0_in_re{signal_suffix}",
                f"p_0_in_im => {entity_name}_0_in_im{signal_suffix}",
            ]
        else:
            return [f"p_0_in => {entity_name}_0_in{signal_suffix}"]

    def get_output_port_mapping(
        self, entity_name: str, signal_suffix: str = ""
    ) -> list[str]:
        if self.is_complex:
            return [
                f"p_0_out_re => {entity_name}_0_out_re{signal_suffix}",
                f"p_0_out_im => {entity_name}_0_out_im{signal_suffix}",
            ]
        else:
            return [f"p_0_out => {entity_name}_0_out{signal_suffix}"]

    def _vhdl_type(self, name: str) -> str:
        return f"{name}({self.high} downto {self.low})"

    def _real_type_str(self, is_signed: bool, use_2008: bool) -> str:
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                if use_2008:
                    name = "sfixed" if is_signed else "ufixed"
                else:
                    name = "signed" if is_signed else "unsigned"
            case NumRepresentation.FLOATING_POINT:
                name = "float" if use_2008 else "std_logic_vector"
            case _:
                raise ValueError
        return self._vhdl_type(name)
