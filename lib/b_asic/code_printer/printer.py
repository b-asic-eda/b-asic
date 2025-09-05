"""
Module for generating code for described architectures.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from b_asic.data_type import DataType

if TYPE_CHECKING:
    from b_asic.architecture import Architecture, Memory, ProcessingElement


class Printer(ABC):
    def __init__(self, dt: DataType) -> None:
        self.set_data_type(dt)

    @abstractmethod
    def print(self, path: str, arch: "Architecture", **kwargs) -> None:
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
    def print_default(self, **kwargs) -> str | None:
        raise NotImplementedError

    def print_operation(self, pe: "ProcessingElement") -> tuple[str, str]:
        fname = f"print_{pe.operation_type.__name__}_{self.num_repr()}_{'complex' if self._dt.is_complex else 'real'}"
        if hasattr(self, fname):
            return getattr(self, fname)(pe)
        fname = f"print_{pe.operation_type.__name__}"
        if hasattr(self, fname):
            return getattr(self, fname)(pe)
        if hasattr(pe, self.CUSTOM_FUNC):
            return getattr(pe, self.CUSTOM_FUNC)(pe)
        # warning, using default printer
        return self.print_default()

    def num_repr(self) -> str:
        return self._dt.num_repr.name.lower()

    def set_data_type(self, dt: DataType):
        self._dt = dt
