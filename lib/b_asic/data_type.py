"""
B-ASIC Data Type Module.
"""

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum, auto


class NumRepresentation(Enum):
    FIXED_POINT = auto()
    FLOATING_POINT = auto()


@dataclass
class DataType:
    internal_wl: tuple[int, int]
    input_wl: tuple[int, int] | None = None
    output_wl: tuple[int, int] | None = None
    num_repr: NumRepresentation = NumRepresentation.FIXED_POINT
    is_signed: bool = True
    is_complex: bool = False

    def __post_init__(self):
        if isinstance(self.internal_wl, int):
            self.internal_wl = (1, self.internal_wl - 1)
        if isinstance(self.input_wl, int):
            self.input_wl = (1, self.input_wl - 1)
        if isinstance(self.output_wl, int):
            self.output_wl = (1, self.output_wl - 1)

        if self.input_wl is None:
            self.input_wl = self.internal_wl
        if self.output_wl is None:
            self.output_wl = self.internal_wl

    @abstractmethod
    def get_type_str(self) -> str:
        raise NotImplementedError

    @property
    def internal_length(self) -> int:
        return sum(self.internal_wl)

    @property
    def internal_high(self) -> int:
        return sum(self.internal_wl) - 1

    @property
    def input_high(self) -> int:
        return sum(self.input_wl) - 1

    @property
    def output_high(self) -> int:
        return sum(self.output_wl) - 1


@dataclass
class VhdlDataType(DataType):
    vhdl_2008: bool = True

    def get_type_str(self) -> str:
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

    def get_input_type_str(self) -> str:
        return f"std_logic_vector({self.input_high()} downto 0)"

    def get_output_type_str(self) -> str:
        return f"std_logic_vector({self.output_high()} downto 0)"

    def _match_unsigned_real(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"unsigned({self.w1 - 1} downto -{self.w0 - 1})"
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
                return f"signed({self.w0 + self.w1 - 1} downto 0)"
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
                return f"ufixed({self.w1 - 1} downto -{self.w0 - 1})"
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
                return f"sfixed({self.w1 - 1} downto -{self.w0 - 1})"
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
