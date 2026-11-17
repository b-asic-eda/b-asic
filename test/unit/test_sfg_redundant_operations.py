"""Tests for structural detection of redundant computations."""

import pytest

from b_asic import SFG, Input, Output
from b_asic.core_operations import (
    MAD,
    Addition,
    AddSub,
    Constant,
    ConstantMultiplication,
    Multiplication,
    Subtraction,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.special_operations import Delay


def named_groups(graph, delayed=False):
    return {
        frozenset(operation.name for operation in group)
        for group in graph.find_redundant_operations(delayed=delayed)
    }


@pytest.mark.parametrize("operation_type", [Addition, Multiplication])
def test_identical_and_swapped_operations(operation_type):
    left, right = Input(), Input()
    operations = [
        operation_type(left, right, name="first", latency=1),
        operation_type(left, right, name="second", latency=2),
        operation_type(right, left, name="swapped"),
        operation_type(left, left, name="different"),
    ]
    graph = SFG([left, right], [Output(op) for op in operations])
    before = [
        (op, dict(op.params), tuple(port.connected_source for port in op.inputs))
        for op in graph.operations
    ]

    assert named_groups(graph) == {frozenset(["first", "second", "swapped"])}
    for operation, parameters, sources in before:
        assert operation.params == parameters
        assert tuple(port.connected_source for port in operation.inputs) == sources
    assert all(
        operation in graph.operations
        for group in graph.find_redundant_operations()
        for operation in group
    )
    assert named_groups(graph) == {frozenset(["first", "second", "swapped"])}


@pytest.mark.parametrize("is_add", [False, True])
def test_addsub_normalization_and_parameters(is_add):
    left, right = Input(), Input()
    kind = Addition if is_add else Subtraction
    operations = [
        kind(left, right, name="ordinary", in0_scale=1),
        AddSub(is_add=is_add, in0=left, in1=right, name="configurable", in0_scale=1),
        kind(right, left, name="reversed", in0_scale=1),
        kind(left, right, name="unscaled"),
        kind(left, right, name="complex", in0_scale=1, mul_j=True),
        kind(left, right, name="output_scaled", in0_scale=1, out0_scale=1),
    ]
    graph = SFG([left, right], [Output(op) for op in operations])

    assert named_groups(graph) == {frozenset(["ordinary", "configurable"])}


def test_duplicates_propagate_through_chains():
    source = Input()
    constants = [Constant(2, name=f"constant{i}") for i in range(3)]
    products = [
        Multiplication(source, value, name=f"product{i}")
        for i, value in enumerate(constants)
    ]
    delays = [Delay(op, name=f"delay{i}") for i, op in enumerate(products)]
    different = Delay(products[0], initial_value=1, name="different")
    graph = SFG([source], [Output(op) for op in [*delays, different]])

    assert named_groups(graph) == {
        frozenset(f"{prefix}{i}" for i in range(3))
        for prefix in ("constant", "product", "delay")
    }


def test_parameters_may_be_unhashable():
    source = Input()
    operations = [
        ConstantMultiplication(value, source, name=name)
        for value, name in [(2, "first"), (2, "second"), (3, "different")]
    ]
    for operation in operations:
        operation.set_param("custom", [1, 2])
    graph = SFG([source], [Output(op) for op in operations])

    assert named_groups(graph) == {frozenset(["first", "second"])}


def test_source_output_indices_are_distinct():
    left, right = Input(), Input()
    butterfly = R2Butterfly(left, right)
    first = ConstantMultiplication(2, butterfly.output(0))
    second = ConstantMultiplication(2, butterfly.output(1))
    graph = SFG([left, right], [Output(first), Output(second)])

    assert graph.find_redundant_operations() == []


def test_partial_input_swap():
    a, b, c = Input(), Input(), Input()
    operations = [
        MAD(a, b, c, name="first"),
        MAD(b, a, c, name="swapped"),
        MAD(c, b, a, name="different"),
    ]
    graph = SFG([a, b, c], [Output(op) for op in operations])

    assert named_groups(graph) == {frozenset(["first", "swapped"])}


def test_subtraction_and_independent_inputs_are_distinct():
    left, right = Input(), Input()
    operations = [
        Subtraction(left, right),
        Subtraction(right, left),
        ConstantMultiplication(2, left),
        ConstantMultiplication(2, right),
    ]
    graph = SFG([left, right], [Output(op) for op in operations])

    assert graph.find_redundant_operations() == []


def test_multioutput_duplicates_propagate_by_output_index():
    left, right = Input(), Input()
    butterflies = [R2Butterfly(left, right, name=f"butterfly{i}") for i in range(2)]
    operations = [
        ConstantMultiplication(2, butterfly.output(index), name=f"port{index}_{i}")
        for i, butterfly in enumerate(butterflies)
        for index in range(2)
    ]
    graph = SFG([left, right], [Output(op) for op in operations])

    assert named_groups(graph) == {
        frozenset(["butterfly0", "butterfly1"]),
        frozenset(["port0_0", "port0_1"]),
        frozenset(["port1_0", "port1_1"]),
    }


def test_swapped_addsub_matches_addition():
    left, right = Input(), Input()
    first = Addition(left, right, name="first")
    second = AddSub(in0=right, in1=left, name="second")
    graph = SFG([left, right], [Output(first), Output(second)])

    assert named_groups(graph) == {frozenset(["first", "second"])}


def test_feedback_terminates_and_preserves_distinct_states():
    source = Input()
    first, second = Delay(initial_value=0), Delay(initial_value=1)
    first.input(0).connect(Addition(source, first))
    second.input(0).connect(Addition(source, second))
    graph = SFG([source], [Output(first), Output(second)])

    assert graph.find_redundant_operations() == []


def test_inputs_outputs_and_nested_graphs_are_distinct():
    source = Input()
    nested = SFG([source], [Output(source)])
    left, right = Input(), Input()
    first = nested(left)
    second = nested(right)
    graph = SFG([left, right], [Output(first), Output(second)])

    assert graph.find_redundant_operations() == []


def test_empty_graph():
    assert SFG().find_redundant_operations() == []


@pytest.mark.parametrize("keep_configurable", [False, True])
def test_merge_preserves_first_operation_and_original_graph(keep_configurable):
    left, right = Input(), Input()
    first = Addition(left, right, name="ordinary", latency=1)
    second = AddSub(in0=right, in1=left, name="configurable", latency=3)
    third = Addition(left, right, name="third")
    graph = SFG([left, right], [Output(Subtraction(first, second) + third)])
    selected = graph.find_redundant_operations()[0]
    selected.sort(
        key=lambda op: op.name != ("configurable" if keep_configurable else "ordinary")
    )
    retained_id = selected[0].graph_id
    removed_ids = [operation.graph_id for operation in selected[1:]]
    before = [
        (operation, tuple(port.connected_source for port in operation.inputs))
        for operation in graph.operations
    ]

    merged = graph.merge_redundant_operations(iter(selected))

    retained = merged.find_by_id(retained_id)
    assert type(retained) is type(selected[0])
    assert retained.name == selected[0].name
    assert retained.params == selected[0].params
    assert retained.latency == selected[0].latency
    assert retained.output(0).signal_count == 3
    assert all(merged.find_by_id(graph_id) is None for graph_id in removed_ids)
    assert len(merged.operations) == len(graph.operations) - 2
    assert merged.evaluate(7, 2) == graph.evaluate(7, 2) == 9
    assert merged.find_redundant_operations() == []
    for operation, sources in before:
        assert tuple(port.connected_source for port in operation.inputs) == sources
    assert all(
        graph.find_by_id(operation.graph_id) is operation for operation in selected
    )


@pytest.mark.parametrize("automatic", [False, True])
@pytest.mark.filterwarnings(
    "ignore:^Two signals connected to the same output port$:UserWarning"
)
def test_merge_multioutput_operations(automatic):
    left, right = Input(), Input()
    first, second = R2Butterfly(left, right), R2Butterfly(left, right)
    outputs = [Output(op.output(index)) for op in (first, second) for index in range(2)]
    graph = SFG([left, right], outputs)
    group = graph.find_redundant_operations()[0]

    merged = graph.merge_redundant_operations(None if automatic else group)

    retained = merged.find_by_id(group[0].graph_id)
    assert len(merged.find_by_type(R2Butterfly)) == 1
    for index, output in enumerate(merged.output_operations):
        assert output.input(0).connected_source is retained.output(index % 2)
    assert merged.evaluate(7, 2) == graph.evaluate(7, 2) == [9, 5, 9, 5]


@pytest.mark.filterwarnings(
    "ignore:^Two signals connected to the same output port$:UserWarning"
)
def test_merge_subset_and_duplicate_chains():
    source = Input()
    products = [ConstantMultiplication(2, source, name=f"product{i}") for i in range(3)]
    totals = [
        Addition(product, source, name=f"total{i}")
        for i, product in enumerate(products)
    ]
    graph = SFG([source], [Output(op) for op in totals])
    group = [graph.find_by_name(f"total{i}")[0] for i in range(2)]

    merged = graph.merge_redundant_operations(group)

    retained = merged.find_by_id(group[0].graph_id)
    assert merged.find_by_id(group[1].graph_id) is None
    assert merged.find_by_name("total2")
    assert merged.output_operations[0].input(0).connected_source is retained.output(0)
    assert merged.output_operations[1].input(0).connected_source is retained.output(0)
    assert merged.evaluate(3) == graph.evaluate(3) == [9, 9, 9]


@pytest.mark.parametrize("automatic", [False, True])
def test_merge_delays_in_feedback_preserves_sequence(automatic):
    from b_asic.simulation import Simulation

    source = Input()
    first = Delay(initial_value=2)
    second = Delay(initial_value=2)
    total = Addition(source, Addition(first, second))
    first.input(0).connect(total)
    second.input(0).connect(total)
    graph = SFG([source], [Output(total)])
    group = graph.find_redundant_operations()[0]

    merged = graph.merge_redundant_operations(None if automatic else group)

    assert len(merged.find_by_type(Delay)) == 1
    original_simulation = Simulation(graph, [lambda iteration: iteration])
    merged_simulation = Simulation(merged, [lambda iteration: iteration])
    original_simulation.run_for(6, save_results=True)
    merged_simulation.run_for(6, save_results=True)
    assert list(merged_simulation.results["out0"]) == list(
        original_simulation.results["out0"]
    )


@pytest.mark.parametrize(
    "invalid",
    ["empty", "single", "duplicate", "foreign", "nonredundant", "input", "wrong_type"],
)
def test_merge_rejects_invalid_operations_without_mutation(invalid):
    source = Input()
    graph = SFG(
        [source],
        [
            Output(ConstantMultiplication(2, source)),
            Output(ConstantMultiplication(3, source)),
        ],
    )
    first, second = graph.find_by_type(ConstantMultiplication)
    selections = {
        "empty": [],
        "single": [first],
        "duplicate": [first, first],
        "foreign": [first, first.copy()],
        "nonredundant": [first, second],
        "input": [first, graph.input_operations[0]],
        "wrong_type": [first, first.graph_id],
    }
    before = graph.operations

    with pytest.raises(TypeError if invalid == "wrong_type" else ValueError):
        graph.merge_redundant_operations(iter(selections[invalid]))

    assert graph.operations == before
    assert graph.evaluate(4) == [8, 12]


def test_merge_rechecks_redundancy_after_parameters_change():
    source = Input()
    graph = SFG(
        [source],
        [
            Output(ConstantMultiplication(2, source)),
            Output(ConstantMultiplication(2, source)),
        ],
    )
    group = graph.find_redundant_operations()[0]
    group[1].value = 3

    with pytest.raises(ValueError, match="not redundant"):
        graph.merge_redundant_operations(group)

    assert graph.evaluate(4) == [8, 12]


@pytest.mark.parametrize("explicit_none", [False, True])
def test_merge_all_redundant_groups_and_chains(explicit_none):
    source, unused = Input("source"), Input("unused")
    constants = [Constant(2, name=f"constant{index}") for index in range(3)]
    products = [
        Multiplication(source, constant, name=f"product{index}", latency=index + 1)
        for index, constant in enumerate(constants)
    ]
    totals = [
        Addition(product, source, name=f"total{index}")
        for index, product in enumerate(products)
    ]
    graph = SFG(
        [source, unused],
        [
            Output(Subtraction(totals[0], totals[1]) + totals[2], "sum"),
            Output(ConstantMultiplication(3, source), "unique"),
        ],
        name="merge all",
    )
    graph.execution_time = 7
    groups = graph.find_redundant_operations()
    assert len(groups) == 3
    retained = [group[0] for group in groups]
    removed = [operation.graph_id for group in groups for operation in group[1:]]
    original_sources = {
        op: tuple(port.connected_source for port in op.inputs)
        for op in graph.operations
    }

    merged = (
        graph.merge_redundant_operations(None)
        if explicit_none
        else graph.merge_redundant_operations()
    )

    assert merged.find_redundant_operations() == []
    assert len(merged.operations) == len(graph.operations) - len(removed)
    assert all(merged.find_by_id(graph_id) is None for graph_id in removed)
    for operation in retained:
        copied = merged.find_by_id(operation.graph_id)
        assert type(copied) is type(operation)
        assert copied.name == operation.name
        assert copied.params == operation.params
        assert [port.latency_offset for port in (*copied.inputs, *copied.outputs)] == [
            port.latency_offset for port in (*operation.inputs, *operation.outputs)
        ]
        assert copied.execution_time == operation.execution_time
    assert merged.name == "merge all"
    assert merged.execution_time == 7
    assert [op.name for op in merged.input_operations] == ["source", "unused"]
    assert [op.name for op in merged.output_operations] == ["sum", "unique"]
    for value in [3, -7, 2 + 3j]:
        assert merged.evaluate(value, 99) == graph.evaluate(value, 99)
    assert len(graph.find_redundant_operations()) == 3
    for operation, sources in original_sources.items():
        assert tuple(port.connected_source for port in operation.inputs) == sources


@pytest.mark.parametrize("empty", [False, True])
def test_merge_all_without_redundancy_returns_a_copy(empty):
    source = Input()
    graph = (
        SFG() if empty else SFG([source], [Output(ConstantMultiplication(2, source))])
    )

    merged = graph.merge_redundant_operations(None)

    assert merged is not graph
    assert len(merged.operations) == len(graph.operations)
    assert merged.find_redundant_operations() == []
    if not empty:
        assert merged.evaluate(3) == graph.evaluate(3) == 6


def test_merge_all_does_not_merge_time_shifted_computations():
    source = Input()
    graph = SFG(
        [source],
        [
            Output(ConstantMultiplication(2, source)),
            Output(ConstantMultiplication(2, Delay(source))),
        ],
    )
    assert graph.find_redundant_operations(delayed=True)

    merged = graph.merge_redundant_operations(None)

    assert len(merged.find_by_type(ConstantMultiplication)) == 2
    assert len(merged.find_by_type(Delay)) == 1


def test_delayed_uniform_shift_and_merge_validation():
    left, right = Input(), Input()
    first = Addition(left, right, name="first")
    second = AddSub(in0=Delay(left), in1=Delay(right), name="second")
    unaligned = Addition(left, Delay(right), name="unaligned")
    graph = SFG([left, right], [Output(op) for op in (first, second, unaligned)])
    before = [
        (operation, tuple(port.connected_source for port in operation.inputs))
        for operation in graph.operations
    ]

    groups = graph.find_redundant_operations(delayed=True)
    arithmetic_groups = [
        group for group in groups if isinstance(group[0], (Addition, AddSub))
    ]
    assert len(arithmetic_groups) == 1
    assert {op.name for op in arithmetic_groups[0]} == {"first", "second"}
    assert not any(
        isinstance(group[0], (Addition, AddSub))
        for group in graph.find_redundant_operations()
    )
    with pytest.raises(ValueError, match="not redundant"):
        graph.merge_redundant_operations(arithmetic_groups[0])
    for operation, sources in before:
        assert tuple(port.connected_source for port in operation.inputs) == sources


@pytest.mark.parametrize("reverse_outputs", [False, True])
def test_delayed_offsets_propagate_and_preserve_relative_input_delays(reverse_outputs):
    left, right = Input(), Input()
    first = ConstantMultiplication(2, left, name="first")
    second = ConstantMultiplication(2, Delay(Delay(left)), name="second")
    early = Addition(first, right, name="early")
    late = Addition(Delay(second), Delay(Delay(Delay(right))), name="late")
    unaligned = Addition(second, right, name="unaligned")
    outputs = [Output(op) for op in (early, late, unaligned)]
    graph = SFG([left, right], outputs[::-1] if reverse_outputs else outputs)

    groups = named_groups(graph, delayed=True)

    assert frozenset(["first", "second"]) in groups
    assert frozenset(["early", "late"]) in groups
    assert not any("unaligned" in group for group in groups)


def test_delayed_relative_delays_with_swapped_inputs():
    left, right = Input(), Input()
    first = Addition(left, Delay(right), name="first")
    second = Addition(Delay(Delay(right)), Delay(left), name="second")
    different = Addition(Delay(left), right, name="different")
    graph = SFG([left, right], [Output(op) for op in (first, second, different)])

    groups = named_groups(graph, delayed=True)

    assert frozenset(["first", "second"]) in groups
    assert not any("different" in group for group in groups)


def test_delayed_initial_values_and_feedback_boundaries():
    left, right = Input(), Input()
    first = Addition(left, right, name="first")
    second = Addition(
        Delay(left, initial_value=3), Delay(right, initial_value=7), name="second"
    )
    state = Delay()
    state.input(0).connect(state)
    independent = Addition(state, right, name="independent")
    graph = SFG([left, right], [Output(op) for op in (first, second, independent)])

    groups = named_groups(graph, delayed=True)

    assert frozenset(["first", "second"]) in groups
    assert not any("independent" in group for group in groups)


def test_delayed_preserves_source_output_indices_and_parameters():
    left, right = Input(), Input()
    butterfly = R2Butterfly(left, right)
    first = ConstantMultiplication(2, butterfly.output(0))
    second = ConstantMultiplication(2, Delay(butterfly.output(1)))
    third = ConstantMultiplication(3, Delay(butterfly.output(0)))
    graph = SFG([left, right], [Output(op) for op in (first, second, third)])

    assert graph.find_redundant_operations(delayed=True) == []
