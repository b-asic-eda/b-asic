"""
B-ASIC Simulation Module.

Contains a class for simulating the result of an SFG given a set of input values.
"""

from collections import defaultdict
from numbers import Number
from typing import (
    Callable,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Sequence,
    Union,
)

import numpy as np

from b_asic.operation import MutableDelayMap, ResultKey
from b_asic.signal_flow_graph import SFG
from b_asic.types import Num

ResultArrayMap = Mapping[ResultKey, Sequence[Num]]
MutableResultArrayMap = MutableMapping[ResultKey, MutableSequence[Num]]
InputFunction = Callable[[int], Num]
InputProvider = Union[Num, Sequence[Num], InputFunction]


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
    _input_functions: List[InputFunction]
    _input_length: Optional[int]

    def __init__(
        self,
        sfg: SFG,
        input_providers: Optional[Sequence[Optional[InputProvider]]] = None,
    ):
        """Construct a Simulation of an SFG."""
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
        Set the input used to get values for the specific input at the
        given index to the internal SFG.

        Parameters
        ----------
        index : int
            The input index.
        input_provider : list, callable, or number
            Can be an array of values, a callable taking a time index and returning the value, or a
            number (constant input).
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

    def set_inputs(self, input_providers: Sequence[Optional[InputProvider]]) -> None:
        """
        Set the input functions used to get values for the inputs to the internal SFG.
        """
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
        bits_override: Optional[int] = None,
        truncate: bool = True,
    ) -> Sequence[Num]:
        """
        Run one iteration of the simulation and return the resulting output values.
        """
        return self.run_for(1, save_results, bits_override, truncate)

    def run_until(
        self,
        iteration: int,
        save_results: bool = True,
        bits_override: Optional[int] = None,
        truncate: bool = True,
    ) -> Sequence[Num]:
        """
        Run the simulation until its iteration is greater than or equal to the given
        iteration and return the output values of the last iteration.
        """
        result: Sequence[Num] = []
        while self._iteration < iteration:
            input_values = [
                self._input_functions[i](self._iteration)
                for i in range(self._sfg.input_count)
            ]
            results = {}
            result = self._sfg.evaluate_outputs(
                input_values,
                results,
                self._delays,
                "",
                bits_override,
                truncate,
            )
            if save_results:
                for key, value in results.items():
                    self._results[key].append(value)
            self._iteration += 1
        return result

    def run_for(
        self,
        iterations: int,
        save_results: bool = True,
        bits_override: Optional[int] = None,
        truncate: bool = True,
    ) -> Sequence[Num]:
        """
        Run a given number of iterations of the simulation and return the output
        values of the last iteration.
        """
        return self.run_until(
            self._iteration + iterations, save_results, bits_override, truncate
        )

    def run(
        self,
        save_results: bool = True,
        bits_override: Optional[int] = None,
        truncate: bool = True,
    ) -> Sequence[Num]:
        """
        Run the simulation until the end of its input arrays and return the output
        values of the last iteration.
        """
        if self._input_length is None:
            raise IndexError("Tried to run unlimited simulation")
        return self.run_until(self._input_length, save_results, bits_override, truncate)

    @property
    def iteration(self) -> int:
        """Get the current iteration number of the simulation."""
        return self._iteration

    @property
    def results(self) -> ResultArrayMap:
        """
        Get a mapping from result keys to numpy arrays containing all results, including
        intermediate values, calculated for each iteration up until now that was run
        with save_results enabled.
        The mapping is indexed using the key() method of Operation with the appropriate
        output index.
        Example result after 3 iterations::

            {"c1": [3, 6, 7], "c2": [4, 5, 5], "bfly1.0": [7, 0, 0], "bfly1.1": [-1, 0, 2], "0": [7, -2, -1]}
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
