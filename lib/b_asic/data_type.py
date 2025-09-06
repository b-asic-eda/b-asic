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
    def internal_low(self) -> int:
        return 0

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

    def get_scalar_type_str(self) -> str:
        if self.is_complex:
            if self.vhdl_2008:
                vhdl_type = "sfixed" if self.is_signed else "ufixed"
            else:
                vhdl_type = "signed" if self.is_signed else "unsigned"
            return f"{vhdl_type}({self.internal_high} downto {self.internal_low})"
        else:
            return self.get_type_str()

    def get_input_type_str(self) -> str:
        return f"std_logic_vector({self.input_length - 1} downto 0)"

    def get_output_type_str(self) -> str:
        return f"std_logic_vector({self.output_length - 1} downto 0)"

    def get_init_val(self) -> str:
        if self.is_complex:
            return "(re => (others => '0'), im => (others => '0'))"
        else:
            return "(others => '0')"

    def get_dontcare_str(self) -> str:
        if self.is_complex:
            return "(re => (others => '-'), im => (others => '-'))"
        else:
            return "(others => '-')"

    def get_input_port_declaration(self, entity_name: str) -> list[str]:
        if self.is_complex:
            return [
                f"{entity_name}_0_in_re : in {self.get_input_type_str()}",
                f"{entity_name}_0_in_im : in {self.get_input_type_str()}",
            ]
        else:
            return [f"{entity_name}_0_in : in {self.get_input_type_str()}"]

    def get_output_port_declaration(self, entity_name: str) -> list[str]:
        if self.is_complex:
            return [
                f"{entity_name}_0_out_re : out {self.get_output_type_str()}",
                f"{entity_name}_0_out_im : out {self.get_output_type_str()}",
            ]
        else:
            return [f"{entity_name}_0_out : out {self.get_output_type_str()}"]

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
                return f"unsigned({self.internal_high} downto {self.internal_low})"
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
                return f"signed({self.internal_high} downto {self.internal_low})"
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
                return f"ufixed({self.internal_high} downto {self.internal_low})"
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
                return f"sfixed({self.internal_high} downto {self.internal_low})"
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
