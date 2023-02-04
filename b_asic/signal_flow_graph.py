"""
B-ASIC Signal Flow Graph Module.

Contains the signal flow graph operation.
"""

import itertools as it
import re
from collections import defaultdict, deque
from io import StringIO
from numbers import Number
from queue import PriorityQueue
from typing import (
    DefaultDict,
    Deque,
    Dict,
    Iterable,
    List,
    MutableSet,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)

from graphviz import Digraph

from b_asic.graph_component import (
    GraphComponent,
    GraphID,
    GraphIDNumber,
    Name,
    TypeName,
)
from b_asic.operation import (
    AbstractOperation,
    MutableDelayMap,
    MutableResultMap,
    Operation,
    ResultKey,
)
from b_asic.port import InputPort, OutputPort, SignalSourceProvider
from b_asic.signal import Signal
from b_asic.special_operations import Delay, Input, Output

DelayQueue = List[Tuple[str, ResultKey, OutputPort]]


class GraphIDGenerator:
    """Generates Graph IDs for objects."""

    _next_id_number: DefaultDict[TypeName, GraphIDNumber]

    def __init__(self, id_number_offset: GraphIDNumber = GraphIDNumber(0)):
        """Construct a GraphIDGenerator."""
        self._next_id_number = defaultdict(lambda: id_number_offset)

    def next_id(
        self, type_name: TypeName, used_ids: MutableSet = set()
    ) -> GraphID:
        """Get the next graph id for a certain graph id type."""
        self._next_id_number[type_name] += 1
        new_id = type_name + str(self._next_id_number[type_name])
        while new_id in used_ids:
            self._next_id_number[type_name] += 1
            new_id = type_name + str(self._next_id_number[type_name])
        return GraphID(new_id)

    @property
    def id_number_offset(self) -> GraphIDNumber:
        """Get the graph id number offset of this generator."""
        return GraphIDNumber(
            self._next_id_number.default_factory()
        )  # pylint: disable=not-callable


class SFG(AbstractOperation):
    """
    Construct an SFG given its inputs and outputs.

    Contains a set of connected operations, forming a new operation.
    Used as a base for simulation, scheduling, etc.

    Inputs/outputs may be specified using either Input/Output operations
    directly with the *inputs*/*outputs* parameters, or using signals with the
    *input_signals*/*output_signals parameters*. If signals are used, the
    corresponding Input/Output operations will be created automatically.

    The *id_number_offset* parameter specifies what number graph IDs will be
    offset by for each new graph component type. IDs start at 1 by default,
    so the default offset of 0 will result in IDs like "c1", "c2", etc.
    while an offset of 3 will result in "c4", "c5", etc.

    Parameters
    ----------
    inputs : array of Input, optional

    outputs : array of Output, optional

    input_signals : array of Signal, optional

    output_signals : array of Signal, optional

    id_number_offset : GraphIDNumber, optional

    name : Name, optional

    input_sources :

    """

    _components_by_id: Dict[GraphID, GraphComponent]
    _components_by_name: DefaultDict[Name, List[GraphComponent]]
    _components_dfs_order: List[GraphComponent]
    _operations_dfs_order: List[Operation]
    _operations_topological_order: List[Operation]
    _graph_id_generator: GraphIDGenerator
    _input_operations: List[Input]
    _output_operations: List[Output]
    _original_components_to_new: Dict[GraphComponent, GraphComponent]
    _original_input_signals_to_indices: Dict[Signal, int]
    _original_output_signals_to_indices: Dict[Signal, int]
    _precedence_list: Optional[List[List[OutputPort]]]
    _used_ids: Set[GraphID] = set()

    def __init__(
        self,
        inputs: Optional[Sequence[Input]] = None,
        outputs: Optional[Sequence[Output]] = None,
        input_signals: Optional[Sequence[Signal]] = None,
        output_signals: Optional[Sequence[Signal]] = None,
        id_number_offset: GraphIDNumber = GraphIDNumber(0),
        name: Name = Name(""),
        input_sources: Optional[
            Sequence[Optional[SignalSourceProvider]]
        ] = None,
    ):
        input_signal_count = 0 if input_signals is None else len(input_signals)
        input_operation_count = 0 if inputs is None else len(inputs)
        output_signal_count = (
            0 if output_signals is None else len(output_signals)
        )
        output_operation_count = 0 if outputs is None else len(outputs)
        super().__init__(
            input_count=input_signal_count + input_operation_count,
            output_count=output_signal_count + output_operation_count,
            name=name,
            input_sources=input_sources,
        )

        self._components_by_id = {}
        self._used_ids = set()
        self._components_by_name = defaultdict(list)
        self._components_dfs_order = []
        self._operations_dfs_order = []
        self._operations_topological_order = []
        self._graph_id_generator = GraphIDGenerator(
            GraphIDNumber(id_number_offset)
        )
        self._input_operations = []
        self._output_operations = []
        self._original_components_to_new = {}
        self._original_input_signals_to_indices = {}
        self._original_output_signals_to_indices = {}
        self._precedence_list = None

        # Setup input signals.
        if input_signals is not None:
            for input_index, signal in enumerate(input_signals):
                if signal in self._original_components_to_new:
                    raise ValueError(
                        f"Duplicate input signal {signal!r} in SFG"
                    )
                new_input_op = cast(
                    Input, self._add_component_unconnected_copy(Input())
                )
                new_signal = cast(
                    Signal, self._add_component_unconnected_copy(signal)
                )
                new_signal.set_source(new_input_op.output(0))
                self._input_operations.append(new_input_op)
                self._original_input_signals_to_indices[signal] = input_index

        # Setup input operations, starting from indices after input signals.
        if inputs is not None:
            for input_index, input_op in enumerate(inputs, input_signal_count):
                if input_op in self._original_components_to_new:
                    raise ValueError(
                        f"Duplicate input operation {input_op!r} in SFG"
                    )
                new_input_op = cast(
                    Input, self._add_component_unconnected_copy(input_op)
                )
                for signal in input_op.output(0).signals:
                    assert signal not in self._original_components_to_new, (
                        "Duplicate input signals connected to input ports"
                        " supplied to SFG constructor."
                    )
                    new_signal = cast(
                        Signal, self._add_component_unconnected_copy(signal)
                    )
                    new_signal.set_source(new_input_op.output(0))
                    self._original_input_signals_to_indices[
                        signal
                    ] = input_index

                self._input_operations.append(new_input_op)

        # Setup output signals.
        if output_signals is not None:
            for output_index, signal in enumerate(output_signals):
                new_output_op = cast(
                    Output, self._add_component_unconnected_copy(Output())
                )
                if signal in self._original_components_to_new:
                    # Signal was already added when setting up inputs.
                    new_signal = cast(
                        Signal, self._original_components_to_new[signal]
                    )
                    new_signal.set_destination(new_output_op.input(0))
                else:
                    # New signal has to be created.
                    new_signal = cast(
                        Signal, self._add_component_unconnected_copy(signal)
                    )
                    new_signal.set_destination(new_output_op.input(0))

                self._output_operations.append(new_output_op)
                self._original_output_signals_to_indices[signal] = output_index

        # Setup output operations, starting from indices after output signals.
        if outputs is not None:
            for output_index, output_op in enumerate(
                outputs, output_signal_count
            ):
                if output_op in self._original_components_to_new:
                    raise ValueError(
                        f"Duplicate output operation {output_op!r} in SFG"
                    )

                new_output_op = cast(
                    Output, self._add_component_unconnected_copy(output_op)
                )
                for signal in output_op.input(0).signals:
                    if signal in self._original_components_to_new:
                        # Signal was already added when setting up inputs.
                        new_signal = cast(
                            Signal, self._original_components_to_new[signal]
                        )
                    else:
                        # New signal has to be created.
                        new_signal = cast(
                            Signal,
                            self._add_component_unconnected_copy(signal),
                        )

                    new_signal.set_destination(new_output_op.input(0))
                    self._original_output_signals_to_indices[
                        signal
                    ] = output_index

                self._output_operations.append(new_output_op)

        output_operations_set = set(self._output_operations)

        # Search the graph inwards from each input signal.
        for (
            signal,
            input_index,
        ) in self._original_input_signals_to_indices.items():
            # Check if already added destination.
            new_signal = cast(Signal, self._original_components_to_new[signal])
            if new_signal.destination is None:
                if signal.destination is None:
                    raise ValueError(
                        f"Input signal #{input_index} is missing destination"
                        " in SFG"
                    )
                if (
                    signal.destination.operation
                    not in self._original_components_to_new
                ):
                    self._add_operation_connected_tree_copy(
                        signal.destination.operation
                    )
            elif new_signal.destination.operation in output_operations_set:
                # Add directly connected input to output to ordered list.
                source = cast(OutputPort, new_signal.source)
                self._components_dfs_order.extend(
                    [
                        source.operation,
                        new_signal,
                        new_signal.destination.operation,
                    ]
                )
                self._operations_dfs_order.extend(
                    [
                        source.operation,
                        new_signal.destination.operation,
                    ]
                )

        # Search the graph inwards from each output signal.
        for (
            signal,
            output_index,
        ) in self._original_output_signals_to_indices.items():
            # Check if already added source.
            new_signal = cast(Signal, self._original_components_to_new[signal])
            if new_signal.source is None:
                if signal.source is None:
                    raise ValueError(
                        f"Output signal #{output_index} is missing source"
                        " in SFG"
                    )
                if (
                    signal.source.operation
                    not in self._original_components_to_new
                ):
                    self._add_operation_connected_tree_copy(
                        signal.source.operation
                    )

    def __str__(self) -> str:
        """Return a string representation of this SFG."""
        string_io = StringIO()
        string_io.write(super().__str__() + "\n")
        string_io.write("Internal Operations:\n")
        line = "-" * 100 + "\n"
        string_io.write(line)

        for operation in self.get_operations_topological_order():
            string_io.write(f"{operation}\n")

        string_io.write(line)

        return string_io.getvalue()

    def __call__(
        self, *src: Optional[SignalSourceProvider], name: Name = Name("")
    ) -> "SFG":
        """
        Return a new independent SFG instance that is identical to this SFG
        except without any of its external connections.
        """
        return SFG(
            inputs=self._input_operations,
            outputs=self._output_operations,
            id_number_offset=self.id_number_offset,
            name=Name(name),
            input_sources=src if src else None,
        )

    @classmethod
    def type_name(cls) -> TypeName:
        # doc-string inherited.
        return TypeName("sfg")

    def evaluate(self, *args):
        result = self.evaluate_outputs(args)
        n = len(result)
        return None if n == 0 else result[0] if n == 1 else result

    def evaluate_output(
        self,
        index: int,
        input_values: Sequence[Number],
        results: Optional[MutableResultMap] = None,
        delays: Optional[MutableDelayMap] = None,
        prefix: str = "",
        bits_override: Optional[int] = None,
        truncate: bool = True,
    ) -> Number:
        # doc-string inherited
        if index < 0 or index >= self.output_count:
            raise IndexError(
                "Output index out of range (expected"
                f" 0-{self.output_count - 1}, got {index})"
            )
        if len(input_values) != self.input_count:
            raise ValueError(
                "Wrong number of inputs supplied to SFG for evaluation"
                f" (expected {self.input_count}, got {len(input_values)})"
            )
        if results is None:
            results = {}
        if delays is None:
            delays = {}

        # Set the values of our input operations to the given input values.
        for op, arg in zip(
            self._input_operations,
            self.truncate_inputs(input_values, bits_override)
            if truncate
            else input_values,
        ):
            op.value = arg

        deferred_delays = []
        value = self._evaluate_source(
            self._output_operations[index].input(0).signals[0].source,
            results,
            delays,
            prefix,
            bits_override,
            truncate,
            deferred_delays,
        )
        while deferred_delays:
            new_deferred_delays = []
            for key_base, key, src in deferred_delays:
                self._do_evaluate_source(
                    key_base,
                    key,
                    src,
                    results,
                    delays,
                    prefix,
                    bits_override,
                    truncate,
                    new_deferred_delays,
                )
            deferred_delays = new_deferred_delays
        results[self.key(index, prefix)] = value
        return value

    def connect_external_signals_to_components(self) -> bool:
        """
        Connects any external signals to this SFG's internal operations.
        This SFG becomes unconnected to the SFG it is a component off,
        causing it to become invalid afterwards. Returns True if successful,
        False otherwise.
        """
        if len(self.inputs) != len(self.input_operations):
            raise IndexError(
                f"Number of inputs ({len(self.inputs)}) does not match the"
                f" number of input_operations ({len(self.input_operations)})"
                " in SFG."
            )
        if len(self.outputs) != len(self.output_operations):
            raise IndexError(
                f"Number of outputs ({len(self.outputs)}) does not match the"
                f" number of output_operations ({len(self.output_operations)})"
                " in SFG."
            )
        if len(self.input_signals) == 0:
            return False
        if len(self.output_signals) == 0:
            return False

        # For each input_signal, connect it to the corresponding operation
        for input_port, input_operation in zip(
            self.inputs, self.input_operations
        ):
            dest = input_operation.output(0).signals[0].destination
            if dest is None:
                raise ValueError("Missing destination in signal.")
            dest.clear()
            input_port.signals[0].set_destination(dest)
        # For each output_signal, connect it to the corresponding operation
        for output_port, output_operation in zip(
            self.outputs, self.output_operations
        ):
            src = output_operation.input(0).signals[0].source
            if src is None:
                raise ValueError("Missing source in signal.")
            src.clear()
            output_port.signals[0].set_source(src)
        return True

    @property
    def input_operations(self) -> Sequence[Operation]:
        """
        Get the internal input operations in the same order as their respective input ports.
        """
        return self._input_operations

    @property
    def output_operations(self) -> Sequence[Operation]:
        """
        Get the internal output operations in the same order as their respective output ports.
        """
        return self._output_operations

    def split(self) -> Iterable[Operation]:
        return self.operations

    def to_sfg(self) -> "SFG":
        return self

    def inputs_required_for_output(self, output_index: int) -> Iterable[int]:
        """
        Return which inputs that the output depends on.

        Parameters
        ----------
        output_index : int
            The output index.

        Returns
        -------
            A  list of inputs that are required to compute the output with the given *output_index*.
        """
        if output_index < 0 or output_index >= self.output_count:
            raise IndexError(
                "Output index out of range (expected"
                f" 0-{self.output_count - 1}, got {output_index})"
            )

        input_indexes_required = []
        sfg_input_operations_to_indexes = {
            input_op: index
            for index, input_op in enumerate(self._input_operations)
        }
        output_op = self._output_operations[output_index]
        queue: Deque[Operation] = deque([output_op])
        visited: Set[Operation] = {output_op}
        while queue:
            op = queue.popleft()
            if isinstance(op, Input):
                if op in sfg_input_operations_to_indexes:
                    input_indexes_required.append(
                        sfg_input_operations_to_indexes[op]
                    )
                    del sfg_input_operations_to_indexes[op]

            for input_port in op.inputs:
                for signal in input_port.signals:
                    if signal.source is not None:
                        new_op = signal.source.operation
                        if new_op not in visited:
                            queue.append(new_op)
                            visited.add(new_op)

        return input_indexes_required

    def copy_component(self, *args, **kwargs) -> GraphComponent:
        return super().copy_component(
            *args,
            **kwargs,
            inputs=self._input_operations,
            outputs=self._output_operations,
            id_number_offset=self.id_number_offset,
            name=self.name,
        )

    @property
    def id_number_offset(self) -> GraphIDNumber:
        """
        Get the graph id number offset of the graph id generator for this SFG.
        """
        return self._graph_id_generator.id_number_offset

    @property
    def components(self) -> List[GraphComponent]:
        """Get all components of this graph in depth-first order."""
        return self._components_dfs_order

    @property
    def operations(self) -> List[Operation]:
        """Get all operations of this graph in depth-first order."""
        return self._operations_dfs_order

    def find_by_type_name(
        self, type_name: TypeName
    ) -> Sequence[GraphComponent]:
        """
        Find all components in this graph with the specified type name.
        Returns an empty sequence if no components were found.

        Parameters
        ==========
        type_name : TypeName
            The TypeName of the desired components.
        """
        reg = f"{type_name}[0-9]+"
        p = re.compile(reg)
        components = [
            val for key, val in self._components_by_id.items() if p.match(key)
        ]
        return components

    def find_by_id(self, graph_id: GraphID) -> Optional[GraphComponent]:
        """
        Find the graph component with the specified ID.
        Returns None if the component was not found.

        Parameters
        ==========

        graph_id : GraphID
            Graph ID of the desired component.
        """
        return self._components_by_id.get(graph_id, None)

    def find_by_name(self, name: Name) -> Sequence[GraphComponent]:
        """
        Find all graph components with the specified name.
        Returns an empty sequence if no components were found.

        Parameters
        ==========

        name : Name
            Name of the desired component(s)
        """
        return self._components_by_name.get(name, [])

    def find_result_keys_by_name(
        self, name: Name, output_index: int = 0
    ) -> Sequence[ResultKey]:
        """
        Find all graph components with the specified name and
        return a sequence of the keys to use when fetching their results
        from a simulation.

        Parameters
        ==========

        name : Name
            Name of the desired component(s)
        output_index : int, default: 0
            The desired output index to get the result from
        """
        keys = []
        for comp in self.find_by_name(name):
            if isinstance(comp, Operation):
                keys.append(comp.key(output_index, comp.graph_id))
        return keys

    def replace_component(
        self, component: Operation, graph_id: GraphID
    ) -> "SFG":
        """
        Find and replace all components matching either on GraphID, Type or both.
        Then return a new deepcopy of the sfg with the replaced component.

        Parameters
        ==========

        component : Operation
            The new component(s), e.g. Multiplication
        graph_id : GraphID
            The GraphID to match the component to replace.
        """

        sfg_copy = self()  # Copy to not mess with this SFG.
        component_copy = sfg_copy.find_by_id(graph_id)

        assert component_copy is not None and isinstance(
            component_copy, Operation
        ), "No operation matching the criteria found"
        assert (
            component_copy.output_count == component.output_count
        ), "The output count may not differ between the operations"
        assert (
            component_copy.input_count == component.input_count
        ), "The input count may not differ between the operations"

        for index_in, inp in enumerate(component_copy.inputs):
            for signal in inp.signals:
                signal.remove_destination()
                signal.set_destination(component.input(index_in))

        for index_out, outp in enumerate(component_copy.outputs):
            for signal in outp.signals:
                signal.remove_source()
                signal.set_source(component.output(index_out))

        return sfg_copy()  # Copy again to update IDs.

    def insert_operation(
        self, component: Operation, output_comp_id: GraphID
    ) -> Optional["SFG"]:
        """
        Insert an operation in the SFG after a given source operation.
        The source operation output count must match the input count of the operation
        as well as the output.
        Then return a new deepcopy of the sfg with the inserted component.

        Parameters
        ==========

        component : Operation
            The new component, e.g. Multiplication.
        output_comp_id : GraphID
            The source operation GraphID to connect from.
        """

        # Preserve the original SFG by creating a copy.
        sfg_copy = self()
        output_comp = cast(Operation, sfg_copy.find_by_id(output_comp_id))
        if output_comp is None:
            return None

        if isinstance(output_comp, Output):
            raise TypeError("Source operation cannot be an output operation.")
        if len(output_comp.output_signals) != component.input_count:
            raise TypeError(
                "Source operation output count"
                f" ({len(output_comp.output_signals)}) does not match input"
                f" count for component ({component.input_count})."
            )
        assert len(output_comp.output_signals) == component.output_count, (
            "Destination operation input count does not match output for"
            " component."
        )

        for index, signal_in in enumerate(output_comp.output_signals):
            destination = cast(InputPort, signal_in.destination)
            signal_in.set_destination(component.input(index))
            destination.connect(component.output(index))

        # Recreate the newly coupled SFG so that all attributes are correct.
        return sfg_copy()

    def remove_operation(self, operation_id: GraphID) -> Union["SFG", None]:
        """
        Returns a version of the SFG where the operation with the specified GraphID removed.
        The operation has to have the same amount of input- and output ports or a ValueError will
        be raised. If no operation with the entered operation_id is found then returns None and does nothing.

        Parameters
        ==========

        operation_id : GraphID
            The GraphID of the operation to remove.

        """
        sfg_copy = self()
        operation = cast(Operation, sfg_copy.find_by_id(operation_id))
        if operation is None:
            return None

        if operation.input_count != operation.output_count:
            raise ValueError(
                "Different number of input and output ports of operation with"
                " the specified id"
            )

        for i, outport in enumerate(operation.outputs):
            if outport.signal_count > 0:
                if (
                    operation.input(i).signal_count > 0
                    and operation.input(i).signals[0].source is not None
                ):
                    in_sig = operation.input(i).signals[0]
                    source_port = cast(OutputPort, in_sig.source)
                    source_port.remove_signal(in_sig)
                    operation.input(i).remove_signal(in_sig)
                    for out_sig in outport.signals.copy():
                        out_sig.set_source(source_port)
                else:
                    for out_sig in outport.signals.copy():
                        out_sig.remove_source()
            else:
                if operation.input(i).signal_count > 0:
                    in_sig = operation.input(i).signals[0]
                    operation.input(i).remove_signal(in_sig)

        return sfg_copy()

    def get_precedence_list(self) -> Sequence[Sequence[OutputPort]]:
        """
        Returns a precedence list of the SFG where each element in n:th the
        list consists of elements that are executed in the n:th step. If the
        precedence list already has been calculated for the current SFG then
        return the cached version.
        """
        if self._precedence_list:
            return self._precedence_list

        # Find all operations with only outputs and no inputs.
        no_input_ops = list(
            filter(lambda op: op.input_count == 0, self.operations)
        )
        delay_ops = self.find_by_type_name(Delay.type_name())

        # Find all first iter output ports for precedence
        first_iter_ports = [
            op.output(i)
            for op in (no_input_ops + delay_ops)
            for i in range(op.output_count)
        ]

        self._precedence_list = self._traverse_for_precedence_list(
            first_iter_ports
        )

        return self._precedence_list

    def show(self) -> None:
        self.precedence_graph().view()

    def precedence_graph(self) -> Digraph:
        p_list = self.get_precedence_list()
        pg = Digraph()
        pg.attr(rankdir="LR")

        # Creates nodes for each output port in the precedence list
        for i in range(len(p_list)):
            ports = p_list[i]
            with pg.subgraph(name=f"cluster_{i}") as sub:
                sub.attr(label=f"N{i+1}")
                for port in ports:
                    portstr = f"{port.operation.graph_id}.{port.index}"
                    if port.operation.output_count > 1:
                        sub.node(portstr)
                    else:
                        sub.node(
                            portstr,
                            label=port.operation.graph_id,
                        )
        # Creates edges for each output port and creates nodes for each operation and edges for them as well
        for i in range(len(p_list)):
            ports = p_list[i]
            for port in ports:
                for signal in port.signals:
                    destination = cast(InputPort, signal.destination)
                    if destination.operation.type_name() == Delay.type_name():
                        dest_node = destination.operation.graph_id + "In"
                    else:
                        dest_node = destination.operation.graph_id
                    dest_label = destination.operation.graph_id
                    node_node = f"{port.operation.graph_id}.{port.index}"
                    pg.edge(node_node, dest_node)
                    pg.node(dest_node, label=dest_label, shape="square")
                if port.operation.type_name() == Delay.type_name():
                    source_node = port.operation.graph_id + "Out"
                else:
                    source_node = port.operation.graph_id
                source_label = port.operation.graph_id
                node_node = f"{port.operation.graph_id}.{port.index}"
                pg.edge(source_node, node_node)
                pg.node(source_node, label=source_label, shape="square")

        return pg

    def print_precedence_graph(self) -> None:
        """
        Print a representation of the SFG's precedence list to the standard out.
        If the precedence list already has been calculated then it uses the
        cached version, otherwise it calculates the precedence list and then
        prints it.
        """
        precedence_list = self.get_precedence_list()

        line = "-" * 120
        out_str = StringIO()
        out_str.write(line)

        printed_ops = set()

        for iter_num, iter in enumerate(precedence_list, start=1):
            for outport_num, outport in enumerate(iter, start=1):
                if outport not in printed_ops:
                    # Only print once per operation, even if it has multiple outports
                    out_str.write("\n")
                    out_str.write(str(iter_num))
                    out_str.write(".")
                    out_str.write(str(outport_num))
                    out_str.write(" \t")
                    out_str.write(str(outport.operation))
                    printed_ops.add(outport)

            out_str.write("\n")
            out_str.write(line)

        print(out_str.getvalue())

    def get_operations_topological_order(self) -> Iterable[Operation]:
        """
        Return an Iterable of the Operations in the SFG in topological order.
        Feedback loops makes an absolutely correct topological order impossible,
        so an approximate topological Order is returned in such cases in this
        implementation.
        """
        if self._operations_topological_order:
            return self._operations_topological_order

        no_inputs_queue = deque(
            list(filter(lambda op: op.input_count == 0, self.operations))
        )
        remaining_inports_per_operation = {
            op: op.input_count for op in self.operations
        }

        # Maps number of input counts to a queue of seen objects with such a size.
        seen_with_inputs_dict: Dict[int, Deque] = defaultdict(deque)
        seen = set()
        top_order = []

        if len(no_inputs_queue) == 0:
            raise ValueError("Illegal SFG state, dangling signals in SFG.")

        first_op = no_inputs_queue.popleft()
        visited = {first_op}
        p_queue = PriorityQueue()
        p_queue_entry_num = it.count()
        # Negative priority as max-heap popping is wanted
        p_queue.put(
            (-first_op.output_count, -next(p_queue_entry_num), first_op)
        )

        operations_left = len(self.operations) - 1

        seen_but_not_visited_count = 0

        while operations_left > 0:
            while not p_queue.empty():
                op = p_queue.get()[2]

                operations_left -= 1
                top_order.append(op)
                visited.add(op)

                for neighbor_op in op.subsequent_operations:
                    if neighbor_op not in visited:
                        remaining_inports_per_operation[neighbor_op] -= 1
                        remaining_inports = remaining_inports_per_operation[
                            neighbor_op
                        ]

                        if remaining_inports == 0:
                            p_queue.put(
                                (
                                    -neighbor_op.output_count,
                                    -next(p_queue_entry_num),
                                    neighbor_op,
                                )
                            )

                        elif remaining_inports > 0:
                            if neighbor_op in seen:
                                seen_with_inputs_dict[
                                    remaining_inports + 1
                                ].remove(neighbor_op)
                            else:
                                seen.add(neighbor_op)
                                seen_but_not_visited_count += 1

                            seen_with_inputs_dict[remaining_inports].append(
                                neighbor_op
                            )

            # Check if have to fetch Operations from somewhere else since p_queue is empty
            if operations_left > 0:
                # First check if can fetch from Operations with no input ports
                if no_inputs_queue:
                    new_op = no_inputs_queue.popleft()
                    p_queue.put(
                        (
                            -new_op.output_count,
                            -next(p_queue_entry_num),
                            new_op,
                        )
                    )

                # Else fetch operation with the lowest input count that is not zero
                elif seen_but_not_visited_count > 0:
                    for i in it.count(start=1):
                        seen_inputs_queue = seen_with_inputs_dict[i]
                        if seen_inputs_queue:
                            new_op = seen_inputs_queue.popleft()
                            p_queue.put(
                                (
                                    -new_op.output_count,
                                    -next(p_queue_entry_num),
                                    new_op,
                                )
                            )
                            seen_but_not_visited_count -= 1
                            break
                else:
                    raise RuntimeError("Disallowed structure in SFG detected")

        self._operations_topological_order = top_order
        return self._operations_topological_order

    def set_latency_of_type(self, type_name: TypeName, latency: int) -> None:
        """
        Set the latency of all components with the given type name.

        Parameters
        ----------
        type_name : TypeName
            The type name of the operation. For example, obtained as ``Addition.type_name()``.
        latency : int
            The latency of the operation.

        """
        for op in self.find_by_type_name(type_name):
            cast(Operation, op).set_latency(latency)

    def set_execution_time_of_type(
        self, type_name: TypeName, execution_time: int
    ) -> None:
        """
        Set the execution time of all operations with the given type name.

        Parameters
        ----------
        type_name : TypeName
            The type name of the operation. For example, obtained as ``Addition.type_name()``.
        execution_time : int
            The execution time of the operation.
        """
        for op in self.find_by_type_name(type_name):
            cast(Operation, op).execution_time = execution_time

    def set_latency_offsets_of_type(
        self, type_name: TypeName, latency_offsets: Dict[str, int]
    ) -> None:
        """
        Set the latency offsets of all operations with the given type name.

        Parameters
        ----------
        type_name : TypeName
            The type name of the operation. For example, obtained as ``Addition.type_name()``.
        latency_offsets : {"in1": int, ...}
            The latency offsets of the inputs and outputs.
        """
        for op in self.find_by_type_name(type_name):
            cast(Operation, op).set_latency_offsets(latency_offsets)

    def _traverse_for_precedence_list(
        self, first_iter_ports: List[OutputPort]
    ) -> List[List[OutputPort]]:
        # Find dependencies of output ports and input ports.
        remaining_inports_per_operation = {
            op: op.input_count for op in self.operations
        }

        # Traverse output ports for precedence
        curr_iter_ports = first_iter_ports
        precedence_list = []

        while curr_iter_ports:
            # Add the found ports to the current iter
            precedence_list.append(curr_iter_ports)

            next_iter_ports = []

            for outport in curr_iter_ports:
                for signal in outport.signals:
                    new_inport = signal.destination
                    # Do not traverse over delays.
                    if new_inport is not None and not isinstance(
                        new_inport.operation, Delay
                    ):
                        new_op = new_inport.operation
                        remaining_inports_per_operation[new_op] -= 1
                        if remaining_inports_per_operation[new_op] == 0:
                            next_iter_ports.extend(new_op.outputs)

            curr_iter_ports = next_iter_ports

        return precedence_list

    def _add_component_unconnected_copy(
        self, original_component: GraphComponent
    ) -> GraphComponent:
        assert (
            original_component not in self._original_components_to_new
        ), "Tried to add duplicate SFG component"
        new_component = original_component.copy_component()
        self._original_components_to_new[original_component] = new_component
        if (
            not new_component.graph_id
            or new_component.graph_id in self._used_ids
        ):
            new_id = self._graph_id_generator.next_id(
                new_component.type_name(), self._used_ids
            )
            new_component.graph_id = new_id
        self._used_ids.add(new_component.graph_id)
        self._components_by_id[new_component.graph_id] = new_component
        self._components_by_name[new_component.name].append(new_component)
        return new_component

    def _add_operation_connected_tree_copy(self, start_op: Operation) -> None:
        op_stack = deque([start_op])
        while op_stack:
            original_op = op_stack.pop()
            # Add or get the new copy of the operation.
            if original_op not in self._original_components_to_new:
                new_op = cast(
                    Operation,
                    self._add_component_unconnected_copy(original_op),
                )
                self._components_dfs_order.append(new_op)
                self._operations_dfs_order.append(new_op)
            else:
                new_op = cast(
                    Operation, self._original_components_to_new[original_op]
                )

            # Connect input ports to new signals.
            for original_input_port in original_op.inputs:
                if original_input_port.signal_count < 1:
                    raise ValueError("Unconnected input port in SFG")

                for original_signal in original_input_port.signals:
                    # Check if the signal is one of the SFG's input signals.
                    if (
                        original_signal
                        in self._original_input_signals_to_indices
                    ):
                        # New signal already created during first step of constructor.
                        new_signal = cast(
                            Signal,
                            self._original_components_to_new[original_signal],
                        )

                        new_signal.set_destination(
                            new_op.input(original_input_port.index)
                        )

                        source = cast(OutputPort, new_signal.source)
                        self._components_dfs_order.extend(
                            [new_signal, source.operation]
                        )
                        self._operations_dfs_order.append(source.operation)

                    # Check if the signal has not been added before.
                    elif (
                        original_signal not in self._original_components_to_new
                    ):
                        if original_signal.source is None:
                            raise ValueError(
                                "Dangling signal without source in SFG"
                            )

                        new_signal = cast(
                            Signal,
                            self._add_component_unconnected_copy(
                                original_signal
                            ),
                        )

                        new_signal.set_destination(
                            new_op.input(original_input_port.index)
                        )

                        self._components_dfs_order.append(new_signal)

                        original_connected_op = (
                            original_signal.source.operation
                        )
                        # Check if connected Operation has been added before.
                        if (
                            original_connected_op
                            in self._original_components_to_new
                        ):
                            component = cast(
                                Operation,
                                self._original_components_to_new[
                                    original_connected_op
                                ],
                            )
                            # Set source to the already added operations port.
                            new_signal.set_source(
                                component.output(original_signal.source.index)
                            )
                        else:
                            # Create new operation, set signal source to it.
                            new_connected_op = cast(
                                Operation,
                                self._add_component_unconnected_copy(
                                    original_connected_op
                                ),
                            )
                            new_signal.set_source(
                                new_connected_op.output(
                                    original_signal.source.index
                                )
                            )

                            self._components_dfs_order.append(new_connected_op)
                            self._operations_dfs_order.append(new_connected_op)

                            # Add connected operation to queue of operations to visit.
                            op_stack.append(original_connected_op)

            # Connect output ports.
            for original_output_port in original_op.outputs:
                for original_signal in original_output_port.signals:
                    # Check if the signal is one of the SFG's output signals.
                    if (
                        original_signal
                        in self._original_output_signals_to_indices
                    ):
                        # New signal already created during first step of constructor.
                        new_signal = cast(
                            Signal,
                            self._original_components_to_new[original_signal],
                        )

                        new_signal.set_source(
                            new_op.output(original_output_port.index)
                        )

                        destination = cast(InputPort, new_signal.destination)
                        self._components_dfs_order.extend(
                            [new_signal, destination.operation]
                        )
                        self._operations_dfs_order.append(
                            destination.operation
                        )

                    # Check if signal has not been added before.
                    elif (
                        original_signal not in self._original_components_to_new
                    ):
                        if original_signal.source is None:
                            raise ValueError(
                                "Dangling signal ({original_signal}) without"
                                " source in SFG"
                            )

                        new_signal = cast(
                            Signal,
                            self._add_component_unconnected_copy(
                                original_signal
                            ),
                        )
                        new_signal.set_source(
                            new_op.output(original_output_port.index)
                        )

                        self._components_dfs_order.append(new_signal)
                        original_destination = cast(
                            InputPort, original_signal.destination
                        )
                        if original_destination is None:
                            raise ValueError(
                                f"Signal ({original_signal}) without"
                                " destination in SFG"
                            )

                        original_connected_op = original_destination.operation
                        if original_connected_op is None:
                            raise ValueError(
                                "Signal with empty destination port"
                                f" ({original_destination}) in SFG"
                            )
                        # Check if connected operation has been added.
                        if (
                            original_connected_op
                            in self._original_components_to_new
                        ):
                            # Set destination to the already connected operations port.
                            new_signal.set_destination(
                                cast(
                                    Operation,
                                    self._original_components_to_new[
                                        original_connected_op
                                    ],
                                ).input(original_destination.index)
                            )
                        else:
                            # Create new operation, set destination to it.
                            new_connected_op = cast(
                                Operation,
                                (
                                    self._add_component_unconnected_copy(
                                        original_connected_op
                                    )
                                ),
                            )
                            new_signal.set_destination(
                                new_connected_op.input(
                                    original_destination.index
                                )
                            )

                            self._components_dfs_order.append(new_connected_op)
                            self._operations_dfs_order.append(new_connected_op)

                            # Add connected operation to the queue of operations to visit.
                            op_stack.append(original_connected_op)

    def _evaluate_source(
        self,
        src: OutputPort,
        results: MutableResultMap,
        delays: MutableDelayMap,
        prefix: str,
        bits_override: Optional[int],
        truncate: bool,
        deferred_delays: DelayQueue,
    ) -> Number:
        key_base = (
            (prefix + "." + src.operation.graph_id)
            if prefix
            else src.operation.graph_id
        )
        key = src.operation.key(src.index, key_base)
        if key in results:
            value = results[key]
            if value is None:
                raise RuntimeError(
                    "Direct feedback loop detected when evaluating operation."
                )
            return value

        value = src.operation.current_output(src.index, delays, key_base)
        results[key] = value
        if value is None:
            value = self._do_evaluate_source(
                key_base,
                key,
                src,
                results,
                delays,
                prefix,
                bits_override,
                truncate,
                deferred_delays,
            )
        else:
            # Evaluate later. Use current value for now.
            deferred_delays.append((key_base, key, src))
        return value

    def _do_evaluate_source(
        self,
        key_base: str,
        key: ResultKey,
        src: OutputPort,
        results: MutableResultMap,
        delays: MutableDelayMap,
        prefix: str,
        bits_override: Optional[int],
        truncate: bool,
        deferred_delays: DelayQueue,
    ) -> Number:
        input_values = [
            self._evaluate_source(
                input_port.signals[0].source,
                results,
                delays,
                prefix,
                bits_override,
                truncate,
                deferred_delays,
            )
            for input_port in src.operation.inputs
        ]
        value = src.operation.evaluate_output(
            src.index,
            input_values,
            results,
            delays,
            key_base,
            bits_override,
            truncate,
        )
        results[key] = value
        return value

    def sfg(self, show_id=False, engine=None) -> Digraph:
        """
        Returns a Digraph of the SFG. Can be directly displayed in IPython.

        Parameters
        ----------
        show_id : Boolean, optional
            If True, the graph_id:s of signals are shown. The default is False.

        engine : string, optional
            Graphviz layout engine to be used, see https://graphviz.org/documentation/.
            Most common are "dot" and "neato". Default is None leading to dot.

        Returns
        -------
        Digraph
            Digraph of the SFG.

        """
        dg = Digraph()
        dg.attr(rankdir="LR")
        if engine is not None:
            dg.engine = engine
        for op in self._components_by_id.values():
            if isinstance(op, Signal):
                source = cast(OutputPort, op.source)
                destination = cast(InputPort, op.destination)
                if show_id:
                    dg.edge(
                        source.operation.graph_id,
                        destination.operation.graph_id,
                        label=op.graph_id,
                    )
                else:
                    dg.edge(
                        source.operation.graph_id,
                        destination.operation.graph_id,
                    )
            else:
                if op.type_name() == Delay.type_name():
                    dg.node(op.graph_id, shape="square")
                else:
                    dg.node(op.graph_id)
        return dg

    def _repr_mimebundle_(self, include=None, exclude=None):
        return self.sfg()._repr_mimebundle_(include=include, exclude=exclude)

    def show_sfg(self, format=None, show_id=False, engine=None) -> None:
        """
        Shows a visual representation of the SFG using the default system viewer.

        Parameters
        ----------
        format : string, optional
            File format of the generated graph. Output formats can be found at
            https://www.graphviz.org/doc/info/output.html
            Most common are "pdf", "eps", "png", and "svg". Default is None which leads to PDF.

        show_id : Boolean, optional
            If True, the graph_id:s of signals are shown. The default is False.

        engine : string, optional
            Graphviz layout engine to be used, see https://graphviz.org/documentation/.
            Most common are "dot" and "neato". Default is None leading to dot.
        """

        dg = self.sfg(show_id=show_id)
        if engine is not None:
            dg.engine = engine
        if format is not None:
            dg.format = format
        dg.view()
