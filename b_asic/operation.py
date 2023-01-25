"""
B-ASIC Operation Module.

Contains the base for operations that are used by B-ASIC.
"""

import collections
import itertools as it
from abc import abstractmethod
from numbers import Number
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    NewType,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

from b_asic.graph_component import AbstractGraphComponent, GraphComponent, Name
from b_asic.core_operations import (
    Addition,
    Subtraction,
    Multiplication,
    ConstantMultiplication,
    Division,
)
from b_asic.port import InputPort, OutputPort, SignalSourceProvider
from b_asic.signal import Signal
from b_asic.signal_flow_graph import SFG

ResultKey = NewType("ResultKey", str)
ResultMap = Mapping[ResultKey, Optional[Number]]
MutableResultMap = MutableMapping[ResultKey, Optional[Number]]
DelayMap = Mapping[ResultKey, Number]
MutableDelayMap = MutableMapping[ResultKey, Number]


class Operation(GraphComponent, SignalSourceProvider):
    """
    Operation interface.

    Operations are graph components that perform a certain function.
    They are connected to each other by signals through their input/output
    ports.

    Operations can be evaluated independently using evaluate_output().
    Operations may specify how to truncate inputs through truncate_input().
    """

    @abstractmethod
    def __add__(self, src: Union[SignalSourceProvider, Number]) -> Addition:
        """
        Overloads the addition operator to make it return a new Addition operation
        object that is connected to the self and other objects.
        """
        raise NotImplementedError

    @abstractmethod
    def __radd__(self, src: Union[SignalSourceProvider, Number]) -> Addition:
        """
        Overloads the addition operator to make it return a new Addition operation
        object that is connected to the self and other objects.
        """
        raise NotImplementedError

    @abstractmethod
    def __sub__(self, src: Union[SignalSourceProvider, Number]) -> Subtraction:
        """
        Overloads the subtraction operator to make it return a new Subtraction operation
        object that is connected to the self and other objects.
        """
        raise NotImplementedError

    @abstractmethod
    def __rsub__(
        self, src: Union[SignalSourceProvider, Number]
    ) -> Subtraction:
        """
        Overloads the subtraction operator to make it return a new Subtraction operation
        object that is connected to the self and other objects.
        """
        raise NotImplementedError

    @abstractmethod
    def __mul__(
        self, src: Union[SignalSourceProvider, Number]
    ) -> Union[Multiplication, ConstantMultiplication]:
        """
        Overloads the multiplication operator to make it return a new Multiplication operation
        object that is connected to the self and other objects. If *src* is a number, then
        returns a ConstantMultiplication operation object instead.
        """
        raise NotImplementedError

    @abstractmethod
    def __rmul__(
        self, src: Union[SignalSourceProvider, Number]
    ) -> Union[Multiplication, ConstantMultiplication]:
        """
        Overloads the multiplication operator to make it return a new Multiplication operation
        object that is connected to the self and other objects. If *src* is a number, then
        returns a ConstantMultiplication operation object instead.
        """
        raise NotImplementedError

    @abstractmethod
    def __truediv__(
        self, src: Union[SignalSourceProvider, Number]
    ) -> Division:
        """
        Overloads the division operator to make it return a new Division operation
        object that is connected to the self and other objects.
        """
        raise NotImplementedError

    @abstractmethod
    def __rtruediv__(
        self, src: Union[SignalSourceProvider, Number]
    ) -> Division:
        """
        Overloads the division operator to make it return a new Division operation
        object that is connected to the self and other objects.
        """
        raise NotImplementedError

    @abstractmethod
    def __lshift__(self, src: SignalSourceProvider) -> Signal:
        """
        Overloads the left shift operator to make it connect the provided signal source
        to this operation's input, assuming it has exactly 1 input port.
        Returns the new signal.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def input_count(self) -> int:
        """Get the number of input ports."""
        raise NotImplementedError

    @property
    @abstractmethod
    def output_count(self) -> int:
        """Get the number of output ports."""
        raise NotImplementedError

    @abstractmethod
    def input(self, index: int) -> InputPort:
        """Get the input port at the given index."""
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
    def input_signals(self) -> Iterable[Signal]:
        """
        Get all the signals that are connected to this operation's input ports,
        in no particular order.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def output_signals(self) -> Iterable[Signal]:
        """
        Get all the signals that are connected to this operation's output ports,
        in no particular order.
        """
        raise NotImplementedError

    @abstractmethod
    def key(self, index: int, prefix: str = "") -> ResultKey:
        """
        Get the key used to access the output of a certain output of this operation
        from the output parameter passed to current_output(s) or evaluate_output(s).
        """
        raise NotImplementedError

    @abstractmethod
    def current_output(
        self, index: int, delays: Optional[DelayMap] = None, prefix: str = ""
    ) -> Optional[Number]:
        """
        Get the current output at the given index of this operation, if available.
        The *delays* parameter will be used for lookup.
        The *prefix* parameter will be used as a prefix for the key string when looking for delays.

        See also
        ========

        current_outputs, evaluate_output, evaluate_outputs
        """
        raise NotImplementedError

    @abstractmethod
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
        """
        Evaluate the output at the given index of this operation with the given input values.
        The *results* parameter will be used to store any results (including intermediate results)
        for caching.
        The *delays* parameter will be used to get the current value of any intermediate delays
        that are encountered, and be updated with their new values.
        The *prefix* parameter will be used as a prefix for the key string when storing results/delays.
        The *bits_override* parameter specifies a word length override when truncating inputs
        which ignores the word length specified by the input signal.
        The *truncate* parameter specifies whether input truncation should be enabled in the first
        place. If set to False, input values will be used directly without any bit truncation.

        See also
        ========

        evaluate_outputs, current_output, current_outputs
        """
        raise NotImplementedError

    @abstractmethod
    def current_outputs(
        self, delays: Optional[DelayMap] = None, prefix: str = ""
    ) -> Sequence[Optional[Number]]:
        """
        Get all current outputs of this operation, if available.
        See current_output for more information.
        """
        raise NotImplementedError

    @abstractmethod
    def evaluate_outputs(
        self,
        input_values: Sequence[Number],
        results: Optional[MutableResultMap] = None,
        delays: Optional[MutableDelayMap] = None,
        prefix: str = "",
        bits_override: Optional[int] = None,
        truncate: bool = True,
    ) -> Sequence[Number]:
        """
        Evaluate all outputs of this operation given the input values.
        See evaluate_output for more information.
        """
        raise NotImplementedError

    @abstractmethod
    def split(self) -> Iterable["Operation"]:
        """
        Split the operation into multiple operations.
        If splitting is not possible, this may return a list containing only the operation itself.
        """
        raise NotImplementedError

    @abstractmethod
    def to_sfg(self) -> SFG:
        """
        Convert the operation into its corresponding SFG.
        If the operation is composed by multiple operations, the operation will be split.
        """
        raise NotImplementedError

    @abstractmethod
    def inputs_required_for_output(self, output_index: int) -> Iterable[int]:
        """
        Get the input indices of all inputs in this operation whose values are
        required in order to evaluate the output at the given output index.
        """
        raise NotImplementedError

    @abstractmethod
    def truncate_input(self, index: int, value: Number, bits: int) -> Number:
        """
        Truncate the value to be used as input at the given index to a certain bit length.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def latency(self) -> int:
        """
        Get the latency of the operation, which is the longest time it takes from one of
        the operations inputport to one of the operations outputport.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def latency_offsets(self) -> Sequence[Sequence[int]]:
        """Get a nested list with all the operations ports latency-offsets, the first list contains the
        latency-offsets of the operations input ports, the second list contains the latency-offsets of
        the operations output ports.
        """
        raise NotImplementedError

    @abstractmethod
    def set_latency(self, latency: int) -> None:
        """
        Sets the latency of the operation to the specified integer value  by setting the
        latency-offsets of operations input ports to 0 and the latency-offsets of the operations
        output ports to the specified value. The latency cannot be a negative integers.
        """
        raise NotImplementedError

    @abstractmethod
    def set_latency_offsets(self, latency_offsets: Dict[str, int]) -> None:
        """
        Sets the latency-offsets for the operations ports specified in the latency_offsets dictionary.
        The latency offsets dictionary should be {'in0': 2, 'out1': 4} if you want to set the latency offset
        for the inport port with index 0 to 2, and the latency offset of the output port with index 1 to 4.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def execution_time(self) -> int:
        """
        Get the execution time of the operation, which is the time it takes before the
        processing element implementing the operation can be reused for starting another operation.
        """
        raise NotImplementedError

    @execution_time.setter
    @abstractmethod
    def execution_time(self, latency: int) -> None:
        """
        Sets the execution time of the operation to the specified integer
        value. The execution time cannot be a negative integer.
        """
        raise NotImplementedError

    @abstractmethod
    def get_plot_coordinates(
        self,
    ) -> Tuple[List[List[Number]], List[List[Number]]]:
        """
        Get a tuple constaining coordinates for the two polygons outlining
        the latency and execution time of the operation.
        The polygons are corresponding to a start time of 0 and are of height 1.
        """
        raise NotImplementedError

    @abstractmethod
    def get_io_coordinates(
        self,
    ) -> Tuple[List[List[Number]], List[List[Number]]]:
        """
        Get a tuple constaining coordinates for inputs and outputs, respectively.
        These maps to the polygons and are corresponding to a start time of 0
        and height 1.
        """
        raise NotImplementedError


class AbstractOperation(Operation, AbstractGraphComponent):
    """
    Generic abstract operation base class.

    Concrete operations should normally derive from this to get the default
    behavior.
    """

    _input_ports: List[InputPort]
    _output_ports: List[OutputPort]
    _execution_time: Union[int, None] = None

    def __init__(
        self,
        input_count: int,
        output_count: int,
        name: Name = "",
        input_sources: Optional[
            Sequence[Optional[SignalSourceProvider]]
        ] = None,
        latency: Optional[int] = None,
        latency_offsets: Optional[Dict[str, int]] = None,
        execution_time: Optional[int] = None,
    ):
        """
        Construct an operation with the given input/output count.

        A list of input sources may be specified to automatically connect
        to the input ports.
        If provided, the number of sources must match the number of inputs.

        The latency offsets may also be specified to be initialized.
        """
        super().__init__(name)

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
                    self._input_ports[i].connect(src.source)

        ports_without_latency_offset = set(
            (
                [f"in{i}" for i in range(self.input_count)]
                + [f"out{i}" for i in range(self.output_count)]
            )
        )

        if latency_offsets is not None:
            self.set_latency_offsets(latency_offsets)

        if latency is not None:
            # Set the latency of the rest of ports with no latency_offset.
            if latency < 0:
                raise ValueError("Latency cannot be negative")
            for inp in self.inputs:
                if inp.latency_offset is None:
                    inp.latency_offset = 0
            for outp in self.outputs:
                if outp.latency_offset is None:
                    outp.latency_offset = latency

        self._execution_time = execution_time

    @abstractmethod
    def evaluate(self, *inputs) -> Any:  # pylint: disable=arguments-differ
        """
        Evaluate the operation and generate a list of output values given a
        list of input values.
        """
        raise NotImplementedError

    def __add__(self, src: Union[SignalSourceProvider, Number]) -> "Addition":
        # Import here to avoid circular imports.
        from b_asic.core_operations import Addition, Constant

        return Addition(
            self, Constant(src) if isinstance(src, Number) else src
        )

    def __radd__(self, src: Union[SignalSourceProvider, Number]) -> "Addition":
        # Import here to avoid circular imports.
        from b_asic.core_operations import Addition, Constant

        return Addition(
            Constant(src) if isinstance(src, Number) else src, self
        )

    def __sub__(
        self, src: Union[SignalSourceProvider, Number]
    ) -> "Subtraction":
        # Import here to avoid circular imports.
        from b_asic.core_operations import Constant, Subtraction

        return Subtraction(
            self, Constant(src) if isinstance(src, Number) else src
        )

    def __rsub__(
        self, src: Union[SignalSourceProvider, Number]
    ) -> "Subtraction":
        # Import here to avoid circular imports.
        from b_asic.core_operations import Constant, Subtraction

        return Subtraction(
            Constant(src) if isinstance(src, Number) else src, self
        )

    def __mul__(
        self, src: Union[SignalSourceProvider, Number]
    ) -> "Union[Multiplication, ConstantMultiplication]":
        # Import here to avoid circular imports.
        from b_asic.core_operations import (
            ConstantMultiplication,
            Multiplication,
        )

        return (
            ConstantMultiplication(src, self)
            if isinstance(src, Number)
            else Multiplication(self, src)
        )

    def __rmul__(
        self, src: Union[SignalSourceProvider, Number]
    ) -> Union[Multiplication, ConstantMultiplication]:
        # Import here to avoid circular imports.
        from b_asic.core_operations import (
            ConstantMultiplication,
            Multiplication,
        )

        return (
            ConstantMultiplication(src, self)
            if isinstance(src, Number)
            else Multiplication(src, self)
        )

    def __truediv__(
        self, src: Union[SignalSourceProvider, Number]
    ) -> Division:
        # Import here to avoid circular imports.
        from b_asic.core_operations import Constant, Division

        return Division(
            self, Constant(src) if isinstance(src, Number) else src
        )

    def __rtruediv__(
        self, src: Union[SignalSourceProvider, Number]
    ) -> Division:
        # Import here to avoid circular imports.
        from b_asic.core_operations import Constant, Division

        return Division(
            Constant(src) if isinstance(src, Number) else src, self
        )

    def __lshift__(self, src: SignalSourceProvider) -> Signal:
        if self.input_count != 1:
            diff = "more" if self.input_count > 1 else "less"
            raise TypeError(
                f"{self.__class__.__name__} cannot be used as a destination"
                f" because it has {diff} than 1 input"
            )
        return self.input(0).connect(src)

    def __str__(self) -> str:
        """Get a string representation of this operation."""
        inputs_dict = {}
        for i, port in enumerate(self.inputs):
            if port.signal_count == 0:
                inputs_dict[i] = "-"
                break
            dict_ele = []
            for signal in port.signals:
                if signal.source:
                    if signal.source.operation.graph_id:
                        dict_ele.append(signal.source.operation.graph_id)
                    else:
                        dict_ele.append("no_id")
                else:
                    if signal.graph_id:
                        dict_ele.append(signal.graph_id)
                    else:
                        dict_ele.append("no_id")
            inputs_dict[i] = dict_ele

        outputs_dict = {}
        for i, port in enumerate(self.outputs):
            if port.signal_count == 0:
                outputs_dict[i] = "-"
                break
            dict_ele = []
            for signal in port.signals:
                if signal.destination:
                    if signal.destination.operation.graph_id:
                        dict_ele.append(signal.destination.operation.graph_id)
                    else:
                        dict_ele.append("no_id")
                else:
                    if signal.graph_id:
                        dict_ele.append(signal.graph_id)
                    else:
                        dict_ele.append("no_id")
            outputs_dict[i] = dict_ele

        return (
            super().__str__()
            + f", \tinputs: {str(inputs_dict)}, \toutputs: {str(outputs_dict)}"
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
    def input_signals(self) -> Iterable[Signal]:
        result = []
        for p in self.inputs:
            for s in p.signals:
                result.append(s)
        return result

    @property
    def output_signals(self) -> Iterable[Signal]:
        result = []
        for p in self.outputs:
            for s in p.signals:
                result.append(s)
        return result

    def key(self, index: int, prefix: str = "") -> ResultKey:
        key = prefix
        if self.output_count != 1:
            if key:
                key += "."
            key += str(index)
        elif not key:
            key = str(index)
        return key

    def current_output(
        self, index: int, delays: Optional[DelayMap] = None, prefix: str = ""
    ) -> Optional[Number]:
        return None

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

        values = self.evaluate(
            *(
                self.truncate_inputs(input_values, bits_override)
                if truncate
                else input_values
            )
        )
        if isinstance(values, collections.abc.Sequence):
            if len(values) != self.output_count:
                raise RuntimeError(
                    "Operation evaluated to incorrect number of outputs"
                    f" (expected {self.output_count}, got {len(values)})"
                )
        elif isinstance(values, Number):
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
        self, delays: Optional[DelayMap] = None, prefix: str = ""
    ) -> Sequence[Optional[Number]]:
        return [
            self.current_output(i, delays, prefix)
            for i in range(self.output_count)
        ]

    def evaluate_outputs(
        self,
        input_values: Sequence[Number],
        results: Optional[MutableResultMap] = None,
        delays: Optional[MutableDelayMap] = None,
        prefix: str = "",
        bits_override: Optional[int] = None,
        truncate: bool = True,
    ) -> Sequence[Number]:
        return [
            self.evaluate_output(
                i,
                input_values,
                results,
                delays,
                prefix,
                bits_override,
                truncate,
            )
            for i in range(self.output_count)
        ]

    def split(self) -> Iterable[Operation]:
        # Import here to avoid circular imports.
        from b_asic.special_operations import Input

        try:
            result = self.evaluate(*([Input()] * self.input_count))
            if isinstance(result, collections.abc.Sequence) and all(
                isinstance(e, Operation) for e in result
            ):
                return result
            if isinstance(result, Operation):
                return [result]
        except TypeError:
            pass
        except ValueError:
            pass
        return [self]

    def to_sfg(self) -> SFG:
        # Import here to avoid circular imports.
        from b_asic.signal_flow_graph import SFG
        from b_asic.special_operations import Input, Output

        inputs = [Input() for _ in range(self.input_count)]

        try:
            last_operations = self.evaluate(*inputs)
            if isinstance(last_operations, Operation):
                last_operations = [last_operations]
            outputs = [Output(o) for o in last_operations]
        except TypeError:
            operation_copy: Operation = self.copy_component()
            inputs = []
            for i in range(self.input_count):
                _input = Input()
                operation_copy.input(i).connect(_input)
                inputs.append(_input)

            outputs = [Output(operation_copy)]

        return SFG(inputs=inputs, outputs=outputs)

    def copy_component(self, *args, **kwargs) -> GraphComponent:
        new_component: Operation = super().copy_component(*args, **kwargs)
        for i, inp in enumerate(self.inputs):
            new_component.input(i).latency_offset = inp.latency_offset
        for i, outp in enumerate(self.outputs):
            new_component.output(i).latency_offset = outp.latency_offset
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
    def neighbors(self) -> Iterable[GraphComponent]:
        return list(self.input_signals) + list(self.output_signals)

    @property
    def preceding_operations(self) -> Iterable[Operation]:
        """
        Return an Iterable of all Operations that are connected to this
        Operations input ports.
        """
        return [
            signal.source.operation
            for signal in self.input_signals
            if signal.source
        ]

    @property
    def subsequent_operations(self) -> Iterable[Operation]:
        """
        Return an Iterable of all Operations that are connected to this
        Operations output ports.
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
                f" because it has {diff} than 1 output"
            )
        return self.output(0)

    def truncate_input(self, index: int, value: Number, bits: int) -> Number:
        return int(value) & ((2**bits) - 1)

    def truncate_inputs(
        self,
        input_values: Sequence[Number],
        bits_override: Optional[int] = None,
    ) -> Sequence[Number]:
        """
        Truncate the values to be used as inputs to the bit lengths specified
        by the respective signals connected to each input.
        """
        args = []
        for i, input_port in enumerate(self.inputs):
            value = input_values[i]
            bits = bits_override
            if bits_override is None and input_port.signal_count >= 1:
                bits = input_port.signals[0].bits
            if bits_override is not None:
                if isinstance(value, complex):
                    raise TypeError(
                        "Complex value cannot be truncated to {bits} bits as"
                        " requested by the signal connected to input #{i}"
                    )
                value = self.truncate_input(i, value, bits)
            args.append(value)
        return args

    @property
    def latency(self) -> int:
        if None in [inp.latency_offset for inp in self.inputs] or None in [
            outp.latency_offset for outp in self.outputs
        ]:
            raise ValueError(
                "All native offsets have to set to a non-negative value to"
                " calculate the latency."
            )

        return max(
            (
                (outp.latency_offset - inp.latency_offset)
                for outp, inp in it.product(self.outputs, self.inputs)
            )
        )

    @property
    def latency_offsets(self) -> Sequence[Sequence[int]]:
        latency_offsets = {}

        for i, inp in enumerate(self.inputs):
            latency_offsets[f"in{i}"] = inp.latency_offset

        for i, outp in enumerate(self.outputs):
            latency_offsets[f"out{i}"] = outp.latency_offset

        return latency_offsets

    def set_latency(self, latency: int) -> None:
        if latency < 0:
            raise ValueError("Latency cannot be negative")
        for inport in self.inputs:
            inport.latency_offset = 0
        for outport in self.outputs:
            outport.latency_offset = latency

    def set_latency_offsets(self, latency_offsets: Dict[str, int]) -> None:
        for port_str, latency_offset in latency_offsets.items():
            port_str = port_str.lower()
            if port_str.startswith("in"):
                index_str = port_str[2:]
                assert index_str.isdigit(), (
                    "Incorrectly formatted index in string, expected 'in' +"
                    f" index, got: {port_str!r}"
                )
                self.input(int(index_str)).latency_offset = latency_offset
            elif port_str.startswith("out"):
                index_str = port_str[3:]
                assert index_str.isdigit(), (
                    "Incorrectly formatted index in string, expected 'out' +"
                    f" index, got: {port_str!r}"
                )
                self.output(int(index_str)).latency_offset = latency_offset
            else:
                raise ValueError(
                    "Incorrectly formatted string, expected 'in' + index or"
                    f" 'out' + index, got: {port_str!r}"
                )

    @property
    def execution_time(self) -> Union[int, None]:
        """Execution time of operation."""
        return self._execution_time

    @execution_time.setter
    def execution_time(self, execution_time: int) -> None:
        if execution_time is not None and execution_time < 0:
            raise ValueError("Execution time cannot be negative")
        self._execution_time = execution_time

    def _increase_time_resolution(self, factor: int):
        if self._execution_time is not None:
            self._execution_time *= factor
        for port in [*self.inputs, *self.outputs]:
            port.latency_offset *= factor

    def _decrease_time_resolution(self, factor: int):
        if self._execution_time is not None:
            self._execution_time = self._execution_time // factor
        for port in [*self.inputs, *self.outputs]:
            port.latency_offset = port.latency_offset // factor

    def get_plot_coordinates(
        self,
    ) -> Tuple[List[List[Number]], List[List[Number]]]:
        return (
            self._get_plot_coordinates_for_latency(),
            self._get_plot_coordinates_for_execution_time(),
        )

    def _get_plot_coordinates_for_execution_time(self) -> List[List[Number]]:
        # Always a rectangle, but easier if coordinates are returned
        if self._execution_time is None:
            return []
        return [
            [0, 0],
            [0, 1],
            [self.execution_time, 1],
            [self.execution_time, 0],
            [0, 0],
        ]

    def _get_plot_coordinates_for_latency(self) -> List[List[Number]]:
        # Points for latency polygon
        latency = []
        # Remember starting point
        start_point = [self.inputs[0].latency_offset, 0]
        num_in = len(self.inputs)
        latency.append(start_point)
        for k in range(1, num_in):
            latency.append([self.inputs[k - 1].latency_offset, k / num_in])
            latency.append([self.inputs[k].latency_offset, k / num_in])
        latency.append([self.inputs[num_in - 1].latency_offset, 1])

        num_out = len(self.outputs)
        latency.append([self.outputs[num_out - 1].latency_offset, 1])
        for k in reversed(range(1, num_out)):
            latency.append([self.outputs[k].latency_offset, k / num_out])
            latency.append([self.outputs[k - 1].latency_offset, k / num_out])
        latency.append([self.outputs[0].latency_offset, 0])
        # Close the polygon
        latency.append(start_point)

        return latency

    def get_io_coordinates(
        self,
    ) -> Tuple[List[List[Number]], List[List[Number]]]:
        input_coords = [
            [
                self.inputs[k].latency_offset,
                (1 + 2 * k) / (2 * len(self.inputs)),
            ]
            for k in range(len(self.inputs))
        ]
        output_coords = [
            [
                self.outputs[k].latency_offset,
                (1 + 2 * k) / (2 * len(self.outputs)),
            ]
            for k in range(len(self.outputs))
        ]
        return input_coords, output_coords
