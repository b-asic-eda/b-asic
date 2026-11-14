"""Memory access events and physical port assignments."""

from collections import defaultdict
from collections.abc import Iterable

from b_asic.process import MemoryProcess


class _MemoryAssignment(dict):
    """Resource coloring carrying the selected physical port of every access."""

    def __init__(self, coloring, ports):
        super().__init__(coloring)
        self.ports = ports


def _memory_access_groups(
    variables: Iterable[MemoryProcess], schedule_time: int
) -> list[list[tuple[MemoryProcess, int | None]]]:
    """
    Group accesses competing for read or write ports in a schedule cycle.

    An access is ``(variable, delay)``; ``None`` denotes its write. Equal-delay
    consumers share a broadcast read.
    """
    slots: defaultdict[tuple[bool, int], list[tuple[MemoryProcess, int | None]]] = (
        defaultdict(list)
    )
    for var in sorted(variables, key=lambda var: (var.start_time, var.name)):
        for delay in (None, *sorted(set(var.reads.values()))):
            cycle = (var.start_time + (delay or 0)) % schedule_time
            slots[delay is None, cycle].append((var, delay))
    return list(slots.values())


def _default_memory_ports(
    variables: Iterable[MemoryProcess], schedule_time: int
) -> dict[tuple[MemoryProcess, int | None], int]:
    """Allocate consecutive ports when no optimized assignment is available."""
    return {
        access: port
        for group in _memory_access_groups(variables, schedule_time)
        for port, access in enumerate(group)
    }
