"""Negation cancellation and operation-specific sign propagation."""

import pytest

from b_asic.core_operations import (
    Addition,
    AddSub,
    Constant,
    ConstantMultiplication,
    Division,
    Multiplication,
    Negation,
    Subtraction,
)
from b_asic.sfg import SFG
from b_asic.simulation import Simulation
from b_asic.special_operations import Delay, Input, Output
from b_asic.utility_operations import Sink


@pytest.mark.parametrize("count", [2, 3, 4, 5])
def test_cancel_negation_chains(count):
    source = Input()
    result = source
    for _ in range(count):
        result = Negation(result)
    original = SFG([source], [Output(result)])

    simplified = original.negation_propagation()

    assert len(simplified.find_by_type(Negation)) == count % 2
    assert len(original.find_by_type(Negation)) == count
    for value in [-7, 0, 2 + 3j]:
        assert simplified.evaluate_outputs([value]) == original.evaluate_outputs(
            [value]
        )
    if count % 2 == 0:
        assert simplified.output_operations[0].input(
            0
        ).connected_source is simplified.input_operations[0].output(0)


@pytest.mark.parametrize("parent_has_output", [False, True])
def test_cancel_negations_preserves_shared_producer_sinks_and_signals(
    parent_has_output,
):
    source = Input()
    parent = Negation(source, name="parent", latency=2)
    child = Negation(parent, name="child")
    Sink(parent, name="termination")
    total = Addition(child, child)
    for index, signal in enumerate(child.output(0).signals):
        signal.name = f"branch{index}"
        signal.set_param("custom", [index])
    original = SFG(
        [source], [Output(total), *([Output(parent)] if parent_has_output else [])]
    )

    simplified = original.negation_propagation()

    assert len(simplified.find_by_type(Negation)) == 1
    retained = simplified.find_by_name("parent")[0]
    assert retained.latency == 2
    assert not simplified.find_by_name("child")
    assert simplified.find_by_name("termination")[0].input(
        0
    ).connected_source is retained.output(0)
    for index in range(2):
        signal = simplified.find_by_name(f"branch{index}")[0]
        assert signal.source is simplified.input_operations[0].output(0)
        assert signal.params == {"custom": [index]}
    assert len(original.find_by_type(Negation)) == 2
    assert simplified.evaluate_outputs([3]) == original.evaluate_outputs([3])


def test_cancel_negations_created_during_propagation():
    source = Input()
    original = SFG(
        [source], [Output(Subtraction(Constant(0), Subtraction(Constant(0), source)))]
    )

    simplified = original.constant_propagation().negation_propagation()

    assert not simplified.find_by_type(Subtraction)
    assert not simplified.find_by_type(Negation)
    assert simplified.evaluate_outputs([3]) == original.evaluate_outputs([3]) == [3]


def test_cancel_negations_preserves_feedback_sequence():
    source = Input()
    delay = Delay(initial_value=2)
    total = Addition(source, Negation(Negation(delay)))
    delay <<= total
    original = SFG([source], [Output(total)])

    simplified = original.negation_propagation()

    assert not simplified.find_by_type(Negation)
    assert simplified.find_by_type(Delay)[0].initial_value == 2
    original_simulation = Simulation(original, [lambda iteration: iteration + 1])
    simplified_simulation = Simulation(simplified, [lambda iteration: iteration + 1])
    original_simulation.run_for(6)
    simplified_simulation.run_for(6)
    assert list(simplified_simulation.results["out0"]) == list(
        original_simulation.results["out0"]
    )


@pytest.mark.parametrize("custom_parent", [False, True])
def test_negation_cancellation_respects_custom_subclass_behavior(custom_parent):
    class IdentityNegation(Negation):
        def evaluate(self, a, data_type=None):
            return a

        def _constant_propagation(self):
            return None

    source = Input()
    parent_type, child_type = (
        (IdentityNegation, Negation) if custom_parent else (Negation, IdentityNegation)
    )
    original = SFG([source], [Output(child_type(parent_type(source)))])

    simplified = original.negation_propagation()

    assert len(simplified.find_by_type(Negation)) == 2
    assert simplified.evaluate_outputs([3]) == original.evaluate_outputs([3]) == [-3]


@pytest.mark.parametrize("operation_type", [Multiplication, Division])
def test_cancel_negations_on_both_arithmetic_inputs(operation_type):
    left, right = Input(), Input()
    operation = operation_type(
        Negation(left), Negation(right), name="arithmetic", latency=3, execution_time=2
    )
    for index, port in enumerate(operation.inputs):
        port.signals[0].name = f"operand{index}"
        port.signals[0].set_param("custom", [index])
    original = SFG([left, right], [Output(operation)])
    original_operation = original.find_by_name("arithmetic")[0]

    simplified = original.negation_propagation()

    assert not simplified.find_by_type(Negation)
    retained = simplified.find_by_id(original_operation.graph_id)
    assert retained.name == "arithmetic"
    assert retained.latency == 3
    assert retained.execution_time == 2
    for index, port in enumerate(retained.inputs):
        assert port.connected_source is simplified.input_operations[index].output(0)
        signal = port.signals[0]
        assert signal.name == f"operand{index}"
        assert signal.graph_id == original_operation.input(index).signals[0].graph_id
        assert signal.params == {"custom": [index]}
    assert len(original.find_by_type(Negation)) == 2
    for values in [(6, 2), (-6, 2), (0, 3), (2 + 3j, 1 - 2j), (6, 0)]:
        assert simplified.evaluate_outputs(values) == pytest.approx(
            original.evaluate_outputs(values)
        )


@pytest.mark.parametrize("operation_type", [Multiplication, Division])
def test_cancel_arithmetic_input_negations_preserves_shared_branches(operation_type):
    left, right = Input(), Input()
    left_negation, right_negation = Negation(left), Negation(right)
    operation = operation_type(left_negation, right_negation)
    Sink(left_negation, name="termination")
    original = SFG([left, right], [Output(operation), Output(right_negation)])

    simplified = original.negation_propagation()

    assert len(simplified.find_by_type(Negation)) == 2
    retained = simplified.find_by_type(operation_type)[0]
    for index, port in enumerate(retained.inputs):
        assert port.connected_source is simplified.input_operations[index].output(0)
    assert isinstance(
        simplified.find_by_name("termination")[0].input(0).connected_source.operation,
        Negation,
    )
    assert simplified.evaluate_outputs([6, 2]) == original.evaluate_outputs([6, 2])


@pytest.mark.parametrize("operation_type", [Multiplication, Division])
@pytest.mark.parametrize(
    ("left_count", "right_count"), [(3, 1), (2, 1), (2, 2), (3, 3)]
)
def test_cancel_arithmetic_input_negation_chains(
    operation_type, left_count, right_count
):
    left, right = Input(), Input()
    left_operand, right_operand = left, right
    for _ in range(left_count):
        left_operand = Negation(left_operand)
    for _ in range(right_count):
        right_operand = Negation(right_operand)
    original = SFG([left, right], [Output(operation_type(left_operand, right_operand))])

    simplified = original.negation_propagation()

    assert len(simplified.find_by_type(Negation)) == abs(
        left_count % 2 - right_count % 2
    )
    assert simplified.evaluate_outputs([6, 2]) == original.evaluate_outputs([6, 2])


@pytest.mark.parametrize("operation_type", [Multiplication, Division])
@pytest.mark.parametrize("negated_index", [0, 1])
def test_single_arithmetic_input_negation_is_preserved(operation_type, negated_index):
    inputs = [Input(), Input()]
    operands = list(inputs)
    operands[negated_index] = Negation(operands[negated_index])
    original = SFG(inputs, [Output(operation_type(*operands))])

    simplified = original.negation_propagation()

    assert len(simplified.find_by_type(Negation)) == 1
    assert simplified.evaluate_outputs([6, 2]) == original.evaluate_outputs([6, 2])


def test_cancel_division_input_negations_preserves_real_valued_setting():
    left, right = Input(), Input()
    original = SFG(
        [left, right],
        [Output(Division(Negation(left), Negation(right), real_valued=True))],
    )

    simplified = original.negation_propagation()

    assert not simplified.find_by_type(Negation)
    assert simplified.find_by_type(Division)[0].real_valued is True
    values = [6 + 8j, 2 + 3j]
    assert (
        simplified.evaluate_outputs(values) == original.evaluate_outputs(values) == [3]
    )


@pytest.mark.parametrize("operation_type", [Multiplication, Division])
def test_arithmetic_input_negation_cancellation_respects_custom_behavior(
    operation_type,
):
    class IdentityNegation(Negation):
        def evaluate(self, a, data_type=None):
            return a

        def _constant_propagation(self):
            return None

    left, right = Input(), Input()
    original = SFG(
        [left, right], [Output(operation_type(IdentityNegation(left), Negation(right)))]
    )

    simplified = original.negation_propagation()

    assert len(simplified.find_by_type(Negation)) == 2
    assert simplified.evaluate_outputs([6, 2]) == original.evaluate_outputs([6, 2])


@pytest.mark.parametrize(
    ("kind", "is_add"),
    [(Addition, True), (Subtraction, False), (AddSub, True), (AddSub, False)],
)
@pytest.mark.parametrize("negated_index", [0, 1])
@pytest.mark.parametrize("mul_j", [False, True])
def test_add_sub_default_negation_rules_preserve_scaled_arithmetic(
    kind, is_add, negated_index, mul_j
):
    left, right = Input("left"), Input("right")
    operands = [left, right]
    operands[negated_index] = Negation(operands[negated_index])
    properties = {"is_add": is_add} if kind is AddSub else {}
    operation = kind(
        in0=operands[0],
        in1=operands[1],
        name="arithmetic",
        latency=3,
        execution_time=2,
        in0_scale=1,
        in1_scale=2,
        out0_scale=1,
        mul_j=mul_j,
        **properties,
    )
    original = SFG([left, right], [Output(operation)], name="signs")
    original.execution_time = 7
    original_id = original.find_by_name("arithmetic")[0].graph_id

    result = original.negation_propagation()

    retained = result.find_by_id(original_id)
    changed = is_add or negated_index == 1
    expected_add = not is_add if changed else is_add
    assert type(retained) is (
        AddSub if kind is AddSub else Addition if expected_add else Subtraction
    )
    if kind is AddSub:
        assert retained.is_add is expected_add
    assert len(result.find_by_type(Negation)) == (0 if changed else 1)
    assert retained.latency == 3
    assert retained.execution_time == 2
    assert result.execution_time == 7
    assert result.name == "signs"
    for values in [(12, 8), (-3, 7), (2 + 3j, 1 - 2j)]:
        assert result.evaluate_outputs(values) == pytest.approx(
            original.evaluate_outputs(values)
        )
    assert len(original.find_by_type(Negation)) == 1


@pytest.mark.parametrize(
    ("kind", "is_add"),
    [(Addition, True), (Subtraction, False), (AddSub, True), (AddSub, False)],
)
def test_add_sub_default_negation_rules_repeat_until_stable(kind, is_add):
    left, right = Input(), Input()
    properties = {"is_add": is_add} if kind is AddSub else {}
    operation = kind(
        in0=Negation(left),
        in1=Negation(right),
        mul_j=True,
        in0_scale=2,
        in1_scale=1,
        **properties,
    )
    original = SFG([left, right], [Output(operation)])

    result = original.negation_propagation()

    assert len(result.find_by_type(Negation)) == int(is_add)
    assert result.evaluate_outputs([2 + 3j, 5 - 2j]) == pytest.approx(
        original.evaluate_outputs([2 + 3j, 5 - 2j])
    )


@pytest.mark.parametrize("negated_index", [0, 1])
@pytest.mark.parametrize("selection", ["id", "list", "iterator"])
def test_targeted_multiplication_moves_input_sign_to_output(negated_index, selection):
    left, right = Input(), Input()
    operands = [left, right]
    operands[negated_index] = Negation(operands[negated_index])
    original = SFG([left, right], [Output(Multiplication(*operands, name="product"))])
    graph_id = original.find_by_name("product")[0].graph_id
    targets = {"id": graph_id, "list": [graph_id], "iterator": iter([graph_id])}

    result = original.negation_propagation(targets[selection])

    retained = result.find_by_id(graph_id)
    assert all(
        port.connected_source is result.input_operations[index].output(0)
        for index, port in enumerate(retained.inputs)
    )
    assert (
        type(result.output_operations[0].input(0).connected_source.operation)
        is Negation
    )
    assert len(result.find_by_type(Negation)) == 1
    assert result.evaluate_outputs([2 + 3j, 1 - 2j]) == pytest.approx(
        original.evaluate_outputs([2 + 3j, 1 - 2j])
    )


@pytest.mark.parametrize(
    "selection", ["default", "first", "second", "list", "iterator", "mapping"]
)
def test_backward_multiplication_selects_receiving_input(selection):
    left, right = Input(), Input()
    product = Multiplication(left, right, name="product", latency=4)
    original = SFG([left, right], [Output(Negation(product))])
    graph_id = original.find_by_name("product")[0].graph_id
    choices = {
        "default": None,
        "first": 0,
        "second": 1,
        "list": [1],
        "iterator": iter([1]),
        "mapping": {graph_id: [1]},
    }
    expected = 0 if selection in {"default", "first"} else 1

    result = original.negation_propagation(
        [graph_id], direction="backward", input_indices=choices[selection]
    )

    retained = result.find_by_id(graph_id)
    assert retained.latency == 4
    assert type(retained.input(expected).connected_source.operation) is Negation
    assert retained.input(1 - expected).connected_source is result.input_operations[
        1 - expected
    ].output(0)
    assert result.output_operations[0].input(0).connected_source is retained.output(0)
    assert len(result.find_by_type(Negation)) == 1
    assert result.evaluate_outputs([2 + 3j, 1 - 2j]) == pytest.approx(
        original.evaluate_outputs([2 + 3j, 1 - 2j])
    )


def test_backward_propagation_copies_a_shared_producer_and_preserves_sinks():
    left, right = Input(), Input()
    product = Multiplication(left, right, name="product", latency=3, execution_time=2)
    Sink(product, name="termination")
    original = SFG([left, right], [Output(product), Output(Negation(product))])
    graph_id = original.find_by_name("product")[0].graph_id

    result = original.negation_propagation(
        [graph_id], direction="backward", input_indices=1
    )

    products = result.find_by_type(Multiplication)
    assert len(products) == 2
    assert all(op.latency == 3 and op.execution_time == 2 for op in products)
    retained = result.find_by_id(graph_id)
    assert result.output_operations[0].input(0).connected_source is retained.output(0)
    assert result.find_by_name("termination")[0].input(
        0
    ).connected_source is retained.output(0)
    assert (
        result.evaluate_outputs([6, 2])
        == original.evaluate_outputs([6, 2])
        == [12, -12]
    )
    assert len(original.find_by_type(Multiplication)) == 1
    components = set(result.components)
    assert len({component.graph_id for component in components}) == len(components)


@pytest.mark.parametrize(
    ("kind", "is_add"),
    [(Addition, True), (Subtraction, False), (AddSub, True), (AddSub, False)],
)
def test_backward_add_sub_distributes_sign_to_both_inputs(kind, is_add):
    left, right = Input(), Input()
    properties = {"is_add": is_add} if kind is AddSub else {}
    operation = kind(
        in0=left,
        in1=right,
        name="arithmetic",
        mul_j=True,
        in0_scale=1,
        in1_scale=2,
        **properties,
    )
    original = SFG([left, right], [Output(Negation(operation))])
    graph_id = original.find_by_name("arithmetic")[0].graph_id

    result = original.negation_propagation(
        [graph_id], direction="backward", input_indices=[0, 1]
    )

    retained = result.find_by_id(graph_id)
    assert type(retained) is kind
    assert all(
        type(port.connected_source.operation) is Negation for port in retained.inputs
    )
    assert len(result.find_by_type(Negation)) == 2
    assert result.output_operations[0].input(0).connected_source is retained.output(0)
    assert result.evaluate_outputs([2 + 3j, 5 - 2j]) == pytest.approx(
        original.evaluate_outputs([2 + 3j, 5 - 2j])
    )


def test_per_operation_input_choices_and_shared_iterator():
    left, right = Input(), Input()
    products = [
        Multiplication(left, right, name=f"product{index}") for index in range(2)
    ]
    original = SFG([left, right], [Output(Negation(op)) for op in products])
    graph_ids = [
        original.find_by_name(f"product{index}")[0].graph_id for index in range(2)
    ]

    result = original.negation_propagation(
        graph_ids,
        direction="backward",
        input_indices=dict(zip(graph_ids, [0, 1], strict=True)),
    )
    common = original.negation_propagation(
        graph_ids, direction="backward", input_indices=iter([1])
    )

    for index, graph_id in enumerate(graph_ids):
        assert (
            type(result.find_by_id(graph_id).input(index).connected_source.operation)
            is Negation
        )
        assert (
            type(common.find_by_id(graph_id).input(1).connected_source.operation)
            is Negation
        )
    assert result.evaluate_outputs([6, 2]) == original.evaluate_outputs([6, 2])


@pytest.mark.parametrize("direction", ["forward", "backward"])
@pytest.mark.parametrize("port", [0, 1])
def test_division_moves_one_sign_only_with_nonzero_constant_divisor(direction, port):
    source = Input()
    operands = [source, Constant(2)]
    if direction == "forward":
        operands[port] = Negation(operands[port])
    operation = Division(*operands, name="quotient", real_valued=True)
    output = Negation(operation) if direction == "backward" else operation
    original = SFG([source], [Output(output)])
    graph_id = original.find_by_name("quotient")[0].graph_id

    result = original.negation_propagation(
        [graph_id], direction=direction, input_indices=port
    )

    retained = result.find_by_id(graph_id)
    assert retained.real_valued is True
    assert len(result.find_by_type(Negation)) == 1
    if direction == "forward":
        assert (
            type(result.output_operations[0].input(0).connected_source.operation)
            is Negation
        )
    else:
        assert type(retained.input(port).connected_source.operation) is Negation
    assert (
        result.evaluate_outputs([6 + 8j]) == original.evaluate_outputs([6 + 8j]) == [-3]
    )


@pytest.mark.parametrize("direction", ["forward", "backward"])
def test_division_zero_behavior_is_preserved(direction):
    left, right = Input(), Input()
    operation = Division(
        Negation(left) if direction == "forward" else left, right, name="quotient"
    )
    original = SFG(
        [left, right],
        [Output(Negation(operation) if direction == "backward" else operation)],
    )
    graph_id = original.find_by_name("quotient")[0].graph_id

    result = original.negation_propagation([graph_id], direction=direction)

    assert result.evaluate_outputs([6, 0]) == original.evaluate_outputs([6, 0])
    assert result.evaluate_outputs([6, 2]) == original.evaluate_outputs([6, 2])


@pytest.mark.parametrize("direction", ["forward", "backward"])
def test_constant_multiplication_moves_sign_without_merging_coefficients(direction):
    source = Input()
    parent = ConstantMultiplication(2, source)
    operation = ConstantMultiplication(
        3, Negation(parent) if direction == "forward" else parent, name="product"
    )
    original = SFG(
        [source],
        [Output(Negation(operation) if direction == "backward" else operation)],
    )
    graph_id = original.find_by_name("product")[0].graph_id

    result = original.negation_propagation([graph_id], direction=direction)

    assert sorted(op.value for op in result.find_by_type(ConstantMultiplication)) == [
        2,
        3,
    ]
    assert len(result.find_by_type(Negation)) == 1
    assert result.evaluate_outputs([3]) == original.evaluate_outputs([3]) == [-18]


@pytest.mark.parametrize("kind", [Multiplication, Division, Addition, Subtraction])
def test_constant_propagation_no_longer_rewrites_dynamic_negations(kind):
    left, right = Input(), Input()
    original = SFG([left, right], [Output(kind(Negation(left), Negation(right)))])

    result = original.constant_propagation()

    assert len(result.find_by_type(Negation)) == 2
    assert len(result.find_by_type(kind)) == 1
    assert result.evaluate_outputs([6, 2]) == original.evaluate_outputs([6, 2])
    source = Input()
    chain = SFG([source], [Output(Negation(Negation(source)))])
    assert len(chain.constant_propagation().find_by_type(Negation)) == 2


@pytest.mark.parametrize(
    "invalid",
    [
        "unknown",
        "negation",
        "signal",
        "type",
        "direction",
        "negative_port",
        "large_port",
        "empty_ports",
        "wrong_port_type",
        "both_mul_ports",
        "unselected_mapping",
    ],
)
def test_invalid_selection_is_rejected_without_mutating_original(invalid):
    left, right = Input(), Input()
    operation = Multiplication(left, right, name="product")
    original = SFG([left, right], [Output(Negation(operation))])
    retained = original.find_by_name("product")[0]
    graph_id = retained.graph_id
    graph_ids = [graph_id]
    options = {"direction": "backward"}
    error = ValueError
    if invalid == "unknown":
        graph_ids = ["missing"]
    elif invalid == "negation":
        graph_ids = [original.find_by_type(Negation)[0].graph_id]
    elif invalid == "signal":
        graph_ids = [retained.input(0).signals[0].graph_id]
        error = TypeError
    elif invalid == "type":
        graph_ids = [42]
        error = TypeError
    elif invalid == "direction":
        options["direction"] = "sideways"
    else:
        options["input_indices"] = {
            "negative_port": -1,
            "large_port": 2,
            "empty_ports": [],
            "wrong_port_type": ["0"],
            "both_mul_ports": [0, 1],
            "unselected_mapping": {"missing": 0},
        }[invalid]
        if invalid == "wrong_port_type":
            error = TypeError

    with pytest.raises(error):
        original.negation_propagation(graph_ids, **options)

    assert len(original.find_by_type(Negation)) == 1
    assert retained.input(0).connected_source is original.input_operations[0].output(0)


def test_custom_operation_hook_can_extend_propagation():
    class CustomMultiplication(Multiplication):
        def _negation_propagation(
            self, *, direction="forward", input_indices=None, propagate=False
        ):
            from b_asic._negation import move_forward, negated_inputs

            return (
                propagate
                and direction == "forward"
                and move_forward(self, negated_inputs(self))
            )

    left, right = Input(), Input()
    original = SFG([left, right], [Output(CustomMultiplication(Negation(left), right))])
    graph_id = original.find_by_type(CustomMultiplication)[0].graph_id

    result = original.negation_propagation([graph_id])

    assert (
        type(result.output_operations[0].input(0).connected_source.operation)
        is Negation
    )
    assert result.evaluate_outputs([6, 2]) == original.evaluate_outputs([6, 2]) == [-12]


@pytest.mark.parametrize(
    ("kind", "is_add"),
    [(Addition, True), (Subtraction, False), (AddSub, True), (AddSub, False)],
)
def test_forward_add_sub_common_input_sign_moves_to_output(kind, is_add):
    left, right = Input(), Input()
    properties = {"is_add": is_add} if kind is AddSub else {}
    operation = kind(
        in0=Negation(left),
        in1=Negation(right),
        name="arithmetic",
        mul_j=True,
        in0_scale=1,
        in1_scale=2,
        **properties,
    )
    original = SFG([left, right], [Output(operation)])
    graph_id = original.find_by_name("arithmetic")[0].graph_id

    result = original.negation_propagation([graph_id], input_indices=[0, 1])

    retained = result.find_by_id(graph_id)
    assert type(retained) is kind
    assert all(
        port.connected_source is result.input_operations[index].output(0)
        for index, port in enumerate(retained.inputs)
    )
    assert (
        type(result.output_operations[0].input(0).connected_source.operation)
        is Negation
    )
    assert len(result.find_by_type(Negation)) == 1
    assert result.evaluate_outputs([2 + 3j, 1 - 2j]) == pytest.approx(
        original.evaluate_outputs([2 + 3j, 1 - 2j])
    )


def test_empty_selection_uses_default_rules_and_unsupported_operations_are_boundaries():
    source = Input()
    original = SFG([source], [Output(Negation(Negation(source)))])

    assert not original.negation_propagation([]).find_by_type(Negation)
    nested_source = Input()
    nested = SFG([nested_source], [Output(Negation(Negation(nested_source)))])
    outer_source = Input()
    outer = SFG([outer_source], [Output(nested(outer_source))])
    assert (
        len(outer.negation_propagation().find_by_type(SFG)[0].find_by_type(Negation))
        == 2
    )
