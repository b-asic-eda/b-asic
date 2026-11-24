import itertools
import sys
from collections import Counter

import pytest

from b_asic import SFG, Input, Output, Signal
from b_asic._subexpressions import (
    _find_sums,
    _partition_sums,
    _simplify_sum_terms,
    _sum_pair_statistics,
    _SumTerm,
)
from b_asic.core_operations import (
    Addition,
    AddSub,
    ConstantMultiplication,
    ImaginaryMultiplication,
    Multiplication,
    Negation,
    Shift,
    Subtraction,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.special_operations import Delay


@pytest.mark.parametrize("multiply", [False, True])
def test_find_sums_without_sum_operations(multiply):
    source = Input()
    graph = SFG(
        [source], [Output(Multiplication(source, source) if multiply else source)]
    )

    assert graph._find_sums() == {}


def test_find_sums_accumulates_signs_and_input_and_output_shifts():
    a, b, c, d = inputs = [Input() for _ in range(4)]
    first = Subtraction(a, b, in0_scale=1, in1_scale=2, out0_scale=3)
    second = AddSub(
        is_add=False,
        in0=Negation(c),
        in1=first,
        in0_scale=4,
        in1_scale=5,
        out0_scale=6,
    )
    total = Negation(Addition(second, d, in0_scale=7, in1_scale=8, out0_scale=9))
    graph = SFG(inputs, [Output(total)])
    root = graph.output_operations[0].input(0).connected_source
    sources = [operation.output(0) for operation in graph.input_operations]
    wiring = [
        (signal, signal.source, signal.destination)
        for signal in graph.find_by_type(Signal)
    ]

    sums = graph._find_sums()

    assert sums == {
        root: (
            (sources[2], 1, 26),
            (sources[0], 1, 31),
            (sources[1], -1, 32),
            (sources[3], -1, 17),
        )
    }
    values = dict(zip(sources, [8, 24, 40, 56], strict=True))
    assert sum(
        term.sign * values[term.source] * 2 ** (-term.shift) for term in sums[root]
    ) == pytest.approx(graph.evaluate(*values.values()))
    assert wiring == [
        (signal, signal.source, signal.destination)
        for signal in graph.find_by_type(Signal)
    ]


@pytest.mark.parametrize("kind", ["add", "sub", "addsub_add", "addsub_sub"])
@pytest.mark.parametrize("mul_j", [False, True])
def test_find_sums_complex_signs(kind, mul_j):
    a, b, c = inputs = [Input() for _ in range(3)]
    inner = Subtraction(b, c, in0_scale=4, in1_scale=5, out0_scale=6, mul_j=True)
    kwargs = {
        "in0": a,
        "in1": Negation(inner),
        "in0_scale": 1,
        "in1_scale": 2,
        "out0_scale": 3,
        "mul_j": mul_j,
    }
    if kind.startswith("addsub"):
        total = AddSub(is_add=kind == "addsub_add", **kwargs)
    else:
        total = (Addition if kind == "add" else Subtraction)(**kwargs)
    graph = SFG(inputs, [Output(total)])
    sources = [operation.output(0) for operation in graph.input_operations]
    phase = (1 if kind in ("add", "addsub_add") else -1) * (1j if mul_j else 1)

    terms = graph._find_sums()[graph.output_operations[0].input(0).connected_source]

    assert terms == (
        (sources[0], 1, 4),
        (sources[1], -phase, 15),
        (sources[2], phase * 1j, 16),
    )
    for samples in [(7, -3, 5), (1 + 2j, -5 + 7j, 3 - 4j)]:
        values = dict(zip(sources, samples, strict=True))
        reconstructed = sum(
            term.sign * values[term.source] * 2 ** (-term.shift) for term in terms
        )
        assert reconstructed == pytest.approx(graph.evaluate(*samples))


@pytest.mark.parametrize("count", range(1, 6))
def test_find_sums_expands_imaginary_multiplication_chains(count):
    source = Input()
    total = source
    for _ in range(count):
        total = ImaginaryMultiplication(total)
    graph = SFG([source], [Output(total)])

    terms = graph._find_sums()[graph.output_operations[0].input(0).connected_source]

    assert terms == ((graph.input_operations[0].output(0), 1j**count, 0),)
    assert terms[0].sign * (2 + 3j) == graph.evaluate(2 + 3j)


@pytest.mark.parametrize("merge_identical", [False, True])
@pytest.mark.parametrize("phase", [1, -1, 1j, -1j])
@pytest.mark.parametrize("negative_position", [0, 1, 2])
def test_find_sums_cancels_opposite_terms_before_merging(
    merge_identical, phase, negative_position
):
    source = Input()
    phased = ImaginaryMultiplication(source) if phase in (1j, -1j) else source
    if phase in (-1, -1j):
        phased = Negation(phased)
    operands = [
        Negation(phased) if index == negative_position else phased for index in range(3)
    ]
    total = Addition(Addition(*operands[:2]), operands[2], out0_scale=3)
    graph = SFG([source], [Output(total)])
    root = graph.output_operations[0].input(0).connected_source
    term = _SumTerm(graph.input_operations[0].output(0), phase, 3)

    assert graph._find_sums(merge_identical=merge_identical) == {root: (term,)}


@pytest.mark.parametrize("phase", [1, -1, 1j, -1j])
def test_find_sums_cancels_opposite_terms_by_default(phase):
    source = Input()
    phased = ImaginaryMultiplication(source) if phase in (1j, -1j) else source
    if phase in (-1, -1j):
        phased = Negation(phased)
    graph = SFG([source], [Output(Subtraction(phased, phased))])
    root = graph.output_operations[0].input(0).connected_source

    assert graph._find_sums() == {root: ()}
    assert graph._find_sums(merge_identical=False) == {root: ()}
    assert graph._find_sums(merge_identical=True) == {root: ()}


@pytest.mark.parametrize("shift", [0, 1, 3])
@pytest.mark.parametrize("phase", [1, -1, 1j, -1j])
def test_find_sums_merges_identical_terms_only_when_requested(shift, phase):
    source = Input()
    phased = ImaginaryMultiplication(source) if phase in (1j, -1j) else source
    if phase in (-1, -1j):
        phased = Negation(phased)
    total = Addition(phased, phased, in0_scale=shift, in1_scale=shift)
    graph = SFG([source], [Output(total)])
    root = graph.output_operations[0].input(0).connected_source
    term = _SumTerm(graph.input_operations[0].output(0), phase, shift)

    assert graph._find_sums() == {root: (term, term)}
    assert graph._find_sums(merge_identical=False) == {root: (term, term)}
    assert graph._find_sums(merge_identical=True) == {
        root: (_SumTerm(term.source, phase, shift - 1),)
    }
    assert _find_sums(graph, merge_identical=True) == graph._find_sums(
        merge_identical=True
    )


@pytest.mark.parametrize(
    ("count", "expected_shifts"),
    [(3, (3, 2)), (4, (1,)), (7, (3, 2, 1)), (8, (0,)), (16, (-1,))],
)
def test_find_sums_merges_larger_groups_repeatedly(count, expected_shifts):
    source = Input()
    phased = ImaginaryMultiplication(source)
    total = phased
    for _ in range(count - 1):
        total = Addition(total, phased)
    total.out0_scale = 3
    graph = SFG([source], [Output(total)])
    root = graph.output_operations[0].input(0).connected_source
    port = graph.input_operations[0].output(0)
    original_counts = graph.operation_counter()

    terms = graph._find_sums(merge_identical=True)[root]

    assert Counter(terms) == Counter(
        _SumTerm(port, 1j, shift) for shift in expected_shifts
    )
    assert len(graph._find_sums()[root]) == count
    assert graph.operation_counter() == original_counts
    assert sum(
        term.sign * (2 + 3j) * 2 ** (-term.shift) for term in terms
    ) == graph.evaluate(2 + 3j)


@pytest.mark.parametrize("phase", [1, 1j])
@pytest.mark.parametrize(
    ("specifications", "expected_shifts"),
    [
        (((1, 1), (1, 1), (-1, 0)), ()),
        (((1, 3), (1, 3), (1, 2)), (1,)),
        (((1, 0), (1, 0), (-1, 1), (-1, 1)), (0,)),
        (((1, 2), (1, 2), (-1, 1), (1, 0)), (0,)),
    ],
)
def test_find_sums_cancels_and_merges_carried_terms(
    phase, specifications, expected_shifts
):
    source = Input()
    phased = source if phase == 1 else ImaginaryMultiplication(source)
    operands = [phased if sign == 1 else Negation(phased) for sign, _ in specifications]
    total = Addition(
        *operands[:2],
        in0_scale=specifications[0][1],
        in1_scale=specifications[1][1],
    )
    for operand, (_, shift) in zip(operands[2:], specifications[2:], strict=True):
        total = Addition(total, operand, in1_scale=shift)
    graph = SFG([source], [Output(total)])
    root = graph.output_operations[0].input(0).connected_source
    port = graph.input_operations[0].output(0)

    assert len(graph._find_sums()[root]) == len(specifications)
    assert graph._find_sums(merge_identical=True) == {
        root: tuple(_SumTerm(port, phase, shift) for shift in expected_shifts)
    }


@pytest.mark.parametrize("merge_identical", [False, True])
def test_find_sums_keeps_terms_with_different_sources_shifts_or_phases(merge_identical):
    a, b = Input(), Input()
    butterfly = R2Butterfly(a, b)
    first = Subtraction(
        butterfly.output(0), ImaginaryMultiplication(butterfly.output(0))
    )
    second = Subtraction(butterfly.output(1), butterfly.output(0), in1_scale=1)
    graph = SFG([a, b], [Output(Addition(first, second))])
    butterfly = graph.find_by_type(R2Butterfly)[0]
    root = graph.output_operations[0].input(0).connected_source

    assert graph._find_sums(merge_identical=merge_identical) == {
        root: (
            _SumTerm(butterfly.output(0), 1, 0),
            _SumTerm(butterfly.output(0), -1j, 0),
            _SumTerm(butterfly.output(1), 1, 0),
            _SumTerm(butterfly.output(0), -1, 1),
        )
    }


def test_find_sums_cancellation_preserves_order_and_removes_partition_connections():
    a, b, c = Input(), Input(), Input()
    total = Addition(Subtraction(a, b), Addition(b, c))
    graph = SFG([a, b, c], [Output(total), Output(Negation(b))])
    first, second = [
        operation.input(0).connected_source for operation in graph.output_operations
    ]
    sources = [operation.output(0) for operation in graph.input_operations]

    sums = graph._find_sums()

    assert sums == {
        first: (_SumTerm(sources[0], 1, 0), _SumTerm(sources[2], 1, 0)),
        second: (_SumTerm(sources[1], -1, 0),),
    }
    assert {frozenset(partition) for partition in _partition_sums(sums)} == {
        frozenset([first]),
        frozenset([second]),
    }


def test_find_sums_merged_left_shift_is_normalized_by_pair_statistics():
    a, b = Input(), Input()
    graph = SFG([a, b], [Output(Addition(Addition(a, a), b))])
    sources = [operation.output(0) for operation in graph.input_operations]
    sums = graph._find_sums(merge_identical=True)

    assert _sum_pair_statistics(_partition_sums(sums)[0]) == Counter(
        {(_SumTerm(sources[0], 1, 0), _SumTerm(sources[1], 1, 1)): 1}
    )


@pytest.mark.parametrize("merge_identical", [False, True])
def test_find_sums_merging_option_applies_to_nested_graphs(merge_identical):
    inner_input = Input()
    inner = SFG(
        [inner_input],
        [Output(Addition(inner_input, inner_input, in0_scale=2, in1_scale=2))],
    )
    source = Input()
    graph = SFG(
        [source], [Output(inner(Addition(source, source, in0_scale=3, in1_scale=3)))]
    )
    inner = graph.find_by_type(SFG)[0]
    outer_root = inner.input(0).connected_source
    inner_root = inner.output_operations[0].input(0).connected_source
    outer_term = _SumTerm(graph.input_operations[0].output(0), 1, 3 - merge_identical)
    inner_term = _SumTerm(inner.input_operations[0].output(0), 1, 2 - merge_identical)
    count = 1 if merge_identical else 2

    assert graph._find_sums(merge_identical=merge_identical) == {
        outer_root: (outer_term,) * count,
        inner_root: (inner_term,) * count,
    }


@pytest.mark.parametrize("merge_identical", [False, True])
def test_simplify_sum_terms_preserves_values_and_eliminates_opposite_pairs(
    merge_identical,
):
    source = Input().output(0)
    for phase in (1, 1j):
        for coefficients in itertools.product(range(-3, 4), repeat=3):
            terms = []
            for shift, coefficient in enumerate(coefficients):
                sign = phase if coefficient >= 0 else -phase
                terms.extend([_SumTerm(source, sign, shift)] * abs(coefficient))
                terms.extend(
                    [_SumTerm(source, phase, shift), _SumTerm(source, -phase, shift)]
                )

            result = _simplify_sum_terms(terms, merge_identical=merge_identical)

            assert sum(term.sign * 2 ** (-term.shift) for term in result) == sum(
                term.sign * 2 ** (-term.shift) for term in terms
            )
            counts = Counter(result)
            assert all(term._replace(sign=-term.sign) not in counts for term in counts)
            if merge_identical:
                assert all(count == 1 for count in counts.values())
            assert counts == Counter(
                _simplify_sum_terms(reversed(terms), merge_identical=merge_identical)
            )


def test_find_sums_preserves_repeated_paths_and_deduplicates_fanout_roots():
    a, b = Input(), Input()
    shared = Subtraction(a, b, in0_scale=1, in1_scale=2, out0_scale=3, name="shared")
    total = AddSub(
        is_add=False,
        in0=shared,
        in1=shared,
        in0_scale=4,
        in1_scale=5,
        out0_scale=6,
        name="total",
    )
    graph = SFG(
        [a, b],
        [
            Output(shared),
            Output(total),
            Output(total),
            Output(Multiplication(total, shared)),
        ],
    )
    product = graph.find_by_type(Multiplication)[0]
    sources = [operation.output(0) for operation in graph.input_operations]
    partial_terms = ((sources[0], 1, 4), (sources[1], -1, 5))
    total_terms = (
        (sources[0], 1, 14),
        (sources[1], -1, 15),
        (sources[0], -1, 15),
        (sources[1], 1, 16),
    )

    sums = graph._find_sums()

    assert sums == {
        product.input(0).connected_source: total_terms,
        product.input(1).connected_source: partial_terms,
    }
    assert sum(_sum_pair_statistics(_partition_sums(sums)[0]).values()) == 7


@pytest.mark.parametrize("fanout", [1, 2, 5])
def test_find_sums_counts_pairs_once_per_shared_output(fanout):
    a, b = Input(), Input()
    total = Addition(a, b)
    graph = SFG([a, b], [Output(total) for _ in range(fanout)])
    root = graph.find_by_type(Addition)[0].output(0)
    sources = [operation.output(0) for operation in graph.input_operations]

    sums = graph._find_sums()

    assert sums == {root: tuple(_SumTerm(source, 1, 0) for source in sources)}
    assert _sum_pair_statistics(_partition_sums(sums)[0]) == Counter(
        {(_SumTerm(sources[0], 1, 0), _SumTerm(sources[1], 1, 0)): 1}
    )


@pytest.mark.parametrize("boundary_type", [Delay, Shift, ConstantMultiplication])
def test_find_sums_stops_at_other_operations(boundary_type):
    a, b = Input(), Input()
    boundary = boundary_type(in0=Addition(a, b), name="boundary")
    graph = SFG([a, b], [Output(Negation(boundary))])
    boundary = graph.find_by_name("boundary")[0]
    sources = [operation.output(0) for operation in graph.input_operations]

    assert graph._find_sums() == {
        boundary.input(0).connected_source: ((sources[0], 1, 0), (sources[1], 1, 0)),
        graph.output_operations[0].input(0).connected_source: (
            (boundary.output(0), -1, 0),
        ),
    }


def test_find_sums_distinguishes_source_output_ports():
    a, b = Input(), Input()
    butterfly = R2Butterfly(a, b)
    graph = SFG([a, b], [Output(Subtraction(butterfly.output(1), butterfly.output(0)))])
    butterfly = graph.find_by_type(R2Butterfly)[0]

    assert graph._find_sums() == {
        graph.output_operations[0].input(0).connected_source: (
            (butterfly.output(1), 1, 0),
            (butterfly.output(0), -1, 0),
        )
    }


def test_find_sums_in_feedback_stops_at_delay():
    source = Input()
    delay = Delay(initial_value=2)
    total = Addition(source, Negation(delay), in0_scale=1, out0_scale=2)
    delay.input(0).connect(total)
    graph = SFG([source], [Output(total)])
    delay = graph.find_by_type(Delay)[0]
    terms = ((graph.input_operations[0].output(0), 1, 3), (delay.output(0), -1, 2))

    assert graph._find_sums() == {
        graph.output_operations[0].input(0).connected_source: terms,
    }


def test_find_sums_in_nested_graphs_keeps_interfaces_as_boundaries():
    inner_input = Input()
    inner = SFG([inner_input], [Output(Negation(inner_input))])
    a, b = Input(), Input()
    graph = SFG([a, b], [Output(Negation(inner(Addition(a, b))))])
    inner = graph.find_by_type(SFG)[0]

    assert graph._find_sums() == {
        inner.input(0).connected_source: tuple(
            (operation.output(0), 1, 0) for operation in graph.input_operations
        ),
        inner.output_operations[0].input(0).connected_source: (
            (inner.input_operations[0].output(0), -1, 0),
        ),
        graph.output_operations[0].input(0).connected_source: (
            (inner.output(0), -1, 0),
        ),
    }


def test_find_sums_treats_specialized_arithmetic_as_a_boundary():
    class SpecializedAddition(Addition):
        __slots__ = ()

        def evaluate(self, a, b, data_type=None):
            return 3 * (a + b)

    a, b = Input(), Input()
    special = SpecializedAddition(Addition(a, b), b, name="special")
    graph = SFG([a, b], [Output(Negation(special))])
    special = graph.find_by_name("special")[0]
    sources = [operation.output(0) for operation in graph.input_operations]

    assert graph._find_sums() == {
        special.input(0).connected_source: ((sources[0], 1, 0), (sources[1], 1, 0)),
        graph.output_operations[0].input(0).connected_source: (
            (special.output(0), -1, 0),
        ),
    }


@pytest.mark.parametrize("self_loop", [False, True])
def test_find_sums_rejects_arithmetic_cycles(self_loop):
    source = Input()
    total = Addition(source)
    total.input(1).connect(total if self_loop else Negation(total))
    graph = SFG([source], [Output(total)])

    with pytest.raises(RuntimeError, match=r"Direct feedback loop.*finding sums"):
        graph._find_sums()


def test_find_sums_rejects_unconnected_arithmetic_input():
    source = Input()
    graph = SFG([source], [Output(Addition(source, source))])
    graph.find_by_type(Addition)[0].input(1).clear()

    with pytest.raises(ValueError, match="Unconnected input port in sum"):
        graph._find_sums()


def test_find_sums_handles_long_chains_without_recursion():
    source = Input()
    total = source
    count = sys.getrecursionlimit() + 10
    for _ in range(count):
        total = Negation(total)
    graph = SFG([source], [Output(total)])

    assert graph._find_sums() == {
        graph.output_operations[0].input(0).connected_source: (
            (graph.input_operations[0].output(0), (-1) ** count, 0),
        )
    }


def test_partition_sums_without_sum_operations():
    source = Input()
    graph = SFG([source], [Output(source)])

    assert _partition_sums(graph._find_sums()) == []


@pytest.mark.parametrize(
    ("order", "expected"),
    [
        ((0, 1, 2, 3, 4, 5, 6), ((0, 2, 3), (1, 4), (5,))),
        ((0, 1, 2, 4, 5, 6, 3), ((0, 2, 3), (1, 4), (5,))),
        ((5, 4, 3, 2, 1, 0, 6), ((5,), (4, 1), (3, 2, 0))),
    ],
)
def test_partition_sums_groups_complete_sums_by_shared_sources(order, expected):
    a, b, c, d, e, f, g = inputs = [Input() for _ in range(7)]
    partial = Subtraction(a, b, in0_scale=1, in1_scale=2, out0_scale=3)
    first = Addition(partial, partial)
    independent = Addition(e, f)
    third = Subtraction(c, d)
    bridge = AddSub(
        is_add=False,
        in0=Negation(b),
        in1=c,
        in0_scale=4,
        in1_scale=5,
        out0_scale=6,
        mul_j=True,
    )
    graph = SFG(
        inputs,
        [
            Output(item)
            for item in [
                first,
                independent,
                third,
                bridge,
                Negation(e),
                Negation(g),
                first,
            ]
        ],
    )
    roots = [
        operation.input(0).connected_source for operation in graph.output_operations
    ]
    found = graph._find_sums()
    sums = {roots[index]: found[roots[index]] for index in order}
    original_items = list(sums.items())

    partitions = _partition_sums(sums)

    assert [list(partition) for partition in partitions] == [
        [roots[index] for index in members] for members in expected
    ]
    assert len(found[roots[0]]) == 4
    assert all(
        type(term.source.operation)
        not in (Addition, Subtraction, AddSub, Negation, ImaginaryMultiplication)
        for partition in partitions
        for root, terms in partition.items()
        for term in terms
    )
    assert all(
        terms is sums[root]
        for partition in partitions
        for root, terms in partition.items()
    )
    assert list(sums.items()) == original_items


def test_partition_sums_distinguishes_output_ports_of_same_operation():
    a, b = Input(), Input()
    butterfly = R2Butterfly(a, b)
    graph = SFG(
        [a, b],
        [
            Output(Addition(butterfly.output(0), butterfly.output(0))),
            Output(Negation(butterfly.output(1))),
            Output(Subtraction(Negation(butterfly.output(0)), butterfly.output(0))),
        ],
    )
    roots = [
        operation.input(0).connected_source for operation in graph.output_operations
    ]
    found = graph._find_sums()
    sums = {root: found[root] for root in roots}

    assert _partition_sums(sums) == [
        {roots[0]: sums[roots[0]], roots[2]: sums[roots[2]]},
        {roots[1]: sums[roots[1]]},
    ]


def test_partition_sums_keeps_sources_with_same_graph_id_in_nested_graphs_separate():
    inner_input = Input()
    inner = SFG([inner_input], [Output(Negation(inner_input))])
    source = Input()
    graph = SFG([source], [Output(inner(source)), Output(Negation(source))])
    inner = graph.find_by_type(SFG)[0]
    inner_root = inner.output_operations[0].input(0).connected_source
    outer_root = graph.output_operations[1].input(0).connected_source
    sums = graph._find_sums()

    assert inner.input_operations[0].graph_id == graph.input_operations[0].graph_id
    assert _partition_sums(sums) == [{root: terms} for root, terms in sums.items()]
    assert set(sums) == {inner_root, outer_root}


@pytest.mark.parametrize("repeated_source", [False, True])
def test_partition_sums_with_one_sum(repeated_source):
    source = Input()
    total = Subtraction(source, source) if repeated_source else Negation(source)
    graph = SFG([source], [Output(total)])
    sums = graph._find_sums()

    partitions = _partition_sums(sums)

    assert partitions == [sums]
    assert partitions[0] is not sums


@pytest.mark.parametrize("first_sign", [1, -1, 1j, -1j])
@pytest.mark.parametrize("second_sign", [1, -1, 1j, -1j])
@pytest.mark.parametrize("shifts", [(0, 0), (2, 5), (6, 3)])
@pytest.mark.parametrize("same_source", [False, True])
def test_sum_pair_statistics_normalization(
    first_sign, second_sign, shifts, same_source
):
    a, b = Input(), Input()
    graph = SFG([a, b], [Output(Addition(a, b))])
    first_source, second_source = (
        operation.output(0) for operation in graph.input_operations
    )
    if same_source:
        second_source = first_source
    first = _SumTerm(first_source, first_sign, shifts[0])
    second = _SumTerm(second_source, second_sign, shifts[1])
    root = graph.output_operations[0].input(0).connected_source

    statistics = _sum_pair_statistics({root: (first, second)})

    assert len(statistics) == 1
    pair = next(iter(statistics))
    assert statistics[pair] == 1
    assert isinstance(pair[0], _SumTerm)
    assert isinstance(pair[1], _SumTerm)
    assert pair[0].sign == 1
    assert pair[0].shift == 0
    assert pair[1].sign in (1, -1, 1j, -1j)
    assert pair[1].shift == abs(shifts[1] - shifts[0])
    if shifts[0] == shifts[1]:
        assert pair[0].source is first_source
    assert statistics == _sum_pair_statistics({root: (second, first)})
    for phase in (1, -1, 1j, -1j):
        scaled = tuple(
            _SumTerm(term.source, phase * term.sign, term.shift + 7)
            for term in (first, second)
        )
        assert statistics == _sum_pair_statistics({root: scaled})

    values = {first_source: 2 + 3j}
    if second_source is not first_source:
        values[second_source] = -5 + 7j

    def evaluate(terms):
        return sum(
            term.sign * values[term.source] * 2 ** (-term.shift) for term in terms
        )

    original_value = evaluate((first, second))
    normalized_value = evaluate(pair)
    assert any(
        original_value == pytest.approx(phase * 2 ** (-min(shifts)) * normalized_value)
        for phase in (1, -1, 1j, -1j)
    )


def test_sum_pair_statistics_counts_pairs_within_each_item():
    a, b, c = [Input().output(0) for _ in range(3)]
    for index, source in enumerate((a, b, c)):
        source.operation.graph_id = f"in{index}"
    roots = [Addition().output(0) for _ in range(4)]
    partition = {
        roots[0]: (_SumTerm(a, 1, 2), _SumTerm(b, -1, 4), _SumTerm(c, 1, 2)),
        roots[1]: (_SumTerm(b, 1, 7), _SumTerm(a, -1, 5)),
        roots[2]: (_SumTerm(c, 1, 0), _SumTerm(a, 1, 0)),
        roots[3]: (_SumTerm(b, 1, 0),),
    }
    original_items = list(partition.items())

    statistics = _sum_pair_statistics(partition)

    assert statistics == Counter(
        {
            (_SumTerm(a, 1, 0), _SumTerm(b, -1, 2)): 2,
            (_SumTerm(a, 1, 0), _SumTerm(c, 1, 0)): 2,
            (_SumTerm(c, 1, 0), _SumTerm(b, -1, 2)): 1,
        }
    )
    assert list(partition.items()) == original_items


def test_sum_pair_statistics_counts_repeated_term_occurrences():
    a, b = [Input().output(0) for _ in range(2)]
    a.operation.graph_id = "in0"
    b.operation.graph_id = "in1"
    first = _SumTerm(a, 1, 0)
    second = _SumTerm(b, 1, 0)
    partition = {Addition().output(0): (first, first, second)}

    assert _sum_pair_statistics(partition) == Counter(
        {(first, first): 1, (first, second): 2}
    )


def test_sum_pair_statistics_does_not_pair_terms_from_different_items():
    term = _SumTerm(Input().output(0), 1, 0)
    partition = {Addition().output(0): (term,), Addition().output(0): (term,)}

    assert _sum_pair_statistics({}) == Counter()
    assert _sum_pair_statistics(partition) == Counter()


def test_sum_pair_statistics_orders_distinct_output_ports_with_same_graph_id():
    first_butterfly, second_butterfly = R2Butterfly(), R2Butterfly()
    first_butterfly.graph_id = second_butterfly.graph_id = "bfly0"
    terms = (
        _SumTerm(first_butterfly.output(1), 1, 0),
        _SumTerm(first_butterfly.output(0), 1j, 0),
        _SumTerm(second_butterfly.output(0), -1, 0),
    )
    root = Addition().output(0)

    statistics = _sum_pair_statistics({root: terms})

    assert statistics == _sum_pair_statistics({root: tuple(reversed(terms))})
    assert len(statistics) == 3
    assert (
        _SumTerm(first_butterfly.output(0), 1, 0),
        _SumTerm(first_butterfly.output(1), -1j, 0),
    ) in statistics
    assert all(
        first.source.index <= second.source.index for first, second in statistics
    )


def test_sum_pair_statistics_with_imaginary_multiplication_and_scaled_sums():
    a, b = Input(), Input()
    first = ImaginaryMultiplication(
        Subtraction(a, b, in0_scale=2, in1_scale=4, out0_scale=1)
    )
    second = Negation(
        Subtraction(
            ImaginaryMultiplication(b),
            a,
            in0_scale=6,
            in1_scale=4,
            out0_scale=2,
            mul_j=True,
        )
    )
    third = Subtraction(a, b, in1_scale=2)
    graph = SFG([a, b], [Output(item) for item in (first, second, third)])

    sums = graph._find_sums()
    partitions = _partition_sums(sums)
    statistics = _sum_pair_statistics(partitions[0])

    sources = [operation.output(0) for operation in graph.input_operations]
    assert len(partitions) == 1
    assert len(sums) == 3
    assert all(term.source in sources for terms in sums.values() for term in terms)
    assert statistics == Counter(
        {(_SumTerm(sources[0], 1, 0), _SumTerm(sources[1], -1, 2)): 3}
    )
    for samples in [(7, -3), (1 + 2j, -5 + 7j)]:
        values = dict(zip(sources, samples, strict=True))
        assert [
            sum(
                term.sign * values[term.source] * 2 ** (-term.shift)
                for term in sums[output.input(0).connected_source]
            )
            for output in graph.output_operations
        ] == pytest.approx(graph.evaluate(*samples))
