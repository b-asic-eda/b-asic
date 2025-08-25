"""
Module for generating code for described architectures.
"""

from abc import ABC, abstractmethod

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.data_type import DataType


class Printer(ABC):
    def __init__(self, dt: DataType) -> None:
        self.set_data_type(dt)

    @abstractmethod
    def print(self, path: str, arch: Architecture, **kwargs) -> None:
        raise NotImplementedError

    @abstractmethod
    def print_Architecture(self, arch: Architecture, **kwargs) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def print_Memory(self, mem: Memory, **kwargs) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def print_ProcessingElement(self, pe: ProcessingElement, **kwargs) -> str | None:
        raise NotImplementedError

    def set_data_type(self, dt: DataType):
        self._dt = dt
