"""
B-ASIC Simulation Module.

Contains a class for simulating the result of an SFG given a set of input values.
"""

from collections import defaultdict
from collections.abc import Callable, Mapping, MutableMapping, MutableSequence, Sequence
from numbers import Number
from typing import NamedTuple

import apytypes as apy
import numpy as np

from b_asic.data_type import DataType, NumRepresentation
from b_asic.operation import MutableDelayMap, Operation, ResultKey
from b_asic.port import InputPort
from b_asic.sfg import SFG
from b_asic.special_operations import Delay
from b_asic.types import Num

ResultArrayMap = Mapping[ResultKey, Sequence[Num]]
MutableResultArrayMap = MutableMapping[ResultKey, MutableSequence[Num]]
InputFunction = Callable[[int], Num]
InputProvider = Num | Sequence[Num] | InputFunction


class _EvaluationStep(NamedTuple):
    key: ResultKey
    operation: Operation
    index: int
    input_keys: tuple[ResultKey, ...]
    prefix: str


class Simulation:
    """
    Simulation of an SFG.

    Build a topological evaluation order once, including nested SFGs, and reuse
    it for each iteration. Delay states are updated after all outputs are computed.

    Use FastSimulation (from the C++ extension module) for a more effective
    simulation when running many iterations.

    Graphs containing Expansion or Compression are normalized on an internal
    copy. One iteration processes one common period, consuming
    ``input_samples_per_iteration`` samples per input and producing
    ``output_samples_per_iteration`` samples per output. Input callables receive
    their local sample index. Saved traces contain consecutive samples at each
    signal's own rate. Run methods return the last sample of each output in the
    last period. Finite input arrays must contain whole periods of equal duration.

    Parameters
    ----------
    sfg : :class:`~b_asic.sfg.SFG`
        The signal flow graph to simulate.
    input_providers : list, optional
        Input values, one list item per input. Each list item can be an array of values,
        a callable taking a time index and returning the value, or a
        number (constant input). If a value is not provided for an input, it will be 0.
    data_type : :class:`~b_asic.data_type.DataType`, optional
        If provided, this finite arithmetic data type will be used for all operations.
    """

    _sfg: SFG
    _results: MutableResultArrayMap
    _delays: MutableDelayMap
    _iteration: int
    _input_functions: list[InputFunction]
    _input_length: int | None
    _data_type: DataType | None

    def __init__(
        self,
        sfg: SFG,
        input_providers: Sequence[InputProvider | None] | None = None,
        data_type: DataType | None = None,
    ) -> None:
        """Construct a Simulation of an SFG."""
        if not isinstance(sfg, SFG):
            raise TypeError("An SFG must be provided")

        # Copy the SFG to make sure it's not modified from the outside.
        self._sfg = sfg()
        self._results = defaultdict(list)
        self._delays = {}
        self._iteration = 0
        self._input_functions = [lambda _: 0 for _ in range(self._sfg.input_count)]
        self._input_length = None
        self._data_type = data_type
        self._rate_normalization = (
            self._sfg.to_single_rate() if self._sfg.is_multirate else None
        )
        self._input_samples = (
            self._rate_normalization.input_samples
            if self._rate_normalization is not None
            else (1,) * self._sfg.input_count
        )
        self._output_samples = (
            self._rate_normalization.output_samples
            if self._rate_normalization is not None
            else (1,) * self._sfg.output_count
        )
        self._rate_simulation: Simulation | None = None
        if input_providers is not None:
            self.set_inputs(input_providers)
        if self._rate_normalization is not None:
            self._rate_simulation = Simulation(
                self._rate_normalization.sfg, data_type=data_type
            )
            for index, (original, phase) in enumerate(
                self._rate_normalization.input_phases
            ):
                count = self._input_samples[original]
                self._rate_simulation.set_input(
                    index,
                    lambda n, original=original, phase=phase, count=count: (
                        self._input_functions[original](n * count + phase)
                    ),
                )
            return
        self._evaluation_order, self._delay_updates, self._result_aliases = (
            self._build_evaluation_order()
        )

    def _build_evaluation_order(
        self,
    ) -> tuple[
        list[_EvaluationStep], dict[ResultKey, ResultKey], dict[ResultKey, ResultKey]
    ]:
        """Use the flattened SFG's topological order for evaluation."""
        graph = self._sfg()
        aliases: dict[ResultKey, ResultKey] = {}
        graphs = [(graph, "")]
        operations = []

        def source_key(port: InputPort, prefix: str) -> ResultKey:
            source = port.connected_source
            if source is None:
                raise ValueError("Missing source in signal.")
            return source.operation.key(
                source.index, prefix + source.operation.graph_id
            )

        while graphs:
            current_graph, prefix = graphs.pop()
            for op in current_graph.operations:
                key_base = prefix + op.graph_id
                operations.append((op, key_base))
                if isinstance(op, SFG):
                    inner_prefix = key_base + "."
                    graphs.append((op, inner_prefix))
                    for port, input_op in zip(
                        op.inputs, op.input_operations, strict=True
                    ):
                        aliases[input_op.key(0, inner_prefix + input_op.graph_id)] = (
                            source_key(port, prefix)
                        )
                    for index, output in enumerate(op.output_operations):
                        aliases[op.key(index, key_base)] = source_key(
                            output.input(0), inner_prefix
                        )

        for output in graph.output_operations:
            aliases[output.graph_id] = source_key(output.input(0), "")

        # Keep hierarchical IDs unique when flattening removes SFG interfaces.
        for op, key_base in operations:
            op.graph_id = key_base
        self._evaluation_sfg = graph.flatten()
        ports = [
            port
            for op in self._evaluation_sfg.get_operations_topological_order()
            for port in op.outputs
        ]
        steps = [
            _EvaluationStep(
                port.operation.key(port.index, port.operation.graph_id),
                port.operation,
                port.index,
                ()
                if isinstance(port.operation, Delay)
                else tuple(
                    source_key(input_port, "") for input_port in port.operation.inputs
                ),
                port.operation.graph_id,
            )
            for port in ports
        ]
        delay_updates = {
            op.key(0, op.graph_id): source_key(op.input(0), "")
            for op in self._evaluation_sfg.find_by_type(Delay)
        }
        for key, source in aliases.items():
            while source in aliases:
                source = aliases[source]
            aliases[key] = source
        return steps, delay_updates, aliases

    def set_input(self, index: int, input_provider: InputProvider) -> None:
        """
        Set the input used to for a specific input index.

        Parameters
        ----------
        index : int
            The input index.
        input_provider : list, callable, or number
            Can be an array of values, a callable taking a time index and returning
            the value, or a number (constant input).
        """
        if index < 0 or index >= len(self._input_functions):
            raise IndexError(
                "Input index out of range (expected"
                f" 0-{len(self._input_functions) - 1}, got {index})"
            )
        if callable(input_provider):
            self._input_functions[index] = input_provider
        elif isinstance(input_provider, Number):
            self._input_functions[index] = lambda _: input_provider
        else:
            count = self._input_samples[index]
            length, remainder = divmod(len(input_provider), count)
            if remainder:
                raise ValueError(
                    "Input arrays must contain whole simulation periods "
                    f"({count} samples per iteration for input {index})."
                )
            if self._input_length is None:
                self._input_length = length
            elif self._input_length != length:
                raise ValueError(
                    "Inconsistent input length for simulation (was"
                    f" {self._input_length} iterations, got {length})"
                )
            self._input_functions[index] = lambda n: input_provider[n]

    def set_inputs(self, input_providers: Sequence[InputProvider | None]) -> None:
        """
        Set the input functions used to get values for the inputs to the internal SFG.

        Parameters
        ----------
        input_providers : sequence of list, callable, or number
            The input functions to use.
        """
        if self._sfg.input_count == 1 and (
            not np.iterable(input_providers) or len(input_providers) != 1
        ):
            input_providers = [input_providers]
        if len(input_providers) != self._sfg.input_count:
            raise ValueError(
                "Wrong number of inputs supplied to simulation (expected"
                f" {self._sfg.input_count}, got {len(input_providers)})"
            )
        for index, input_provider in enumerate(input_providers):
            if input_provider is not None:
                self.set_input(index, input_provider)

    def step(self, save_results: bool = True) -> Sequence[Num]:
        """
        Run one iteration of the simulation and return the resulting output values.

        Parameters
        ----------
        save_results : bool, default: True
            Whether the results should be saved.

        Returns
        -------
        list[:data:`~b_asic.types.Num`]
            Output values for the simulated iteration, in SFG output order.
        """
        return self.run_for(1, save_results)

    def run_until(self, iteration: int, save_results: bool = True) -> Sequence[Num]:
        """
        Run the simulation until the iteration number.

        Will run until the number of iterations is greater than or equal to the given
        iteration and return the output values of the last iteration. The number of
        iterations actually simulated depends on the current state of the Simulation.

        Parameters
        ----------
        iteration : int
            Iteration number to stop the simulation at.
        save_results : bool, default: True
            Whether the results should be saved.

        Returns
        -------
        list[:data:`~b_asic.types.Num`]
            Output values of the last iteration, in SFG output order.
        """
        if self._rate_simulation is not None:
            return self._run_multirate_until(iteration, save_results)
        results: dict[ResultKey, Num] = {}
        while self._iteration < iteration:
            results = {}
            # Fetch the input values for this iteration
            input_values = [
                self._input_functions[i](self._iteration)
                for i in range(self._sfg.input_count)
            ]

            # Set the input operation outputs to the fetched input values
            for i, input_op in enumerate(self._sfg.input_operations):
                input_op.value = input_values[i]
                self._evaluation_sfg.input_operations[i].value = input_values[i]

            for step in self._evaluation_order:
                # Evaluating one output normally also populates the other outputs.
                if step.key in results:
                    continue
                op = step.operation
                input_vals = [results[key] for key in step.input_keys]
                if isinstance(op, Delay):
                    results[step.key] = op.evaluate(
                        None,
                        self._data_type,
                        self._delays,
                    )
                else:
                    results[step.key] = op.evaluate_output(
                        step.index,
                        input_vals,
                        results,
                        self._delays,
                        step.prefix,
                        data_type=self._data_type,
                    )

            # All delay inputs read this iteration's values before state advances.
            self._delays.update(
                {key: results[source] for key, source in self._delay_updates.items()}
            )
            results.update(
                {key: results[source] for key, source in self._result_aliases.items()}
            )

            if save_results:
                for key, value in results.items():
                    self._results[key].append(value)
            self._iteration += 1

        return [results[op.graph_id] for op in self._sfg.output_operations]

    def _run_multirate_until(self, iteration: int, save_results: bool) -> Sequence[Num]:
        """Pack phase inputs and reconstruct native-rate traces for each period."""
        simulation = self._rate_simulation
        normalization = self._rate_normalization
        assert simulation is not None
        assert normalization is not None
        outputs = []
        while self._iteration < iteration:
            values = simulation.step(save_results)
            if save_results:
                for key, phases in normalization.result_phases.items():
                    self._results[key].extend(
                        simulation._results[phase][0] for phase in phases
                    )
                simulation.clear_results()
            offset = 0
            outputs = []
            for count in self._output_samples:
                outputs.append(values[offset + count - 1])
                offset += count
            self._iteration += 1
        return outputs

    def run_for(self, iterations: int, save_results: bool = True) -> Sequence[Num]:
        """
        Run a given number of iterations of the simulation.

        Return the output values of the last iteration.

        Parameters
        ----------
        iterations : int
            Number of iterations to simulate.
        save_results : bool, default: True
            Whether the results should be saved.

        Returns
        -------
        list[:data:`~b_asic.types.Num`]
            Output values of the last iteration, in SFG output order.
        """
        return self.run_until(self._iteration + iterations, save_results)

    def run(self, save_results: bool = True) -> Sequence[Num]:
        """
        Run the simulation until the end of its input arrays.

        Return the output values of the last iteration.

        Parameters
        ----------
        save_results : bool, default: True
            Whether the results should be saved.

        Returns
        -------
        list[:data:`~b_asic.types.Num`]
            Output values of the last iteration, in SFG output order.
        """
        if self._input_length is None:
            raise IndexError("Tried to run unlimited simulation")
        return self.run_until(self._input_length, save_results)

    @property
    def iteration(self) -> int:
        """Get the current iteration number of the simulation."""
        return self._iteration

    @property
    def input_samples_per_iteration(self) -> tuple[int, ...]:
        """Get the number of samples consumed per original input in one period."""
        return self._input_samples

    @property
    def output_samples_per_iteration(self) -> tuple[int, ...]:
        """Get the number of samples produced per original output in one period."""
        return self._output_samples

    @property
    def results(self) -> ResultArrayMap:
        """
        A mapping from result keys to numpy arrays containing all results.

        This includes intermediate values, calculated for each iteration up until now
        that was run with *save_results* enabled.
        The mapping is indexed using the ``key()`` method of Operation with the
        appropriate output index.

        Example result after 3 iterations::
            {"c1": [3, 6, 7], "c2": [4, 5, 5], "bfly1.0": [7, 0, 0], "bfly1.1":\
 [-1, 0, 2], "out0": [7, -2, -1]}
        """
        if self._data_type:
            if self._data_type.num_repr == NumRepresentation.FIXED_POINT:
                if self._data_type.is_complex:
                    return {
                        key: apy.APyCFixedArray(
                            [v.to_bits() for v in value],
                            int_bits=self._data_type.int_bits,
                            frac_bits=self._data_type.frac_bits,
                        )
                        for key, value in self._results.items()
                    }
                else:
                    return {
                        key: apy.APyFixedArray(
                            [v.to_bits() for v in value],
                            int_bits=self._data_type.int_bits,
                            frac_bits=self._data_type.frac_bits,
                        )
                        for key, value in self._results.items()
                    }
            if self._data_type.num_repr == NumRepresentation.FLOATING_POINT:
                if self._data_type.is_complex:
                    raise NotImplementedError
                return {
                    key: apy.APyFloatArray.from_bits(
                        [v.to_bits() for v in value],
                        exp_bits=self._data_type.exp_bits,
                        man_bits=self._data_type.man_bits,
                    )
                    for key, value in self._results.items()
                }
        return {key: np.array(value) for key, value in self._results.items()}

    def clear_results(self) -> None:
        """Clear all results that were saved until now."""
        self._results.clear()

    def clear_state(self) -> None:
        """
        Clear all current state of the simulation, except for the results and iteration.
        """
        self._delays.clear()
        if self._rate_simulation is not None:
            self._rate_simulation.clear_state()

    @property
    def sfg(self) -> SFG:
        """The signal flow graph being simulated."""
        return self._sfg

    def show(self) -> None:
        """Show the simulation results."""
        # import here to avoid cyclic imports
        from b_asic.gui_utils.plot_window import (  # noqa: PLC0415
            start_simulation_dialog,
        )

        start_simulation_dialog(self.results, self._sfg.name)
