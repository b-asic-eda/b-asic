"""Normalize fixed integer sample-rate changes into a single-rate phase graph."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, cast

from b_asic.core_operations import Constant
from b_asic.operation import Operation, ResultKey
from b_asic.port import InputPort, OutputPort
from b_asic.signal import Signal
from b_asic.special_operations import Compression, Delay, Expansion, Input, Output
from b_asic.types import GraphID
from b_asic.utility_operations import Sink

if TYPE_CHECKING:
    from b_asic.sfg import SFG

__all__ = ["RateNormalization"]


@dataclass(frozen=True)
class RateNormalization:
    """
    A single-rate graph and the stream layout of one common iteration period.

    ``input_samples`` and ``output_samples`` give the number of samples per
    original port in a period. ``input_phases`` and ``output_phases`` describe
    the corresponding scalar ports of ``sfg`` as ``(original_port, phase)``.
    Ports are grouped by original port, with phases in chronological order.
    Disconnected input components use the same reference input sample rate.

    ``result_phases`` maps each original result key to the single-rate result
    keys for its consecutive samples within a period. Several original keys
    may refer to the same result after rate-changing operations become wiring.
    The phase mappings describe ``sfg`` before any further simplification.
    """

    sfg: SFG
    input_samples: tuple[int, ...]
    output_samples: tuple[int, ...]
    input_phases: tuple[tuple[int, int], ...]
    output_phases: tuple[tuple[int, int], ...]
    result_phases: dict[ResultKey, tuple[ResultKey, ...]]


def _source_key(port: InputPort, prefix: str = "") -> ResultKey:
    source = port.connected_source
    if source is None:
        raise ValueError("Missing source in signal.")
    return source.operation.key(source.index, prefix + source.operation.graph_id)


def _flatten_with_aliases(sfg: SFG) -> tuple[SFG, dict[ResultKey, ResultKey]]:
    """Flatten a copy while retaining hierarchical result keys at interfaces."""
    from b_asic.sfg import SFG  # noqa: PLC0415

    graph = sfg()
    aliases: dict[ResultKey, ResultKey] = {}
    graphs = [(graph, "")]
    operations = []
    while graphs:
        current_graph, prefix = graphs.pop()
        for op in current_graph.operations:
            key_base = prefix + op.graph_id
            operations.append((op, key_base))
            if isinstance(op, SFG):
                inner_prefix = key_base + "."
                graphs.append((op, inner_prefix))
                for port, input_op in zip(op.inputs, op.input_operations, strict=True):
                    aliases[input_op.key(0, inner_prefix + input_op.graph_id)] = (
                        _source_key(port, prefix)
                    )
                for index, output in enumerate(op.output_operations):
                    source = _source_key(output.input(0), inner_prefix)
                    aliases[op.key(index, key_base)] = source
                    aliases[ResultKey(inner_prefix + output.graph_id)] = source

    for output in graph.output_operations:
        aliases[ResultKey(output.graph_id)] = _source_key(output.input(0))
    for op, key_base in operations:
        op.graph_id = GraphID(key_base)
    graph = graph.flatten()
    for key, source in aliases.items():
        visited = {key}
        while source in aliases:
            if source in visited:
                raise ValueError("Direct feedback loop through SFG interfaces.")
            visited.add(source)
            source = aliases[source]
        aliases[key] = source
    return graph, aliases


def _input_samples(operation: Operation, output_samples: int | Fraction) -> Fraction:
    output_samples = Fraction(output_samples)
    if isinstance(operation, Expansion):
        return output_samples / operation.factor
    if isinstance(operation, Compression):
        return output_samples * operation.factor
    return output_samples


def _sample_counts(graph: SFG) -> dict[Operation, int]:
    """Solve exact rate constraints and choose integer counts over a common period."""
    adjacency: dict[Operation, list[tuple[Operation, Fraction]]] = defaultdict(list)
    for operation in graph.operations:
        ratio = (
            Fraction(operation.factor)
            if isinstance(operation, Expansion)
            else Fraction(1, operation.factor)
            if isinstance(operation, Compression)
            else Fraction(1)
        )
        for port in operation.inputs:
            source = port.connected_source
            if source is None:
                raise ValueError("Missing source in signal.")
            # Constants are values, rather than streams with an intrinsic rate.
            if not isinstance(source.operation, Constant):
                adjacency[source.operation].append((operation, ratio))
                adjacency[operation].append((source.operation, 1 / ratio))

    rates: dict[Operation, Fraction] = {}
    for start in [*graph.input_operations, *graph.operations]:
        if start in rates or isinstance(start, Constant):
            continue
        rates[start] = Fraction(1)
        pending = [start]
        while pending:
            operation = pending.pop()
            for neighbor, ratio in adjacency[operation]:
                rate = rates[operation] * ratio
                if neighbor in rates:
                    if rates[neighbor] != rate:
                        raise ValueError(
                            "Inconsistent sample rates at operation "
                            f"{neighbor.graph_id!r}. Ordinary operations require "
                            "matching input rates."
                        )
                else:
                    rates[neighbor] = rate
                    pending.append(neighbor)

    # Include the input rate of expansions driven only by constants, and use
    # one period for all components rather than stopping them at different times.
    denominator = math.lcm(
        *(
            value.denominator
            for op, rate in rates.items()
            for value in (rate, _input_samples(op, rate))
        )
    )
    counts = {op: int(rate * denominator) for op, rate in rates.items()}

    for operation in graph.operations:
        if isinstance(operation, Constant):
            counts[operation] = max(
                (
                    int(
                        _input_samples(
                            signal.destination.operation,
                            counts[signal.destination.operation],
                        )
                    )
                    for signal in operation.output(0).signals
                    if signal.destination is not None
                ),
                default=1,
            )
    return counts


def normalize_rates(sfg: SFG) -> RateNormalization:
    """Build phase copies, replacing rate changes and within-period delays by wiring."""
    from b_asic.sfg import SFG  # noqa: PLC0415

    graph, aliases = _flatten_with_aliases(sfg)
    counts = _sample_counts(graph)
    copies: dict[Operation, list[Operation]] = {}
    sources: dict[tuple[OutputPort, int], OutputPort] = {}
    for operation in graph.operations:
        if isinstance(operation, Expansion | Compression):
            continue
        phases = 1 if isinstance(operation, Delay) else counts[operation]
        copies[operation] = []
        for phase in range(phases):
            replacement = cast(Operation, operation.copy())
            replacement.graph_id = GraphID(f"{operation.graph_id}_{phase}")
            copies[operation].append(replacement)
            for port in operation.outputs:
                sources[port, phase] = replacement.output(port.index)

    zeros: list[Constant] = []

    def resolve(port: OutputPort, phase: int) -> OutputPort:
        key = (port, phase)
        path = []
        visited = set()
        while key not in sources:
            if key in visited:
                raise ValueError(
                    "Direct feedback loop through rate-changing operations."
                )
            visited.add(key)
            path.append(key)
            current_port, current_phase = key
            operation = current_port.operation
            source = operation.input(0).connected_source
            if source is None:
                raise ValueError("Missing source in signal.")
            if isinstance(operation, Expansion):
                if current_phase % operation.factor != operation.phase:
                    zero = Constant(0)
                    zero.graph_id = GraphID(f"rate_zero{len(zeros)}")
                    zeros.append(zero)
                    sources[key] = zero.output(0)
                    break
                key = (source, (current_phase - operation.phase) // operation.factor)
            elif isinstance(operation, Compression):
                key = (source, current_phase * operation.factor + operation.phase)
            elif isinstance(operation, Delay):
                key = (source, current_phase - 1)
            else:
                raise ValueError(
                    f"Missing phase {current_phase} of {operation.graph_id}."
                )
        result = sources[key]
        for entry in path:
            sources[entry] = result
        return result

    for operation, replacements in copies.items():
        for phase, replacement in enumerate(replacements):
            input_phase = (
                counts[operation] - 1 if isinstance(operation, Delay) else phase
            )
            for port in operation.inputs:
                source = port.connected_source
                if source is None:
                    raise ValueError("Missing source in signal.")
                signal = cast(Signal, port.signals[0].copy())
                signal.set_source(resolve(source, input_phase))
                signal.set_destination(replacement.input(port.index))

    # Preserve every sample as an intermediate trace, including computations
    # discarded by compression. Explicit Sinks allow subsequent dead-code removal.
    result_sources = {
        operation.key(port.index, operation.graph_id): tuple(
            resolve(port, phase) for phase in range(counts[operation])
        )
        for operation in graph.operations
        for port in operation.outputs
    }
    sink_roots = [
        replacement
        for replacements in copies.values()
        for replacement in replacements
        if isinstance(replacement, Sink)
    ]
    for replacements in [*copies.values(), zeros]:
        for replacement in replacements:
            sink_roots.extend(
                Sink(port) for port in replacement.outputs if not port.signals
            )

    input_samples = tuple(counts[op] for op in graph.input_operations)
    output_samples = tuple(counts[op] for op in graph.output_operations)
    normalized = SFG(
        [cast(Input, copy) for op in graph.input_operations for copy in copies[op]],
        [cast(Output, copy) for op in graph.output_operations for copy in copies[op]],
        name=graph.name,
    )
    for sink in sink_roots:
        if sink not in normalized._original_components_to_new:
            normalized._add_operation_connected_tree_copy(sink)
    normalized.get_operations_topological_order()

    def result_key(port: OutputPort) -> ResultKey:
        operation = cast(
            Operation, normalized._original_components_to_new[port.operation]
        )
        return operation.key(port.index, operation.graph_id)

    result_phases = {
        key: tuple(result_key(port) for port in ports)
        for key, ports in result_sources.items()
    }
    for key, source in aliases.items():
        result_phases[key] = result_phases[source]
    return RateNormalization(
        sfg=normalized,
        input_samples=input_samples,
        output_samples=output_samples,
        input_phases=tuple(
            (index, phase)
            for index, count in enumerate(input_samples)
            for phase in range(count)
        ),
        output_phases=tuple(
            (index, phase)
            for index, count in enumerate(output_samples)
            for phase in range(count)
        ),
        result_phases=result_phases,
    )
