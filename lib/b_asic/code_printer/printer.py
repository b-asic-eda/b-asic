"""
Module for generating code for described architectures.
"""

import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from b_asic.data_type import DataType

if TYPE_CHECKING:
    from b_asic.architecture import Architecture, Memory, ProcessingElement

WLS = list[tuple[int, int]]
CODE = tuple[str, ...]


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
    def print_default(self, **kwargs) -> tuple[WLS, CODE]:
        raise NotImplementedError

    def print_operation(self, pe: "ProcessingElement") -> CODE:
        """Find and call the appropriate print method for the operation and apply casts per output signal."""
        type_suffix = f"_{self.num_repr()}_{'complex' if self.is_complex else 'real'}"
        fname = f"print_{pe.operation_type.__name__}{type_suffix}"
        # Try to find a printer method specific to the operation type and data type
        if hasattr(self, fname):
            wls, arith_code = getattr(self, fname)(pe)
        else:
            # If that fails, try to find a generic printer method for the operation
            fname = f"print_{pe.operation_type.__name__}"
            if hasattr(self, fname):
                wls, arith_code = getattr(self, fname)(pe)
            else:
                # If that fails, try to find a print method given by the operation and data type
                fname = f"{self.CUSTOM_PRINTER_PREFIX}{type_suffix}"
                if hasattr(self, fname):
                    wls, arith_code = getattr(pe._operation_type, fname)(pe)
                # If that fails, try to find a print method given by the operation
                elif hasattr(pe.operation_type, self.CUSTOM_PRINTER_PREFIX):
                    wls, arith_code = getattr(
                        pe.operation_type, self.CUSTOM_PRINTER_PREFIX
                    )(pe, self._dt)
                else:
                    warnings.warn(
                        f"No printing function found for {pe.operation_type.__name__} and the provided data type.\nThe resulting files are not complete.",
                        stacklevel=2,
                    )
                    wls, arith_code = self.print_default()
        result = list(arith_code)

        # Apply casts for each output signal, if necessary.
        for i, wl in enumerate(wls):
            cast_code = self.print_cast(wl, i, pe)
            result = [r + c for r, c in zip(result, cast_code, strict=True)]
        return tuple(result)

    @abstractmethod
    def print_cast(
        self, wl: tuple[int, int], port_number: int, pe: "ProcessingElement"
    ) -> CODE:
        """Generate quantization and overflow code for a single output signal."""
        raise NotImplementedError

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
        return self._dt.int_bits

    @property
    def frac_bits(self) -> int:
        return self._dt.frac_bits

    @property
    def exp_bits(self) -> int:
        return self._dt.exp_bits

    @property
    def man_bits(self) -> int:
        return self._dt.man_bits

    @property
    def bits(self) -> int:
        return self._dt.bits
