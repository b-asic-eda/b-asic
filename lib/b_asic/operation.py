"""
B-ASIC Operation Module.

Contains the base for operations that are used by B-ASIC.
"""

import collections
import collections.abc
import itertools as it
from abc import abstractmethod
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from numbers import Number
from typing import (
    TYPE_CHECKING,
    NewType,
    cast,
    overload,
)

import apytypes as apy
from apytypes import APyCFixed, APyCFloat, APyFixed, APyFloat

from b_asic.data_type import DataType, NumRepresentation
from b_asic.graph_component import AbstractGraphComponent, GraphComponent, GraphID, Name
from b_asic.port import InputPort, OutputPort, SignalSourceProvider
from b_asic.signal import Signal
from b_asic.types import Num, ShapeCoordinates

if TYPE_CHECKING:
    from b_asic.sfg import SFG


ResultKey = NewType("ResultKey", str)
ResultMap = Mapping[ResultKey, Num | None]
MutableResultMap = MutableMapping[ResultKey, Num | None]
DelayMap = Mapping[ResultKey, Num]
MutableDelayMap = MutableMapping[ResultKey, Num]


class Operation(GraphComponent, SignalSourceProvider):
    """
    Operation interface.

    Operations are graph components that perform a certain function.
    They are connected to each other by signals through their input/output
    ports.

    Operations can be evaluated independently using evaluate_output().
    Operations may specify how to quantize inputs through quantize_input().
    """

    @abstractmethod
    def __ilshift__(self, src: SignalSourceProvider) -> "Operation":
        """
        Overload the inline left shift operator.

        In order to make it connect the provided signal source
        to this operation's input, assuming it has exactly one input port.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def input_count(self) -> int:
        """
        Get the number of input ports.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def output_count(self) -> int:
        """
        Get the number of output ports.
        """
        raise NotImplementedError

    @abstractmethod
    def input(self, index: int) -> InputPort:
        """
        Get the input port at the given index.
        """
        raise NotImplementedError

    @abstractmethod
    def output(self, index: int) -> OutputPort:
        """Get the output port at the given index."""
        raise NotImplementedError

    @property
    @abstractmethod
    def inputs(self) -> Sequence[InputPort]:
        """Get all input ports."""
        raise NotImplementedError

    @property
    @abstractmethod
    def outputs(self) -> Sequence[OutputPort]:
        """Get all output ports."""
        raise NotImplementedError

    @property
    @abstractmethod
    def input_signals(self) -> Sequence[Signal]:
        """
        Get all the signals that are connected to this operation's input ports.

        The signals are not ordered.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def output_signals(self) -> Sequence[Signal]:
        """
        Get all the signals that are connected to this operation's output ports.

        The signals are not ordered.
        """
        raise NotImplementedError

    @abstractmethod
    def key(self, index: int, prefix: str = "") -> ResultKey:
        """
        Get the key used to access the output of a certain index.

        This keu can be used to access the simulation results and used as
        the *output* parameter passed to current_output(s) or evaluate_output(s).
        """
        raise NotImplementedError

    @abstractmethod
    def current_output(
        self, index: int, delays: DelayMap | None = None, prefix: str = ""
    ) -> Num | None:
        """
        Get the current output at the given index of this operation, if available.

        The *delays* parameter will be used for lookup.
        The *prefix* parameter will be used as a prefix for the key string when looking
        for delays.

        See Also
        --------
        current_outputs, evaluate_output, evaluate_outputs
        """
        raise NotImplementedError

    @abstractmethod
    def evaluate_output(
        self,
        index: int,
        input_values: Sequence[Num],
        results: MutableResultMap | None = None,
        delays: MutableDelayMap | None = None,
        prefix: str = "",
        data_type: DataType | None = None,
    ) -> Num:
        """
        Evaluate the output at the given index with the given input values.

        Parameters
        ----------
        index : int
            Which output to return the value for.
        input_values : array of float or complex
            The input values.
        results : MutableResultMap, optional
            Used to store any results (including intermediate results)
            for caching.
        delays : MutableDelayMap, optional
            Used to get the current value of any intermediate delay elements
            that are encountered, and be updated with their new values.
        prefix : str, optional
            Used as a prefix for the key string when storing results/delays.
        data_type : :class:`DataType`, optional
            Data type to use for quantization during evaluation.

        See Also
        --------
        evaluate_outputs, current_output, current_outputs
        """
        raise NotImplementedError

    @abstractmethod
    def current_outputs(
        self, delays: DelayMap | None = None, prefix: str = ""
    ) -> Sequence[Num | None]:
        """
        Get all current outputs of this operation, if available.

        See Also
        --------
        current_output
        """
        raise NotImplementedError

    @abstractmethod
    def evaluate_outputs(
        self,
        input_values: Sequence[Num],
        results: MutableResultMap | None = None,
        delays: MutableDelayMap | None = None,
        prefix: str = "",
    ) -> Sequence[Num]:
        """
        Evaluate all outputs of this operation given the input values.

        See Also
        --------
        evaluate_output
        """
        raise NotImplementedError

    @abstractmethod
    def split(self) -> Iterable["Operation"]:
        """
        Split the operation into multiple operations.

        If splitting is not possible, this may return a list containing only the
        operation itself.
        """
        raise NotImplementedError

    @abstractmethod
    def to_sfg(self) -> "SFG":
        """
        Convert the operation into its corresponding SFG.

        If the operation is composed by multiple operations, the operation will be
        split.
        """
        raise NotImplementedError

    @abstractmethod
    def inputs_required_for_output(self, output_index: int) -> Iterable[int]:
        """
        Return the input indices needed to evaluate the output at a given index.
        """
        raise NotImplementedError

    @abstractmethod
    def quantize_input(self, index: int, value: Num, bits: int) -> Num:
        """
        Quantize the value to be used as input at the given index to a certain bit
        length.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def latency(self) -> int:
        """
        Get the latency of the operation.

        This is the longest time it takes from one of the input ports to one of the
        output ports.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def latency_offsets(self) -> dict[str, int | None]:
        """
        Get a dictionary with all the operations ports latency-offsets.
        """
        raise NotImplementedError

    @abstractmethod
    def set_latency(self, latency: int) -> None:
        """
        Set the latency of the operation to the specified integer value.

        This is done by setting the latency-offsets of operations input ports to 0
        and the latency-offsets of the operations output ports to the specified value.

        The latency is the time it takes to produce an output from the corresponding
        input of the underlying operator.

        The latency cannot be a negative integer.

        Parameters
        ----------
        latency : int
            Non-negative int corresponding to the latency of the operation.
        """
        raise NotImplementedError

    @abstractmethod
    def set_latency_offsets(self, latency_offsets: dict[str, int]) -> None:
        """
        Set the latency-offsets for the operations port.

        The latency offsets dictionary should be {'in0': 2, 'out1': 4} if you want to
        set the latency offset for the input port with index 0 to 2, and the latency
        offset of the output port with index 1 to 4.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def execution_time(self) -> int | None:
        """
        Get the execution time of the operation.

        The execution time is the time between executing two operations on the
        underlying operator. This is also called initiation interval.
        """
        raise NotImplementedError

    @execution_time.setter
    @abstractmethod
    def execution_time(self, execution_time: int | None) -> None:
        """
        Set the execution time of the operation.

        The execution time is the time between executing two operations on the
        underlying operator. This is also called initiation interval.

        The execution time cannot be a negative integer.

        Parameters
        ----------
        execution_time : int or None
            Non-negative integer corresponding to the execution time of the operation.
            Unset execution time by passing ``None``.
        """
        raise NotImplementedError

    @abstractmethod
    def get_plot_coordinates(
        self,
    ) -> tuple[ShapeCoordinates, ShapeCoordinates]:
        """
        Return coordinates for the latency and execution time polygons.

        This returns a tuple containing coordinates for the two polygons outlining
        the latency and execution time of the operation.
        The polygons are corresponding to a start time of 0 and are of height 1.
        """
        raise NotImplementedError

    @abstractmethod
    def get_input_coordinates(
        self,
    ) -> ShapeCoordinates:
        """
        Return coordinates for inputs.

        These maps to the polygons and are corresponding to a start time of 0
        and height 1.

        See Also
        --------
        get_output_coordinates
        """
        raise NotImplementedError

    @abstractmethod
    def get_output_coordinates(
        self,
    ) -> ShapeCoordinates:
        """
        Return coordinates for outputs.

        These maps to the polygons and are corresponding to a start time of 0
        and height 1.

        See Also
        --------
        get_input_coordinates
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def source(self) -> OutputPort:
        """
        Return the OutputPort if there is only one output port.

        If not, raise a TypeError.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def destination(self) -> InputPort:
        """
        Return the InputPort if there is only one input port.

        If not, raise a TypeError.
        """
        raise NotImplementedError

    @abstractmethod
    def _increase_time_resolution(self, factor: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def _decrease_time_resolution(self, factor: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def _check_all_latencies_set(self) -> None:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_linear(self) -> bool:
        """
        Return True if the operation is linear.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def is_constant(self) -> bool:
        """
        Return True if the output(s) of the operation is(are) constant.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def is_swappable(self) -> bool:
        """
        Return True if the inputs (and outputs) to the operation can be swapped.

        Swapping require that the operation retains the same function, but it is allowed
        to modify values to do so.
        """
        raise NotImplementedError

    @abstractmethod
    def swap_io(self) -> None:
        """
        Swap inputs (and outputs) of operation.

        Errors if :meth:`is_swappable` is False.
        """
        raise NotImplementedError


class AbstractOperation(Operation, AbstractGraphComponent):
    """
    Generic abstract operation base class.

    Concrete operations should normally derive from this to get the default
    behavior.
    """

    __slots__ = ("_execution_time", "_input_ports", "_output_ports")
    _input_ports: list[InputPort]
    _output_ports: list[OutputPort]
    _execution_time: int | None

    def __init__(
        self,
        input_count: int,
        output_count: int,
        name: Name = Name(""),
        input_sources: Sequence[SignalSourceProvider | None] | None = None,
        latency: int | None = None,
        latency_offsets: dict[str, int] | None = None,
        execution_time: int | None = None,
    ) -> None:
        """
        Construct an operation with the given input/output count.

        A list of input sources may be specified to automatically connect
        to the input ports.
        If provided, the number of sources must match the number of inputs.

        The latency offsets may also be specified to be initialized.
        """
        super().__init__(Name(name))

        self._input_ports = [InputPort(self, i) for i in range(input_count)]
        self._output_ports = [OutputPort(self, i) for i in range(output_count)]

        # Connect given input sources, if any.
        if input_sources is not None:
            source_count = len(input_sources)
            if source_count != input_count:
                raise ValueError(
                    "Wrong number of input sources supplied to Operation"
                    f" (expected {input_count}, got {source_count})"
                )
            for i, src in enumerate(input_sources):
                if src is not None:
                    if isinstance(src, Signal):
                        # Already existing signal
                        src.set_destination(self._input_ports[i])
                    else:
                        self._input_ports[i].connect(src.source)

        # Set specific latency_offsets
        if latency_offsets is not None:
            self.set_latency_offsets(latency_offsets)

        if latency is not None:
            # Set the latency for all ports initially.
            if latency < 0:
                raise ValueError("Latency cannot be negative")
            for inp in self.inputs:
                if inp.latency_offset is None:
                    inp.latency_offset = 0
            for output in self.outputs:
                if output.latency_offset is None:
                    output.latency_offset = latency

        self._execution_time = execution_time

    @overload
    @abstractmethod
    def evaluate(
        self, *inputs: Operation, data_type: DataType | None = None
    ) -> list[Operation]:  # pylint: disable=arguments-differ
        ...

    @overload
    @abstractmethod
    def evaluate(self, *inputs: Num, data_type: DataType | None = None) -> list[Num]:  # pylint: disable=arguments-differ
        ...

    @abstractmethod
    def evaluate(self, *inputs, data_type: DataType | None = None):  # pylint: disable=arguments-differ
        """
        Evaluate the operation and generate a list of output values.

        Parameters
        ----------
        *inputs
            List of input values.
        data_type : :class:`DataType`, optional
            Data type to use for quantization during evaluation.
        """
        raise NotImplementedError

    def _cast_to_data_type(self, value: Number, data_type: DataType) -> Number:
        if data_type is None:
            return value

        if not isinstance(value, (APyFixed, APyFloat, APyCFixed, APyCFloat)):
            if data_type.num_repr == NumRepresentation.FLOATING_POINT:
                value = apy.fp(value, data_type.wl[0], data_type.wl[1])
            elif data_type.num_repr == NumRepresentation.FIXED_POINT:
                value = apy.fx(value, data_type.wl[0], data_type.wl[1])

        return value.cast(
            data_type.wl[0],
            data_type.wl[1],
            data_type.quantization_mode.to_apytypes(),
            data_type.overflow_mode.to_apytypes(),
        )

    def __ilshift__(self, src: SignalSourceProvider) -> "Operation":
        if self.input_count != 1:
            diff = "more" if self.input_count > 1 else "less"
            raise TypeError(
                f"{self.__class__.__name__} cannot be used as a destination"
                f" because it has {diff} than 1 input"
            )
        self.input(0).connect(src)
        return self

    def __repr__(self) -> str:
        """Get a detailed representation of this operation including all parameters."""
        return self.__str__()

    def __str__(self) -> str:
        """Get a string representation of this operation."""
        inputs_dict: dict[int, list[GraphID] | str] = {}
        for i, current_input in enumerate(self.inputs):
            if current_input.signal_count == 0:
                inputs_dict[i] = "-"
                break
            dict_ele = []
            for signal in current_input.signals:
                if signal.source:
                    dict_ele.append(
                        cast(Operation, signal.source_operation).graph_id
                        or GraphID("no_id")
                    )
                else:
                    dict_ele.append(signal.graph_id or GraphID("no_id"))
            inputs_dict[i] = dict_ele

        outputs_dict: dict[int, list[GraphID] | str] = {}
        for i, outport in enumerate(self.outputs):
            if outport.signal_count == 0:
                outputs_dict[i] = "-"
                break
            dict_ele = []
            for signal in outport.signals:
                if signal.destination:
                    dict_ele.append(
                        cast(Operation, signal.destination_operation).graph_id
                        or GraphID("no_id")
                    )
                else:
                    dict_ele.append(signal.graph_id or GraphID("no_id"))
            outputs_dict[i] = dict_ele

        return (
            super().__str__()
            + f", \tinputs: {inputs_dict!s}, \toutputs: {outputs_dict!s}"
        )

    @property
    def input_count(self) -> int:
        return len(self._input_ports)

    @property
    def output_count(self) -> int:
        return len(self._output_ports)

    def input(self, index: int) -> InputPort:
        return self._input_ports[index]

    def output(self, index: int) -> OutputPort:
        return self._output_ports[index]

    @property
    def inputs(self) -> Sequence[InputPort]:
        return self._input_ports

    @property
    def outputs(self) -> Sequence[OutputPort]:
        return self._output_ports

    @property
    def input_signals(self) -> Sequence[Signal]:
        result = []
        for p in self.inputs:
            result.extend(p.signals)
        return result

    @property
    def output_signals(self) -> Sequence[Signal]:
        result = []
        for p in self.outputs:
            result.extend(p.signals)
        return result

    def key(self, index: int, prefix: str = "") -> ResultKey:
        key = prefix
        if self.output_count != 1:
            if key:
                key += "."
            key += str(index)
        elif not key:
            key = str(index)
        return ResultKey(key)

    def current_output(
        self, index: int, delays: DelayMap | None = None, prefix: str = ""
    ) -> Num | None:
        return None

    def evaluate_output(
        self,
        index: int,
        input_values: Sequence[Num],
        results: MutableResultMap | None = None,
        delays: MutableDelayMap | None = None,
        prefix: str = "",
        data_type: DataType | None = None,
    ) -> Num:
        if index < 0 or index >= self.output_count:
            raise IndexError(
                "Output index out of range (expected"
                f" 0-{self.output_count - 1}, got {index})"
            )
        if len(input_values) != self.input_count:
            raise ValueError(
                "Wrong number of input values supplied to operation (expected"
                f" {self.input_count}, got {len(input_values)})"
            )

        values = self.evaluate(*input_values, data_type=data_type)
        if isinstance(values, collections.abc.Sequence):
            if len(values) != self.output_count:
                raise RuntimeError(
                    f"Operation {self.graph_id} evaluated to incorrect number of outputs"
                    f" (expected {self.output_count}, got {len(values)})"
                )

        elif isinstance(values, (Number, APyFixed, APyFloat, APyCFixed, APyCFloat)):
            if self.output_count != 1:
                raise RuntimeError(
                    "Operation evaluated to incorrect number of outputs"
                    f" (expected {self.output_count}, got 1)"
                )
            values = (values,)
        else:
            raise RuntimeError(
                "Operation evaluated to invalid type (expected"
                f" Sequence/Number, got {values.__class__.__name__})"
            )

        if results is not None:
            for i in range(self.output_count):
                results[self.key(i, prefix)] = values[i]
        return values[index]

    def current_outputs(
        self, delays: DelayMap | None = None, prefix: str = ""
    ) -> Sequence[Num | None]:
        return [
            self.current_output(i, delays, prefix) for i in range(self.output_count)
        ]

    def evaluate_outputs(
        self,
        input_values: Sequence[Num],
        results: MutableResultMap | None = None,
        delays: MutableDelayMap | None = None,
        prefix: str = "",
    ) -> Sequence[Num]:
        return [
            self.evaluate_output(
                i,
                input_values,
                results,
                delays,
                prefix,
            )
            for i in range(self.output_count)
        ]

    def split(self) -> Iterable[Operation]:
        # Import here to avoid circular imports.
        from b_asic.special_operations import Input  # noqa: PLC0415

        result = self.evaluate(*([Input()] * self.input_count))
        if isinstance(result, collections.abc.Sequence) and all(
            isinstance(e, Operation) for e in result
        ):
            return cast(list[Operation], result)
        return [self]

    def to_sfg(self) -> "SFG":
        # Import here to avoid circular imports.
        from b_asic.sfg import SFG  # noqa: PLC0415
        from b_asic.special_operations import Input, Output  # noqa: PLC0415

        inputs = [Input() for _ in range(self.input_count)]

        try:
            last_operations = self.evaluate(*inputs)
            if isinstance(last_operations, Operation):
                last_operations = [last_operations]
            outputs = [Output(o) for o in last_operations]
        except TypeError:
            operation_copy: Operation = cast(Operation, self.copy())
            inputs = []
            for i in range(self.input_count):
                input_ = Input()
                operation_copy.input(i).connect(input_)
                inputs.append(input_)

            outputs = [Output(operation_copy)]

        return SFG(inputs=inputs, outputs=outputs)

    def copy(self, *args, **kwargs) -> GraphComponent:
        new_component: Operation = cast(Operation, super().copy(*args, **kwargs))
        for i, _input in enumerate(self.inputs):
            new_component.input(i).latency_offset = _input.latency_offset
        for i, output in enumerate(self.outputs):
            new_component.output(i).latency_offset = output.latency_offset
        new_component.execution_time = self._execution_time
        return new_component

    def inputs_required_for_output(self, output_index: int) -> Iterable[int]:
        if output_index < 0 or output_index >= self.output_count:
            raise IndexError(
                "Output index out of range (expected"
                f" 0-{self.output_count - 1}, got {output_index})"
            )
        # By default, assume each output depends on all inputs.
        return list(range(self.input_count))

    @property
    def neighbors(self) -> Sequence[GraphComponent]:
        return list(self.input_signals) + list(self.output_signals)

    @property
    def preceding_operations(self) -> list[Operation]:
        """
        Return an Iterable of all Operations that are connected to the
        input ports of the operation.
        """
        return [
            signal.source_operation for signal in self.input_signals if signal.source
        ]

    @property
    def subsequent_operations(self) -> list[Operation]:
        """
        Return an Iterable of all Operations that are connected to the
        output ports of the operation.
        """
        return [
            signal.destination.operation
            for signal in self.output_signals
            if signal.destination
        ]

    @property
    def source(self) -> OutputPort:
        if self.output_count != 1:
            diff = "more" if self.output_count > 1 else "less"
            raise TypeError(
                f"{self.__class__.__name__} cannot be used as an input source"
                f" because it has {diff} than one output"
            )
        return self.output(0)

    @property
    def destination(self) -> InputPort:
        if self.input_count != 1:
            diff = "more" if self.input_count > 1 else "less"
            raise TypeError(
                f"{self.__class__.__name__} cannot be used as an output"
                f" destination because it has {diff} than one input"
            )
        return self.input(0)

    def quantize_input(self, index: int, value: Num, bits: int) -> Num:
        if isinstance(value, (float, int)):
            b = 2**bits
            return round((value + 1) * b % (2 * b) - b) / b
        else:
            raise TypeError

    @property
    def latency(self) -> int:
        if None in [inp.latency_offset for inp in self.inputs] or None in [
            output.latency_offset for output in self.outputs
        ]:
            raise ValueError(
                "All native offsets have to set to a non-negative value to"
                " calculate the latency."
            )

        return max(
            (
                (cast(int, output.latency_offset) - cast(int, input_.latency_offset))
                for output, input_ in it.product(self.outputs, self.inputs)
            )
        )

    @property
    def latency_offsets(self) -> dict[str, int | None]:
        latency_offsets = {}

        for i, input_ in enumerate(self.inputs):
            latency_offsets[f"in{i}"] = input_.latency_offset

        for i, output in enumerate(self.outputs):
            latency_offsets[f"out{i}"] = output.latency_offset

        return latency_offsets

    def _check_all_latencies_set(self) -> None:
        """
        Raise an exception if an input or output does not have a latency offset.
        """
        self.input_latency_offsets  # noqa: B018
        self.output_latency_offsets  # noqa: B018

    @property
    def input_latency_offsets(self) -> list[int]:
        latency_offsets = [i.latency_offset for i in self.inputs]

        if any(val is None for val in latency_offsets):
            missing = [
                i for (i, latency) in enumerate(latency_offsets) if latency is None
            ]
            raise ValueError(f"Missing latencies for input(s) {missing}")

        return cast(list[int], latency_offsets)

    @property
    def output_latency_offsets(self) -> list[int]:
        latency_offsets = [i.latency_offset for i in self.outputs]

        if any(val is None for val in latency_offsets):
            missing = [
                i for (i, latency) in enumerate(latency_offsets) if latency is None
            ]
            raise ValueError(f"Missing latencies for output(s) {missing}")

        return cast(list[int], latency_offsets)

    def set_latency(self, latency: int) -> None:
        if latency < 0:
            raise ValueError("Latency cannot be negative")
        for current_input in self.inputs:
            current_input.latency_offset = 0
        for outport in self.outputs:
            outport.latency_offset = latency

    def set_latency_offsets(self, latency_offsets: dict[str, int]) -> None:
        for port_str, latency_offset in latency_offsets.items():
            port_str = port_str.lower()
            if port_str.startswith("in"):
                index_str = port_str[2:]
                if not index_str.isdigit():
                    raise ValueError(
                        "Incorrectly formatted index in string, expected 'in'"
                        f" + index, got: {port_str!r}"
                    )
                self.input(int(index_str)).latency_offset = latency_offset
            elif port_str.startswith("out"):
                index_str = port_str[3:]
                if not index_str.isdigit():
                    raise ValueError(
                        "Incorrectly formatted index in string, expected"
                        f" 'out' + index, got: {port_str!r}"
                    )
                self.output(int(index_str)).latency_offset = latency_offset
            else:
                raise ValueError(
                    "Incorrectly formatted string, expected 'in' + index or"
                    f" 'out' + index, got: {port_str!r}"
                )

    @property
    def execution_time(self) -> int | None:
        """Execution time of operation."""
        return self._execution_time

    @execution_time.setter
    def execution_time(self, execution_time: int) -> None:
        if execution_time is not None and execution_time < 0:
            raise ValueError("Execution time cannot be negative")
        self._execution_time = execution_time

    def _increase_time_resolution(self, factor: int) -> None:
        if self._execution_time is not None:
            self._execution_time *= factor
        for port in [*self.inputs, *self.outputs]:
            if port.latency_offset is not None:
                port.latency_offset *= factor

    def _decrease_time_resolution(self, factor: int) -> None:
        if self._execution_time is not None:
            self._execution_time = self._execution_time // factor
        for port in [*self.inputs, *self.outputs]:
            if port.latency_offset is not None:
                port.latency_offset = port.latency_offset // factor

    def get_plot_coordinates(
        self,
    ) -> tuple[ShapeCoordinates, ShapeCoordinates]:
        # Doc-string inherited
        return (
            self._get_plot_coordinates_for_latency(),
            self._get_plot_coordinates_for_execution_time(),
        )

    def _get_plot_coordinates_for_execution_time(
        self,
    ) -> ShapeCoordinates:
        # Always a rectangle, but easier if coordinates are returned
        execution_time = self._execution_time  # Copy for type checking
        if execution_time is None:
            return ()
        return (
            (0, 0),
            (0, 1),
            (execution_time, 1),
            (execution_time, 0),
            (0, 0),
        )

    def _get_plot_coordinates_for_latency(
        self,
    ) -> ShapeCoordinates:
        # Points for latency polygon
        latency = []
        input_latencies = self.input_latency_offsets
        output_latencies = self.output_latency_offsets
        # Remember starting point
        start_point = (input_latencies[0], 0.0)
        num_in = self.input_count
        latency.append(start_point)
        for k in range(1, num_in):
            latency.append((input_latencies[k - 1], k / num_in))
            latency.append((input_latencies[k], k / num_in))
        latency.append((input_latencies[num_in - 1], 1))

        num_out = self.output_count
        latency.append((output_latencies[num_out - 1], 1))
        for k in reversed(range(1, num_out)):
            latency.append((output_latencies[k], k / num_out))
            latency.append((output_latencies[k - 1], k / num_out))
        latency.append((output_latencies[0], 0.0))
        # Close the polygon
        latency.append(start_point)

        return tuple(latency)

    def get_input_coordinates(self) -> ShapeCoordinates:
        # doc-string inherited
        num_in = self.input_count
        return tuple(
            (
                self.input_latency_offsets[k],
                (1 + 2 * k) / (2 * num_in),
            )
            for k in range(num_in)
        )

    def get_output_coordinates(self) -> ShapeCoordinates:
        # doc-string inherited
        num_out = self.output_count
        return tuple(
            (
                self.output_latency_offsets[k],
                (1 + 2 * k) / (2 * num_out),
            )
            for k in range(num_out)
        )

    @property
    def is_linear(self) -> bool:
        # doc-string inherited
        return self.is_constant

    @property
    def is_constant(self) -> bool:
        # doc-string inherited
        return all(
            input_.connected_source.operation.is_constant for input_ in self.inputs
        )

    @property
    def is_swappable(self) -> bool:
        # doc-string inherited
        return False

    def swap_io(self) -> None:
        # doc-string inherited
        if not self.is_swappable:
            raise TypeError(f"operation io cannot be swapped for {type(self)}")
        if self.input_count == 2 and self.output_count == 1:
            self._input_ports.reverse()
            for i, p in enumerate(self._input_ports):
                p._index = i
