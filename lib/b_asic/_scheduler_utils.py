"""Validated connections and resource occupancy shared by schedulers."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from b_asic.operation import Operation
from b_asic.port import InputPort, OutputPort
from b_asic.special_operations import Delay
from b_asic.utility_operations import DontCare


def _execution_occupancy(
    start: int, duration: int, period: int | None = None
) -> Counter[int]:
    """Count occupied slots, including overlapping iterations of one operation."""
    if period is None:
        return Counter(range(start, start + duration))
    full_periods, remainder = divmod(duration, period)
    occupancy = (
        Counter(dict.fromkeys(range(period), full_periods))
        if full_periods
        else Counter()
    )
    occupancy.update((start + offset) % period for offset in range(remainder))
    return occupancy


def _execution_count(
    start: int, duration: int, time: int, period: int | None = None
) -> int:
    """Return occupancy at one slot without constructing an occupancy table."""
    if period is None:
        return int(start <= time < start + duration)
    full_periods, remainder = divmod(duration, period)
    return full_periods + int((time - start) % period < remainder)


@dataclass(frozen=True, slots=True)
class _Connection:
    """A single input connection, with delay chains resolved independently."""

    source: OutputPort
    destination: InputPort
    delay_count: int
    source_offset: int
    destination_offset: int


def _get_connections(operations: Iterable[Operation]) -> tuple[_Connection, ...]:
    """Validate port offsets and resolve delay chains without merging edges."""
    connections = []
    for op in operations:
        for port in (*op.inputs, *op.outputs):
            if port.latency_offset is None:
                raise ValueError(
                    f"Port {port.index} of operation {op.graph_id} has no latency-offset."
                )
        for port in op.inputs:
            source = port.connected_source
            depth = 0
            seen = set()
            while source is not None and isinstance(source.operation, Delay):
                if id(source.operation) in seen:
                    raise ValueError("A delay-only feedback loop cannot be scheduled.")
                seen.add(id(source.operation))
                source = source.operation.input(0).connected_source
                depth += 1
            if source is None:
                raise ValueError(
                    f"Input port {port.index} of operation {op.graph_id} is unconnected."
                )
            if isinstance(source.operation, DontCare):
                continue
            if source.latency_offset is None:
                raise ValueError(
                    f"Output port {source.index} of operation {source.operation.graph_id} has no latency-offset."
                )
            connections.append(
                _Connection(
                    source,
                    port,
                    depth,
                    source.latency_offset,
                    cast(int, port.latency_offset),
                )
            )
    return tuple(connections)
