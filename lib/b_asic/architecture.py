"""
B-ASIC architecture classes.
"""

import math
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import (
    Literal,
    NoReturn,
    TextIO,
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
from b_asic.codegen.vhdl import architecture as vhdl_architecture
from b_asic.codegen.vhdl import common, write
from b_asic.codegen.vhdl import common as vhdl_common
from b_asic.codegen.vhdl import entity as vhdl_entity
from b_asic.operation import Operation
from b_asic.port import InputPort, OutputPort
from b_asic.process import MemoryProcess, MemoryVariable, OperatorProcess, Process
from b_asic.resources import ProcessCollection, _sanitize_port_option
from b_asic.special_operations import Input, Output


def _interconnect_dict() -> int:
    # Needed as pickle does not support lambdas
    return 0


@dataclass
class WordLengths:
    internal: int
    input: int
    output: int
    state: int

    def generics(self) -> list[str]:
        return [
            "WL_INTERNAL : integer",
            "WL_INPUT : integer",
            "WL_OUTPUT : integer",
            "WL_STATE : integer",
        ]

    def generics_with_default(self) -> list[str]:
        return [
            f"WL_INTERNAL : integer := {self.internal}",
            f"WL_INPUT : integer := {self.input}",
            f"WL_OUTPUT : integer := {self.output}",
            f"WL_STATE : integer := {self.state}",
        ]

    def generic_mapping(self) -> list[str]:
        return [
            "WL_INTERNAL => WL_INTERNAL",
            "WL_INPUT => WL_INPUT",
            "WL_OUTPUT => WL_OUTPUT",
            "WL_STATE => WL_STATE",
        ]


class HardwareBlock(ABC):
    """
    Base class for architectures and resources.

    Parameters
    ----------
    entity_name : str, optional
        The name of the resulting entity.
    """

    __slots__ = ("_entity_name",)
    _entity_name: str | None

    def __init__(self, entity_name: str | None = None) -> None:
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
        if not vhdl_common.is_valid_vhdl_identifier(entity_name):
            raise ValueError(f"{entity_name} is not a valid VHDL identifier")
        self._entity_name = entity_name

    def write_code(
        self,
        path: str,
        wl_internal: int,
        wl_input: int,
        wl_output: int,
        is_signed: bool = False,
    ) -> None:
        """
        Write VHDL code for hardware block.

        Parameters
        ----------
        path : str
            Directory to write code in.
        wl_input : int
            Bit widths of all input signals.
        wl_internal : int
            Bit widths of all internal signals.
        wl_output : int
            Bit widths of all output signals.
        is_signed : bool
            Whether to use signed or unsigned data processing.
        """
        if not self._entity_name:
            raise ValueError("Entity name must be set")
        if not wl_input:
            raise ValueError("Input word length must be set")
        if not wl_internal:
            raise ValueError("Internal word length must be set")
        if not wl_output:
            raise ValueError("Output word length must be set")
        wl = WordLengths(
            wl_internal, wl_input, wl_output, self.schedule_time.bit_length()
        )
        self._write_code(Path(path), wl, is_signed)

    @abstractmethod
    def _write_code(self, path: Path, wl: WordLengths) -> None:
        raise NotImplementedError()

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
        """
        The schedule time for hardware block.
        """
        raise NotImplementedError()

    @abstractmethod
    def write_component_declaration(self, f: TextIO, indent: int = 1) -> None:
        """
        Write component declaration of hardware block.

        Parameters
        ----------
        f : TextIO
            File object (or other TextIO object) to write the declaration to.
        indent : int, default: 1
            Indentation level to use for this process.
        """
        raise NotImplementedError()

    @abstractmethod
    def write_component_instantiation(self, f: TextIO, indent: int = 1) -> None:
        """
        Write component instantiation of hardware block.

        Parameters
        ----------
        f : TextIO
            File object (or other TextIO object) to write the instantiation to.
        indent : int, default: 1
            Indentation level to use for this process.
        """
        raise NotImplementedError()


class Resource(HardwareBlock, ABC):
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
    ) -> None:
        if not len(process_collection):
            raise ValueError("Do not create Resource with empty ProcessCollection")
        super().__init__(entity_name=entity_name)
        self._collection = process_collection
        self._input_count = -1
        self._output_count = -1
        self._assignment: list[ProcessCollection] | None = None

    def __repr__(self) -> str:
        return self.entity_name

    def __iter__(self) -> Iterator[ProcessCollection]:
        return iter(self._collection)

    def _digraph(self, fontname: str = "Times New Roman") -> Digraph:
        """
        Parameters
        ----------
        fontname : str, default: "Times New Roman"
            Font to use.
        """
        dg = Digraph(node_attr={"shape": "box"})
        dg.node(
            self.entity_name,
            self._struct_def(),
            style="filled",
            fillcolor=self._color,
            fontname=fontname,
        )
        return dg

    @property
    def input_count(self) -> int:
        """
        Number of input ports.
        """
        return self._input_count

    @property
    def output_count(self) -> int:
        """
        Number of output ports.
        """
        return self._output_count

    def _struct_def(self) -> str:
        # Create GraphViz struct
        inputs = [f"in{i}" for i in range(self.input_count)]
        outputs = [f"out{i}" for i in range(self.output_count)]
        ret = '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">'
        table_width = max(len(inputs), len(outputs), 1)
        if inputs:
            in_strs = [
                f'<TD COLSPAN="{int(table_width / len(inputs))}"'
                f' PORT="{in_str}">{in_str}</TD>'
                for in_str in inputs
            ]
            ret += f"<TR>{''.join(in_strs)}</TR>"
        ret += (
            f'<TR><TD COLSPAN="{table_width}">'
            f"<B>{self.entity_name}{self._info()}</B></TD></TR>"
        )
        if outputs:
            out_strs = [
                f'<TD COLSPAN="{int(table_width / len(outputs))}"'
                f' PORT="{out_str}">{out_str}</TD>'
                for out_str in outputs
            ]
            ret += f"<TR>{''.join(out_strs)}</TR>"
        return ret + "</TABLE>>"

    def _info(self) -> str:
        return ""

    @property
    def _color(self) -> str:
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
            height = 0.8
            fig.suptitle(title)
        fig.set_figheight(math.floor(max(ax.get_ylim())) * 0.3 + height)
        fig.show()  # type: ignore

    @property
    def is_assigned(self) -> bool:
        return self._assignment is not None

    def assign(self, strategy: Literal["left_edge"] = "left_edge") -> NoReturn:
        """
        Perform assignment of processes to resource.

        Parameters
        ----------
        strategy : str
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
    def assignment(self) -> list[ProcessCollection] | None:
        return self._assignment

    @property
    def operation_type(self) -> type[MemoryProcess] | type[Operation]:
        raise NotImplementedError("ABC Resource does not implement operation_type")

    def add_process(self, proc: Process, assign=False) -> None:
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

    def remove_process(self, proc: Process, assign: bool = False) -> None:
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
    __slots__ = ("_entity_name", "_process_collection")
    _process_collection: ProcessCollection
    _entity_name: str | None

    def __init__(
        self,
        process_collection: ProcessCollection,
        entity_name: str | None = None,
        assign: bool = True,
    ) -> None:
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
        self, strategy: Literal["left_edge", "graph_color"] = "left_edge"
    ) -> None:
        """
        Perform assignment of the processes.

        Parameters
        ----------
        strategy : {'left_edge', 'graph_color'}, default: 'left_edge'
            The assignment algorithm.

            * 'left_edge': Left-edge algorithm.
            * 'graph_color': Graph-coloring based on exclusion graph.
        """
        self._assignment = list(
            self._collection.split_on_execution_time(strategy=strategy)
        )
        if len(self._assignment) > 1:
            self._assignment = None
            raise ValueError("Cannot map ProcessCollection to single ProcessingElement")

    def _write_code(self, path: Path, wl: WordLengths, is_signed: bool) -> None:
        with (path / f"{self._entity_name}.vhd").open("w") as f:
            vhdl_common.b_asic_preamble(f)
            vhdl_common.ieee_header(f)
            vhdl_entity.processing_element(f, self, wl)
            vhdl_architecture.processing_element(f, self, is_signed)

    def write_component_declaration(
        self, f: TextIO, wl: WordLengths, indent: int = 1
    ) -> None:
        generics = wl.generics()
        ports = [
            "clk : in std_logic",
            "rst : in std_logic",
            "schedule_cnt : in unsigned(WL_STATE-1 downto 0)",
        ]
        ports += [
            f"p_{port_number}_in : in std_logic_vector(WL_INTERNAL-1 downto 0)"
            for port_number in range(self.input_count)
        ]
        if self.operation_type == Input:
            ports.append("p_0_in : in std_logic_vector(WL_INPUT-1 downto 0)")
        ports += [
            f"p_{port_number}_out : out std_logic_vector(WL_INTERNAL-1 downto 0)"
            for port_number in range(self.output_count)
        ]
        if self.operation_type == Output:
            ports.append("p_0_out : out std_logic_vector(WL_OUTPUT-1 downto 0)")
        common.component_declaration(f, self.entity_name, generics, ports, indent)
        write(f, 1, "")

    def write_signal_declarations(self, f: TextIO, indent: int = 1) -> None:
        write(f, indent, f"-- {self.entity_name} signals")
        if self.operation_type != Input:
            for port_number in range(self.input_count):
                common.signal_declaration(
                    f,
                    name=f"{self.entity_name}_{port_number}_in",
                    signal_type="std_logic_vector(WL_INTERNAL-1 downto 0)",
                    indent=indent,
                )
        if self.operation_type != Output:
            for port_number in range(self.output_count):
                common.signal_declaration(
                    f,
                    name=f"{self.entity_name}_{port_number}_out",
                    signal_type="std_logic_vector(WL_INTERNAL-1 downto 0)",
                    indent=indent,
                )
        write(f, indent, "")

    def write_component_instantiation(
        self, f: TextIO, wl: WordLengths, indent: int = 1
    ) -> None:
        port_mappings = ["clk => clk", "rst => rst"]
        port_mappings += ["schedule_cnt => schedule_cnt"]
        port_mappings += [
            f"p_{port_number}_in => {self.entity_name}_{port_number}_in"
            for port_number in range(self.input_count)
        ]
        if self.operation_type == Input:
            port_mappings.append(f"p_0_in => {self.entity_name}_0_in")
        port_mappings += [
            f"p_{port_number}_out => {self.entity_name}_{port_number}_out"
            for port_number in range(self.output_count)
        ]
        if self.operation_type == Output:
            port_mappings.append(f"p_0_out => {self.entity_name}_0_out")

        generic_mappings = wl.generic_mapping()

        common.component_instantiation(
            f,
            f"{self.entity_name}_inst",
            self.entity_name,
            port_mappings=port_mappings,
            generic_mappings=generic_mappings,
            indent=indent,
        )
        write(f, indent, "")

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
    ) -> None:
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

        self._validate_ports_in_bounds(read_ports, write_ports, total_ports)

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

    def _validate_ports_in_bounds(self, read_ports, write_ports, total_ports):
        read_ports_bound = self._collection.read_ports_bound()
        if read_ports is None:
            self._input_count = read_ports_bound
        else:
            if read_ports < read_ports_bound:
                raise ValueError(f"At least {read_ports_bound} read ports required")
            self._input_count = read_ports

        write_ports_bound = self._collection.write_ports_bound()
        if write_ports is None:
            self._output_count = write_ports_bound
        else:
            if write_ports < write_ports_bound:
                raise ValueError(f"At least {write_ports_bound} write ports required")
            self._output_count = write_ports

        total_ports_bound = self._collection.total_ports_bound()
        if total_ports is not None and total_ports < total_ports_bound:
            raise ValueError(f"At least {total_ports_bound} total ports required")
        self._total_ports = total_ports

    def _info(self) -> str:
        if self.is_assigned:
            if self._memory_type == "RAM":
                plural_s = "s" if len(self._assignment) >= 2 else ""
                return f": (RAM, {len(self._assignment)} cell{plural_s})"
            else:
                pass
        return ""

    def assign(
        self,
        strategy: Literal[
            "left_edge", "greedy_graph_color", "ilp_graph_color"
        ] = "left_edge",
    ) -> None:
        """
        Perform assignment of the memory variables.

        Parameters
        ----------
        strategy : str, default: 'left_edge'
            The assignment algorithm. Depending on memory type the following are
            available:

            * 'RAM'
                * 'left_edge': Left-edge algorithm.
                * 'greedy_graph_color': Greedy graph-coloring based on exclusion graph.
                * 'ilp_graph_color': Optimal graph-coloring based on exclusion graph.
            * 'register'
                * ...
        """
        if self._memory_type == "RAM":
            self._assignment = self._collection.split_on_execution_time(
                strategy=strategy
            )
        else:  # "register"
            raise NotImplementedError()

    def _write_code(self, path: Path, wl: WordLengths) -> None:
        with (path / f"{self._entity_name}.vhd").open("w") as f:
            vhdl_common.b_asic_preamble(f)
            vhdl_common.ieee_header(f)
            vhdl_entity.memory_based_storage(f, self, wl)
            vhdl_architecture.memory_based_storage(
                f, self, wl, input_sync=False, output_sync=False
            )

    def write_component_declaration(self, f: TextIO, wl: WordLengths, indent: int = 1):
        generics = wl.generics()
        ports = [
            "clk : in std_logic",
            "rst : in std_logic",
        ]
        ports += ["schedule_cnt : in unsigned(WL_STATE-1 downto 0)"]
        ports += [
            f"p_{port_number}_in : in std_logic_vector(WL_INTERNAL-1 downto 0)"
            for port_number in range(self.input_count)
        ]
        ports += [
            f"p_{port_number}_out : out std_logic_vector(WL_INTERNAL-1 downto 0)"
            for port_number in range(self.output_count)
        ]
        common.component_declaration(f, self.entity_name, generics, ports, indent)
        write(f, indent, "")

    def write_signal_declarations(self, f: TextIO, indent: int = 1) -> None:
        write(f, indent, f"-- {self.entity_name} signals")
        for port_number in range(self.input_count):
            common.signal_declaration(
                f,
                name=f"{self.entity_name}_{port_number}_in",
                signal_type="std_logic_vector(WL_INTERNAL-1 downto 0)",
                indent=indent,
            )
        for port_number in range(self.output_count):
            common.signal_declaration(
                f,
                name=f"{self.entity_name}_{port_number}_out",
                signal_type="std_logic_vector(WL_INTERNAL-1 downto 0)",
                indent=indent,
            )
        write(f, indent, "")

    def write_component_instantiation(
        self, f: TextIO, wl: WordLengths, indent: int = 1
    ) -> None:
        port_mappings = ["clk => clk", "rst => rst"]
        port_mappings += ["schedule_cnt => schedule_cnt"]
        port_mappings += [
            f"p_{port_number}_in => {self.entity_name}_{port_number}_in"
            for port_number in range(self.input_count)
        ]
        port_mappings += [
            f"p_{port_number}_out => {self.entity_name}_{port_number}_out"
            for port_number in range(self.output_count)
        ]

        generic_mappings = wl.generic_mapping()

        common.component_instantiation(
            f,
            f"{self.entity_name}_inst",
            self.entity_name,
            port_mappings=port_mappings,
            generic_mappings=generic_mappings,
            indent=indent,
        )
        write(f, 1, "")

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
    ) -> None:
        super().__init__(entity_name)

        pe_names = [pe._entity_name for pe in processing_elements]
        if len(pe_names) != len(set(pe_names)):
            raise ValueError("Entity names of processing elements needs to be unique.")
        self._processing_elements = (
            [processing_elements]
            if isinstance(processing_elements, ProcessingElement)
            else list(processing_elements)
        )

        mem_names = [mem._entity_name for mem in memories]
        if len(mem_names) != len(set(mem_names)):
            raise ValueError("Entity names of memories needs to be unique.")
        self._memories = [memories] if isinstance(memories, Memory) else list(memories)

        self._direct_interconnects = direct_interconnects

        self._variable_input_port_to_resource: defaultdict[
            InputPort, set[tuple[Resource, int]]
        ] = defaultdict(set)
        self._variable_outport_to_resource: defaultdict[
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

    def _write_code(self, path: Path, wl: WordLengths, is_signed: bool) -> None:
        counter = 0
        dir_path = path / f"{self.entity_name}_{counter}"
        while dir_path.exists():
            counter += 1
            dir_path = path / f"{self.entity_name}_{counter}"
        dir_path.mkdir(parents=True)

        for pe in self.processing_elements:
            pe._write_code(dir_path, wl, is_signed)

        for mem in self.memories:
            mem._write_code(dir_path, wl)

        with (dir_path / f"{self._entity_name}.vhd").open("w") as f:
            vhdl_common.b_asic_preamble(f)
            vhdl_common.ieee_header(f)
            vhdl_entity.architecture(f, self, wl)
            vhdl_architecture.architecture(f, self, wl)

        with (dir_path / f"{self._entity_name}_tb.vhd").open("w") as f:
            vhdl_common.b_asic_preamble(f)
            vhdl_common.ieee_header(f)
            vhdl_entity.architecture_test_bench(f, self)
            vhdl_architecture.architecture_test_bench(f, self, wl)

    def write_component_declaration(
        self, f: TextIO, wl: WordLengths, indent: int = 1
    ) -> None:
        write(f, 1, "-- Component declaration", start="\n")
        generics = wl.generics()
        ports = [
            "clk : in std_logic",
            "rst : in std_logic",
        ]
        inputs = [pe for pe in self.processing_elements if pe.operation_type == Input]
        ports += [
            f"{pe.entity_name}_0_in : in std_logic_vector(WL_INPUT-1 downto 0)"
            for pe in inputs
        ]
        outputs = [pe for pe in self.processing_elements if pe.operation_type == Output]
        ports += [
            f"{pe.entity_name}_0_out : out std_logic_vector(WL_OUTPUT-1 downto 0)"
            for pe in outputs
        ]
        common.component_declaration(f, self.entity_name, generics, ports, indent)

    def write_signal_declarations(self, f: TextIO, indent: int = 1) -> None:
        write(f, indent, "-- Signal declaration")
        for pe in self.processing_elements:
            pe.write_signal_declarations(f, indent)
        for mem in self.memories:
            mem.write_signal_declarations(f, indent)
        common.signal_declaration(f, "schedule_cnt", "unsigned(WL_STATE-1 downto 0)")

    def write_component_instantiation(self, f: TextIO, indent: int = 1) -> None:
        write(f, 1, "-- Component Instantiation", start="\n")
        generic_mappings = ["WL => WL", "WL_STATE => WL_STATE"]
        port_mappings = ["clk => tb_clk", "rst => tb_rst"]
        inputs = [pe for pe in self.processing_elements if pe.operation_type == Input]
        port_mappings += [
            f"{pe.entity_name}_0_in => tb_{pe.entity_name}_0_in" for pe in inputs
        ]
        outputs = [pe for pe in self.processing_elements if pe.operation_type == Output]
        port_mappings += [
            f"{pe.entity_name}_0_out => tb_{pe.entity_name}_0_out" for pe in outputs
        ]
        common.component_instantiation(
            f,
            f"{self.entity_name}_inst",
            self.entity_name,
            generic_mappings,
            port_mappings,
            indent,
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
            A dictionary with the ProcessingElements that are connected to the read and
            write ports, respectively, with counts of the number of accesses.
        """
        if isinstance(mem, str):
            mem = cast(Memory, self.resource_from_name(mem))

        d_in: defaultdict[Resource, int] = defaultdict(_interconnect_dict)
        d_out: defaultdict[Resource, int] = defaultdict(_interconnect_dict)
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
            List of dictionaries indicating the sources for each input port and the
            frequency of accesses.
        list
            List of dictionaries indicating the destinations for each output port and the
            frequency of accesses.
        """
        if isinstance(pe, str):
            pe = cast(ProcessingElement, self.resource_from_name(pe))

        d_in: list[defaultdict[tuple[Resource, int], int]] = [
            defaultdict(_interconnect_dict) for _ in range(pe.input_count)
        ]
        d_out: list[defaultdict[tuple[Resource, int], int]] = [
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

    def add_resource(
        self,
        resource: Resource,
    ) -> None:
        """
        Add a new :class:`Resource` to the architecture.

        Parameters
        ----------
        resource : :class:`~b_asic.architecture.Resource`
            The resource to add.
        """
        if isinstance(resource, Memory):
            self.memories.append(resource)
        elif isinstance(resource, ProcessingElement):
            self.processing_elements.append(resource)
        else:
            raise ValueError(
                "Provided resource must be a Memory or a ProcessingElement"
            )

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
            raise ValueError("Resource not in architecture")

    def assign_resources(self, strategy: Literal["left_edge"] = "left_edge") -> None:
        """
        Assign all resources in the architecture.

        Parameters
        ----------
        strategy : str, default: "left_edge"
            The heurstic to use.

        See Also
        --------
        Memory.assign
        ProcessingElement.assign
        """
        for resource in chain(self.memories, self.processing_elements):
            resource.assign(strategy=strategy)

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

        proc = cast(Process, proc)
        # Move the process
        if proc in source:
            destination.add_process(proc, assign=assign)
            source.remove_process(proc, assign=assign)
        else:
            raise KeyError(f"{proc} not in {source.entity_name}")
        self._build_dicts()

    def show(
        self,
        fmt: str | None = None,
        branch_node: bool = True,
        cluster: bool = True,
        splines: Literal["spline", "line", "ortho", "polyline", "curved"] = "spline",
        io_cluster: bool = True,
        multiplexers: bool = True,
        colored: bool = True,
    ) -> None:
        """
        Display a visual representation of the Architecture using the default system viewer.

        Parameters
        ----------
        fmt : str, optional
            File format of the generated graph. Output formats can be found at
            https://www.graphviz.org/doc/info/output.html
            Most common are "pdf", "eps", "png", and "svg". Default is None which
            leads to PDF.
        branch_node : bool, default: True
            Whether to create a branch node for outputs with fan-out of two or higher.
        cluster : bool, default: True
            Whether to draw memories and PEs in separate clusters.
        splines : {"spline", "line", "ortho", "polyline", "curved"}, default: "spline"
            Spline style, see https://graphviz.org/docs/attrs/splines/ for more info.
        io_cluster : bool, default: True
            Whether Inputs and Outputs are drawn inside an IO cluster. Only relevant
            if *cluster* is True.
        multiplexers : bool, default: True
            Whether input multiplexers are included.
        colored : bool, default: True
            Whether to color the nodes.
        """
        dg = self._digraph(
            branch_node=branch_node,
            cluster=cluster,
            splines=splines,
            io_cluster=io_cluster,
            multiplexers=multiplexers,
            colored=colored,
        )
        if fmt is not None:
            dg.format = fmt
        dg.view()

    def _digraph(
        self,
        branch_node: bool = True,
        cluster: bool = True,
        splines: Literal["spline", "line", "ortho", "polyline", "curved"] = "spline",
        io_cluster: bool = True,
        multiplexers: bool = True,
        colored: bool = True,
        fontname: str = "Times New Roman",
    ) -> Digraph:
        """
        Return a Digraph of the architecture.

        Can be directly displayed in IPython.

        Parameters
        ----------
        branch_node : bool, default: True
            Whether to create a branch node for outputs with fan-out of two or higher.
        cluster : bool, default: True
            Whether to draw memories and PEs in separate clusters.
        splines : {"spline", "line", "ortho", "polyline", "curved"}, default: "spline"
            Spline style, see https://graphviz.org/docs/attrs/splines/ for more info.
        io_cluster : bool, default: True
            Whether Inputs and Outputs are drawn inside an IO cluster. Only relevant
            if *cluster* is True.
        multiplexers : bool, default: True
            Whether input multiplexers are included.
        colored : bool, default: True
            Whether to color the nodes.
        fontname : str, default: "Times New Roman"
            Font to use.

        Returns
        -------
        Digraph
            Digraph of the rendered architecture.
        """
        dg = Digraph(node_attr={"shape": "box"})
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
                with dg.subgraph(name="cluster_memories") as c:
                    for mem in self._memories:
                        c.node(
                            mem.entity_name,
                            mem._struct_def(),
                            style="filled",
                            fillcolor=memory_color,
                            fontname=fontname,
                        )
                    label = "Memory" if len(self._memories) <= 1 else "Memories"
                    c.attr(label=label, bgcolor=memory_cluster_color, fontname=fontname)
            with dg.subgraph(name="cluster_pes") as c:
                for pe in self._processing_elements:
                    if pe._type_name not in ("in", "out"):
                        c.node(
                            pe.entity_name,
                            pe._struct_def(),
                            style="filled",
                            fillcolor=pe_color,
                            fontname=fontname,
                        )
                label = (
                    "Processing element"
                    if len(self._processing_elements) <= 1
                    else "Processing elements"
                )
                c.attr(label=label, bgcolor=pe_cluster_color, fontname=fontname)
            if io_cluster:
                with dg.subgraph(name="cluster_io") as c:
                    for pe in self._processing_elements:
                        if pe._type_name in ("in", "out"):
                            c.node(
                                pe.entity_name,
                                pe._struct_def(),
                                style="filled",
                                fillcolor=io_color,
                                fontname=fontname,
                            )
                    c.attr(label="IO", bgcolor=io_cluster_color, fontname=fontname)
            else:
                for pe in self._processing_elements:
                    if pe._type_name in ("in", "out"):
                        dg.node(
                            pe.entity_name,
                            pe._struct_def(),
                            style="filled",
                            fillcolor=io_color,
                            fontname=fontname,
                        )
        else:
            for mem in self._memories:
                dg.node(
                    mem.entity_name,
                    mem._struct_def(),
                    style="filled",
                    fillcolor=memory_color,
                    fontname=fontname,
                )
            for pe in self._processing_elements:
                dg.node(
                    pe.entity_name,
                    pe._struct_def(),
                    style="filled",
                    fillcolor=pe_color,
                    fontname=fontname,
                )

        # Create list of interconnects
        edges: defaultdict[str, set[tuple[str, str]]] = defaultdict(set)
        destination_edges: defaultdict[str, set[str]] = defaultdict(set)
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
                        style="filled",
                        fillcolor=mux_color,
                        fontname=fontname,
                    )
                    # Add edge from mux output to resource input
                    dg.edge(f"{name}:out0", destination_str)

        # Add edges to graph
        for src_str, destination_counts in edges.items():
            original_src_str = src_str
            if len(destination_counts) > 1 and branch_node:
                branch = f"{src_str}_branch".replace(":", "")
                dg.node(branch, shape="point")
                dg.edge(src_str, branch, arrowhead="none", fontname=fontname)
                src_str = branch
            for destination_str, cnt_str in destination_counts:
                if multiplexers and len(destination_list[destination_str]) > 1:
                    idx = destination_list[destination_str].index(original_src_str)
                    destination_str = f"{destination_str.replace(':', '_')}_mux:in{idx}"
                dg.edge(src_str, destination_str, label=cnt_str, fontname=fontname)
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
