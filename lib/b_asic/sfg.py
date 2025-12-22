"""
B-ASIC Signal Flow Graph Module.

Contains the signal flow graph operation.
"""

import itertools
import math
import re
import warnings
from collections import Counter, defaultdict, deque
from collections.abc import Iterable, MutableSet, Sequence
from fractions import Fraction
from io import StringIO
from queue import PriorityQueue
from typing import TYPE_CHECKING, Literal, Union, cast

import numpy as np
import numpy.typing as npt
from graphviz import Digraph

from b_asic.data_type import DataType
from b_asic.graph_component import GraphComponent
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
from b_asic.state_space import StateSpace
from b_asic.types import GraphID, GraphIDNumber, Name, Num, TypeName

if TYPE_CHECKING:
    from b_asic.simulation import Simulation

DelayQueue = list[tuple[str, ResultKey, OutputPort]]
OpSpecifier = GraphID | type[Operation] | Operation
OpInstanceSpecifier = GraphID | Operation


_OPERATION_SHAPE: defaultdict[TypeName, str] = defaultdict(lambda: "ellipse")
_OPERATION_SHAPE.update(
    {
        Input.type_name(): "cds",
        Output.type_name(): "cds",
        Delay.type_name(): "square",
    }
)


class GraphIDGenerator:
    """Generates Graph IDs for objects."""

    _next_id_number: defaultdict[TypeName, GraphIDNumber]

    def __init__(self, id_number_offset: GraphIDNumber = GraphIDNumber(0)) -> None:
        """Construct a GraphIDGenerator."""
        self._next_id_number = defaultdict(lambda: id_number_offset)

    def next_id(self, type_name: TypeName, used_ids: MutableSet = set()) -> GraphID:  # noqa: B006
        """Get the next graph id for a certain graph id type."""
        new_id = type_name + str(self._next_id_number[type_name])
        while new_id in used_ids:
            self._next_id_number[type_name] += 1
            new_id = type_name + str(self._next_id_number[type_name])
        used_ids.add(GraphID(new_id))
        return GraphID(new_id)

    @property
    def id_number_offset(self) -> GraphIDNumber:
        """Get the graph id number offset of this generator."""
        return GraphIDNumber(self._next_id_number.default_factory())  # pylint: disable=not-callable


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

    _components_by_id: dict[GraphID, GraphComponent]
    _components_by_name: defaultdict[Name, list[GraphComponent]]
    _components_dfs_order: list[GraphComponent]
    _operations_dfs_order: list[Operation]
    _operations_topological_order: list[Operation]
    _graph_id_generator: GraphIDGenerator
    _input_operations: list[Input]
    _output_operations: list[Output]
    _original_components_to_new: dict[GraphComponent, GraphComponent]
    _original_input_signals_to_indices: dict[Signal, int]
    _original_output_signals_to_indices: dict[Signal, int]
    _precedence_list: list[list[OutputPort]]
    _used_ids: set[GraphID]

    def __init__(
        self,
        inputs: Sequence[Input] | None = None,
        outputs: Sequence[Output] | None = None,
        input_signals: Sequence[Signal] | None = None,
        output_signals: Sequence[Signal] | None = None,
        id_number_offset: GraphIDNumber = GraphIDNumber(0),
        name: Name = Name(""),
        input_sources: Sequence[SignalSourceProvider | None] | None = None,
    ) -> None:
        input_signal_count = 0 if input_signals is None else len(input_signals)
        input_operation_count = 0 if inputs is None else len(inputs)
        output_signal_count = 0 if output_signals is None else len(output_signals)
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
        self._graph_id_generator = GraphIDGenerator(GraphIDNumber(id_number_offset))
        self._input_operations = []
        self._output_operations = []
        self._original_components_to_new = {}
        self._original_input_signals_to_indices = {}
        self._original_output_signals_to_indices = {}
        self._precedence_list = []

        # Setup input signals.
        if input_signals is not None:
            for input_index, signal in enumerate(input_signals):
                if signal in self._original_components_to_new:
                    raise ValueError(f"Duplicate input signal {signal!r} in SFG")
                new_input_op = cast(
                    Input, self._add_component_unconnected_copy(Input())
                )
                new_signal = cast(Signal, self._add_component_unconnected_copy(signal))
                new_signal.set_source(new_input_op.output(0))
                self._input_operations.append(new_input_op)
                self._original_input_signals_to_indices[signal] = input_index

        # Setup input operations, starting from indices after input signals.
        if inputs is not None:
            for input_index, input_op in enumerate(inputs, input_signal_count):
                if input_op in self._original_components_to_new:
                    raise ValueError(f"Duplicate input operation {input_op!r} in SFG")
                new_input_op = cast(
                    Input, self._add_component_unconnected_copy(input_op)
                )
                for signal in input_op.output(0).signals:
                    if signal in self._original_components_to_new:
                        raise ValueError(
                            "Duplicate input signals connected to input ports"
                            " supplied to SFG constructor."
                        )
                    new_signal = cast(
                        Signal, self._add_component_unconnected_copy(signal)
                    )
                    new_signal.set_source(new_input_op.output(0))
                    self._original_input_signals_to_indices[signal] = input_index

                self._input_operations.append(new_input_op)

        # Setup output signals.
        if output_signals is not None:
            for output_index, signal in enumerate(output_signals):
                new_output_op = cast(
                    Output, self._add_component_unconnected_copy(Output())
                )
                if signal in self._original_components_to_new:
                    # Signal was already added when setting up inputs.
                    new_signal = cast(Signal, self._original_components_to_new[signal])
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
            for output_index, output_op in enumerate(outputs, output_signal_count):
                if output_op in self._original_components_to_new:
                    raise ValueError(f"Duplicate output operation {output_op!r} in SFG")

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
                    self._original_output_signals_to_indices[signal] = output_index

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
                        f"Input signal #{input_index} is missing destination in SFG"
                    )
                if signal.destination.operation not in self._original_components_to_new:
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
        output_sources = []
        for (
            signal,
            output_index,
        ) in self._original_output_signals_to_indices.items():
            # Check if already added source.
            new_signal = cast(Signal, self._original_components_to_new[signal])

            if new_signal.source in output_sources:
                warnings.warn(
                    "Two signals connected to the same output port", stacklevel=2
                )
            output_sources.append(new_signal.source)

            if new_signal.source is None:
                if signal.source is None:
                    raise ValueError(
                        f"Output signal #{output_index} is missing source in SFG"
                    )
                if signal.source.operation not in self._original_components_to_new:
                    self._add_operation_connected_tree_copy(signal.source.operation)

        if len(output_sources) != (output_operation_count + output_signal_count):
            raise ValueError(
                "At least one output operation is not connected!, Tips: Check for output ports that are connected to the same signal"
            )

    def __str__(self) -> str:
        """Return a string representation of this SFG."""
        string_io = StringIO()
        string_io.write(super().__str__() + "\n")
        string_io.write("Internal Operations:\n")
        line = "-" * 100 + "\n"
        string_io.write(line)

        for operation in self.get_operations_topological_order():
            string_io.write(f"{operation.graph_str()}\n")

        string_io.write(line)

        return string_io.getvalue()

    def __call__(
        self, *src: SignalSourceProvider | None, name: Name = Name("")
    ) -> "SFG":
        """
        Return a new SFG identical without any of its external connections.
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

    def evaluate(self, *args, data_type=None) -> Num | list[Num] | None:
        result = self.evaluate_outputs(args)
        n = len(result)
        res = None if n == 0 else result[0] if n == 1 else result
        return self._cast_to_data_type(res, data_type)

    def evaluate_output(
        self,
        index: int,
        input_values: Sequence[Num],
        results: MutableResultMap | None = None,
        delays: MutableDelayMap | None = None,
        prefix: str = "",
        data_type: DataType | None = None,
    ) -> Num:
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
            input_values,
            strict=True,
        ):
            op.value = arg

        deferred_delays = []
        value = self._evaluate_source(
            self._output_operations[index].input(0).signals[0].source,
            results,
            delays,
            prefix,
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
                    new_deferred_delays,
                )
            deferred_delays = new_deferred_delays
        results[self.key(index, prefix)] = value
        return value

    def connect_external_signals_to_components(self) -> bool:
        """
        Connect any external signals to the internal operations of SFG.

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
            self.inputs, self.input_operations, strict=True
        ):
            destination = input_operation.output(0).signals[0].destination
            if destination is None:
                raise ValueError("Missing destination in signal.")
            destination.clear()
            input_port.signals[0].set_destination(destination)
            for signal in input_operation.output(0).signals[1:]:
                other_destination = signal.destination
                if other_destination is None:
                    raise ValueError("Missing destination in signal.")
                other_destination.clear()
                other_destination.add_signal(Signal(destination.signals[0].source))
            input_operation.output(0).clear()
        # For each output_signal, connect it to the corresponding operation
        for output_port, output_operation in zip(
            self.outputs, self.output_operations, strict=True
        ):
            src = output_operation.input(0).signals[0].source
            if src is None:
                raise ValueError("Missing source in signal.")
            for sig in output_operation.input(0).signals[:]:
                src.remove_signal(sig)
                for signal in output_port.signals[:]:
                    signal.set_source(src)
        return True

    @property
    def input_operations(self) -> Sequence[Operation]:
        """
        Internal input operations in the same order as their respective input ports.
        """
        return self._input_operations

    @property
    def output_operations(self) -> Sequence[Operation]:
        """
        Internal output operations in the same order as their respective output ports.
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
        A  list of inputs that are required to compute the output with the given
        *output_index*.
        """
        if output_index < 0 or output_index >= self.output_count:
            raise IndexError(
                "Output index out of range (expected"
                f" 0-{self.output_count - 1}, got {output_index})"
            )

        input_indexes_required = []
        sfg_input_operations_to_indexes = {
            input_op: index for index, input_op in enumerate(self._input_operations)
        }
        output_op = self._output_operations[output_index]
        queue: deque[Operation] = deque([output_op])
        visited: set[Operation] = {output_op}
        while queue:
            op = queue.popleft()
            if isinstance(op, Input) and op in sfg_input_operations_to_indexes:
                input_indexes_required.append(sfg_input_operations_to_indexes[op])
                del sfg_input_operations_to_indexes[op]

            for input_port in op.inputs:
                for signal in input_port.signals:
                    if signal.source is not None:
                        new_op = signal.source.operation
                        if new_op not in visited:
                            queue.append(new_op)
                            visited.add(new_op)

        return input_indexes_required

    def copy(self, *args, **kwargs) -> GraphComponent:
        return super().copy(
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
    def components(self) -> list[GraphComponent]:
        """Get all components of this graph in depth-first order."""
        return self._components_dfs_order

    @property
    def operations(self) -> list[Operation]:
        """Get all operations of this graph in depth-first order."""
        return list(self._operations_dfs_order)

    def find_by_type_name(self, type_name: TypeName) -> list[GraphComponent]:
        """
        Find all components in this graph with the specified type name.

        Returns an empty list if no components were found.

        Parameters
        ----------
        type_name : TypeName
            The TypeName of the desired components.
        """
        reg = f"{type_name}[0-9]+"
        p = re.compile(reg)
        return [val for key, val in self._components_by_id.items() if p.match(key)]

    def find_by_type(
        self, component_type: type[GraphComponent]
    ) -> list[GraphComponent]:
        """
        Find all components in this graph with the specified type.

        Returns an empty list if no components were found.

        Parameters
        ----------
        component_type : type of GraphComponent
            The TypeName of the desired components.
        """
        components = [
            comp
            for comp in self._components_dfs_order
            if isinstance(comp, component_type)
        ]
        components = list(set(components))  # ensure no redundant elements
        return sorted(components, key=lambda c: c.name or c.graph_id)

    def find_by_id(self, graph_id: GraphID) -> GraphComponent | None:
        """
        Find the graph component with the specified ID.

        Returns None if the component was not found.

        Parameters
        ----------
        graph_id : GraphID
            Graph ID of the desired component.
        """
        return self._components_by_id.get(graph_id, None)

    def find_by_name(self, name: Name) -> Sequence[GraphComponent]:
        """
        Find all graph components with the specified name.

        Returns an empty sequence if no components were found.

        Parameters
        ----------
        name : Name
            Name of the desired component(s).
        """
        return self._components_by_name.get(name, [])

    def find_result_keys_by_name(
        self, name: Name, output_index: int = 0
    ) -> Sequence[ResultKey]:
        """
        Find all graph components with the specified name.

        Return a sequence of the keys to use when fetching their results
        from a simulation.

        Parameters
        ----------
        name : Name
            Name of the desired component(s).
        output_index : int, default: 0
            The desired output index to get the result from.
        """
        return [
            comp.key(output_index, comp.graph_id)
            for comp in self.find_by_name(name)
            if isinstance(comp, Operation)
        ]

    def extract(self, targets: Iterable[GraphID]) -> "SFG":
        sfg_copy = self()

        for target in targets:
            target_op = sfg_copy.find_by_id(target)
            if target_op is None:
                raise ValueError(
                    f"No target operation with ID {target} found in the SFG"
                )

        # Perform the extraction
        inputs = []
        outputs = []
        for target_gid in targets:
            op = sfg_copy.find_by_id(target_gid)
            # Find all input ports to the subgraph
            for input_port in op.inputs:
                sig = input_port.signals[0]
                if sig.source_operation.graph_id not in targets:
                    input_op = Input()
                    sig.remove_destination()
                    input_port.connect(input_op)
                    inputs.append((sig.graph_id, input_op))

            # Find all output ports from the subgraph
            for output_port in op.outputs:
                for sig in output_port.signals[:]:
                    if sig.destination_operation.graph_id not in targets:
                        output_op = Output()
                        output_op.input(0).connect(output_port)
                        sig.remove_source()
                        outputs.append((sig.graph_id, output_op))

        sub_sfg = SFG(
            inputs=[inp[1] for inp in inputs],
            outputs=[out[1] for out in outputs],
        )

        # Map the external signals (from the original sfg_copy) to the corresponding
        # input/output operations created inside sub_sfg (which now have graph_ids).
        sub_inputs = list(sub_sfg.input_operations)
        sub_outputs = list(sub_sfg.output_operations)
        if len(inputs) != len(sub_inputs) or len(outputs) != len(sub_outputs):
            raise RuntimeError(
                "Mismatch between extracted boundary ports and sub-SFG ports"
            )

        for idx, ((in_sig_id, _), (out_sig_id, _)) in enumerate(
            zip(inputs, outputs, strict=False)
        ):
            in_sig = sfg_copy.find_by_id(in_sig_id)
            in_sig.remove_destination()
            in_sig.set_destination(sub_sfg.input(idx))

            out_sig = sfg_copy.find_by_id(out_sig_id)
            out_sig.remove_source()
            out_sig.set_source(sub_sfg.output(idx))

        return sfg_copy()

    def replace(self, target: GraphID, component: Operation) -> "SFG":
        sfg_copy = self()

        # Check that the target is valid
        if target is None:
            raise ValueError("Given target cannot be None")
        if not isinstance(target, str):
            raise TypeError("Given target is not a GraphID")
        target_op = sfg_copy.find_by_id(target)
        if target_op is None:
            raise ValueError(
                f"No target operation with Graph ID {target} found in the SFG"
            )

        # Check that the component is valid
        if component is None:
            raise ValueError("Given component cannot be None")
        if not isinstance(component, Operation):
            raise TypeError("Given component is not an Operation")

        # Check that component and target are compatible
        if component.input_count != target_op.input_count:
            raise TypeError(
                "The input count may not differ between the provided component and target"
            )
        if component.output_count != target_op.output_count:
            raise TypeError(
                "The output count may not differ between the provided component and target"
            )

        # Perform the replacement
        for index_in, input_ in enumerate(target_op.inputs):
            for signal in input_.signals:
                signal.remove_destination()
                signal.set_destination(component.input(index_in))

        for index_out, output in enumerate(target_op.outputs):
            for signal in output.signals[:]:
                signal.remove_source()
                signal.set_source(component.output(index_out))

        if isinstance(target_op, Output):
            sfg_copy._output_operations.remove(target_op)
            warnings.warn(
                f"Output port {target_op.graph_id} has been removed", stacklevel=2
            )
        if isinstance(component, Output):
            sfg_copy._output_operations.append(component)

        return sfg_copy()

    def insert_operation(self, component: Operation, output_comp_id: GraphID) -> "SFG":
        """
        Insert an operation in the SFG after a given source operation.

        The source operation output count must match the input count of the operation
        as well as the output.
        Then return a new deepcopy of the sfg with the inserted component.

        Parameters
        ----------
        component : Operation
            The new component, e.g. Multiplication.
        output_comp_id : GraphID
            The source operation GraphID to connect from.
        """
        # Preserve the original SFG by creating a copy.
        sfg_copy = self()
        comp = sfg_copy._add_component_unconnected_copy(component)
        output_comp = cast(Operation, sfg_copy.find_by_id(output_comp_id))
        if output_comp is None:
            return None

        if isinstance(output_comp, Output):
            raise TypeError("Source operation cannot be an output operation.")
        if len(output_comp.output_signals) != comp.input_count:
            raise TypeError(
                "Source operation output count"
                f" ({len(output_comp.output_signals)}) does not match input"
                f" count for component ({comp.input_count})."
            )
        if len(output_comp.output_signals) != comp.output_count:
            raise TypeError(
                "Destination operation input count does not match output for component."
            )

        for index, signal_in in enumerate(output_comp.output_signals):
            destination = cast(InputPort, signal_in.destination)
            signal_in.set_destination(comp.input(index))
            destination.connect(comp.output(index))

        # Recreate the newly coupled SFG so that all attributes are correct.
        return sfg_copy()

    def insert_operation_after(
        self,
        output_comp_id: GraphID,
        new_operation: Operation,
    ) -> "SFG":
        """
        Insert an operation in the SFG after a given source operation.

        Then return a new deepcopy of the sfg with the inserted component.

        The graph_id can be an Operation or a Signal. If the operation has multiple
        outputs, (copies of) the same operation will be inserted on every port.
        To specify a port use ``'graph_id.port_number'``, e.g., ``'sym2p4.1'``.

        Currently, the new operation must have one input and one output.

        Parameters
        ----------
        output_comp_id : GraphID
            The source operation GraphID to connect from.
        new_operation : Operation
            The new operation, e.g. Multiplication.
        """
        # Preserve the original SFG by creating a copy.
        sfg_copy = self()
        if new_operation.output_count != 1 or new_operation.input_count != 1:
            raise TypeError(
                "Only operations with one input and one output can be inserted."
            )
        if "." in output_comp_id:
            output_comp_id, port_id_str = output_comp_id.split(".")
            port_id = int(port_id_str)
        else:
            port_id = None

        output_comp = sfg_copy.find_by_id(output_comp_id)
        if output_comp is None:
            raise ValueError(f"Unknown component: {output_comp_id!r}")
        if isinstance(output_comp, Operation):
            comp = sfg_copy._add_component_unconnected_copy(new_operation)

            if port_id is None:
                sfg_copy._insert_operation_after_operation(output_comp, comp)
            else:
                sfg_copy._insert_operation_after_outputport(
                    output_comp.output(port_id), comp
                )
        elif isinstance(output_comp, Signal):
            sfg_copy._insert_operation_before_signal(output_comp, comp)
        # Recreate the newly coupled SFG so that all attributes are correct.
        return sfg_copy()

    def insert_operation_before(
        self,
        input_comp_id: GraphID,
        new_operation: Operation,
        port: int | None = None,
    ) -> "SFG":
        """
        Insert an operation in the SFG before a given source operation.

        Then return a new deepcopy of the sfg with the inserted component.

        The graph_id can be an Operation or a Signal. If the operation has multiple
        inputs, (copies of) the same operation will be inserted on every port.
        To specify a port use the ``port`` parameter.

        Currently, the new operation must have one input and one output.

        Parameters
        ----------
        input_comp_id : GraphID
            The source operation GraphID to connect to.
        new_operation : Operation
            The new operation, e.g. Multiplication.
        port : int, optional
            The number of the InputPort before which the new operation shall be
            inserted.
        """
        # Preserve the original SFG by creating a copy.
        sfg_copy = self()
        if new_operation.output_count != 1 or new_operation.input_count != 1:
            raise TypeError(
                "Only operations with one input and one output can be inserted."
            )

        input_comp = sfg_copy.find_by_id(input_comp_id)
        if input_comp is None:
            raise ValueError(f"Unknown component: {input_comp_id!r}")
        if isinstance(input_comp, Operation):
            comp = sfg_copy._add_component_unconnected_copy(new_operation)
            if port is None:
                sfg_copy._insert_operation_before_operation(input_comp, comp)
            else:
                sfg_copy._insert_operation_before_inputport(
                    input_comp.input(port), comp
                )
        elif isinstance(input_comp, Signal):
            sfg_copy._insert_operation_after_signal(input_comp, comp)

        # Recreate the newly coupled SFG so that all attributes are correct.
        return sfg_copy()

    def simplify_delay_element_placement(self) -> "SFG":
        """
        Simplify an SFG by removing redundant delay elements.

        For example, two signals originating from the same starting point, each
        connected to a delay element will combine into a single delay element.

        Returns a copy of the simplified SFG.
        """
        sfg_copy = self()
        no_of_delays = len(sfg_copy.find_by_type(Delay))
        while True:
            for delay_element in sfg_copy.find_by_type(Delay):
                if len(delay_element.inputs[0].signals) > 0:
                    neighboring_delays = [
                        signal.destination.operation
                        for signal in delay_element.inputs[0].signals[0].source.signals
                        if isinstance(signal.destination.operation, Delay)
                    ]

                    if delay_element in neighboring_delays:
                        neighboring_delays.remove(delay_element)

                    for delay in neighboring_delays:
                        for output in delay.outputs[0].signals:
                            output.set_source(delay_element.outputs[0])
                        in_sig = delay.input(0).signals[0]
                        delay.input(0).remove_signal(in_sig)
                        in_sig.source.remove_signal(in_sig)
            sfg_copy = sfg_copy()
            if no_of_delays <= len(sfg_copy.find_by_type(Delay)):
                break
            no_of_delays = len(sfg_copy.find_by_type(Delay))

        return sfg_copy

    def _insert_operation_after_operation(
        self, output_operation: Operation, new_operation: Operation
    ) -> None:
        for output in output_operation.outputs:
            self._insert_operation_after_outputport(output, new_operation.copy())

    def _insert_operation_before_operation(
        self, input_operation: Operation, new_operation: Operation
    ) -> None:
        for port in input_operation.inputs:
            self._insert_operation_before_inputport(port, new_operation.copy())

    def _insert_operation_after_outputport(
        self, output_port: OutputPort, new_operation: Operation
    ) -> None:
        # Make copy as list will be updated
        signal_list = output_port.signals[:]
        for signal in signal_list:
            signal.set_source(new_operation)
        new_operation.input(0).connect(output_port)

    def _insert_operation_before_inputport(
        self, input_port: InputPort, new_operation: Operation
    ) -> None:
        # Make copy as list will be updated
        input_port.signals[0].set_destination(new_operation)
        new_operation.output(0).add_signal(Signal(destination=input_port))

    def _insert_operation_before_signal(
        self, signal: Signal, new_operation: Operation
    ) -> None:
        output_port = signal.source
        output_port.remove_signal(signal)
        Signal(output_port, new_operation)
        signal.set_source(new_operation)

    def _insert_operation_after_signal(
        self, signal: Signal, new_operation: Operation
    ) -> None:
        input_port = signal.destination
        input_port.remove_signal(signal)
        Signal(new_operation, input_port)
        signal.set_destination(new_operation)

    def swap_io_of_operation(self, operation_id: GraphID) -> None:
        """
        Swap the inputs (and outputs) of operation.

        Parameters
        ----------
        operation_id : GraphID
            The GraphID of the operation to swap.
        """
        operation = cast(Operation, self.find_by_id(operation_id))
        if operation is not None:
            operation.swap_io()

    def remove_operation(self, operation_id: GraphID) -> Union["SFG", None]:
        """
        Remove operation.

        Returns a version of the SFG where the operation with the specified GraphID
        removed.

        The operation must have the same amount of input- and output ports or a
        ValueError is raised. If no operation with the entered operation_id is found
        then returns None and does nothing.

        Parameters
        ----------
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
        Return a precedence list of the SFG.

        In the precedence list each element in n:th the list consists of elements that
        are executed in the n:th step. If the precedence list already has been
        calculated for the current SFG then return the cached version.
        """
        if self._precedence_list:
            return self._precedence_list

        # Find all operations with only outputs and no inputs.
        no_input_ops = list(filter(lambda op: op.input_count == 0, self.operations))
        delay_ops = self.find_by_type(Delay)

        # Find all first iter output ports for precedence
        first_iter_ports = [
            output for op in (no_input_ops + delay_ops) for output in op.outputs
        ]

        self._precedence_list = self._traverse_for_precedence_list(first_iter_ports)

        return self._precedence_list

    def show_precedence_graph(self) -> None:
        """
        Display the output of :func:`precedence_graph` in the system viewer.
        """
        self.precedence_graph.view()

    @property
    def precedence_graph(self) -> Digraph:
        """
        The SFG in precedence form in Graphviz format.

        This can be rendered in enriched shells.
        """
        p_list = self.get_precedence_list()
        pg = Digraph()
        pg.attr(rankdir="LR")

        # Creates nodes for each output port in the precedence list
        for i, ports in enumerate(p_list):
            with pg.subgraph(name=f"cluster_{i}") as sub:
                sub.attr(label=f"N{i}")
                for port in ports:
                    port_string = port.name
                    if port.operation.output_count > 1:
                        sub.node(
                            port_string,
                            shape="rectangle",
                            height="0.1",
                            width="0.1",
                        )
                    else:
                        sub.node(
                            port_string,
                            shape="rectangle",
                            label=port.operation.graph_id,
                            height="0.1",
                            width="0.1",
                        )
        # Creates edges for each output port and creates nodes for each operation
        # and edges for them as well
        for ports in p_list:
            for port in ports:
                source_label = port.operation.graph_id
                node_node = port.name
                for signal in port.signals:
                    destination = cast(InputPort, signal.destination)
                    destination_label = destination.operation.graph_id
                    destination_node = (
                        destination_label + "In"
                        if isinstance(destination.operation, Delay)
                        else destination_label
                    )
                    pg.edge(node_node, destination_node)
                    pg.node(
                        destination_node,
                        label=destination_label,
                        shape=_OPERATION_SHAPE[destination.operation.type_name()],
                    )
                source_node = (
                    source_label + "Out"
                    if port.operation.type_name() == Delay.type_name()
                    else source_label
                )
                pg.edge(source_node, node_node)
                pg.node(
                    source_node,
                    label=source_label,
                    shape=_OPERATION_SHAPE[port.operation.type_name()],
                )

        return pg

    def print_precedence_graph(self) -> None:
        """
        Print a representation of the SFG precedence list to the standard out.

        If the precedence list already has been calculated then it uses the
        cached version, otherwise it calculates the precedence list and then
        prints it.
        """
        precedence_list = self.get_precedence_list()

        line = "-" * 120
        out_str = StringIO()
        out_str.write(line)

        printed_ops = set()

        for iter_num, iterable in enumerate(precedence_list, start=1):
            for outport_num, outport in enumerate(iterable, start=1):
                if outport not in printed_ops:
                    # Only print once per operation, even if it has multiple outports
                    out_str.write("\n")
                    out_str.write(str(iter_num))
                    out_str.write(".")
                    out_str.write(str(outport_num))
                    out_str.write(" \t")
                    out_str.write(outport.operation.graph_str())
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
        remaining_inports_per_operation = {op: op.input_count for op in self.operations}

        # Maps number of input counts to a queue of seen objects with such a size.
        seen_with_inputs_dict: dict[int, deque] = defaultdict(deque)
        seen = set()
        top_order = []

        if len(no_inputs_queue) == 0:
            raise ValueError("Illegal SFG state, dangling signals in SFG.")

        first_op = no_inputs_queue.popleft()
        visited = {first_op}
        p_queue = PriorityQueue()
        p_queue_entry_num = itertools.count()
        # Negative priority as max-heap popping is wanted
        p_queue.put((-first_op.output_count, -next(p_queue_entry_num), first_op))

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
                        remaining_inports = remaining_inports_per_operation[neighbor_op]

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
                                seen_with_inputs_dict[remaining_inports + 1].remove(
                                    neighbor_op
                                )
                            else:
                                seen.add(neighbor_op)
                                seen_but_not_visited_count += 1

                            seen_with_inputs_dict[remaining_inports].append(neighbor_op)

            # Check if have to fetch Operations from somewhere else since p_queue
            # is empty
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
                    for i in itertools.count(start=1):
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

    def set_latency_of_type_name(self, type_name: TypeName, latency: int) -> None:
        """
        Set the latency of all components with the given type name.

        Parameters
        ----------
        type_name : TypeName
            The type name of the operation. For example, obtained as
            ``Addition.type_name()``.
        latency : int
            The latency of the operation.
        """
        for op in self.find_by_type_name(type_name):
            cast(Operation, op).set_latency(latency)

    def set_latency_of_type(
        self, operation_type: type[Operation], latency: int
    ) -> None:
        """
        Set the latency of all operations with the given type.

        Parameters
        ----------
        operation_type : type of Operation
            The operation type. For example, ``Addition``.
        latency : int
            The latency of the operation.
        """
        for op in self.find_by_type(operation_type):
            cast(Operation, op).set_latency(latency)

    def set_execution_time_of_type_name(
        self, type_name: TypeName, execution_time: int
    ) -> None:
        """
        Set the execution time of all operations with the given type name.

        Parameters
        ----------
        type_name : TypeName
            The type name of the operation. For example, obtained as
            ``Addition.type_name()``.
        execution_time : int
            The execution time of the operation.
        """
        for op in self.find_by_type_name(type_name):
            cast(Operation, op).execution_time = execution_time

    def set_execution_time_of_type(
        self, operation_type: type[Operation], execution_time: int
    ) -> None:
        """
        Set the latency of all operations with the given type.

        Parameters
        ----------
        operation_type : type of Operation
            The operation type. For example, ``Addition``.
        execution_time : int
            The execution time of the operation.
        """
        for op in self.find_by_type(operation_type):
            cast(Operation, op).execution_time = execution_time

    def set_latency_offsets_of_type_name(
        self, type_name: TypeName, latency_offsets: dict[str, int]
    ) -> None:
        """
        Set the latency offsets of all operations with the given type name.

        Parameters
        ----------
        type_name : TypeName
            The type name of the operation. For example, obtained as
            ``Addition.type_name()``.
        latency_offsets : {"in1": int, ...}
            The latency offsets of the inputs and outputs.
        """
        for op in self.find_by_type_name(type_name):
            cast(Operation, op).set_latency_offsets(latency_offsets)

    def set_latency_offsets_of_type(
        self, operation_type: type[Operation], latency_offsets: dict[str, int]
    ) -> None:
        """
        Set the latency offsets of all operations with the given type.

        Parameters
        ----------
        operation_type : type of Operation
            The operation type. For example, ``Addition``.
        latency_offsets : {"in1": int, ...}
            The latency offsets of the inputs and outputs.
        """
        for op in self.find_by_type(operation_type):
            cast(Operation, op).set_latency_offsets(latency_offsets)

    def _traverse_for_precedence_list(
        self, first_iter_ports: list[OutputPort]
    ) -> list[list[OutputPort]]:
        # Find dependencies of output ports and input ports.
        remaining_inports_per_operation = {op: op.input_count for op in self.operations}

        # Traverse output ports for precedence
        curr_iter_ports = first_iter_ports
        precedence_list = []

        while curr_iter_ports:
            # Add the found ports to the current iter
            precedence_list.append(curr_iter_ports)

            next_iter_ports = []

            for outport in curr_iter_ports:
                for signal in outport.signals:
                    new_input_port = signal.destination
                    # Do not traverse over delays.
                    if new_input_port is not None and not isinstance(
                        new_input_port.operation, Delay
                    ):
                        new_op = new_input_port.operation
                        remaining_inports_per_operation[new_op] -= 1
                        if remaining_inports_per_operation[new_op] == 0:
                            next_iter_ports.extend(new_op.outputs)

            curr_iter_ports = next_iter_ports

        return precedence_list

    def _add_component_unconnected_copy(
        self, original_component: GraphComponent
    ) -> GraphComponent:
        if original_component in self._original_components_to_new:
            graph_id = (
                original_component.name
                if original_component.name
                else (
                    original_component.graph_id
                    if original_component.graph_id
                    else original_component.type_name()
                )
            )
            raise ValueError(f"Tried to add duplicate SFG component: {graph_id}")
        new_component = original_component.copy()
        self._original_components_to_new[original_component] = new_component
        if not new_component.graph_id or new_component.graph_id in self._used_ids:
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
                new_op = cast(Operation, self._original_components_to_new[original_op])

            # Connect input ports to new signals.
            for original_input_port in original_op.inputs:
                if original_input_port.signal_count < 1:
                    graph_id = (
                        original_op.name
                        if original_op.name
                        else (
                            original_op.graph_id
                            if original_op.graph_id
                            else original_op.type_name()
                        )
                    )
                    raise ValueError(
                        f"Unconnected input port in SFG. Operation: {graph_id}"
                    )

                for original_signal in original_input_port.signals:
                    # Check if the signal is one of the SFG's input signals.
                    if original_signal in self._original_input_signals_to_indices:
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
                        if source.operation not in self._operations_dfs_order:
                            self._operations_dfs_order.append(source.operation)

                    # Check if the signal has not been added before.
                    elif original_signal not in self._original_components_to_new:
                        if original_signal.source is None:
                            dest = (
                                original_signal.destination.operation.name
                                if original_signal.destination is not None
                                else "None"
                            )
                            raise ValueError(
                                "Dangling signal without source in SFG"
                                f" (destination: {dest})"
                            )

                        new_signal = cast(
                            Signal,
                            self._add_component_unconnected_copy(original_signal),
                        )

                        new_signal.set_destination(
                            new_op.input(original_input_port.index)
                        )

                        self._components_dfs_order.append(new_signal)

                        original_connected_op = original_signal.source.operation
                        # Check if connected Operation has been added before.
                        if original_connected_op in self._original_components_to_new:
                            component = cast(
                                Operation,
                                self._original_components_to_new[original_connected_op],
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
                                new_connected_op.output(original_signal.source.index)
                            )

                            self._components_dfs_order.append(new_connected_op)
                            self._operations_dfs_order.append(new_connected_op)

                            # Add connected operation to queue of operations to visit.
                            op_stack.append(original_connected_op)

            # Connect output ports.
            for original_output_port in original_op.outputs:
                for original_signal in original_output_port.signals:
                    # Check if the signal is one of the SFG's output signals.
                    if original_signal in self._original_output_signals_to_indices:
                        # New signal already created during first step of constructor.
                        new_signal = cast(
                            Signal,
                            self._original_components_to_new[original_signal],
                        )

                        new_signal.set_source(new_op.output(original_output_port.index))

                        destination = cast(InputPort, new_signal.destination)
                        self._components_dfs_order.extend(
                            [new_signal, destination.operation]
                        )
                        self._operations_dfs_order.append(destination.operation)

                    # Check if signal has not been added before.
                    elif original_signal not in self._original_components_to_new:
                        if original_signal.source is None:
                            raise ValueError(
                                "Dangling signal ({original_signal}) without"
                                " source in SFG"
                            )

                        new_signal = cast(
                            Signal,
                            self._add_component_unconnected_copy(original_signal),
                        )
                        new_signal.set_source(new_op.output(original_output_port.index))

                        self._components_dfs_order.append(new_signal)
                        original_destination = cast(
                            InputPort, original_signal.destination
                        )
                        if original_destination is None:
                            raise ValueError(
                                f"Signal ({original_signal}) without destination in SFG"
                            )

                        original_connected_op = original_destination.operation
                        if original_connected_op is None:
                            raise ValueError(
                                "Signal with empty destination port"
                                f" ({original_destination}) in SFG"
                            )
                        # Check if connected operation has been added.
                        if original_connected_op in self._original_components_to_new:
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
                                new_connected_op.input(original_destination.index)
                            )

                            self._components_dfs_order.append(new_connected_op)
                            self._operations_dfs_order.append(new_connected_op)

                            # Add connected operation to the queue of operations
                            # to visit.
                            op_stack.append(original_connected_op)

    def _evaluate_source(
        self,
        src: OutputPort,
        results: MutableResultMap,
        delays: MutableDelayMap,
        prefix: str,
        deferred_delays: DelayQueue,
    ) -> Num:
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
        deferred_delays: DelayQueue,
    ) -> Num:
        input_values = [
            self._evaluate_source(
                input_port.signals[0].source,
                results,
                delays,
                prefix,
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
        )
        results[key] = value
        return value

    def sfg_digraph(
        self,
        show_signal_id: bool = False,
        engine: str | None = None,
        branch_node: bool = True,
        port_numbering: bool = True,
        splines: Literal["spline", "line", "ortho", "polyline", "curved"] = "spline",
    ) -> Digraph:
        """
        Return a Digraph of the SFG.

        Can be directly displayed in IPython.

        Parameters
        ----------
        show_signal_id : bool, default: False
            If True, the graph_id:s of signals are shown.
        engine : str, optional
            Graphviz layout engine to be used, see https://graphviz.org/documentation/.
            Most common are "dot" and "neato". Default is None leading to dot.
        branch_node : bool, default: True
            Add a branch node in case the fan-out of a signal is two or more.
        port_numbering : bool, default: True
            Show the port number in case the number of ports (input or output) is two or
            more.
        splines : {"spline", "line", "ortho", "polyline", "curved"}, default: "spline"
            Spline style, see https://graphviz.org/docs/attrs/splines/ for more info.

        Returns
        -------
        Digraph
            Digraph of the SFG.
        """
        dg = Digraph()
        dg.attr(rankdir="LR", splines=splines)
        branch_nodes = set()
        if engine is not None:
            dg.engine = engine
        for op in self._components_by_id.values():
            if isinstance(op, Signal):
                source = cast(OutputPort, op.source)
                destination = cast(InputPort, op.destination)
                source_name = (
                    source.name
                    if branch_node and source.signal_count > 1
                    else source.operation.graph_id
                )
                label = op.graph_id if show_signal_id else None
                taillabel = (
                    str(source.index)
                    if source.operation.output_count > 1
                    and (not branch_node or source.signal_count == 1)
                    and port_numbering
                    else None
                )
                headlabel = (
                    str(destination.index)
                    if destination.operation.input_count > 1 and port_numbering
                    else None
                )
                dg.edge(
                    source_name,
                    destination.operation.graph_id,
                    label=label,
                    taillabel=taillabel,
                    headlabel=headlabel,
                )
                if (
                    branch_node
                    and source.signal_count > 1
                    and source_name not in branch_nodes
                ):
                    branch_nodes.add(source_name)
                    dg.node(source_name, shape="point")
                    taillabel = (
                        str(source.index)
                        if source.operation.output_count > 1 and port_numbering
                        else None
                    )
                    dg.edge(
                        source.operation.graph_id,
                        source_name,
                        arrowhead="none",
                        taillabel=taillabel,
                    )
            else:
                dg.node(
                    op.graph_id,
                    shape=_OPERATION_SHAPE[op.type_name()],
                    label=f"{op.name}\n({op.graph_id})" if op.name else None,
                )
        return dg

    def _repr_mimebundle_(self, include=None, exclude=None):
        return self.sfg_digraph()._repr_mimebundle_(include=include, exclude=exclude)

    def _repr_jpeg_(self):
        return self.sfg_digraph()._repr_mimebundle_(include=["image/jpeg"])[
            "image/jpeg"
        ]

    def _repr_png_(self):
        return self.sfg_digraph()._repr_mimebundle_(include=["image/png"])["image/png"]

    def _repr_svg_(self):
        return self.sfg_digraph()._repr_mimebundle_(include=["image/svg+xml"])[
            "image/svg+xml"
        ]

    # SVG is valid HTML. This is useful for e.g. sphinx-gallery
    _repr_html_ = _repr_svg_

    def show(
        self,
        fmt: str | None = None,
        show_signal_id: bool = False,
        engine: str | None = None,
        branch_node: bool = True,
        port_numbering: bool = True,
        splines: Literal["spline", "line", "ortho", "polyline", "curved"] = "spline",
    ) -> None:
        """
        Display a visual representation of the SFG using the default system viewer.

        Parameters
        ----------
        fmt : str, optional
            File format of the generated graph. Output formats can be found at
            https://www.graphviz.org/doc/info/output.html
            Most common are "pdf", "eps", "png", and "svg". Default is None which
            leads to PDF.
        show_signal_id : bool, default: False
            If True, the graph_id:s of signals are shown.
        engine : str, optional
            Graphviz layout engine to be used, see https://graphviz.org/documentation/.
            Most common are "dot" and "neato". Default is None leading to dot.
        branch_node : bool, default: True
            Add a branch node in case the fan-out of a signal is two or more.
        port_numbering : bool, default: True
            Show the port number in case the number of ports (input or output) is two or
            more.
        splines : {"spline", "line", "ortho", "polyline", "curved"}, default: "spline"
            Spline style, see https://graphviz.org/docs/attrs/splines/ for more info.
        """
        dg = self.sfg_digraph(
            show_signal_id=show_signal_id,
            engine=engine,
            branch_node=branch_node,
            port_numbering=port_numbering,
            splines=splines,
        )
        if fmt is not None:
            dg.format = fmt
        dg.view()

    def critical_path_time(self) -> int:
        """Return the time of the critical path."""
        # Import here needed to avoid circular imports
        from b_asic.schedule import Schedule  # noqa: PLC0415
        from b_asic.scheduler import ASAPScheduler  # noqa: PLC0415

        return Schedule(self, ASAPScheduler()).schedule_time

    def _dfs(self, graph, start, end):
        """
        Find loop(s) in graph.

        Parameters
        ----------
        graph : dictionary
            The dictionary that are to be searched for loops.
        start : key in dictionary graph
            The "node" in the dictionary that are set as the start point.
        end : key in dictionary graph
            The "node" in the dictionary that are set as the end point.
        """
        fringe = [(start, [])]
        while fringe:
            state, path = fringe.pop()
            if path and state == end:
                yield path
                continue
            for next_state in graph[state]:
                if next_state in path:
                    continue
                fringe.append((next_state, [*path, next_state]))

    def resource_lower_bound(self, type_name: TypeName, schedule_time: int) -> int:
        """
        Return the lowest amount of resources of the given type needed to reach the scheduling time.

        Parameters
        ----------
        type_name : TypeName
            Type name of the given resource.
        schedule_time : int
            Scheduling time to evaluate for.
        """
        ops = self.find_by_type_name(type_name)
        if not ops:
            return 0
        if schedule_time <= 0:
            raise ValueError(
                f"Schedule time must be positive, current schedule time is: {schedule_time}."
            )
        exec_times = [cast(Operation, op).execution_time for op in ops]
        if any(time is None for time in exec_times):
            raise ValueError(
                f"Execution times not set for all operations of type {type_name}."
            )

        total_exec_time = sum(exec_times)
        return math.ceil(total_exec_time / schedule_time)

    def iteration_period_bound(self) -> Fraction:
        """
        Return the iteration period bound of the SFG.

        If -1, the SFG does not have any loops and therefore no iteration period bound.

        Returns
        -------
        The iteration period bound.
        """
        loops = self.loops
        if not loops:
            return Fraction(-1)

        op_and_latency = {}
        for op in self.operations:
            for loop in loops:
                for _ in loop:
                    if op.type_name() not in op_and_latency:
                        op_and_latency[op.type_name()] = op.latency
        t_l_values = []

        for loop in loops:
            loop.pop()
            time_of_loop = 0
            number_of_t_in_loop = 0
            for element in loop:
                if isinstance(self.find_by_id(element), Delay):
                    number_of_t_in_loop += 1
                for key, item in op_and_latency.items():
                    if key in element:
                        time_of_loop += item
            if number_of_t_in_loop in (0, 1):
                t_l_values.append(Fraction(time_of_loop, 1))
            else:
                t_l_values.append(Fraction(time_of_loop, number_of_t_in_loop))
        return max(t_l_values)

    @property
    def loops(self) -> list[list[GraphID]]:
        """
        Return the recursive loops found in the SFG.

        Returns
        -------
        A list of the recursive loops.
        """
        if not self.input_count:
            return []
        dict_of_sfg: dict[GraphID, list[GraphID]] = {}
        queue: deque[Operation] = deque(self._input_operations)
        visited: set[Operation] = set(self._input_operations)
        while queue:
            op = queue.popleft()
            for output_port in op.outputs:
                if not isinstance(op, (Input, Output)):
                    dict_of_sfg[op.graph_id] = []
                for signal in output_port.signals:
                    if signal.destination is not None:
                        new_op = signal.destination.operation
                        if not isinstance(op, (Input, Output)) and not isinstance(
                            new_op, Output
                        ):
                            dict_of_sfg[op.graph_id].append(new_op.graph_id)
                        if new_op not in visited:
                            queue.append(new_op)
                            visited.add(new_op)
                    else:
                        raise ValueError("Destination for {signal!r} does not exist")
        cycles = [
            [node, *path]
            for node in dict_of_sfg
            for path in self._dfs(dict_of_sfg, node, node)
        ]

        # Get non-redundant cycles
        unique_lists = []
        seen_cycles = set()
        for cycle in cycles:
            operation_set = frozenset(cycle)
            if operation_set not in seen_cycles:
                unique_lists.append(cycle)
                seen_cycles.add(operation_set)
        return unique_lists

    def to_ss(self) -> StateSpace:
        """
        Return the state-space representation of the SFG.

        Returns
        -------
        The state-space representation.
        """
        return StateSpace.from_sfg(self)

    def to_tf(self):
        """
        Return the transfer function representation of the SFG.

        Returns
        -------
        The transfer function representation.
        """
        from b_asic.transfer_function import TransferFunction  # noqa: PLC0415

        return TransferFunction.from_sfg(self)

    def find_all_paths(
        self, graph: dict, start: str, end: str, path: list | None = None
    ) -> list:
        """
        Find all paths in graph from node start to node end.

        Parameters
        ----------
        graph : dictionary
            The dictionary that are to be searched for loops.
        start : key in dictionary graph
            The "node" in the dictionary that are set as the start point.
        end : key in dictionary graph
            The "node" in the dictionary that are set as the end point.
        path : list
            This parameter should not be provided directly and is only used internally.

        Returns
        -------
        The state-space representation of the SFG.
        """
        if path is None:
            path = []

        path = [*path, start]
        if start == end:
            return [path]
        if start not in graph:
            return []
        paths = []
        for node in graph[start]:
            if node not in path:
                paths.extend(self.find_all_paths(graph, node, end, path))
        return paths

    def operation_counter(self) -> Counter:
        """Return a Counter with the number of instances for each type."""
        return Counter(op.type_name() for op in self.operations)

    def edit(self) -> dict[str, "SFG"]:
        """Edit SFG in GUI."""
        from b_asic.sfg_gui.main_window import start_editor  # noqa: PLC0415

        return start_editor(self)

    def unfold(self, factor: int) -> "SFG":
        """
        Unfold the SFG *factor* times. Return a new SFG without modifying the original.

        Inputs and outputs are ordered with early inputs first. That is for an SFG
        with n inputs, the first n inputs are the inputs at time t, the next n
        inputs are the inputs at time t+1, the next n at t+2 and so on.

        Parameters
        ----------
        factor : int
            Number of times to unfold.
        """
        if factor == 0:
            raise ValueError("Unfolding 0 times removes the SFG")

        sfg = self()  # copy the sfg

        inputs = sfg.input_operations
        outputs = sfg.output_operations

        # Remove all delay elements in the SFG and replace each one
        # with one input operation and one output operation
        for delay in sfg.find_by_type(Delay):
            tmp_input = Input(name="input_" + delay.graph_id)
            tmp_output = Output(
                src0=delay.input(0).signals[0].source, name="output_" + delay.graph_id
            )

            inputs.append(tmp_input)
            outputs.append(tmp_output)

            # move all outgoing signals from the delay to the new input operation
            while len(delay.output(0).signals) > 0:
                signal = delay.output(0).signals[0]
                destination = signal.destination
                destination.remove_signal(signal)
                signal.remove_source()
                destination.connect(tmp_input.output(0))

            delay.input(0).signals[0].remove_source()
            delay.input(0).clear()

        new_sfg = SFG(inputs, outputs)  # The new sfg without the delays

        sfgs = [new_sfg() for _ in range(factor)]  # Copy the SFG factor times

        # Add suffixes to all graphIDs and names in order to keep them separated
        for i in range(factor):
            for operation in sfgs[i].operations:
                suffix = f"_{i}"
                operation.graph_id = operation.graph_id + suffix
                if operation.name[:7] not in ["", "input_t", "output_"]:
                    operation.name = operation.name + suffix

        input_name_to_idx = {}  # save the input port indices for future reference
        new_inputs = []
        # For each copy of the SFG, create new input operations for every "original"
        # input operation and connect them to begin creating the unfolded SFG
        for i in range(factor):
            for port, operation in zip(
                sfgs[i].inputs, sfgs[i].input_operations, strict=True
            ):
                if not operation.name.startswith("input_t"):
                    i = Input()
                    new_inputs.append(i)
                    port.connect(i)
                else:
                    # If the input was created earlier when removing the delays
                    # then just save the index
                    input_name_to_idx[operation.name] = port.index

        # Connect the original outputs in the same way as the inputs
        # Also connect the copies of the SFG together according to a formula
        # from the TSTE87 course material, and save the number of delays for
        # each interconnection
        new_outputs = []
        delay_placements = {}
        for i in range(factor):
            for port, operation in zip(
                sfgs[i].outputs, sfgs[i].output_operations, strict=True
            ):
                if not operation.name.startswith("output_t"):
                    new_outputs.append(Output(port))
                else:
                    index = operation.name[8:]  # Remove the "output_t" prefix
                    j = (i + 1) % factor
                    number_of_delays_between = (i + 1) // factor
                    input_port = sfgs[j].input(input_name_to_idx["input_t" + index])
                    input_port.connect(port)
                    delay_placements[port] = [i, number_of_delays_between]
            # deterministically set the graphID of the SFGs
            sfgs[i].graph_id = f"sfg{i}"

        sfg = SFG(new_inputs, new_outputs)  # create a new SFG to remove floating nodes

        # Insert the interconnect delays according to what is saved in delay_placements
        for port, val in delay_placements.items():
            i, no_of_delays = val
            for _ in range(no_of_delays):
                sfg = sfg.insert_operation_after(f"sfg{i}.{port.index}", Delay())

        # Flatten all the copies of the original SFG
        for i in range(factor):
            sfg.find_by_id(f"sfg{i}").connect_external_signals_to_components()
            sfg = sfg()

        return sfg

    def rewrite(
        self,
        source: type[Operation],
        target: OpSpecifier | Iterable[OpSpecifier],
    ) -> None:
        """
        Return a new SFG with the specified operations rewritten.

        The operations specified by *target* are replaced by the operations specified by *substitute*.

        Parameters
        ----------
        source : Type[Operation]
            The type of operation to replace the target(s) with.
        target : OpSpecifier | Iterable[OpSpecifier]
            The operation(s) to be replaced.
        """
        if isinstance(target, type) and issubclass(target, Operation):
            target = self.find_by_type(target)
        elif not isinstance(target, (list, tuple, set)):
            target = [target]

        # Validate that the source is an Operation type
        if not isinstance(source, type) or not issubclass(source, Operation):
            raise TypeError("Source must be an Operation type")

        new_sfg = self()
        for t in target:
            if isinstance(t, str):
                op = self.find_by_id(t)
                if op is None:
                    raise ValueError(
                        f"Graph ID {t} not found in SFG and cannot be replaced"
                    )
            elif isinstance(t, Operation):
                op = t
            elif isinstance(t, type) and issubclass(t, Operation):
                op = self.find_by_type(t)
            else:
                raise TypeError("Target must be a GraphID or an Operation type")

            func_name = f"_rewrite_{source.__name__}"
            if hasattr(op, func_name):
                sub_sfg = getattr(op, func_name)()
                new_sfg = new_sfg.replace(op.graph_id, sub_sfg)
            else:
                warnings.warn(
                    f"No rewrite method found for target operation type {type(op).__name__} to source operation type {source.__name__}",
                    stacklevel=2,
                )
                # Try the other way around
                func_name = f"_from_{type(op).__name__}"
                if hasattr(source, func_name):
                    sub_sfg = getattr(source, func_name)(op)
                    new_sfg = new_sfg.replace(op.graph_id, sub_sfg)
                else:
                    warnings.warn(
                        f"No rewrite method found for target operation type {type(op).__name__} to source operation type {source.__name__}",
                        stacklevel=2,
                    )
                    return new_sfg()

            if not isinstance(sub_sfg, SFG):
                continue

            new_sfg.find_by_id("sfg0").connect_external_signals_to_components()
            new_sfg = new_sfg()

        return new_sfg()

    def _rewrite_ShiftAddSub(self) -> "SFG":
        from b_asic.core_operations import (  # noqa: PLC0415
            Addition,
            AddSub,
            Shift,
            ShiftAddSub,
            Subtraction,
        )

        if len(self.inputs) != 2:
            raise ValueError("SFG to ShiftAddSub rewrite requires exactly 2 inputs")

        ops = [op for op in self.operations if not isinstance(op, (Input, Output))]
        if len(ops) != 2:
            raise ValueError("SFG to ShiftAddSub rewrite requires exactly 2 operations")

        # check that one operation is a shift and one is an addsub-like operation
        if not (
            isinstance(ops[0], Shift)
            and isinstance(ops[1], (Addition, Subtraction, AddSub))
        ) or (
            isinstance(ops[1], Shift)
            and isinstance(ops[0], (Addition, Subtraction, AddSub))
        ):
            raise ValueError(
                "SFG to ShiftAddSub rewrite requires one Shift and one of (Addition, Subtraction, AddSub)"
            )

        # determine the modes of the ShiftAddSub operation
        for op in ops:
            if isinstance(op, Addition):
                is_add = True
            elif isinstance(op, Subtraction):
                is_add = False
            elif isinstance(op, AddSub):
                is_add = op.is_add
            else:
                shift = op.value

        # Construct and return the new SFG
        in0 = Input()
        in1 = Input()
        op = ShiftAddSub(in0, in1, is_add=is_add, shift=shift)
        outs = []
        for out in self.outputs:
            out = Output()
            out <<= op
            outs.append(out)

        op_after_in0 = self.find_by_id("in0").output(0).signals[0].destination_operation
        if isinstance(op_after_in0, Shift):
            sfg = SFG([in1, in0], outs)
        else:
            sfg = SFG([in0, in1], outs)
        return sfg

    def join(self, target: GraphID, direction: Literal["forward", "backward"]) -> "SFG":
        """
        Return a new SFG with the specified operation joined with its predecessor or successor.

        Parameters
        ----------
        target : GraphID
            The operation to be joined with its predecessor(s) or successor(s).
        direction : {"forward", "backward"}
            The direction to join. "forward" joins with the successor(s), "backward" with the predecessor(s).
        """
        new_sfg = self()
        op = new_sfg.find_by_id(target)
        if not isinstance(op, Operation):
            raise ValueError(f"Operation {target} not found in SFG")

        if direction not in ["forward", "backward"]:
            raise ValueError("Direction must be 'forward' or 'backward'")

        if direction == "forward":
            if len(op.outputs) != 1:
                raise ValueError(
                    "Can only join forward if the operation has exactly one output"
                )
            for sig in op.output(0).signals:
                dest_op = sig.destination_operation
                if hasattr(op, "_join"):
                    joined_op = op._join(dest_op)
                    new_sfg = new_sfg.replace(dest_op.graph_id, joined_op)
                    new_sfg.find_by_id("sfg0").connect_external_signals_to_components()
                    new_sfg = new_sfg()
            new_sfg = new_sfg.remove_operation(target)
        elif direction == "backward":
            raise NotImplementedError("Joining backward is not implemented yet")
        return new_sfg

    @property
    def is_linear(self) -> bool:
        return all(op.is_linear for op in self.split())

    @property
    def is_constant(self) -> bool:
        return all(output.is_constant for output in self._output_operations)

    def get_used_type_names(self) -> list[TypeName]:
        """Get a list of all TypeNames used in the SFG."""
        ret = list({op.type_name() for op in self.operations})
        ret.sort()
        return ret

    def get_used_operation_types(self) -> list[type[Operation]]:
        """Get a list of all Operations used in the SFG."""
        ret = list({type(op) for op in self.operations})
        ret.sort(key=lambda op: op.type_name())
        return ret

    def get_used_graph_ids(self) -> set[GraphID]:
        """Get a list of all GraphID:s used in the SFG."""
        ret = set({op.graph_id for op in self.operations})
        sorted(ret)
        return ret

    def _output_ports_decayed(
        self, op: Operation, sim: "Simulation", threshold: float
    ) -> bool:
        if isinstance(op, Output):
            key = op.graph_id
            return abs(sim.results[key][-1]) <= threshold
        for idx in range(op.output_count):
            key = op.key(idx, op.graph_id)
            if abs(sim.results[key][-1]) > threshold:
                return False
        return True

    def get_impulse_responses(
        self, threshold: float = 1e-12, max_iters: int = -1, all_nodes: bool = False
    ) -> dict[str, list[npt.NDArray]]:
        """
        Return the impulse response for all output ports of all operations in the SFG.

        The simulation runs until all output and delay values decay below the threshold.
        One impulse response is computed for each SFG input.

        Parameters
        ----------
        threshold : float, default: 1e-12
            The threshold below which output values are considered to have decayed to zero.

        all_nodes : bool, default: False
            If True, impulse responses are collected for all operations.
            If False, only output operations of the SFG are collected.

        max_iters : int, default: -1
            Maximum number of simulation time steps to prevent infinite loops.
            If -1, there is no limit.

        Returns
        -------
        dict[str, list[npt.NDArray]]
            Dictionary mapping each operation's output port key (e.g., "add1.0", "mul2.0")
            to a list of impulse responses (as numpy arrays), one for each SFG input.
        """
        # Determine target nodes based on all_nodes flag
        if all_nodes:
            target_nodes = [op for op in self.operations if not isinstance(op, Input)]
        else:
            target_nodes = list(self._output_operations)

        responses_dict = self._get_impulse_responses_between_nodes(
            list(self.input_operations), target_nodes, threshold, max_iters
        )

        # Construct the impulse responses dictionary
        impulse_responses = {}
        for target_op in target_nodes:
            if isinstance(target_op, Output):
                target_keys = [target_op.graph_id]
            else:
                # Collect all output ports for multi-output operations
                target_keys = [
                    target_op.key(idx, target_op.graph_id)
                    for idx in range(target_op.output_count)
                ]
            for target_key in target_keys:
                impulse_responses[target_key] = []
                for input_op in self.input_operations:
                    source_key = input_op.graph_id
                    response_key = (source_key, target_key)
                    if response_key in responses_dict:
                        impulse_responses[target_key].append(
                            responses_dict[response_key]
                        )
                    else:
                        impulse_responses[target_key].append(np.array([]))

        return impulse_responses

    def _get_impulse_responses_between_nodes(
        self,
        source_nodes: list[Operation],
        target_nodes: list[Operation],
        threshold: float = 1e-12,
        max_iters: int = -1,
    ) -> dict[tuple[str, str], npt.NDArray]:
        from b_asic.signal_generator import Impulse  # noqa: PLC0415
        from b_asic.simulation import Simulation  # noqa: PLC0415

        if not self.is_linear:
            raise ValueError("SFG must be linear to compute impulse responses")

        # For each source node, apply impulse and record responses at target nodes
        impulse_responses = {}
        ops_to_check = self._output_operations + self.find_by_type(Delay)
        for source_op in source_nodes:
            # Create impulse inputs -- impulse on this source, zero on others
            impulse_inputs = [
                Impulse() if inp_op == source_op else None
                for inp_op in self.input_operations
            ]
            sim = Simulation(self, impulse_inputs)
            # If the source is a delay, initialize its state to 1
            if isinstance(source_op, Delay):
                sim._delays[source_op.graph_id] = 1

            # Simulate until outputs and delay elements are below threshold or max_iters reached
            iteration = 0
            while max_iters < 0 or iteration < max_iters:
                sim.run_for(1)
                iteration += 1

                # Check for convergence after one full iteration
                if iteration > 1:
                    all_decayed = all(
                        self._output_ports_decayed(op, sim, threshold)
                        for op in ops_to_check
                    )
                    if all_decayed:
                        break

            # Collect responses at target nodes
            for target_op in target_nodes:
                source_key = source_op.graph_id

                if isinstance(target_op, Output):
                    target_keys = [target_op.graph_id]
                else:
                    # Collect all output ports for multi-output operations
                    target_keys = [
                        target_op.key(idx, target_op.graph_id)
                        for idx in range(target_op.output_count)
                    ]

                for target_key in target_keys:
                    response_key = (source_key, target_key)
                    response = sim.results[target_key]
                    # Find the last non-zero element to avoid multiple array copies
                    cutoff = len(response)
                    while cutoff > 0 and abs(response[cutoff - 1]) <= threshold:
                        cutoff -= 1
                    impulse_responses[response_key] = response[:cutoff]
        return impulse_responses

    def get_impulse_responses_from_nodes(
        self,
        nodes: list[GraphID] | None = None,
        threshold: float = 1e-12,
        max_iters: int = -1,
    ) -> dict[str, dict[str, npt.NDArray]]:
        """
        Return the impulse responses for the specified nodes to the SFG outputs.

        Can e.g. be used to compute roundoff noise gains.

        The simulation runs until all output and delay values decay below the threshold.
        Alternatively, a maximum number of iterations can be set to prevent infinite loops.

        Parameters
        ----------
        nodes : list[GraphID], optional
            List of operation GraphIDs where impulses should be injected.

        threshold : float, default: 1e-12
            The threshold below which output values are considered to have decayed to zero.

        max_iters : int, default: -1
            Maximum number of simulation time steps to prevent infinite loops.
            If -1, there is no limit.

        Returns
        -------
        dict[str, dict[str, npt.NDArray]]
            Dictionary mapping each SFG output GraphID (e.g., "out0", "out1")
            to a dictionary that maps operation GraphIDs to their corresponding
            impulse responses.
        """
        from b_asic.core_operations import Addition  # noqa: PLC0415
        from b_asic.utility_operations import DontCare, Sink  # noqa: PLC0415

        if not self.is_linear:
            raise ValueError("SFG must be linear to compute roundoff noise responses")

        sfg_copy = self()
        if nodes is None:
            nodes = [
                op
                for op in sfg_copy.operations
                if not isinstance(op, (Input, Output, DontCare, Sink, Delay))
            ]
        else:
            nodes = [
                sfg_copy.find_by_id(node_id)
                for node_id in nodes
                if sfg_copy.find_by_id(node_id) is not None
            ]

        # For each operation that performs quantization, create noise sources
        # and adders to inject noise into its outputs
        noise_inputs = []
        for op in nodes:
            for output_idx in range(op.output_count):
                noise_input = Input(name=f"noise_{op.graph_id}_out{output_idx}")
                noise_inputs.append(noise_input)
                noise_adder = Addition(
                    src0=op.output(output_idx),
                    src1=noise_input,
                    name=f"noise_add_{op.graph_id}_out{output_idx}",
                )
                output_port = op.output(output_idx)
                for signal in output_port.signals[:-1]:
                    signal.set_source(noise_adder.output(0))

        # Create new SFG with all inputs (original + noise) and original outputs
        all_inputs = list(sfg_copy.input_operations) + noise_inputs
        noise_sfg = SFG(inputs=all_inputs, outputs=list(sfg_copy.output_operations))

        # Get noise source operations in the new SFG
        num_original_inputs = sfg_copy.input_count
        noise_sfg_inputs = list(noise_sfg.input_operations)

        # Compute impulse responses from noise sources to outputs
        responses_dict = noise_sfg._get_impulse_responses_between_nodes(
            noise_sfg_inputs[num_original_inputs:],  # Only noise source inputs
            list(noise_sfg._output_operations),
            threshold,
            max_iters,
        )

        # Construct the noise gain dictionary with operation IDs
        noise_gains = {}
        for output_idx in range(len(noise_sfg._output_operations)):
            output_key = f"out{output_idx}"
            noise_gains[output_key] = {}

        # Map noise sources back to their original operations
        for noise_source_op in noise_sfg_inputs[num_original_inputs:]:
            noise_name = noise_source_op.name
            op_graph_id = noise_name.replace("noise_", "").rsplit("_out", 1)[0]

            for out_idx, output_op in enumerate(noise_sfg._output_operations):
                output_key = f"out{out_idx}"
                response_key = (noise_source_op.graph_id, output_op.graph_id)
                noise_gains[output_key][op_graph_id] = responses_dict[response_key]

        return noise_gains
