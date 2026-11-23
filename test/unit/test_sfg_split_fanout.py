"""Tests for moving unary operations across fanouts."""

import pytest

from b_asic import SFG, Input, Output
from b_asic.core_operations import (
    Addition,
    Constant,
    ConstantMultiplication,
    Negation,
    Subtraction,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.operation import Operation
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay


@pytest.mark.parametrize("repeat", [False, True])
def test_split_fanout_preserves_behavior_metadata_and_existing_ids(repeat):
    source, unused = Input("source"), Input("unused")
    shared = ConstantMultiplication(
        3, source, name="shared", latency=4, execution_time=2
    )
    shared.input(0).signals[0].name = "operand"
    shared.input(0).signals[0].set_param("custom", [1, 2])
    other = ConstantMultiplication(5, source, name="other")
    outputs = [
        Output(Addition(shared, shared), "sum"),
        Output(Subtraction(shared, other), "difference"),
    ]
    for index, signal in enumerate(shared.output(0).signals):
        signal.name = f"branch{index}"
    graph = SFG([source, unused], outputs, name="fanout graph")
    graph.execution_time = 7
    graph.input(0).latency_offset = 2
    original = graph.find_by_name("shared")[0]
    original_components = {item.graph_id: item for item in graph.components}

    transformed = graph.split_fanout(repeat=repeat)
    copies = transformed.find_by_name("shared")

    assert len(copies) == 3
    assert all(op.output(0).signal_count == 1 for op in copies)
    assert all(
        op.input(0).connected_source is transformed.input_operations[0].output(0)
        for op in copies
    )
    assert all(op.params == original.params for op in copies)
    assert all(op.latency == 4 and op.execution_time == 2 for op in copies)
    assert all(op.input(0).signals[0].name == "operand" for op in copies)
    assert all(op.input(0).signals[0].params == {"custom": [1, 2]} for op in copies)
    assert len(transformed.find_by_type(ConstantMultiplication)) == 4
    assert original.output(0).signal_count == 3
    assert len(graph.find_by_type(ConstantMultiplication)) == 2
    assert transformed.name == graph.name
    assert transformed.execution_time == 7
    assert transformed.input(0).latency_offset == 2
    assert [op.name for op in transformed.input_operations] == ["source", "unused"]
    assert [op.name for op in transformed.output_operations] == ["sum", "difference"]
    transformed_ids = {item.graph_id for item in transformed.components}
    assert set(original_components).issubset(transformed_ids)
    assert len(transformed_ids) == len(set(transformed.components))
    for graph_id, component in original_components.items():
        clone = transformed.find_by_id(graph_id)
        assert type(clone) is type(component)
        assert clone.name == component.name
    for value in [-7, 0, 4, 2 + 3j]:
        assert transformed.evaluate(value, 99) == graph.evaluate(value, 99)
    assert len(transformed.split_fanout().find_by_name("shared")) == 3

    copies[0].input(0).signals[0].param("custom").append(3)
    assert original.input(0).signals[0].param("custom") == [1, 2]
    assert copies[1].input(0).signals[0].param("custom") == [1, 2]


def two_fanouts():
    source = Input()
    first = ConstantMultiplication(2, source, name="first")
    second = Negation(source, name="second")
    return SFG(
        [source],
        [Output(Addition(first, first)), Output(Addition(second, second))],
    )


@pytest.mark.parametrize("repeat", [False, True])
@pytest.mark.parametrize(
    "selection",
    [
        "operation",
        "operation_type",
        "graph_id",
        "operation_list",
        "operation_type_list",
        "graph_id_list",
        "operation_iterator",
        "operation_type_iterator",
        "graph_id_iterator",
        "mixed",
        "mixed_with_type",
        "duplicate",
        "duplicate_type",
        "base_type",
        "all",
    ],
)
def test_split_fanout_selection(selection, repeat):
    graph = two_fanouts()
    first = graph.find_by_name("first")[0]
    second = graph.find_by_name("second")[0]
    targets = {
        "operation": first,
        "operation_type": ConstantMultiplication,
        "graph_id": first.graph_id,
        "operation_list": [first, second],
        "operation_type_list": [ConstantMultiplication, Negation],
        "graph_id_list": [first.graph_id, second.graph_id],
        "operation_iterator": iter([first, second]),
        "operation_type_iterator": iter([ConstantMultiplication, Negation]),
        "graph_id_iterator": iter([first.graph_id, second.graph_id]),
        "mixed": (first, second.graph_id),
        "mixed_with_type": (ConstantMultiplication, first, second.graph_id),
        "duplicate": [first, first.graph_id],
        "duplicate_type": [ConstantMultiplication, first, first.graph_id],
        "base_type": Operation,
        "all": None,
    }

    transformed = graph.split_fanout(targets[selection], repeat=repeat)

    assert len(transformed.find_by_name("first")) == 2
    assert len(transformed.find_by_name("second")) == (
        1
        if selection
        in {"operation", "operation_type", "graph_id", "duplicate", "duplicate_type"}
        else 2
    )
    assert first.output(0).signal_count == second.output(0).signal_count == 2
    assert transformed.evaluate(3) == graph.evaluate(3) == [12, -6]


def test_split_fanout_type_selects_all_instances_and_subclasses():
    class CustomMultiplication(ConstantMultiplication):
        pass

    source = Input()
    first = ConstantMultiplication(2, source, name="first")
    second = CustomMultiplication(3, source, name="second")
    other = Negation(source, name="other")
    graph = SFG(
        [source],
        [
            Output(Addition(first, first)),
            Output(Addition(second, second)),
            Output(Addition(other, other)),
        ],
    )

    transformed = graph.split_fanout(ConstantMultiplication)

    assert len(transformed.find_by_name("first")) == 2
    assert len(transformed.find_by_name("second")) == 2
    assert all(
        type(op) is CustomMultiplication for op in transformed.find_by_name("second")
    )
    assert len(transformed.find_by_name("other")) == 1
    assert len(graph.find_by_name("first")) == len(graph.find_by_name("second")) == 1
    assert transformed.evaluate(3) == graph.evaluate(3) == [12, 18, -6]


@pytest.mark.parametrize("operation_type", [Delay, Addition])
def test_split_fanout_type_without_eligible_instances(operation_type):
    graph = two_fanouts()

    transformed = graph.split_fanout(operation_type)

    assert transformed is not graph
    assert len(transformed.operations) == len(graph.operations)
    assert transformed.evaluate(3) == graph.evaluate(3) == [12, -6]


@pytest.mark.parametrize("repeat", [False, True])
@pytest.mark.parametrize("selection", [None, [], iter(())])
def test_split_fanout_without_fanout(selection, repeat):
    source = Input()
    graph = SFG([source], [Output(Negation(source))])

    transformed = graph.split_fanout(selection, repeat=repeat)

    assert transformed is not graph
    assert len(transformed.operations) == len(graph.operations)
    assert transformed.evaluate(3) == graph.evaluate(3) == -3


def test_split_fanout_empty_selection_leaves_fanouts():
    graph = two_fanouts()

    transformed = graph.split_fanout([])

    assert len(transformed.find_by_name("first")) == 1
    assert len(transformed.find_by_name("second")) == 1
    assert transformed.evaluate(3) == graph.evaluate(3)
    assert SFG().split_fanout().operations == []


def test_split_fanout_preserves_source_output_index():
    left, right = Input(), Input()
    butterfly = R2Butterfly(left, right)
    shared = Negation(butterfly.output(1))
    graph = SFG(
        [left, right],
        [Output(butterfly.output(0)), Output(Addition(shared, shared))],
    )

    transformed = graph.split_fanout()
    copied_butterfly = transformed.find_by_type(R2Butterfly)[0]

    assert len(transformed.find_by_type(Negation)) == 2
    assert all(
        operation.input(0).connected_source is copied_butterfly.output(1)
        for operation in transformed.find_by_type(Negation)
    )
    assert transformed.evaluate(7, 2) == graph.evaluate(7, 2) == [9, -10]


@pytest.mark.parametrize("repeat", [False, True])
def test_split_fanout_delays_in_feedback_preserve_initial_state_and_sequence(repeat):
    source = Input()
    delay = Delay(initial_value=3)
    total = Addition(source, delay)
    delay.input(0).connect(total)
    graph = SFG([source], [Output(total), Output(Subtraction(total, delay))])

    transformed = graph.split_fanout(repeat=repeat)

    assert len(transformed.find_by_type(Delay)) == 2
    assert all(op.initial_value == 3 for op in transformed.find_by_type(Delay))
    assert len(graph.find_by_type(Delay)) == 1
    original_simulation = Simulation(graph, [lambda iteration: iteration + 1])
    transformed_simulation = Simulation(transformed, [lambda iteration: iteration + 1])
    original_simulation.run_for(6, save_results=True)
    transformed_simulation.run_for(6, save_results=True)
    for output in ("out0", "out1"):
        assert list(transformed_simulation.results[output]) == list(
            original_simulation.results[output]
        )


@pytest.mark.parametrize("repeat", [False, True])
def test_split_fanout_nested_sfg_as_unary_operation(repeat):
    inner_source = Input()
    inner_shared = Negation(inner_source)
    inner = SFG([inner_source], [Output(Addition(inner_shared, inner_shared))])
    outer_source = Input()
    nested = inner(outer_source)
    graph = SFG([outer_source], [Output(Addition(nested, nested))])

    transformed = graph.split_fanout(repeat=repeat)
    copies = transformed.find_by_type(SFG)

    assert len(copies) == 2
    assert all(op.output(0).signal_count == 1 for op in copies)
    assert all(len(op.find_by_type(Negation)) == 1 for op in copies)
    assert transformed.evaluate(3) == graph.evaluate(3) == -12
    assert len(graph.find_by_type(SFG)) == 1


@pytest.mark.parametrize("selection", [42, [42], [None], int, [str]])
def test_split_fanout_rejects_invalid_selection_types(selection):
    graph = two_fanouts()

    with pytest.raises(TypeError, match=r"operation|graph ID"):
        graph.split_fanout(selection)

    assert len(graph.find_by_type(ConstantMultiplication)) == 1
    assert graph.evaluate(3) == [12, -6]


@pytest.mark.parametrize("invalid", ["unknown", "signal", "foreign", "input", "output"])
def test_split_fanout_validates_graph_membership_and_ports(invalid):
    graph = two_fanouts()
    first = graph.find_by_name("first")[0]
    selections = {
        "unknown": "missing",
        "signal": first.input(0).signals[0].graph_id,
        "foreign": first.copy(),
        "input": graph.input_operations[0],
        "output": graph.output_operations[0].graph_id,
    }

    with pytest.raises(ValueError if invalid in {"unknown", "foreign"} else TypeError):
        graph.split_fanout([first, selections[invalid]])

    assert first.output(0).signal_count == 2
    assert graph.evaluate(3) == [12, -6]


@pytest.mark.parametrize("kind", [Constant, Addition, R2Butterfly])
def test_split_fanout_rejects_operations_without_one_input_and_one_output(kind):
    source = Input()
    operation = kind(2) if kind is Constant else kind(source, source)
    graph = SFG([source], [Output(operation.output(0))])

    with pytest.raises(TypeError, match="one input and one output"):
        graph.split_fanout(graph.find_by_type(kind)[0])


def test_split_fanout_copies_can_be_found_and_merged():
    graph = two_fanouts()
    first = graph.find_by_name("first")[0]

    transformed = graph.split_fanout(first)
    groups = transformed.find_redundant_operations()

    assert len(groups) == 1
    assert {operation.name for operation in groups[0]} == {"first"}
    assert len(groups[0]) == 2
    merged = transformed.merge_redundant_operations(groups[0])
    assert len(merged.operations) == len(graph.operations)
    assert merged.evaluate(3) == graph.evaluate(3) == [12, -6]


def fanout_chain():
    source = Input("source")
    first = Negation(source, name="first")
    middle = ConstantMultiplication(2, first, name="middle")
    retained = Output(middle)
    last = ConstantMultiplication(3, middle, name="last")
    return SFG([source], [retained, Output(Addition(last, last))])


@pytest.mark.parametrize(
    "selection",
    [
        "all",
        "type",
        "ids",
        "instances",
        "class_iterator",
        "ids_iterator",
        "instances_iterator",
        "mixed",
    ],
)
def test_split_fanout_repeat_processes_upstream_fanouts_and_copies(selection):
    graph = fanout_chain()
    selected = [op for op in graph.operations if op.input_count == op.output_count == 1]
    graph_ids = [op.graph_id for op in selected]
    targets = {
        "all": None,
        "type": Operation,
        "ids": graph_ids,
        "instances": selected,
        "class_iterator": iter([Negation, ConstantMultiplication]),
        "ids_iterator": iter(graph_ids),
        "instances_iterator": iter(selected),
        "mixed": [graph.find_by_name("first")[0].graph_id, ConstantMultiplication],
    }
    one_pass = graph.split_fanout()
    assert any(
        op.output(0).signal_count > 1
        for op in one_pass.operations
        if op.input_count == op.output_count == 1
    )

    transformed = graph.split_fanout(targets[selection], repeat=True)

    assert len(transformed.find_by_name("first")) == 3
    assert len(transformed.find_by_name("middle")) == 3
    assert len(transformed.find_by_name("last")) == 2
    assert all(
        op.output(0).signal_count <= 1
        for op in transformed.operations
        if op.input_count == op.output_count == 1
    )
    assert len(graph.find_by_name("middle")) == 1
    assert len(graph.find_by_name("last")) == 1
    assert transformed.evaluate(3) == graph.evaluate(3) == [-6, -36]
    assert {op.graph_id for op in graph.components}.issubset(
        {op.graph_id for op in transformed.components}
    )
    stable = transformed.split_fanout(repeat=True)
    assert {op.graph_id for op in stable.components} == {
        op.graph_id for op in transformed.components
    }


@pytest.mark.parametrize("selection", ["class", "ids", "instances", "empty"])
def test_split_fanout_repeat_preserves_selection_scope(selection):
    graph = fanout_chain()
    selected = [graph.find_by_name(name)[0] for name in ("middle", "last")]
    targets = {
        "class": ConstantMultiplication,
        "ids": [op.graph_id for op in selected],
        "instances": iter(selected),
        "empty": [],
    }

    transformed = graph.split_fanout(targets[selection], repeat=True)

    assert len(transformed.find_by_name("first")) == 1
    assert len(transformed.find_by_name("middle")) == (1 if selection == "empty" else 3)
    assert len(transformed.find_by_name("last")) == (1 if selection == "empty" else 2)
    assert transformed.evaluate(3) == graph.evaluate(3) == [-6, -36]


@pytest.mark.parametrize("cycle_length", [1, 2])
@pytest.mark.parametrize("selection", ["all", "type", "ids", "iterator"])
def test_split_fanout_repeat_rejects_feedback_that_cannot_converge(
    cycle_length, selection
):
    delays = [Delay(initial_value=index + 1) for index in range(cycle_length)]
    for index, delay in enumerate(delays):
        delay <<= delays[index - 1]
    graph = SFG(outputs=[Output(delays[0])])
    graph_ids = [op.graph_id for op in graph.find_by_type(Delay)]
    targets = {
        "all": None,
        "type": Delay,
        "ids": graph_ids,
        "iterator": iter(graph_ids),
    }
    original_sources = [
        op.input(0).connected_source for op in graph.find_by_type(Delay)
    ]

    with pytest.raises(ValueError, match=r"cycle|feedback"):
        graph.split_fanout(targets[selection], repeat=True)

    assert len(graph.find_by_type(Delay)) == cycle_length
    assert [
        op.input(0).connected_source for op in graph.find_by_type(Delay)
    ] == original_sources
    assert graph.split_fanout() is not graph
    assert len(graph.split_fanout([], repeat=True).operations) == len(graph.operations)


def test_split_fanout_repeat_stops_at_unselected_feedback_operation():
    first, second = Delay(initial_value=2, name="first"), Delay(initial_value=5)
    first <<= second
    second <<= first
    graph = SFG(outputs=[Output(first)])

    transformed = graph.split_fanout(graph.find_by_name("first")[0], repeat=True)

    assert len(transformed.find_by_name("first")) == 2
    assert all(
        op.output(0).signal_count == 1 for op in transformed.find_by_name("first")
    )
    original_simulation = Simulation(graph)
    transformed_simulation = Simulation(transformed)
    original_simulation.run_for(6)
    transformed_simulation.run_for(6)
    assert list(transformed_simulation.results["out0"]) == list(
        original_simulation.results["out0"]
    )
    assert SFG().split_fanout(repeat=True).operations == []
