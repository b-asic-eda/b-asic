"""
B-ASIC Data Type Module.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Self

from b_asic.quantization import OverflowMode, QuantizationMode


class NumRepresentation(Enum):
    """
    Type of number representation.
    """

    FIXED_POINT = auto()
    FLOATING_POINT = auto()


@dataclass
class DataType(ABC):
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
    num_repr : :class:`NumRepresentation`, default: :attr:`NumRepresentation.FIXED_POINT`
        Type of number representation to use.
    is_signed : bool, default: True
        If the number representation is signed.
    is_complex : bool, default: False
        If the number representation is complex-valued.
    quantization_mode : :class:`QuantizationMode`, default: :attr:`QuantizationMode.TRUNCATION`
        Type of quantization to use.
    overflow_mode : :class:`OverflowMode`, default: :attr:`OverflowMode.WRAPPING`
        Type of overflow to use.
    """

    wl: tuple[int, int]
    input_wl: tuple[int, int] | None = None
    output_wl: tuple[int, int] | None = None
    num_repr: NumRepresentation = NumRepresentation.FIXED_POINT
    is_signed: bool = True
    is_complex: bool = False
    quantization_mode: QuantizationMode = QuantizationMode.TRUNCATION
    overflow_mode: OverflowMode = OverflowMode.WRAPPING

    def __post_init__(self):
        if isinstance(self.wl, int):
            if self.num_repr == NumRepresentation.FLOATING_POINT:
                raise TypeError(
                    "Both exponent and mantissa word lengths must be provided for floating-point."
                )
            self.wl = (1, self.wl - 1)
        if isinstance(self.input_wl, int):
            if self.num_repr == NumRepresentation.FLOATING_POINT:
                raise TypeError(
                    "Both exponent and mantissa word lengths must be provided for floating-point."
                )
            self.input_wl = (1, self.input_wl - 1)
        if isinstance(self.output_wl, int):
            if self.num_repr == NumRepresentation.FLOATING_POINT:
                raise TypeError(
                    "Both exponent and mantissa word lengths must be provided for floating-point."
                )
            self.output_wl = (1, self.output_wl - 1)

        if self.input_wl is None:
            self.input_wl = self.wl
        if self.output_wl is None:
            self.output_wl = self.wl

    @property
    @abstractmethod
    def type_str(self) -> str:
        """
        Type used for computations.

        Returns
        -------
        str
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def init_val(self) -> str:
        """
        Initial value for signals of this data type.

        Returns
        -------
        str
        """
        raise NotImplementedError

    @property
    def dontcare_str(self) -> str:
        """
        Don't care value for signals of this data type.

        Returns
        -------
        str
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def scalar_type_str(self) -> str:
        """
        Scalar type used for computations.

        Same as :meth:`type_str` when using a real type. The inner type when using a complex type.

        Returns
        -------
        str
        """
        if self.is_complex:
            raise NotImplementedError
        return self.type_str()

    @property
    @abstractmethod
    def input_type_str(self) -> str:
        """
        Type used for input.

        Returns
        -------
        str
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def output_type_str(self) -> str:
        """
        Type used for output.

        Returns
        -------
        str
        """
        raise NotImplementedError

    @property
    def bits(self) -> int:
        """
        Number of bits used for computations.

        Returns
        -------
        int
        """
        return sum(self.wl)

    @property
    def high(self) -> int:
        """
        Index of most significant bit.

        Returns
        -------
        int
        """
        return self.bits - 1

    @property
    def low(self) -> int:
        """
        Index of least significant bit.

        Returns
        -------
        int
        """
        return 0

    @property
    def input_bits(self) -> int:
        """
        Number of bits used for input.

        Returns
        -------
        int
        """
        return sum(self.input_wl)

    @property
    def input_high(self) -> int:
        """
        Index of most significant bit for input.

        Returns
        -------
        int
        """
        return self.input_bits - 1

    @property
    def output_bits(self) -> int:
        """
        Number of bits used for output.

        Returns
        -------
        int
        """
        return sum(self.output_wl)

    @property
    def output_high(self) -> int:
        """
        Index of most significant bit for output.

        Returns
        -------
        int
        """
        return self.output_bits - 1

    @classmethod
    def from_DataType(cls, other: "DataType") -> Self:
        """
        Create DataType subclass from other subclass.

        Parameters
        ----------
        other : :class:`DataType`
            The DataType to base new object on.
        """
        return cls(**other.__dict__)


@dataclass
class VhdlDataType(DataType):
    """
    Data type specification for VHDL.

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
    num_repr : :class:`NumRepresentation`, default: :attr:`NumRepresentation.FIXED_POINT`
        Type of number representation to use.
    is_signed : bool, default: True
        If number representation is signed.
    is_complex : bool, default: False
        If number representation is complex-valued.
    vhdl_2008 : bool, default: False
        If True, use ``fixed_pkg`` for fixed-point values and ``float_pkg`` for floating-point values.
    quantization_mode : :class:`QuantizationMode`, default: :attr:`QuantizationMode.TRUNCATION`
        Type of quantization to use.
    overflow_mode : :class:`OverflowMode`, default: :attr:`OverflowMode.WRAPPING`
        Type of overflow to use.
    """

    vhdl_2008: bool = False

    @property
    def low(self) -> int:
        # Doc-string inherited
        _LOW_LUT = {
            (0, 0): 0,
            (0, 1): 0,
            (1, 0): -self.wl[1],
            (1, 1): 0,
        }
        return _LOW_LUT[(self.vhdl_2008, self.is_complex)]

    @property
    def type_str(self) -> str:
        # Doc-string inherited
        _TYPE_LUT = {
            # Pre VHDL-2008
            (0, 0, 0): self._match_unsigned_real,
            (0, 0, 1): self._match_unsigned_complex,
            (0, 1, 0): self._match_signed_real,
            (0, 1, 1): self._match_signed_complex,
            # Post VHDL-2008
            (1, 0, 0): self._match_unsigned_real_2008,
            (1, 0, 1): self._match_unsigned_complex_2008,
            (1, 1, 0): self._match_signed_real_2008,
            (1, 1, 1): self._match_signed_complex_2008,
        }
        return _TYPE_LUT[(self.vhdl_2008, self.is_signed, self.is_complex)]()

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
        if self.is_complex:
            if self.vhdl_2008:
                vhdl_type = "sfixed" if self.is_signed else "ufixed"
            else:
                vhdl_type = "signed" if self.is_signed else "unsigned"
            return f"{vhdl_type}({self.high} downto {self.low})"
        else:
            return self.type_str()

    @property
    def input_type_str(self) -> str:
        return f"std_logic_vector({self.input_bits - 1} downto 0)"

    @property
    def output_type_str(self) -> str:
        return f"std_logic_vector({self.output_bits - 1} downto 0)"

    def get_input_port_declaration(self, entity_name: str) -> list[str]:
        if self.is_complex:
            return [
                f"{entity_name}_0_in_re : in {self.input_type_str}",
                f"{entity_name}_0_in_im : in {self.input_type_str}",
            ]
        else:
            return [f"{entity_name}_0_in : in {self.input_type_str}"]

    def get_output_port_declaration(self, entity_name: str) -> list[str]:
        if self.is_complex:
            return [
                f"{entity_name}_0_out_re : out {self.output_type_str}",
                f"{entity_name}_0_out_im : out {self.output_type_str}",
            ]
        else:
            return [f"{entity_name}_0_out : out {self.output_type_str}"]

    def get_input_port_mapping(self, entity_name: str) -> list[str]:
        if self.is_complex:
            return [
                f"p_0_in_re => {entity_name}_0_in_re",
                f"p_0_in_im => {entity_name}_0_in_im",
            ]
        else:
            return [f"p_0_in => {entity_name}_0_in"]

    def get_output_port_mapping(self, entity_name: str) -> list[str]:
        if self.is_complex:
            return [
                f"p_0_out_re => {entity_name}_0_out_re",
                f"p_0_out_im => {entity_name}_0_out_im",
            ]
        else:
            return [f"p_0_out => {entity_name}_0_out"]

    def _match_unsigned_real(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"unsigned({self.high} downto {self.low})"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_unsigned_complex(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return "complex"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_signed_real(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"signed({self.high} downto {self.low})"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_signed_complex(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return "complex"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_unsigned_real_2008(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"ufixed({self.high} downto {self.low})"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_unsigned_complex_2008(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return "complex"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_signed_real_2008(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"sfixed({self.high} downto {self.low})"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_signed_complex_2008(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return "complex"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError
