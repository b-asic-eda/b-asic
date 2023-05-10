"""
B-ASIC architecture classes.
"""
from collections import defaultdict
from io import TextIOWrapper
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple, Union, cast

import matplotlib.pyplot as plt
from graphviz import Digraph

from b_asic.mpl_utils import FigureWrapper
from b_asic.port import InputPort, OutputPort
from b_asic.process import MemoryVariable, OperatorProcess, PlainMemoryVariable
from b_asic.resources import ProcessCollection


def _interconnect_dict() -> int:
    # Needed as pickle does not support lambdas
    return 0


class HardwareBlock:
    """
    Base class for architectures and resources.

    Parameters
    ----------
    entity_name : str, optional
        The name of the resulting entity.
    """

    def __init__(self, entity_name: Optional[str] = None):
        self._entity_name = None
        if entity_name is not None:
            self.set_entity_name(entity_name)

    def set_entity_name(self, entity_name: str):
        """
        Set entity name of hardware block.

        Parameters
        ----------
        entity_name : str
            The entity name.
        """
        # Should be a better check.
        # See https://stackoverflow.com/questions/7959587/regex-for-vhdl-identifier
        if " " in entity_name:
            raise ValueError("Cannot have space in entity name")
        self._entity_name = entity_name

    def write_code(self, path: str) -> None:
        """
        Write VHDL code for hardware block.

        Parameters
        ----------
        path : str
            Directory to write code in.
        """
        if not self._entity_name:
            raise ValueError("Entity name must be set")
        raise NotImplementedError

    def _repr_mimebundle_(self, include=None, exclude=None):
        return self._digraph()._repr_mimebundle_(include=include, exclude=exclude)

    def _repr_jpeg_(self):
        return self._digraph()._repr_mimebundle_(include=["image/jpeg"])["image/jpeg"]

    def _repr_png_(self):
        return self._digraph()._repr_mimebundle_(include=["image/png"])["image/png"]

    @property
    def entity_name(self) -> str:
        if self._entity_name is None:
            return "Undefined entity name"
        return self._entity_name

    def _digraph(self) -> Digraph:
        raise NotImplementedError()

    @property
    def schedule_time(self) -> int:
        """The schedule time for hardware block"""
        raise NotImplementedError()

    def write_component_declaration(self, f: TextIOWrapper, indent: int = 1) -> None:
        """
        Write component declaration of hardware block.

        Parameters
        ----------
        f : TextIOWrapper
            File object (or other TextIOWrapper object) to write the declaration to.
        indent : int, default: 1
            Indentation level to use for this process.
        """
        raise NotImplementedError()

    def write_component_instantiation(self, f: TextIOWrapper, indent: int = 1) -> None:
        """
        Write component instantiation of hardware block.

        Parameters
        ----------
        f : TextIOWrapper
            File object (or other TextIOWrapper object) to write the instantiation to.
        indent : int, default: 1
            Indentation level to use for this process.
        """
        raise NotImplementedError()


class Resource(HardwareBlock):
    """
    Base class for resource.

    Parameters
    ----------
    process_collection : :class:`~b_asic.resources.ProcessCollection`
        The process collection containing processes to be mapped to resource.
    entity_name : str, optional
        The name of the resulting entity.

    """

    def __init__(
        self, process_collection: ProcessCollection, entity_name: Optional[str] = None
    ):
        if not len(process_collection):
            raise ValueError("Do not create Resource with empty ProcessCollection")
        super().__init__(entity_name=entity_name)
        self._collection = process_collection
        self._input_count = -1
        self._output_count = -1
        self._assignment: Optional[List[ProcessCollection]] = None

    def __repr__(self):
        return self.entity_name

    def __iter__(self):
        return iter(self._collection)

    def _digraph(self) -> Digraph:
        dg = Digraph(node_attr={'shape': 'record'})
        dg.node(self.entity_name, self._struct_def())
        return dg

    @property
    def input_count(self) -> int:
        """Number of input ports."""
        return self._input_count

    @property
    def output_count(self) -> int:
        """Number of output ports."""
        return self._output_count

    def _struct_def(self) -> str:
        inputs = [f"in{i}" for i in range(self._input_count)]
        outputs = [f"out{i}" for i in range(self._output_count)]
        ret = ""
        if inputs:
            instrs = [f"<{instr}> {instr}" for instr in inputs]
            ret += f"{{{'|'.join(instrs)}}}|"
        ret += f"{self.entity_name}"
        if outputs:
            outstrs = [f"<{outstr}> {outstr}" for outstr in outputs]
            ret += f"|{{{'|'.join(outstrs)}}}"
        return "{" + ret + "}"

    @property
    def schedule_time(self) -> int:
        # doc-string inherited
        return self._collection.schedule_time

    def plot_content(self, ax: plt.Axes) -> None:
        if not self.is_assigned:
            self._collection.plot(ax)
        else:
            for i, pc in enumerate(self._assignment):  # type: ignore
                pc.plot(ax=ax, row=i)

    def show_content(self):
        fig, ax = plt.subplots()
        self.plot_content(ax)
        fig.show()  # type: ignore

    @property
    def is_assigned(self) -> bool:
        return self._assignment is not None

    @property
    def content(self) -> FigureWrapper:
        """
        Return a graphical representation of the content.

        This is visible in enriched shells, but the object in itself has no further
        meaning.
        """
        fig, ax = plt.subplots()
        self.plot_content(ax)
        return FigureWrapper(fig)


class ProcessingElement(Resource):
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
        super().__init__(process_collection=process_collection, entity_name=entity_name)
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
        self._input_count = ops[0].input_count
        self._output_count = ops[0].output_count
        self._assignment = list(
            self._collection.split_on_execution_time(heuristic="left_edge")
        )
        if len(self._assignment) > 1:
            raise ValueError("Cannot map ProcessCollection to single ProcessingElement")

    @property
    def processes(self) -> Set[OperatorProcess]:
        return {cast(OperatorProcess, p) for p in self._collection}


class Memory(Resource):
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
    read_ports : int, optional
        Number of read ports for memory.
    write_ports : int, optional
        Number of write ports for memory.
    """

    def __init__(
        self,
        process_collection: ProcessCollection,
        memory_type: str = "RAM",
        entity_name: Optional[str] = None,
        read_ports: Optional[int] = None,
        write_ports: Optional[int] = None,
    ):
        super().__init__(process_collection=process_collection, entity_name=entity_name)
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
        read_ports_bound = self._collection.read_ports_bound()
        if read_ports is None:
            self._output_count = read_ports_bound
        else:
            if read_ports < read_ports_bound:
                raise ValueError(f"At least {read_ports_bound} read ports required")
            self._output_count = read_ports
        write_ports_bound = self._collection.write_ports_bound()
        if write_ports is None:
            self._input_count = write_ports_bound
        else:
            if write_ports < write_ports_bound:
                raise ValueError(f"At least {write_ports_bound} write ports required")
            self._input_count = write_ports
        self._memory_type = memory_type

    def __iter__(self) -> Iterator[MemoryVariable]:
        # Add information about the iterator type
        return cast(Iterator[MemoryVariable], iter(self._collection))

    def _assign_ram(self, heuristic: str = "left_edge"):
        """
        Perform RAM-type assignment of MemoryVariables in this Memory.

        Parameters
        ----------
        heuristic : {'left_edge', 'graph_color'}
            The underlying heuristic to use when performing RAM assignment.
        """
        self._assignment = list(
            self._collection.split_on_execution_time(heuristic=heuristic)
        )


class Architecture(HardwareBlock):
    """
    Class representing an architecture.

    Parameters
    ----------
    processing_elements : :class:`~b_asic.architecture.ProcessingElement` or iterable \
of :class:`~b_asic.architecture.ProcessingElement`
        The processing elements in the architecture.
    memories : :class:`~b_asic.architecture.Memory` or iterable of \
:class:`~b_asic.architecture.Memory`
        The memories in the architecture.
    entity_name : str, default: "arch"
        Name for the top-level entity.
    direct_interconnects : :class:`~b_asic.resources.ProcessCollection`, optional
        Process collection of zero-time memory variables used for direct interconnects.
    """

    def __init__(
        self,
        processing_elements: Union[ProcessingElement, Iterable[ProcessingElement]],
        memories: Union[Memory, Iterable[Memory]],
        entity_name: str = "arch",
        direct_interconnects: Optional[ProcessCollection] = None,
    ):
        super().__init__(entity_name)
        self._processing_elements = (
            set(processing_elements)
            if isinstance(processing_elements, ProcessingElement)
            else processing_elements
        )
        self._memories = set(memories) if isinstance(memories, Memory) else memories
        self._direct_interconnects = direct_interconnects
        self._variable_inport_to_resource: Dict[InputPort, Tuple[Resource, int]] = {}
        self._variable_outport_to_resource: Dict[OutputPort, Tuple[Resource, int]] = {}
        self._operation_inport_to_resource: Dict[InputPort, Resource] = {}
        self._operation_outport_to_resource: Dict[OutputPort, Resource] = {}

        self._schedule_time = self._check_and_get_schedule_time()

        # Validate input and output ports
        self.validate_ports()

        self._build_dicts()

    def _check_and_get_schedule_time(self) -> int:
        schedule_times = set()
        for memory in self._memories:
            schedule_times.add(memory.schedule_time)
        for pe in self._processing_elements:
            schedule_times.add(pe.schedule_time)
        if self._direct_interconnects is not None:
            schedule_times.add(self._direct_interconnects.schedule_time)
        if len(schedule_times) != 1:
            raise ValueError(f"Different schedule times: {schedule_times}")
        return schedule_times.pop()

    def _build_dicts(self):
        for pe in self.processing_elements:
            for operator in pe.processes:
                for input_port in operator.operation.inputs:
                    self._operation_inport_to_resource[input_port] = pe
                for output_port in operator.operation.outputs:
                    self._operation_outport_to_resource[output_port] = pe

        for memory in self.memories:
            for mv in memory:
                for read_port in mv.read_ports:
                    self._variable_inport_to_resource[read_port] = (memory, 0)  # Fix
                self._variable_outport_to_resource[mv.write_port] = (memory, 0)  # Fix
        if self._direct_interconnects:
            for di in self._direct_interconnects:
                di = cast(MemoryVariable, di)
                for read_port in di.read_ports:
                    self._variable_inport_to_resource[read_port] = (
                        self._operation_outport_to_resource[di.write_port],
                        di.write_port.index,
                    )
                    self._variable_outport_to_resource[di.write_port] = (
                        self._operation_inport_to_resource[read_port],
                        read_port.index,
                    )

    def validate_ports(self):
        # Validate inputs and outputs of memory variables in all the memories in this
        # architecture
        memory_read_ports = set()
        memory_write_ports = set()
        for memory in self.memories:
            for mv in memory:
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

    def get_interconnects_for_memory(self, mem: Memory):
        """
        Return a dictionary with interconnect information for a Memory.

        Parameters
        ----------
        mem : :class:`Memory`
            The memory to obtain information about.

        Returns
        -------
        (dict, dict)
            A dictionary with the ProcessingElements that are connected to the write and
            read ports, respectively, with counts of the number of accesses.
        """
        d_in = defaultdict(_interconnect_dict)
        d_out = defaultdict(_interconnect_dict)
        for var in mem._collection:
            var = cast(MemoryVariable, var)
            d_in[self._operation_outport_to_resource[var.write_port]] += 1
            for read_port in var.read_ports:
                d_out[self._operation_inport_to_resource[read_port]] += 1
        return dict(d_in), dict(d_out)

    def get_interconnects_for_pe(
        self, pe: ProcessingElement
    ) -> Tuple[
        List[Dict[Tuple[Resource, int], int]], List[Dict[Tuple[Resource, int], int]]
    ]:
        """
        Return lists of dictionaries with interconnect information for a
        ProcessingElement.

        Parameters
        ----------
        pe : :class:`ProcessingElement`
            The processing element to get information for.

        Returns
        -------
        list
            List of dictionaries indicating the sources for each inport and the
            frequency of accesses.
        list
            List of dictionaries indicating the sources for each outport and the
            frequency of accesses.

        """
        ops = cast(List[OperatorProcess], list(pe._collection))
        d_in = [defaultdict(_interconnect_dict) for _ in ops[0].operation.inputs]
        d_out = [defaultdict(_interconnect_dict) for _ in ops[0].operation.outputs]
        for var in pe._collection:
            var = cast(OperatorProcess, var)
            for i, input in enumerate(var.operation.inputs):
                d_in[i][self._variable_inport_to_resource[input]] += 1
            for i, output in enumerate(var.operation.outputs):
                d_out[i][self._variable_outport_to_resource[output]] += 1
        return [dict(d) for d in d_in], [dict(d) for d in d_out]

    def _digraph(self) -> Digraph:
        edges = set()
        dg = Digraph(node_attr={'shape': 'record'})
        # dg.attr(rankdir="LR")
        for i, mem in enumerate(self._memories):
            dg.node(mem.entity_name, mem._struct_def())
        for i, pe in enumerate(self._processing_elements):
            dg.node(pe.entity_name, pe._struct_def())
        for pe in self._processing_elements:
            inputs, outputs = self.get_interconnects_for_pe(pe)
            for i, inp in enumerate(inputs):
                for (source, port), cnt in inp.items():
                    edges.add(
                        (
                            f"{source.entity_name}:out{port}",
                            f"{pe.entity_name}:in{i}",
                            f"{cnt}",
                        )
                    )
            for o, outp in enumerate(outputs):
                for (dest, port), cnt in outp.items():
                    edges.add(
                        (
                            f"{pe.entity_name}:out{o}",
                            f"{dest.entity_name}:in{port}",
                            f"{cnt}",
                        )
                    )
        for src, dest, cnt in edges:
            dg.edge(src, dest, label=cnt)
        return dg

    @property
    def memories(self) -> Iterable[Memory]:
        return self._memories

    @property
    def processing_elements(self) -> Iterable[ProcessingElement]:
        return self._processing_elements

    @property
    def direct_interconnects(self) -> Optional[ProcessCollection]:
        return self._direct_interconnects

    @property
    def schedule_time(self) -> int:
        # doc-string inherited
        return self._schedule_time
