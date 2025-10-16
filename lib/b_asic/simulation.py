"""
B-ASIC Simulation Module.

Contains a class for simulating the result of an SFG given a set of input values.
"""

from collections import defaultdict
from collections.abc import Callable, Mapping, MutableMapping, MutableSequence, Sequence
from numbers import Number

import numpy as np

from b_asic.operation import MutableDelayMap, ResultKey
from b_asic.sfg import SFG
from b_asic.special_operations import Delay
from b_asic.types import Num

ResultArrayMap = Mapping[ResultKey, Sequence[Num]]
MutableResultArrayMap = MutableMapping[ResultKey, MutableSequence[Num]]
InputFunction = Callable[[int], Num]
InputProvider = Num | Sequence[Num] | InputFunction


class Simulation:
    """
    Simulation of an SFG.

    Use FastSimulation (from the C++ extension module) for a more effective
    simulation when running many iterations.

    Parameters
    ----------
    sfg : SFG
        The signal flow graph to simulate.
    input_providers : list, optional
        Input values, one list item per input. Each list item can be an array of values,
        a callable taking a time index and returning the value, or a
        number (constant input). If a value is not provided for an input, it will be 0.
    """

    _sfg: SFG
    _results: MutableResultArrayMap
    _delays: MutableDelayMap
    _iteration: int
    _input_functions: list[InputFunction]
    _input_length: int | None

    def __init__(
        self,
        sfg: SFG,
        input_providers: Sequence[InputProvider | None] | None = None,
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
        if input_providers is not None:
            self.set_inputs(input_providers)

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
            if self._input_length is None:
                self._input_length = len(input_provider)
            elif self._input_length != len(input_provider):
                raise ValueError(
                    "Inconsistent input length for simulation (was"
                    f" {self._input_length}, got {len(input_provider)})"
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

    def step(
        self,
        save_results: bool = True,
        bits_override: int | None = None,
        quantize: bool = True,
    ) -> Sequence[Num]:
        """
        Run one iteration of the simulation and return the resulting output values.

        Parameters
        ----------
        save_results : bool, default: True
            Whether the results should be saved.
        bits_override : int, optional
            Specifies a word length override when truncating inputs
            which ignores the word length specified by the input signal.
        quantize : bool, default: True
            Specifies whether input truncation should be enabled in the first
            place. If set to False, input values will be used directly without any
            bit truncation.

        Returns
        -------
        The result of the simulation.
        """
        return self.run_for(1, save_results, bits_override, quantize)

    def run_until(
        self,
        iteration: int,
        save_results: bool = True,
        bits_override: int | None = None,
        quantize: bool = True,
    ) -> Sequence[Num]:
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
        bits_override : int, optional
            Specifies a word length override when truncating inputs
            which ignores the word length specified by the input signal.
        quantize : bool, default: True
            Specifies whether input truncation should be enabled in the first
            place. If set to False, input values will be used directly without any
            bit truncation.

        Returns
        -------
        The result of the simulation.
        """

        def get_input_values_for_op(op) -> list[Num]:
            input_vals = []
            for in_port in op.inputs:
                # Find the source port
                sig = in_port.signals[0]
                src_port = sig.source
                src_op = src_port.operation

                if src_op in self._sfg.input_operations:
                    val = src_op.evaluate()
                    input_vals.append(val)
                else:
                    src_key = src_op.key(src_port.index, src_op.graph_id)
                    if src_key in results:
                        input_vals.append(results[src_key])
                    else:
                        val = src_op.current_output(
                            src_port.index, self._delays, src_op.graph_id
                        )
                        input_vals.append(val)
            return input_vals

        results: dict[ResultKey, Num] = {}
        while self._iteration < iteration:
            # Fetch the input values for this iteration
            input_values = [
                self._input_functions[i](self._iteration)
                for i in range(self._sfg.input_count)
            ]

            # Set the input operation outputs to the fetched input values
            for i, input_op in enumerate(self._sfg.input_operations):
                input_op.value = input_values[i]

            # Evaluate the SFG for this iteration level-per-level using the precedence list
            prec_list = self._sfg.get_precedence_list()
            for level in prec_list:
                for out_port in level:
                    # If the operation is a Delay, handle it specially
                    if isinstance(out_port.operation, Delay):
                        val = out_port.operation.current_output(
                            0, self._delays, out_port.operation.graph_id
                        )
                        results[
                            out_port.operation.key(0, out_port.operation.graph_id)
                        ] = val
                        continue

                    # Build input values for the operation feeding this source
                    input_vals = get_input_values_for_op(out_port.operation)

                    # Evaluate the output port
                    val = out_port.operation.evaluate_output(
                        out_port.index,
                        input_vals,
                        results,
                        self._delays,
                        out_port.operation.graph_id,
                        bits_override,
                        quantize,
                    )
                    results[
                        out_port.operation.key(
                            out_port.index, out_port.operation.graph_id
                        )
                    ] = val

            # Update the value of the delay elements
            for delay_op in self._sfg.find_by_type(Delay):
                input_val = get_input_values_for_op(delay_op)[0]
                self._delays[delay_op.key(0, delay_op.graph_id)] = input_val

            # Update the output values
            for output_op in self._sfg.output_operations:
                val = get_input_values_for_op(output_op)[0]
                results[output_op.graph_id] = val

            if save_results:
                for key, value in results.items():
                    self._results[key].append(value)
            self._iteration += 1

        return [results[op.graph_id] for op in self._sfg.output_operations]

    def run_for(
        self,
        iterations: int,
        save_results: bool = True,
        bits_override: int | None = None,
        quantize: bool = True,
    ) -> Sequence[Num]:
        """
        Run a given number of iterations of the simulation.

        Return the output values of the last iteration.

        Parameters
        ----------
        iterations : int
            Number of iterations to simulate.
        save_results : bool, default: True
            Whether the results should be saved.
        bits_override : int, optional
            Specifies a word length override when truncating inputs
            which ignores the word length specified by the input signal.
        quantize : bool, default: True
            Specifies whether input truncation should be enabled in the first
            place. If set to False, input values will be used directly without any
            bit truncation.

        Returns
        -------
        The result of the simulation.
        """
        return self.run_until(
            self._iteration + iterations, save_results, bits_override, quantize
        )

    def run(
        self,
        save_results: bool = True,
        bits_override: int | None = None,
        quantize: bool = True,
    ) -> Sequence[Num]:
        """
        Run the simulation until the end of its input arrays.

        Return the output values of the last iteration.

        Parameters
        ----------
        save_results : bool, default: True
            Whether the results should be saved.
        bits_override : int, optional
            Specifies a word length override when truncating inputs
            which ignores the word length specified by the input signal.
        quantize : bool, default: True
            Specifies whether input truncation should be enabled in the first
            place. If set to False, input values will be used directly without any
            bit truncation.

        Returns
        -------
        The result of the simulation.
        """
        if self._input_length is None:
            raise IndexError("Tried to run unlimited simulation")
        return self.run_until(self._input_length, save_results, bits_override, quantize)

    @property
    def iteration(self) -> int:
        """Get the current iteration number of the simulation."""
        return self._iteration

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
        return {key: np.array(value) for key, value in self._results.items()}

    def clear_results(self) -> None:
        """Clear all results that were saved until now."""
        self._results.clear()

    def clear_state(self) -> None:
        """
        Clear all current state of the simulation, except for the results and iteration.
        """
        self._delays.clear()

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
