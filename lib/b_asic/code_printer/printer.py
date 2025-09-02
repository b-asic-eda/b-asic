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

    def print_operation(self, pe: "ProcessingElement") -> tuple[str, str]:
        return getattr(
            self,
            f"print_{pe.operation_type.__name__}_{self._dt.num_repr.name.lower()}_{'complex' if self._dt.is_complex else 'real'}",
            getattr(self, f"print_{pe.operation_type.__name__}", self.print_default),
        )(pe)

    def set_data_type(self, dt: DataType):
        self._dt = dt
