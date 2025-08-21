"""
B-ASIC Data Type Module.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto


class NumRepresentation(Enum):
    FIXED_POINT = auto()
    FLOATING_POINT = auto()


@dataclass
class DataType(ABC):
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
        return self.internal_length - 1

    @property
    @abstractmethod
    def internal_low(self) -> int:
        raise NotImplementedError()

    @property
    def input_length(self) -> int:
        return sum(self.input_wl)

    @property
    def input_high(self) -> int:
        return self.input_length - 1

    @property
    def output_length(self) -> int:
        return sum(self.output_wl)

    @property
    def output_high(self) -> int:
        return self.output_length - 1


@dataclass
class VhdlDataType(DataType):
    vhdl_2008: bool = False

    # @property
    # def internal_high(self) -> int:
    #     _HIGH_LUT = {
    #         (0, 0): sum(self.internal_wl) - 1,
    #         (0, 1): 2*sum(self.internal_wl) - 1,
    #         (1, 0): self.internal_wl[0] - 1,
    #         (1, 1): 2*sum(self.internal_wl) - 1,
    #     }
    #     return _HIGH_LUT[(self.vhdl_2008, self.is_complex)]

    @property
    def internal_low(self) -> int:
        _LOW_LUT = {
            (0, 0): 0,
            (0, 1): 0,
            (1, 0): -self.internal_wl[1],
            (1, 1): 0,
        }
        return _LOW_LUT[(self.vhdl_2008, self.is_complex)]

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
        if self.is_complex:
            return f"std_logic_vector({2 * self.input_length - 1} downto 0)"
        else:
            return f"std_logic_vector({self.input_length - 1} downto 0)"

    def get_output_type_str(self) -> str:
        if self.is_complex:
            return f"std_logic_vector({2 * self.output_length - 1} downto 0)"
        else:
            return f"std_logic_vector({self.output_length - 1} downto 0)"

    def _match_unsigned_real(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"unsigned({self.internal_high} downto {self.internal_low})"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_unsigned_complex(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"std_logic_vector({2 * self.internal_length - 1} downto {self.internal_low})"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_signed_real(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"signed({self.internal_high} downto {self.internal_low})"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_signed_complex(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"std_logic_vector({2 * self.internal_length - 1} downto {self.internal_low})"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_unsigned_real_2008(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"ufixed({self.internal_high} downto {self.internal_low})"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_unsigned_complex_2008(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"std_logic_vector({2 * self.internal_length - 1} downto {self.internal_low})"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_signed_real_2008(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"sfixed({self.internal_high} downto {self.internal_low})"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError

    def _match_signed_complex_2008(self):
        match self.num_repr:
            case NumRepresentation.FIXED_POINT:
                return f"std_logic_vector({2 * self.internal_length - 1} downto {self.internal_low})"
            case NumRepresentation.FLOATING_POINT:
                raise NotImplementedError
            case _:
                raise ValueError
