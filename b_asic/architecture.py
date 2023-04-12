"""
B-ASIC architecture classes.
"""
from typing import Set, cast

from b_asic.process import MemoryVariable, OperatorProcess, PlainMemoryVariable
from b_asic.resources import ProcessCollection


class ProcessingElement:
    """
    Create a processing element for a ProcessCollection with OperatorProcesses.

    Parameters
    ----------
    process_collection : :class:`~b_asic.resources.ProcessCollection`
    """

    def __init__(self, process_collection: ProcessCollection):
        if not len(ProcessCollection):
            raise ValueError(
                "Do not create ProcessingElement with empty ProcessCollection"
            )
        if not all(
            isinstance(operator, OperatorProcess)
            for operator in process_collection.collection
        ):
            raise TypeError(
                "Can only have OperatorProcesses in ProcessCollection when creating"
                " ProcessingElement"
            )
        ops = [
            cast(operand, OperatorProcess).operation
            for operand in process_collection.collection
        ]
        op_type = type(ops[0])
        if not all(isinstance(op, op_type) for op in ops):
            raise TypeError("Different Operation types in ProcessCollection")
        self._collection = process_collection
        self._operation_type = op_type
        self._type_name = op_type.type_name()

    def write_code(self, path: str, entity_name: str) -> None:
        """
        Write VHDL code for processing element.

        Parameters
        ----------
        path : str
            Directory to write code in.
        entity_name : str
        """
        raise NotImplementedError


class Memory:
    """
    Create a memory from a ProcessCollection with memory variables.

    Parameters
    ----------
    process_collection : :class:`~b_asic.resources.ProcessCollection`
        The ProcessCollection to create a Memory for.
    memory_type : {'RAM', 'register'}
        The type of memory.
    """

    def __init__(self, process_collection: ProcessCollection, memory_type: str = "RAM"):
        if not len(ProcessCollection):
            raise ValueError("Do not create Memory with empty ProcessCollection")
        if not all(
            isinstance(operator, (MemoryVariable, PlainMemoryVariable))
            for operator in process_collection.collection
        ):
            raise TypeError(
                "Can only have MemoryVariable or PlainMemoryVariable in"
                " ProcessCollection when creating Memory"
            )
        self._collection = process_collection
        self._memory_type = memory_type

    def write_code(self, path: str, entity_name: str) -> None:
        """
        Write VHDL code for memory.

        Parameters
        ----------
        path : str
            Directory to write code in.
        entity_name : str

        Returns
        -------


        """
        raise NotImplementedError


class Architecture:
    """
    Class representing an architecture.

    Parameters
    ----------
    processing_elements : set of :class:`~b_asic.architecture.ProcessingElement`
        The processing elements in the architecture.
    memories : set of :class:`~b_asic.architecture.Memory`
        The memories in the architecture.
    name : str, default: "arch"
        Name for the top-level architecture. Used for the entity and as prefix for all
        building blocks.
    """

    def __init__(
        self,
        processing_elements: Set[ProcessingElement],
        memories: Set[Memory],
        name: str = "arch",
    ):
        self._processing_elements = processing_elements
        self._memories = memories
        self._name = name

    def write_code(self, path: str) -> None:
        """
        Write HDL of architecture.

        Parameters
        ----------
        path : str
            Directory to write code in.
        """
        raise NotImplementedError
