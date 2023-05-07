"""
B-ASIC architecture classes.
"""
from collections import defaultdict
from typing import List, Optional, Set, cast

from b_asic.process import MemoryVariable, OperatorProcess, PlainMemoryVariable
from b_asic.resources import ProcessCollection


class ProcessingElement:
    """
    Create a processing element for a ProcessCollection with OperatorProcesses.

    Parameters
    ----------
    process_collection : :class:`~b_asic.resources.ProcessCollection`
        Process collection containing operations to map to processing element.
    entity_name : str, optional
        Name of processing element entity.
    """

    def __init__(
        self, process_collection: ProcessCollection, entity_name: Optional[str] = None
    ):
        if not len(process_collection):
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
            cast(OperatorProcess, operand).operation
            for operand in process_collection.collection
        ]
        op_type = type(ops[0])
        if not all(isinstance(op, op_type) for op in ops):
            raise TypeError("Different Operation types in ProcessCollection")
        self._collection = process_collection
        self._operation_type = op_type
        self._type_name = op_type.type_name()
        self._entity_name = entity_name

    @property
    def processes(self) -> Set[OperatorProcess]:
        return {cast(OperatorProcess, p) for p in self._collection}

    def __repr__(self):
        return self._entity_name or self._type_name

    def set_entity_name(self, entity_name: str):
        self._entity_name = entity_name

    def write_code(self, path: str) -> None:
        """
        Write VHDL code for processing element.

        Parameters
        ----------
        path : str
            Directory to write code in.
        """
        if not self._entity_name:
            raise ValueError("Entity name must be set")
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
    entity_name : str, optional
        Name of memory entity.
    """

    def __init__(
        self,
        process_collection: ProcessCollection,
        memory_type: str = "RAM",
        entity_name: Optional[str] = None,
    ):
        if not len(process_collection):
            raise ValueError("Do not create Memory with empty ProcessCollection")
        if not all(
            isinstance(operator, (MemoryVariable, PlainMemoryVariable))
            for operator in process_collection.collection
        ):
            raise TypeError(
                "Can only have MemoryVariable or PlainMemoryVariable in"
                " ProcessCollection when creating Memory"
            )
        if memory_type not in ("RAM", "register"):
            raise ValueError(
                f"memory_type must be 'RAM' or 'register', not {memory_type!r}"
            )
        self._collection = process_collection
        self._memory_type = memory_type
        self._entity_name = entity_name

    def __iter__(self):
        return iter(self._collection)

    def set_entity_name(self, entity_name: str):
        self._entity_name = entity_name

    def __repr__(self):
        return self._entity_name or self._memory_type

    def write_code(self, path: str) -> None:
        """
        Write VHDL code for memory.

        Parameters
        ----------
        path : str
            Directory to write code in.
        """
        if not self._entity_name:
            raise ValueError("Entity name must be set")
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
    entity_name : str, default: "arch"
        Name for the top-level entity.
    direct_interconnects : ProcessCollection, optional
        Process collection of zero-time memory variables used for direct interconnects.
    """

    def __init__(
        self,
        processing_elements: Set[ProcessingElement],
        memories: Set[Memory],
        entity_name: str = "arch",
        direct_interconnects: Optional[ProcessCollection] = None,
    ):
        self._processing_elements = processing_elements
        self._memories = memories
        self._entity_name = entity_name
        self._direct_interconnects = direct_interconnects
        self._variable_inport_to_resource = {}
        self._variable_outport_to_resource = {}
        self._operation_inport_to_resource = {}
        self._operation_outport_to_resource = {}

        self._build_dicts()

        # Validate input and output ports
        self.validate_ports()

    def _build_dicts(self):
        for pe in self.processing_elements:
            for operator in pe.processes:
                for input_port in operator.operation.inputs:
                    self._operation_inport_to_resource[input_port] = pe
                for output_port in operator.operation.outputs:
                    self._operation_outport_to_resource[output_port] = pe

        for memory in self.memories:
            for mv in memory:
                mv = cast(MemoryVariable, mv)
                for read_port in mv.read_ports:
                    self._variable_inport_to_resource[read_port] = memory
                self._variable_outport_to_resource[mv.write_port] = memory
        if self._direct_interconnects:
            for di in self._direct_interconnects:
                di = cast(MemoryVariable, di)
                for read_port in di.read_ports:
                    self._variable_inport_to_resource[
                        read_port
                    ] = self._operation_outport_to_resource[di.write_port]
                    self._variable_outport_to_resource[
                        di.write_port
                    ] = self._operation_inport_to_resource[read_port]

    def validate_ports(self):
        # Validate inputs and outputs of memory variables in all the memories in this architecture
        memory_read_ports = set()
        memory_write_ports = set()
        for memory in self.memories:
            for mv in memory:
                mv = cast(MemoryVariable, mv)
                memory_write_ports.add(mv.write_port)
                memory_read_ports.update(mv.read_ports)
        if self._direct_interconnects:
            for mv in self._direct_interconnects:
                mv = cast(MemoryVariable, mv)
                memory_write_ports.add(mv.write_port)
                memory_read_ports.update(mv.read_ports)

        pe_input_ports = set()
        pe_output_ports = set()
        for pe in self.processing_elements:
            for operator in pe.processes:
                pe_input_ports.update(operator.operation.inputs)
                pe_output_ports.update(operator.operation.outputs)

        read_port_diff = memory_read_ports.symmetric_difference(pe_input_ports)
        write_port_diff = memory_write_ports.symmetric_difference(pe_output_ports)
        if read_port_diff:
            raise ValueError(
                "Memory read port and PE output port difference:"
                f" {[port.name for port in read_port_diff]}"
            )
        if write_port_diff:
            raise ValueError(
                "Memory read port and PE output port difference:"
                f" {[port.name for port in write_port_diff]}"
            )
        # Make sure all inputs and outputs in the architecture are in use

    def write_code(self, path: str) -> None:
        """
        Write HDL of architecture.

        Parameters
        ----------
        path : str
            Directory to write code in.
        """
        raise NotImplementedError

    def get_interconnects_for_memory(self, mem: Memory):
        d_in = defaultdict(lambda: 0)
        d_out = defaultdict(lambda: 0)
        for var in mem._collection:
            var = cast(MemoryVariable, var)
            d_in[self._operation_outport_to_resource[var.write_port]] += 1
            for read_port in var.read_ports:
                d_out[self._operation_inport_to_resource[read_port]] += 1
        return dict(d_in), dict(d_out)

    def get_interconnects_for_pe(self, pe: ProcessingElement):
        ops = cast(List[OperatorProcess], list(pe._collection))
        d_in = [defaultdict(lambda: 0) for _ in ops[0].operation.inputs]
        d_out = [defaultdict(lambda: 0) for _ in ops[0].operation.outputs]
        for var in pe._collection:
            var = cast(OperatorProcess, var)
            for i, input in enumerate(var.operation.inputs):
                d_in[i][self._variable_inport_to_resource[input]] += 1
            for i, output in enumerate(var.operation.outputs):
                d_out[i][self._variable_outport_to_resource[output]] += 1
        return [dict(d) for d in d_in], [dict(d) for d in d_out]

    def set_entity_name(self, entity_name: str):
        self._entity_name = entity_name

    @property
    def memories(self) -> Set[Memory]:
        return self._memories

    @property
    def processing_elements(self) -> Set[ProcessingElement]:
        return self._processing_elements

    @property
    def direct_interconnects(self) -> Optional[ProcessCollection]:
        return self._direct_interconnects
