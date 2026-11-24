"""Analyze sums and shared subexpressions in signal flow graphs."""

import itertools
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, NamedTuple, cast

import networkx as nx

from b_asic.port import OutputPort

if TYPE_CHECKING:
    from b_asic.sfg import SFG


class _SumTerm(NamedTuple):
    """A source contribution ``sign * source_value * 2**(-shift)``."""

    source: OutputPort
    sign: int | complex
    shift: int


def _simplify_sum_terms(
    terms: Iterable[_SumTerm], *, merge_identical: bool
) -> tuple[_SumTerm, ...]:
    """Cancel opposite terms before optionally merging equal terms by carrying."""
    remaining: list[_SumTerm | None] = []
    positions: defaultdict[_SumTerm, list[int]] = defaultdict(list)
    for term in terms:
        opposite = term._replace(sign=-term.sign)
        opposite_positions = positions.get(opposite)
        if opposite_positions:
            remaining[opposite_positions.pop()] = None
        else:
            positions[term].append(len(remaining))
            remaining.append(term)

    if merge_identical:
        # Process the smallest contributions first, so their carries can cancel
        # larger contributions before those are merged. Each merge removes a term.
        for initial in sorted(positions, key=lambda term: term.shift, reverse=True):
            while len(positions[initial]) >= 2:
                term = initial
                while len(positions[term]) >= 2:
                    first = positions[term].pop()
                    second = positions[term].pop()
                    remaining[first] = remaining[second] = None
                    merged = term._replace(shift=term.shift - 1)
                    opposite = merged._replace(sign=-merged.sign)
                    opposite_positions = positions.get(opposite)
                    if opposite_positions:
                        remaining[opposite_positions.pop()] = None
                        break
                    position = min(first, second)
                    remaining[position] = merged
                    positions[merged].append(position)
                    term = merged

    return tuple(term for term in remaining if term is not None)


def _find_sums(
    sfg: "SFG", merge_identical: bool = False
) -> dict[OutputPort, tuple[_SumTerm, ...]]:
    """
    Find the signed, shifted terms at each distinct sum output port.

    A sum contains one or more interconnected built-in Addition,
    Subtraction, Negation, AddSub, or ImaginaryMultiplication operations.
    Its root is an output port connected to at least one operation outside
    these types, including Output and Delay. Each root is included once,
    regardless of fanout, even if it also feeds other sum operations. Nested
    SFGs are analyzed separately, without expanding sums across their
    interfaces. Subclasses of the sum operations are treated as boundaries,
    since their arithmetic may differ.

    Each term contains its source OutputPort, sign, and accumulated right
    shift. It contributes ``sign * source_value * 2**(-shift)`` to the root.
    Both input and output scale parameters are accumulated. A sign is 1 or
    -1, or 1j or -1j when a path includes imaginary factors from ``mul_j`` or
    ImaginaryMultiplication. Opposite signs with identical source ports and
    shifts are always cancelled pairwise before any merging. Surviving terms
    follow input-port order. Roots whose terms all cancel retain an empty tuple.

    If *merge_identical* is True, pairs with the same source, sign, and shift
    are replaced by one term with its shift reduced by one. Merging repeats,
    including cancellation of opposite terms created by a merge. Shifts may
    become negative, representing left shifts. This option is intended for
    fixed-point arithmetic; by default, equal terms remain separate.

    The returned ports belong to *sfg* or its nested graphs. No graph
    components are modified. The expansion describes unquantized arithmetic
    and does not model rounding at intermediate operations.

    Raises
    ------
    ValueError
        If an input of a sum operation is unconnected.
    RuntimeError
        If a sum contains a feedback loop without a non-sum boundary.
    """
    from b_asic.core_operations import (  # noqa: PLC0415
        Addition,
        AddSub,
        ImaginaryMultiplication,
        Negation,
        Subtraction,
    )
    from b_asic.sfg import SFG  # noqa: PLC0415

    sum_types = (Addition, Subtraction, Negation, AddSub, ImaginaryMultiplication)
    sums: dict[OutputPort, tuple[_SumTerm, ...]] = {}

    def expand(root: OutputPort) -> tuple[_SumTerm, ...]:
        terms = []
        active: set[OutputPort] = set()
        pending: list[tuple[OutputPort, int | complex, int, bool]] = [
            (root, 1, 0, False)
        ]
        while pending:
            source, sign, shift, leaving = pending.pop()
            if leaving:
                active.remove(source)
                continue
            operation = source.operation
            if type(operation) not in sum_types:
                terms.append(_SumTerm(source, sign, shift))
                continue
            if source in active:
                raise RuntimeError(
                    "Direct feedback loop detected while finding sums. "
                    f"Operation: {operation.graph_id}"
                )
            active.add(source)
            pending.append((source, sign, shift, True))
            for port in reversed(operation.inputs):
                upstream = port.connected_source
                if upstream is None:
                    raise ValueError(
                        "Unconnected input port in sum. "
                        f"Operation: {operation.graph_id}, input: {port.index}"
                    )
                if isinstance(operation, Negation):
                    input_sign = -sign
                    input_shift = shift
                elif isinstance(operation, ImaginaryMultiplication):
                    input_sign = sign * 1j
                    input_shift = shift
                else:
                    arithmetic = cast(Addition | Subtraction | AddSub, operation)
                    input_sign = sign
                    input_shift = shift + arithmetic.out0_scale
                    if port.index == 0:
                        input_shift += arithmetic.in0_scale
                    else:
                        input_shift += arithmetic.in1_scale
                        if isinstance(arithmetic, Subtraction) or (
                            isinstance(arithmetic, AddSub) and not arithmetic.is_add
                        ):
                            input_sign = -input_sign
                        if arithmetic.mul_j:
                            input_sign *= 1j
                pending.append((upstream, input_sign, input_shift, False))
        return _simplify_sum_terms(terms, merge_identical=merge_identical)

    pending_graphs = [sfg]
    while pending_graphs:
        graph = pending_graphs.pop()
        for operation in dict.fromkeys(graph.operations):
            if isinstance(operation, SFG):
                pending_graphs.append(operation)
            if type(operation) in sum_types:
                continue
            for port in operation.inputs:
                source = port.connected_source
                if (
                    source is not None
                    and type(source.operation) in sum_types
                    and source not in sums
                ):
                    sums[source] = expand(source)
    return sums


def _partition_sums(
    sums: Mapping[OutputPort, tuple[_SumTerm, ...]],
) -> list[dict[OutputPort, tuple[_SumTerm, ...]]]:
    """
    Partition complete sums into groups connected by shared sources.

    The input is the result of :func:`_find_sums`; each sum is already
    expanded to sources outside the sum operations. Two sums are connected
    if any of their terms share the same source OutputPort, regardless of
    sign or shift. Connections are transitive: sums containing ``a + b``,
    ``b + c``, and ``c + d`` belong to one partition.

    Each partition maps sum output ports to their original term tuples. Isolated
    sums form singleton partitions. Partitions and their members follow
    the order of their first occurrence in *sums*. An empty input produces
    an empty list. Neither the input mapping nor the graph is modified.
    """
    groups = nx.utils.UnionFind(sums)
    first_root_by_source: dict[OutputPort, OutputPort] = {}
    for root, terms in sums.items():
        for term in terms:
            first_root = first_root_by_source.setdefault(term.source, root)
            groups.union(root, first_root)

    partitions: dict[OutputPort, dict[OutputPort, tuple[_SumTerm, ...]]] = {}
    for root, terms in sums.items():
        partitions.setdefault(groups[root], {})[root] = terms
    return list(partitions.values())


def _sum_pair_statistics(
    partition: Mapping[OutputPort, tuple[_SumTerm, ...]],
) -> Counter[tuple[_SumTerm, _SumTerm]]:
    """
    Count normalized pairs of term occurrences within each sum in a partition.

    The input is one partition returned by :func:`_partition_sums`. All
    unordered pairs of term positions are counted separately within each
    sum; terms from different sums are never paired. Repeated terms retain
    their multiplicity. Each sum is counted once, independently of its output
    fanout. Empty sums and single-term sums contribute no pairs.

    A pair is normalized by factoring out its common power of two and the
    phase of its first term. The first _SumTerm has sign 1 and shift 0. The
    second has a nonnegative relative right shift and a sign of 1, -1, 1j,
    or -1j, carrying any remaining imaginary factor. Pairs differing only
    by order, a common shift, or a common sign or imaginary factor are counted
    together.

    The less-shifted term comes first. Equal shifts are ordered by source
    graph ID and output index, with source identity breaking any remaining
    ties. For identical sources and shifts, a relative -1j is ordered as 1j
    by swapping the terms. The returned keys contain normalized _SumTerms;
    the original terms and graph are not modified.
    """
    phases = (1, -1, 1j, -1j)
    phase_order = {phase: index for index, phase in enumerate(phases)}
    source_order = {
        term.source: (
            term.source.operation.graph_id,
            term.source.index,
            id(term.source),
        )
        for terms in partition.values()
        for term in terms
    }

    def normalize(first: _SumTerm, second: _SumTerm) -> tuple[_SumTerm, _SumTerm]:
        relative_phase = second.sign * first.sign.conjugate()
        return (
            _SumTerm(first.source, 1, 0),
            _SumTerm(
                second.source,
                phases[phase_order[relative_phase]],
                second.shift - first.shift,
            ),
        )

    statistics: Counter[tuple[_SumTerm, _SumTerm]] = Counter()
    for terms in partition.values():
        for first, second in itertools.combinations(terms, 2):
            if first.shift > second.shift:
                first, second = second, first
            pair = normalize(first, second)
            if first.shift == second.shift:
                pair = min(
                    pair,
                    normalize(second, first),
                    key=lambda candidate: (
                        source_order[candidate[0].source],
                        source_order[candidate[1].source],
                        phase_order[candidate[1].sign],
                    ),
                )
            statistics[pair] += 1
    return statistics
