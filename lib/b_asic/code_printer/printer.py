"""
Module for generating code for described architectures.
"""

import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from b_asic.data_type import DataType, NumRepresentation

if TYPE_CHECKING:
    from b_asic.architecture import Architecture, Memory, ProcessingElement


class Printer(ABC):
    CUSTOM_PRINTER_PREFIX = "generic"

    def __init__(self, dt: DataType) -> None:
        self.set_data_type(dt)

    @abstractmethod
    def print(
        self, arch: "Architecture", *, path: str | Path = Path(), **kwargs
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def print_Architecture(self, arch: "Architecture", **kwargs) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def print_Memory(self, mem: "Memory", **kwargs) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def print_ProcessingElement(self, pe: "ProcessingElement", **kwargs) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def print_default(self, **kwargs) -> tuple[str, ...] | None:
        raise NotImplementedError

    def print_operation(self, pe: "ProcessingElement") -> tuple[str, ...]:
        type_suffix = f"_{self.num_repr()}_{'complex' if self.is_complex else 'real'}"
        fname = f"print_{pe.operation_type.__name__}{type_suffix}"
        if hasattr(self, fname):
            return getattr(self, fname)(pe)
        fname = f"print_{pe.operation_type.__name__}"
        if hasattr(self, fname):
            return getattr(self, fname)(pe)
        fname = f"{self.CUSTOM_PRINTER_PREFIX}{type_suffix}"
        if hasattr(self, fname):
            return getattr(pe, fname)(pe, self._dt)
        if hasattr(pe, self.CUSTOM_PRINTER_PREFIX):
            return getattr(pe, self.CUSTOM_PRINTER_PREFIX)(pe, self._dt)
        warnings.warn(
            f"No printing function found for {pe.operation_type.__name__} and the provided data type.\nThe resulting files are not complete.",
            stacklevel=2,
        )
        return self.print_default()

    def print_quantization(self, wls: list[tuple[int, int]]) -> tuple[str, ...]:
        type_suffix = f"_{self.num_repr()}_{'complex' if self.is_complex else 'real'}"
        fname = f"print_{self._dt.quantization_mode.name}{type_suffix}"
        if hasattr(self, fname):
            return getattr(self, fname)(wls)
        return ("", "")

    def print_overflow(self, wls: list[tuple[int, int]]) -> tuple[str, ...]:
        fname = f"print_{self._dt.overflow_mode.name}"
        if hasattr(self, fname):
            return getattr(self, fname)(wls)
        return ("", "")

    def num_repr(self) -> str:
        return self._dt.num_repr.name.lower()

    @property
    def is_real(self) -> bool:
        return not self._dt.is_complex

    @property
    def is_complex(self) -> bool:
        return self._dt.is_complex

    def set_data_type(self, dt: DataType):
        self._dt = dt

    @property
    def type_str(self):
        return self._dt.type_str

    @property
    def int_bits(self) -> int:
        if self._dt.num_repr == NumRepresentation.FIXED_POINT:
            return self._dt.wl[0]
        raise TypeError("Only fixed-point data types has integer bits")

    @property
    def frac_bits(self) -> int:
        if self._dt.num_repr == NumRepresentation.FIXED_POINT:
            return self._dt.wl[1]
        raise TypeError("Only fixed-point data types has fractional bits")

    @property
    def exp_bits(self) -> int:
        if self._dt.num_repr == NumRepresentation.FLOATING_POINT:
            return self._dt.wl[0]
        raise TypeError("Only floating-point data types has exponent bits")

    @property
    def man_bits(self) -> int:
        if self._dt.num_repr == NumRepresentation.FLOATING_POINT:
            return self._dt.wl[1]
        raise TypeError("Only floating-point data types has mantissa bits")

    @property
    def bits(self) -> int:
        return self._dt.bits
