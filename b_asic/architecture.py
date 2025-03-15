"""
B-ASIC architecture classes.
"""

import math
from collections import defaultdict
from collections.abc import Iterable, Iterator
from io import TextIOWrapper
from itertools import chain
from typing import (
    DefaultDict,
    Literal,
    cast,
)

import matplotlib.pyplot as plt
from graphviz import Digraph

from b_asic._preferences import (
    IO_CLUSTER_COLOR,
    IO_COLOR,
    MEMORY_CLUSTER_COLOR,
    MEMORY_COLOR,
    MUX_COLOR,
    PE_CLUSTER_COLOR,
    PE_COLOR,
)
from b_asic.codegen.vhdl.common import is_valid_vhdl_identifier
from b_asic.operation import Operation
from b_asic.port import InputPort, OutputPort
from b_asic.process import MemoryProcess, MemoryVariable, OperatorProcess, Process
from b_asic.resources import ProcessCollection, _sanitize_port_option


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

    __slots__ = "_entity_name"
    _entity_name: str | None

    __slots__ = "_entity_name"
    _entity_name: str | None

    def __init__(self, entity_name: str | None = None):
        self._entity_name: str | None = None
        if entity_name is not None:
            self.set_entity_name(entity_name)

    def set_entity_name(self, entity_name: str) -> None:
        """
        Set entity name of hardware block.

        Parameters
        ----------
        entity_name : str
            The entity name.
        """
        if not is_valid_vhdl_identifier(entity_name):
            raise ValueError(f'{entity_name} is not a valid VHDL identifier')
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

    def _repr_svg_(self):
        return self._digraph()._repr_mimebundle_(include=["image/svg+xml"])[
            "image/svg+xml"
        ]

    _repr_html_ = _repr_svg_

    @property
    def entity_name(self) -> str:
        if self._entity_name is None:
            return "Undefined entity name"
        return self._entity_name

    def _digraph(self) -> Digraph:
        raise NotImplementedError()

    @property
    def schedule_time(self) -> int:
        """The schedule time for hardware block."""
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
        self, process_collection: ProcessCollection, entity_name: str | None = None
    ):
        if not len(process_collection):
            raise ValueError("Do not create Resource with empty ProcessCollection")
        super().__init__(entity_name=entity_name)
        self._collection = process_collection
        self._input_count = -1
        self._output_count = -1
        self._assignment: list[ProcessCollection] | None = None

    def __repr__(self):
        return self.entity_name

    def __iter__(self):
        return iter(self._collection)

    def _digraph(self) -> Digraph:
        dg = Digraph(node_attr={'shape': 'box'})
        dg.node(
            self.entity_name,
            self._struct_def(),
            style='filled',
            fillcolor=self._color,
            fontname='Times New Roman',
        )
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
        # Create GraphViz struct
        inputs = [f"in{i}" for i in range(self.input_count)]
        outputs = [f"out{i}" for i in range(self.output_count)]
        ret = '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">'
        table_width = max(len(inputs), len(outputs), 1)
        if inputs:
            in_strs = [
                f'<TD COLSPAN="{int(table_width/len(inputs))}"'
                f' PORT="{in_str}">{in_str}</TD>'
                for in_str in inputs
            ]
            ret += f"<TR>{''.join(in_strs)}</TR>"
        ret += (
            f'<TR><TD COLSPAN="{table_width}">'
            f'<B>{self.entity_name}{self._info()}</B></TD></TR>'
        )
        if outputs:
            out_strs = [
                f'<TD COLSPAN="{int(table_width/len(outputs))}"'
                f' PORT="{out_str}">{out_str}</TD>'
                for out_str in outputs
            ]
            ret += f"<TR>{''.join(out_strs)}</TR>"
        return ret + "</TABLE>>"

    def _info(self):
        return ""

    @property
    def _color(self):
        raise NotImplementedError

    @property
    def schedule_time(self) -> int:
        # doc-string inherited
        return self._collection.schedule_time

    def plot_content(self, ax: plt.Axes, **kwargs) -> None:
        """
        Plot the content of the resource.

        This plots the assigned processes executed on this resource.

        Parameters
        ----------
        ax : Axes
            Matplotlib Axes to plot in.
        **kwargs
            Passed to :meth:`~b_asic.resources.ProcessCollection.plot`.
        """
        if not self.is_assigned:
            self._collection.plot(ax, **kwargs)
        else:
            for i, pc in enumerate(self._assignment):  # type: ignore
                pc.plot(ax=ax, row=i, **kwargs)

    def show_content(self, title=None, **kwargs) -> None:
        """
        Display the content of the resource.

        This displays the assigned processes executed on this resource.

        Parameters
        ----------
        title : str, optional
            Figure title.
        **kwargs
            Passed to :meth:`~b_asic.resources.ProcessCollection.plot`.
        """
        fig, ax = plt.subplots(layout="constrained")
        self.plot_content(ax, **kwargs)
        height = 0.4
        if title:
            height += 0.4
            fig.suptitle(title)
        fig.set_figheight(math.floor(max(ax.get_ylim())) * 0.3 + height)
        fig.show()  # type: ignore

    @property
    def is_assigned(self) -> bool:
        return self._assignment is not None

    def assign(self, heuristic: str = 'left_edge'):
        """
        Perform assignment of processes to resource.

        Parameters
        ----------
        heuristic : str
            See the specific resource types for more information.

        See Also
        --------
        Memory.assign
        ProcessingElement.assign
        """
        raise NotImplementedError()

    @property
    def content(self) -> plt.Figure:
        """
        Return a graphical representation of the content.

        This is visible in enriched shells, but the object itself has no further
        meaning (it is a Matplotlib Figure).
        """
        fig, ax = plt.subplots(layout="constrained")
        self.plot_content(ax)
        fig.set_figheight(math.floor(max(ax.get_ylim())) * 0.3 + 0.4)
        return fig

    @property
    def collection(self) -> ProcessCollection:
        return self._collection

    @property
    def operation_type(self) -> type[MemoryProcess] | type[Operation]:
        raise NotImplementedError("ABC Resource does not implement operation_type")

    def add_process(self, proc: Process, assign=False):
        """
        Add a :class:`~b_asic.process.Process` to this :class:`Resource`.

        Parameters
        ----------
        proc : :class:`~b_asic.process.Process`
            The process to add.
        assign : bool, default=False
            Whether to perform assignment of the resource after adding.

        Raises
        ------
        :class:`TypeError`
            If the process being added is not of the same type as the other processes.
        """
        if isinstance(proc, OperatorProcess):
            # operation_type marks OperatorProcess associated operation.
            if not isinstance(proc.operation, self.operation_type):
                raise TypeError(f"{proc} not of type {self.operation_type}")
        else:
            # operation_type is MemoryVariable or PlainMemoryVariable
            if not isinstance(proc, self.operation_type):
                raise TypeError(f"{proc} not of type {self.operation_type}")
        self.collection.add_process(proc)
        if assign:
            self.assign()
        else:
            self._assignment = None

    def remove_process(self, proc: Process, assign: bool = False):
        """
        Remove a :class:`~b_asic.process.Process` from this :class:`Resource`.

        Raises :class:`KeyError` if the process being added is not of the same type
        as the other processes.

        Parameters
        ----------
        proc : :class:`~b_asic.process.Process`
            The process to remove.
        assign : bool, default=False
            Whether to perform assignment of the resource after removal.

        Raises
        ------
        :class:`KeyError`
            If *proc* is not present in resource.
        """
        self.collection.remove_process(proc)
        if assign:
            self.assign()
        else:
            self._assignment = None


class ProcessingElement(Resource):
    """
    Create a processing element for a ProcessCollection with OperatorProcesses.

    Parameters
    ----------
    process_collection : :class:`~b_asic.resources.ProcessCollection`
        Process collection containing operations to map to processing element.
    entity_name : str, optional
        Name of processing element entity.
    assign : bool, default True
        Perform assignment when creating the ProcessingElement.
    """

    _color = f"#{''.join(f'{v:0>2X}' for v in PE_COLOR)}"
    __slots__ = ("_process_collection", "_entity_name")
    _process_collection: ProcessCollection
    _entity_name: str | None

    def __init__(
        self,
        process_collection: ProcessCollection,
        entity_name: str | None = None,
        assign: bool = True,
    ):
        super().__init__(process_collection=process_collection, entity_name=entity_name)

        if not isinstance(process_collection, ProcessCollection):
            raise TypeError(
                "Argument process_collection must be ProcessCollection, "
                f"not {type(process_collection)}"
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
        self._operation_type = op_type
        self._type_name = op_type.type_name()
        self._input_count = ops[0].input_count
        self._output_count = ops[0].output_count
        if assign:
            self.assign()

    @property
    def processes(self) -> list[OperatorProcess]:
        return [cast(OperatorProcess, p) for p in self._collection]

    def assign(
        self, heuristic: Literal["left_edge", "graph_color"] = "left_edge"
    ) -> None:
        """
        Perform assignment of the processes.

        Parameters
        ----------
        heuristic : {'left_edge', 'graph_color'}, default: 'left_edge'
            The assignment algorithm.

            * 'left_edge': Left-edge algorithm.
            * 'graph_color': Graph-coloring based on exclusion graph.
        """
        self._assignment = list(
            self._collection.split_on_execution_time(heuristic=heuristic)
        )
        if len(self._assignment) > 1:
            self._assignment = None
            raise ValueError("Cannot map ProcessCollection to single ProcessingElement")

    @property
    def operation_type(self) -> type[Operation]:
        return self._operation_type


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
    total_ports : int, optional
        Total number of read and write ports for memory.
    assign : bool, default False
        Perform assignment when creating the Memory (using the default properties).
    """

    _color = f"#{''.join(f'{v:0>2X}' for v in MEMORY_COLOR)}"
    _slots__ = (
        "_process_collection",
        "_memory_type",
        "_entity_name",
        "_read_ports",
        "_write_ports",
        "_total_ports",
        "_assign",
    )
    _process_collection: ProcessCollection
    _memory_type: Literal["RAM", "register"]
    _entity_name: str | None
    _read_ports: int | None
    _write_ports: int | None
    _total_ports: int | None
    _assign: bool

    def __init__(
        self,
        process_collection: ProcessCollection,
        memory_type: Literal["RAM", "register"] = "RAM",
        entity_name: str | None = None,
        read_ports: int | None = None,
        write_ports: int | None = None,
        total_ports: int | None = None,
        assign: bool = False,
    ):
        super().__init__(process_collection=process_collection, entity_name=entity_name)
        if not all(
            isinstance(operator, MemoryProcess)
            for operator in process_collection.collection
        ):
            raise TypeError(
                "Can only have MemoryProcess in ProcessCollection when creating Memory"
            )
        if memory_type not in ("RAM", "register"):
            raise ValueError(
                f"memory_type must be 'RAM' or 'register', not {memory_type!r}"
            )
        if read_ports is not None or write_ports is not None or total_ports is not None:
            read_ports, write_ports, total_ports = _sanitize_port_option(
                read_ports, write_ports, total_ports
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

        total_ports_bound = self._collection.total_ports_bound()
        if total_ports is not None and total_ports < total_ports_bound:
            raise ValueError(f"At least {total_ports_bound} total ports required")

        self._memory_type = memory_type
        if assign:
            self.assign()

        memory_processes = [
            cast(MemoryProcess, process) for process in process_collection
        ]
        mem_proc_type = type(memory_processes[0])
        if not all(isinstance(proc, mem_proc_type) for proc in memory_processes):
            raise TypeError("Different MemoryProcess types in ProcessCollection")
        self._operation_type = mem_proc_type

    def __iter__(self) -> Iterator[MemoryVariable]:
        # Add information about the iterator type
        return cast(Iterator[MemoryVariable], iter(self._collection))

    def _info(self):
        if self.is_assigned:
            if self._memory_type == "RAM":
                plural_s = 's' if len(self._assignment) >= 2 else ''
                return f": (RAM, {len(self._assignment)} cell{plural_s})"
        return ""

    def assign(self, heuristic: str = "left_edge") -> None:
        """
        Perform assignment of the memory variables.

        Parameters
        ----------
        heuristic : str, default: 'left_edge'
            The assignment algorithm. Depending on memory type the following are
            available:

            * 'RAM'
                * 'left_edge': Left-edge algorithm.
                * 'graph_color': Graph-coloring based on exclusion graph.
            * 'register'
                * ...
        """
        if self._memory_type == "RAM":
            self._assignment = self._collection.split_on_execution_time(
                heuristic=heuristic
            )
        else:  # "register"
            raise NotImplementedError()

    @property
    def operation_type(self) -> type[MemoryProcess]:
        return self._operation_type


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
        processing_elements: ProcessingElement | Iterable[ProcessingElement],
        memories: Memory | Iterable[Memory],
        entity_name: str = "arch",
        direct_interconnects: ProcessCollection | None = None,
    ):
        super().__init__(entity_name)
        self._processing_elements = (
            [processing_elements]
            if isinstance(processing_elements, ProcessingElement)
            else list(processing_elements)
        )
        self._memories = [memories] if isinstance(memories, Memory) else list(memories)
        self._direct_interconnects = direct_interconnects
        self._variable_input_port_to_resource: DefaultDict[
            InputPort, set[tuple[Resource, int]]
        ] = defaultdict(set)
        self._variable_outport_to_resource: DefaultDict[
            OutputPort, set[tuple[Resource, int]]
        ] = defaultdict(set)
        self._operation_input_port_to_resource: dict[InputPort, Resource] = {}
        self._operation_outport_to_resource: dict[OutputPort, Resource] = {}

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

    def _build_dicts(self) -> None:
        self._variable_input_port_to_resource = defaultdict(set)
        self._variable_outport_to_resource = defaultdict(set)
        self._operation_input_port_to_resource = {}
        self._operation_outport_to_resource = {}
        for pe in self.processing_elements:
            for operator in pe.processes:
                for input_port in operator.operation.inputs:
                    self._operation_input_port_to_resource[input_port] = pe
                for output_port in operator.operation.outputs:
                    self._operation_outport_to_resource[output_port] = pe

        for memory in self.memories:
            for mv in memory:
                for read_port in mv.read_ports:
                    self._variable_input_port_to_resource[read_port].add(
                        (memory, 0)
                    )  # Fix
                self._variable_outport_to_resource[mv.write_port].add(
                    (memory, 0)
                )  # Fix
        if self._direct_interconnects:
            for di in self._direct_interconnects:
                di = cast(MemoryVariable, di)
                for read_port in di.read_ports:
                    self._variable_input_port_to_resource[read_port].add(
                        (
                            self._operation_outport_to_resource[di.write_port],
                            di.write_port.index,
                        )
                    )
                    self._variable_outport_to_resource[di.write_port].add(
                        (
                            self._operation_input_port_to_resource[read_port],
                            read_port.index,
                        )
                    )

    def validate_ports(self) -> None:
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

        pe_input_ports: set[InputPort] = set()
        pe_output_ports: set[OutputPort] = set()
        for pe in self.processing_elements:
            for operator in pe.processes:
                pe_input_ports.update(operator.operation.inputs)
                pe_output_ports.update(operator.operation.outputs)

        # Make sure all inputs and outputs in the architecture are in use
        read_port_diff = memory_read_ports.symmetric_difference(pe_input_ports)
        write_port_diff = memory_write_ports.symmetric_difference(pe_output_ports)

        if any(port.name.startswith("dontcare") for port in read_port_diff):
            raise NotImplementedError(
                "DontCare operations not supported in architecture yet."
            )

        if any(port.name.startswith("sink") for port in read_port_diff):
            raise NotImplementedError(
                "Sink operations not supported in architecture yet."
            )

        if any(port.name.startswith("dontcare") for port in write_port_diff):
            raise NotImplementedError(
                "DontCare operations not supported in architecture yet."
            )

        if any(port.name.startswith("sink") for port in write_port_diff):
            raise NotImplementedError(
                "Sink operations not supported in architecture yet."
            )

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

    def get_interconnects_for_memory(
        self, mem: Memory | str
    ) -> tuple[dict[Resource, int], dict[Resource, int]]:
        """
        Return a dictionary with interconnect information for a Memory.

        Parameters
        ----------
        mem : :class:`Memory` or str
            The memory or entity name to obtain information about.

        Returns
        -------
        (dict, dict)
            A dictionary with the ProcessingElements that are connected to the write and
            read ports, respectively, with counts of the number of accesses.
        """
        if isinstance(mem, str):
            mem = cast(Memory, self.resource_from_name(mem))

        d_in: DefaultDict[Resource, int] = defaultdict(_interconnect_dict)
        d_out: DefaultDict[Resource, int] = defaultdict(_interconnect_dict)
        for var in mem.collection:
            var = cast(MemoryVariable, var)
            d_in[self._operation_outport_to_resource[var.write_port]] += 1
            for read_port in var.read_ports:
                d_out[self._operation_input_port_to_resource[read_port]] += 1
        return dict(d_in), dict(d_out)

    def get_interconnects_for_pe(
        self, pe: str | ProcessingElement
    ) -> tuple[
        list[dict[tuple[Resource, int], int]], list[dict[tuple[Resource, int], int]]
    ]:
        """
        Return with interconnect information for a ProcessingElement.

        The information is tuple, where each element is a lists of dictionaries.

        Parameters
        ----------
        pe : :class:`ProcessingElement` or str
            The processing element or entity name to get information for.

        Returns
        -------
        list
            List of dictionaries indicating the sources for each import and the
            frequency of accesses.
        list
            List of dictionaries indicating the sources for each outport and the
            frequency of accesses.
        """
        if isinstance(pe, str):
            pe = cast(ProcessingElement, self.resource_from_name(pe))

        d_in: list[DefaultDict[tuple[Resource, int], int]] = [
            defaultdict(_interconnect_dict) for _ in range(pe.input_count)
        ]
        d_out: list[DefaultDict[tuple[Resource, int], int]] = [
            defaultdict(_interconnect_dict) for _ in range(pe.output_count)
        ]
        for var in pe.collection:
            var = cast(OperatorProcess, var)
            for i, input_ in enumerate(var.operation.inputs):
                for v in self._variable_input_port_to_resource[input_]:
                    d_in[i][v] += 1
            for i, output in enumerate(var.operation.outputs):
                for v in self._variable_outport_to_resource[output]:
                    d_out[i][v] += 1
        return [dict(d) for d in d_in], [dict(d) for d in d_out]

    def resource_from_name(self, name: str) -> Resource:
        """
        Get :class:`Resource` based on name.

        Parameters
        ----------
        name : str
            Name of the resource.

        Returns
        -------
        :class:`Resource`

        """
        re = {p.entity_name: p for p in chain(self.memories, self.processing_elements)}
        return re[name]

    def remove_resource(
        self,
        resource: str | Resource,
    ) -> None:
        """
        Remove an empty :class:`Resource` from the architecture.

        Parameters
        ----------
        resource : :class:`~b_asic.architecture.Resource` or str
            The resource or the resource name to remove.
        """
        if isinstance(resource, str):
            resource = self.resource_from_name(resource)

        if resource.collection:
            raise ValueError("Resource must be empty")

        if resource in self.memories:
            self.memories.remove(cast(Memory, resource))
        elif resource in self.processing_elements:
            self.processing_elements.remove(cast(ProcessingElement, resource))
        else:
            raise ValueError('Resource not in architecture')

    def assign_resources(self, heuristic: str = "left_edge") -> None:
        """
        Convenience method to assign all resources in the architecture.

        Parameters
        ----------
        heuristic : str, default: "left_edge"
            The heurstic to use.

        See Also
        --------
        Memory.assign
        ProcessingElement.assign

        """
        for resource in chain(self.memories, self.processing_elements):
            resource.assign(heuristic=heuristic)

    def move_process(
        self,
        proc: str | Process,
        source: str | Resource,
        destination: str | Resource,
        assign: bool = False,
    ) -> None:
        """
        Move a :class:`~b_asic.process.Process` from one :class:`Resource`  to another.

        Both the resource moved from and will become unassigned after a process has been
        moved, unless *assign* is True.

        Parameters
        ----------
        proc : :class:`~b_asic.process.Process` or str
            The process (or its name) to move.
        source : :class:`~b_asic.architecture.Resource` or str
            The resource (or its entity name) to move the process from.
        destination : :class:`~b_asic.architecture.Resource` or str
            The resource (or its entity name) to move the process to.
        assign : bool, default=False
            Whether to perform assignment of the resources after moving.

        Raises
        ------
        :class:`KeyError`
            If *proc* is not present in resource *source*.
        """
        # Extract resources from name
        if isinstance(source, str):
            source = self.resource_from_name(source)
        if isinstance(destination, str):
            destination = self.resource_from_name(destination)

        # Extract process from name
        if isinstance(proc, str):
            proc = source.collection.from_name(proc)

        # Move the process
        if proc in source:
            destination.add_process(proc, assign=assign)
            source.remove_process(proc, assign=assign)
        else:
            raise KeyError(f"{proc} not in {source.entity_name}")
        self._build_dicts()

    def _digraph(
        self,
        branch_node: bool = True,
        cluster: bool = True,
        splines: str = "spline",
        io_cluster: bool = True,
        multiplexers: bool = True,
        colored: bool = True,
    ) -> Digraph:
        """
        Parameters
        ----------
        branch_node : bool, default: True
            Whether to create a branch node for outputs with fan-out of two or higher.
        cluster : bool, default: True
            Whether to draw memories and PEs in separate clusters.
        splines : str, default: "spline"
            The type of interconnect to use for graph drawing.
        io_cluster : bool, default: True
            Whether Inputs and Outputs are drawn inside an IO cluster. Only relevant
            if *cluster* is True.
        multiplexers : bool, default: True
            Whether input multiplexers are included.
        colored : bool, default: True
            Whether to color the nodes.
        """
        dg = Digraph(node_attr={'shape': 'box'})
        dg.attr(splines=splines)
        # Setup colors
        pe_color = (
            f"#{''.join(f'{v:0>2X}' for v in PE_COLOR)}" if colored else "transparent"
        )
        pe_cluster_color = (
            f"#{''.join(f'{v:0>2X}' for v in PE_CLUSTER_COLOR)}"
            if colored
            else "transparent"
        )
        memory_color = (
            f"#{''.join(f'{v:0>2X}' for v in MEMORY_COLOR)}"
            if colored
            else "transparent"
        )
        memory_cluster_color = (
            f"#{''.join(f'{v:0>2X}' for v in MEMORY_CLUSTER_COLOR)}"
            if colored
            else "transparent"
        )
        io_color = (
            f"#{''.join(f'{v:0>2X}' for v in IO_COLOR)}" if colored else "transparent"
        )
        io_cluster_color = (
            f"#{''.join(f'{v:0>2X}' for v in IO_CLUSTER_COLOR)}"
            if colored
            else "transparent"
        )
        mux_color = (
            f"#{''.join(f'{v:0>2X}' for v in MUX_COLOR)}" if colored else "transparent"
        )

        # Add nodes for memories and PEs to graph
        if cluster:
            # Add subgraphs
            if len(self._memories):
                with dg.subgraph(name='cluster_memories') as c:
                    for mem in self._memories:
                        c.node(
                            mem.entity_name,
                            mem._struct_def(),
                            style='filled',
                            fillcolor=memory_color,
                            fontname='Times New Roman',
                        )
                    label = "Memory" if len(self._memories) <= 1 else "Memories"
                    c.attr(label=label, bgcolor=memory_cluster_color)
            with dg.subgraph(name='cluster_pes') as c:
                for pe in self._processing_elements:
                    if pe._type_name not in ('in', 'out'):
                        c.node(
                            pe.entity_name,
                            pe._struct_def(),
                            style='filled',
                            fillcolor=pe_color,
                            fontname='Times New Roman',
                        )
                label = (
                    "Processing element"
                    if len(self._processing_elements) <= 1
                    else "Processing elements"
                )
                c.attr(label=label, bgcolor=pe_cluster_color)
            if io_cluster:
                with dg.subgraph(name='cluster_io') as c:
                    for pe in self._processing_elements:
                        if pe._type_name in ('in', 'out'):
                            c.node(
                                pe.entity_name,
                                pe._struct_def(),
                                style='filled',
                                fillcolor=io_color,
                                fontname='Times New Roman',
                            )
                    c.attr(label="IO", bgcolor=io_cluster_color)
            else:
                for pe in self._processing_elements:
                    if pe._type_name in ('in', 'out'):
                        dg.node(
                            pe.entity_name,
                            pe._struct_def(),
                            style='filled',
                            fillcolor=io_color,
                            fontname='Times New Roman',
                        )
        else:
            for i, mem in enumerate(self._memories):
                dg.node(
                    mem.entity_name,
                    mem._struct_def(),
                    style='filled',
                    fillcolor=memory_color,
                    fontname='Times New Roman',
                )
            for i, pe in enumerate(self._processing_elements):
                dg.node(
                    pe.entity_name, pe._struct_def(), style='filled', fillcolor=pe_color
                )

        # Create list of interconnects
        edges: DefaultDict[str, set[tuple[str, str]]] = defaultdict(set)
        destination_edges: DefaultDict[str, set[str]] = defaultdict(set)
        for pe in self._processing_elements:
            inputs, outputs = self.get_interconnects_for_pe(pe)
            for i, inp in enumerate(inputs):
                for (source, port), cnt in inp.items():
                    source_str = f"{source.entity_name}:out{port}"
                    destination_str = f"{pe.entity_name}:in{i}"
                    edges[source_str].add(
                        (
                            destination_str,
                            f"{cnt}",
                        )
                    )
                    destination_edges[destination_str].add(source_str)
            for o, output in enumerate(outputs):
                for (destination, port), cnt in output.items():
                    source_str = f"{pe.entity_name}:out{o}"
                    destination_str = f"{destination.entity_name}:in{port}"
                    edges[source_str].add(
                        (
                            destination_str,
                            f"{cnt}",
                        )
                    )
                    destination_edges[destination_str].add(source_str)

        destination_list = {k: list(v) for k, v in destination_edges.items()}
        if multiplexers:
            for destination_str, source_list in destination_list.items():
                if len(source_list) > 1:
                    # Create GraphViz struct for multiplexer
                    input_strings = [f"in{i}" for i in range(len(source_list))]
                    ret = (
                        '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0"'
                        ' CELLPADDING="4">'
                    )
                    in_strs = [
                        f'<TD COLSPAN="1" PORT="{in_str}">{in_str}</TD>'
                        for in_str in input_strings
                    ]
                    ret += f"<TR>{''.join(in_strs)}</TR>"
                    name = f"{destination_str.replace(':', '_')}_mux"
                    ret += (
                        f'<TR><TD COLSPAN="{len(input_strings)}"'
                        f' PORT="{name}"><B>{name}</B></TD></TR>'
                    )
                    ret += f'<TR><TD COLSPAN="{len(input_strings)}" PORT="out0">out0</TD></TR>'
                    dg.node(
                        name,
                        ret + "</TABLE>>",
                        style='filled',
                        fillcolor=mux_color,
                        fontname='Times New Roman',
                    )
                    # Add edge from mux output to resource input
                    dg.edge(f"{name}:out0", destination_str)

        # Add edges to graph
        for src_str, destination_counts in edges.items():
            original_src_str = src_str
            if len(destination_counts) > 1 and branch_node:
                branch = f"{src_str}_branch".replace(":", "")
                dg.node(branch, shape='point')
                dg.edge(src_str, branch, arrowhead='none')
                src_str = branch
            for destination_str, cnt_str in destination_counts:
                if multiplexers and len(destination_list[destination_str]) > 1:
                    idx = destination_list[destination_str].index(original_src_str)
                    destination_str = f"{destination_str.replace(':', '_')}_mux:in{idx}"
                dg.edge(src_str, destination_str, label=cnt_str)
        return dg

    @property
    def memories(self) -> list[Memory]:
        return self._memories

    @property
    def processing_elements(self) -> list[ProcessingElement]:
        return self._processing_elements

    @property
    def direct_interconnects(self) -> ProcessCollection | None:
        return self._direct_interconnects

    @property
    def schedule_time(self) -> int:
        # doc-string inherited
        return self._schedule_time
