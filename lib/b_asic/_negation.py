"""Connection helpers for operation-specific negation propagation hooks."""

from collections.abc import Mapping
from copy import deepcopy
from typing import cast

from b_asic.core_operations import (
    Addition,
    AddSub,
    Constant,
    ImaginaryMultiplication,
    Negation,
    Subtraction,
)
from b_asic.operation import Operation
from b_asic.port import OutputPort
from b_asic.signal import Signal
from b_asic.types import GraphID


def negated_inputs(operation: Operation) -> dict[int, OutputPort]:
    """Return the unnegated source of each input with an adjacent Negation."""
    result = {}
    for index, port in enumerate(operation.inputs):
        source = port.connected_source
        if source is not None and type(source.operation) is Negation:
            upstream = source.operation.input(0).connected_source
            if upstream is not None and upstream.operation is not operation:
                result[index] = upstream
    return result


def bypass_inputs(operation: Operation, sources: Mapping[int, OutputPort]) -> bool:
    """Bypass input signs for this consumer while preserving its signals."""
    for index, source in sources.items():
        operation.input(index).signals[0].set_source(source)
    return bool(sources)


def cancel_pair(operation: Operation) -> bool:
    """Remove a Negation whose input is another ordinary Negation."""
    sources = negated_inputs(operation)
    if not sources:
        return False
    for signal in list(operation.output(0).signals):
        signal.set_source(sources[0])
    for signal in list(operation.input(0).signals):
        signal.remove_source()
        signal.remove_destination()
    return True


def move_forward(operation: Operation, sources: Mapping[int, OutputPort]) -> bool:
    """Move selected multiplicative input signs to one output sign."""
    if not bypass_inputs(operation, sources):
        return False
    if len(sources) % 2:
        negate_output(operation)
    return True


def negate_output(operation: Operation) -> None:
    """Insert one sign before all current consumers of an operation."""
    negation = Negation()
    for signal in list(operation.output(0).signals):
        signal.set_source(negation.output(0))
    negation.input(0).connect(operation.output(0))


def move_linear_forward(
    operation: Operation, sources: Mapping[int, OutputPort]
) -> bool:
    """Move a common sign on all linear inputs to the output."""
    if len(sources) != operation.input_count:
        return False
    bypass_inputs(operation, sources)
    negation = Negation()
    for signal in list(operation.output(0).signals):
        signal.set_source(negation.output(0))
    negation.input(0).connect(operation.output(0))
    return True


def output_negations(operation: Operation) -> list[Negation]:
    """Find ordinary Negations immediately consuming an operation's output."""
    return [
        signal.destination.operation
        for signal in operation.output(0).signals
        if signal.destination is not None
        and type(signal.destination.operation) is Negation
    ]


def move_backward(operation: Operation, indices: set[int]) -> bool:
    """Move output signs onto inputs, copying producers shared with other users."""
    negations = output_negations(operation)
    for negation in negations:
        retained = operation
        if operation.output(0).signal_count != 1:
            retained = cast(Operation, operation.copy())
            retained.graph_id = GraphID("")
            for original, copied in zip(operation.inputs, retained.inputs, strict=True):
                signal = cast(Signal, original.signals[0].copy())
                signal.graph_id = GraphID("")
                signal.set_source(cast(OutputPort, original.connected_source))
                signal.set_destination(copied)
        for index in indices:
            port = retained.input(index)
            source = port.connected_source
            if source is not None and type(source.operation) is Negation:
                upstream = source.operation.input(0).connected_source
                if upstream is not None:
                    port.signals[0].set_source(upstream)
                    continue
            added = Negation()
            added.input(0).connect(cast(OutputPort, source))
            port.signals[0].set_source(added.output(0))
        for signal in list(negation.output(0).signals):
            signal.set_source(retained.output(0))
        for signal in list(negation.input(0).signals):
            signal.remove_source()
            signal.remove_destination()
    return bool(negations)


def nonzero_divisor(operation: Operation) -> bool:
    """Check the effective constant divisor, preserving Division's zero behavior."""
    source = operation.input(1).connected_source
    visited = set()
    while source is not None and type(source.operation) is Negation:
        if source.operation in visited:
            return False
        visited.add(source.operation)
        source = source.operation.input(0).connected_source
    if source is None or type(source.operation) is not Constant:
        return False
    value = source.operation.value
    if getattr(operation, "real_valued", False):
        value = value.real
    return bool(value != 0)


def replace_add_sub(
    operation: Operation, *, is_add: bool, swap: bool = False
) -> Operation:
    """Change an adder's kind while retaining metadata and input arithmetic."""
    if type(operation) is AddSub:
        replacement = AddSub(is_add=is_add)
    else:
        replacement = Addition() if is_add else Subtraction()
    for name, value in operation.params.items():
        replacement.set_param(name, deepcopy(value))
    if type(replacement) is AddSub:
        replacement.set_param("is_add", is_add)
    replacement.name = operation.name
    replacement.graph_id = (
        operation.graph_id if type(replacement) is type(operation) else GraphID("")
    )
    replacement.execution_time = operation.execution_time
    permutation = (1, 0) if swap else (0, 1)
    for new_index, old_index in enumerate(permutation):
        old_port, new_port = operation.input(old_index), replacement.input(new_index)
        new_port.latency_offset = old_port.latency_offset
        for signal in list(old_port.signals):
            signal.set_destination(new_port)
    replacement.output(0).latency_offset = operation.output(0).latency_offset
    for signal in list(operation.output(0).signals):
        signal.set_source(replacement.output(0))
    if swap:
        replacement.set_param("in0_scale", operation.param("in1_scale"))
        replacement.set_param("in1_scale", operation.param("in0_scale"))
        if operation.param("mul_j"):
            port = replacement.input(0)
            factor = ImaginaryMultiplication(port.connected_source)
            port.signals[0].set_source(factor.output(0))
            replacement.set_param("mul_j", False)
    return replacement


def propagate_add_sub(
    operation: Operation,
    *,
    is_add: bool,
    direction: str,
    input_indices: set[int] | None,
    propagate: bool,
) -> bool:
    """Absorb input signs into addition/subtraction or distribute an output sign."""
    if propagate and direction == "backward":
        if output_negations(operation) and input_indices not in (None, {0, 1}):
            raise ValueError(
                "Addition and subtraction require both inputs for backward negation propagation"
            )
        return move_backward(operation, {0, 1})
    sources = negated_inputs(operation)
    if propagate and input_indices is not None:
        sources = {
            index: source for index, source in sources.items() if index in input_indices
        }
    if propagate and len(sources) == operation.input_count:
        return move_linear_forward(operation, sources)
    index = 1 if 1 in sources else 0 if 0 in sources else None
    if index is None:
        return False
    if not is_add and index == 0 and not propagate:
        return False
    bypass_inputs(operation, {index: sources[index]})
    replacement = replace_add_sub(
        operation, is_add=not is_add, swap=is_add and index == 0
    )
    if not is_add and index == 0:
        negate_output(replacement)
    return True
