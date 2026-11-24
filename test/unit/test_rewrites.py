"""Generic port-aware subgraph matching and replacement."""

from itertools import permutations

import pytest

from b_asic import (
    SFG,
    Addition,
    ComplexConjugate,
    Constant,
    ConstantMultiplication,
    ImaginaryMultiplication,
    Input,
    LeftShift,
    Multiplication,
    Negation,
    Output,
    RewriteRegistry,
    RewriteRule,
    RightShift,
    Shift,
    Subtraction,
    available_rewrites,
    get_rewrite,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.special_operations import Delay
from b_asic.utility_operations import Sink


def product_graph(*, extra=None, negated_input=0, product_input=0, root_type=Addition):
    inputs = [Input(name) for name in ("a", "b", "c", "unused")]
    negative = Negation(inputs[0], name="negative")
    operands = [negative, inputs[1]]
    if negated_input:
        operands.reverse()
    product = Multiplication(*operands, name="product", latency=3, execution_time=2)
    product.input(0).latency_offset = 1
    product.input(1).latency_offset = 2
    terms = [product, inputs[2]]
    if product_input:
        terms.reverse()
    root = root_type(*terms, name="sum", latency=5, execution_time=3)
    root.input(0).latency_offset = 1
    root.input(1).latency_offset = 2
    for name, port in (
        ("a_wire", negative.input(0)),
        ("b_wire", product.input(1 - negated_input)),
        ("c_wire", root.input(1 - product_input)),
    ):
        port.signals[0].name = name
        port.signals[0].set_param("custom", [name])
    output = Output(root, name="result")
    output.input(0).signals[0].name = "result_wire"
    if extra == "negative":
        Sink(negative)
    elif extra == "product":
        Sink(product)
    elif extra == "root":
        Sink(root, name="termination")
    graph = SFG(inputs, [output], name="example")
    graph.execution_time = 7
    graph.input(0).latency_offset = 1
    return graph


def triple_rule(*, preserve=False):
    return RewriteRule.from_builders(
        "test.triple",
        inputs=("a",),
        pattern=lambda a: Negation(Negation(Negation(a)), name="root"),
        replacement=lambda a: Negation(a, name="root"),
        preserve={"root": "root"} if preserve else {},
    )


def product_difference_graph(
    *, consumer=Addition, negated_input=0, inner_input=0, extra=None
):
    inputs = [Input(name) for name in ("a", "b", "c", "d")]
    negative = Negation(inputs[0], name="negative")
    factors = (negative, inputs[1]) if negated_input == 0 else (inputs[1], negative)
    product = Multiplication(*factors, name="product", latency=3, execution_time=2)
    inner = Subtraction(product, inputs[2], name="inner", latency=4, execution_time=3)
    terms = (inner, inputs[3]) if inner_input == 0 else (inputs[3], inner)
    root = consumer(*terms, name="root", latency=7, execution_time=5)
    for operation in (product, inner, root):
        operation.input(0).latency_offset = 1
        operation.input(1).latency_offset = 2
    for name, port in (
        ("a_wire", negative.input(0)),
        ("b_wire", product.input(1 - negated_input)),
        ("c_wire", inner.input(1)),
        ("d_wire", root.input(1 - inner_input)),
    ):
        port.signals[0].name = name
    output = Output(root)
    output.input(0).signals[0].name = "result_wire"
    if extra == "boundaries":
        for source in inputs:
            Sink(source)
        Sink(root, name="root_sink")
    elif extra is not None:
        Sink({"negative": negative, "product": product, "inner": inner}[extra])
    return SFG(inputs, [output])


@pytest.mark.parametrize("negated_input", [0, 1])
@pytest.mark.parametrize("product_input", [0, 1])
def test_builtin_preview_and_replacement_preserve_graph_and_boundaries(
    negated_input, product_input
):
    graph = product_graph(
        extra="root", negated_input=negated_input, product_input=product_input
    )
    before = [
        (op, tuple(port.connected_source for port in op.inputs))
        for op in graph.operations
    ]
    original_root = graph.find_by_name("sum")[0]
    original_product = graph.find_by_name("product")[0]
    wire_ids = {
        name: graph.find_by_name(name)[0].graph_id
        for name in ("a_wire", "b_wire", "c_wire", "result_wire")
    }

    matches = graph.find_rewrites("arithmetic.negated_product")

    assert len(matches) == 1
    match = matches[0]
    assert match.anchor is original_root
    assert match.operations["product"] is original_product
    assert set(match.inputs) == {"a", "b", "c"}
    assert match.outputs["out0"] is original_root.output(0)
    with pytest.raises(TypeError):
        match.operations["root"] = original_product

    rewritten = graph.apply_rewrites(match)

    assert not rewritten.find_by_type(Negation)
    assert len(rewritten.operations) == len(graph.operations) - 1
    root = rewritten.find_by_name(original_root.name)[0]
    product = rewritten.find_by_id(original_product.graph_id)
    assert type(root) is Subtraction
    assert root.graph_id.removeprefix("sub").isdigit()
    assert rewritten.find_by_id(original_root.graph_id) is None
    assert type(product) is Multiplication
    assert root.name == "sum"
    assert root.execution_time == 3
    assert product.execution_time == 2
    assert [port.latency_offset for port in product.inputs] == [
        original_product.input(negated_input).latency_offset,
        original_product.input(1 - negated_input).latency_offset,
    ]
    assert product.input(0).connected_source is rewritten.input_operations[0].output(0)
    assert product.input(1).connected_source is rewritten.input_operations[1].output(0)
    assert (
        root.input(0).latency_offset
        == original_root.input(1 - product_input).latency_offset
    )
    assert (
        root.input(1).latency_offset
        == original_root.input(product_input).latency_offset
    )
    assert root.output(0).latency_offset == 5
    assert root.input(0).connected_source is rewritten.input_operations[2].output(0)
    assert root.input(1).connected_source is product.output(0)
    assert rewritten.find_by_name("termination")[0].input(
        0
    ).connected_source is root.output(0)
    assert rewritten.name == graph.name
    assert rewritten.execution_time == 7
    assert rewritten.input(0).latency_offset == 1
    assert [op.name for op in rewritten.input_operations] == ["a", "b", "c", "unused"]
    for name, graph_id in wire_ids.items():
        assert rewritten.find_by_name(name)[0].graph_id == graph_id
    for values in [(2, 3, 7, 99), (-2, 3, 1, 0), (2 + 3j, 1 - 2j, 5j, 0)]:
        assert rewritten.evaluate_outputs(values) == pytest.approx(
            graph.evaluate_outputs(values)
        )
    for operation, sources in before:
        assert tuple(port.connected_source for port in operation.inputs) == sources
    components = set(rewritten.components)
    assert len({component.graph_id for component in components}) == len(components)
    rewritten.find_by_name("a_wire")[0].param("custom").append("changed")
    assert graph.find_by_name("a_wire")[0].param("custom") == ["a_wire"]


@pytest.mark.parametrize("extra", ["negative", "product"])
@pytest.mark.parametrize("negated_input", [0, 1])
def test_undeclared_internal_fanout_rejects_match(extra, negated_input):
    graph = product_graph(extra=extra, negated_input=negated_input)
    assert graph.find_rewrites("arithmetic.negated_product") == []
    assert graph.transform("arithmetic.negated_product").evaluate(2, 3, 7, 0) == 1


@pytest.mark.parametrize(
    "rules", [None, "arithmetic.subtract_negated_product", "arithmetic", "negations"]
)
@pytest.mark.parametrize("negated_input", [0, 1])
def test_subtract_negated_product(rules, negated_input):
    graph = product_graph(
        root_type=Subtraction,
        product_input=1,
        extra="root",
        negated_input=negated_input,
    )
    original_root = graph.find_by_name("sum")[0]
    original_product = graph.find_by_name("product")[0]

    (match,) = graph.find_rewrites(rules, target=Subtraction)

    assert match.rule.name == "arithmetic.subtract_negated_product"
    assert match.anchor is original_root
    assert not graph.find_rewrites(match.rule, target=Addition)

    rewritten = graph.transform(rules, target=original_root.graph_id)

    root = rewritten.find_by_name(original_root.name)[0]
    product = rewritten.find_by_id(original_product.graph_id)
    assert type(root) is Addition
    assert root.graph_id.removeprefix("add").isdigit()
    assert rewritten.find_by_id(original_root.graph_id) is None
    assert type(product) is Multiplication
    assert not rewritten.find_by_type(Negation)
    assert root.input(0).connected_source is rewritten.input_operations[2].output(0)
    assert root.input(1).connected_source is product.output(0)
    assert [port.latency_offset for port in root.inputs] == [1, 2]
    assert root.output(0).latency_offset == 5
    assert root.execution_time == 3
    assert product.execution_time == 2
    assert [port.latency_offset for port in product.inputs] == [
        original_product.input(negated_input).latency_offset,
        original_product.input(1 - negated_input).latency_offset,
    ]
    assert product.input(0).connected_source is rewritten.input_operations[0].output(0)
    assert product.input(1).connected_source is rewritten.input_operations[1].output(0)
    assert rewritten.find_by_name("termination")[0].input(
        0
    ).connected_source is root.output(0)
    for name in ("a_wire", "b_wire", "c_wire", "result_wire"):
        assert (
            rewritten.find_by_name(name)[0].graph_id
            == graph.find_by_name(name)[0].graph_id
        )
    for a, b, c in [(2, 3, 7), (-2, 3, 1), (0, 4, -5), (2 + 3j, 1 - 2j, 5j)]:
        assert rewritten.evaluate(a, b, c, 0) == pytest.approx(c + a * b)
        assert rewritten.evaluate(a, b, c, 0) == pytest.approx(
            graph.evaluate(a, b, c, 0)
        )
    assert type(original_root) is Subtraction
    assert graph.find_by_type(Negation)


@pytest.mark.parametrize("extra", ["negative", "product"])
@pytest.mark.parametrize("negated_input", [0, 1])
def test_subtract_negated_product_rejects_shared_internal_operations(
    extra, negated_input
):
    graph = product_graph(
        root_type=Subtraction,
        product_input=1,
        extra=extra,
        negated_input=negated_input,
    )

    assert graph.find_rewrites("arithmetic.subtract_negated_product") == []
    assert (
        graph.transform("arithmetic.subtract_negated_product").evaluate(2, 3, 7, 0)
        == 13
    )


@pytest.mark.parametrize("negated_input", [0, 1])
def test_subtract_negated_product_requires_product_on_negative_input(negated_input):
    graph = product_graph(
        root_type=Subtraction,
        negated_input=negated_input,
    )

    assert graph.find_rewrites("arithmetic.subtract_negated_product") == []


@pytest.mark.parametrize(
    ("consumer", "inner_input", "rule_name", "replacement_type"),
    [
        (Addition, 0, "arithmetic.negated_product_difference", Subtraction),
        (Addition, 1, "arithmetic.negated_product_difference", Subtraction),
        (Subtraction, 1, "arithmetic.subtract_negated_product_difference", Addition),
    ],
)
@pytest.mark.parametrize("negated_input", [0, 1])
def test_negated_product_difference_through_consumer(
    consumer, inner_input, rule_name, replacement_type, negated_input
):
    graph = product_difference_graph(
        consumer=consumer,
        inner_input=inner_input,
        negated_input=negated_input,
        extra="boundaries",
    )
    old_root, old_inner, old_product = (
        graph.find_by_name(name)[0] for name in ("root", "inner", "product")
    )

    (match,) = graph.find_rewrites(rule_name, target=old_root.graph_id)
    assert match.anchor is old_root
    result = graph.apply_rewrites(match)

    assert not result.find_by_type(Negation)
    assert len(result.operations) == len(graph.operations) - 1
    root = result.find_by_name(old_root.name)[0]
    inner = result.find_by_name(old_inner.name)[0]
    product = result.find_by_id(old_product.graph_id)
    assert isinstance(root, (Addition, Subtraction))
    assert type(root) is replacement_type
    assert type(inner) is Addition
    assert type(product) is Multiplication
    assert result.find_by_id(old_root.graph_id) is None
    assert result.find_by_id(old_inner.graph_id) is None
    assert root.graph_id.removeprefix(root.type_name()).isdigit()
    assert inner.graph_id.removeprefix("add").isdigit()
    assert [root.execution_time, inner.execution_time, product.execution_time] == [
        5,
        3,
        2,
    ]
    assert [root.output(0).latency_offset, inner.output(0).latency_offset] == [7, 4]
    assert [port.latency_offset for port in product.inputs] == [
        old_product.input(negated_input).latency_offset,
        old_product.input(1 - negated_input).latency_offset,
    ]
    assert [port.latency_offset for port in inner.inputs] == [1, 2]
    assert [port.latency_offset for port in root.inputs] == [
        old_root.input(1 - inner_input).latency_offset,
        old_root.input(inner_input).latency_offset,
    ]
    assert root.input(0).connected_source is result.input_operations[3].output(0)
    assert root.input(1).connected_source is inner.output(0)
    assert inner.input(0).connected_source is product.output(0)
    assert inner.input(1).connected_source is result.input_operations[2].output(0)
    assert result.find_by_name("root_sink")[0].input(0).connected_source is root.output(
        0
    )
    for name in ("a_wire", "b_wire", "c_wire", "d_wire", "result_wire"):
        assert (
            result.find_by_name(name)[0].graph_id
            == graph.find_by_name(name)[0].graph_id
        )
    for a, b, c, d in [
        (2, 3, 7, 11),
        (-2, 3, 1, 0),
        (0, 4, -5, 2),
        (2j, 1 - 2j, 5j, 3),
    ]:
        expected = d - (a * b + c) if consumer is Addition else d + (a * b + c)
        assert result.evaluate(a, b, c, d) == pytest.approx(expected)
        assert result.evaluate(a, b, c, d) == pytest.approx(graph.evaluate(a, b, c, d))
    assert type(old_inner) is Subtraction
    assert type(old_root) is consumer
    assert graph.find_by_type(Negation)


@pytest.mark.parametrize("consumer", [Addition, Subtraction])
@pytest.mark.parametrize("rules", [None, "arithmetic", "negations"])
def test_negated_product_difference_is_in_default_collections(consumer, rules):
    graph = product_difference_graph(consumer=consumer, inner_input=1)

    result = graph.transform(rules)

    assert not result.find_by_type(Negation)
    assert result.evaluate(2, 3, 7, 11) == graph.evaluate(2, 3, 7, 11)


@pytest.mark.parametrize(
    ("consumer", "rule_name"),
    [
        (Addition, "arithmetic.negated_product_difference"),
        (Subtraction, "arithmetic.subtract_negated_product_difference"),
    ],
)
@pytest.mark.parametrize("extra", ["negative", "product", "inner"])
def test_negated_product_difference_rejects_internal_fanout(consumer, rule_name, extra):
    graph = product_difference_graph(
        consumer=consumer, inner_input=1, negated_input=1, extra=extra
    )

    assert graph.find_rewrites(rule_name) == []
    assert graph.transform(rule_name).evaluate(2, 3, 7, 11) == graph.evaluate(
        2, 3, 7, 11
    )


@pytest.mark.parametrize("negated_input", [0, 1])
def test_product_difference_requires_negative_input_of_subtraction_consumer(
    negated_input,
):
    graph = product_difference_graph(
        consumer=Subtraction, inner_input=0, negated_input=negated_input
    )

    assert graph.find_rewrites("arithmetic.subtract_negated_product_difference") == []


@pytest.mark.parametrize(
    ("subtract", "product_input"), [(False, 0), (False, 1), (True, 1)]
)
@pytest.mark.parametrize("negated_input", [0, 1])
@pytest.mark.parametrize("boundary", [0, 1, 2])
@pytest.mark.parametrize("derived_source", [False, True])
def test_product_rewrites_allow_fanout_on_boundary_inputs(
    subtract, product_input, negated_input, boundary, derived_source
):
    inputs = [Input(name) for name in ("a", "b", "c")]
    arguments = list(inputs)
    source = (
        Multiplication(inputs[boundary], Constant(2), name="boundary_source")
        if derived_source
        else inputs[boundary]
    )
    arguments[boundary] = source
    a, b, c = arguments
    negative = Negation(a)
    factors = (negative, b) if negated_input == 0 else (b, negative)
    product = Multiplication(*factors)
    terms = (product, c) if product_input == 0 else (c, product)
    root = Subtraction(*terms) if subtract else Addition(*terms)
    rule = (
        "arithmetic.subtract_negated_product"
        if subtract
        else "arithmetic.negated_product"
    )
    graph = SFG(inputs, [Output(root), Output(source)])
    external_wire = graph.output_operations[1].input(0).signals[0]
    source_port = external_wire.source
    assert source_port is not None
    assert len(source_port.signals) == 2

    (match,) = graph.find_rewrites(rule)

    assert match.inputs[("a", "b", "c")[boundary]] is source_port
    result = graph.apply_rewrites(match)
    assert not result.find_by_type(Negation)
    assert result.evaluate(2, 3, 7) == graph.evaluate(2, 3, 7)
    retained_wire = result.output_operations[1].input(0).signals[0]
    assert retained_wire.graph_id == external_wire.graph_id
    assert retained_wire.source is not None
    assert retained_wire.source.operation.graph_id == source_port.operation.graph_id


def test_repeated_product_rewrites_apply_newly_enabled_matches():
    a, b, c, d = Input(), Input(), Input(), Input()
    graph = SFG(
        [a, b, c, d],
        [
            Output(
                Subtraction(
                    Multiplication(Negation(a), b),
                    Multiplication(Negation(c), d),
                )
            )
        ],
    )

    single = graph.transform("arithmetic")

    assert len(single.find_by_type(Negation)) == 1
    assert len(single.find_rewrites("arithmetic.negated_product")) == 1
    repeated = graph.transform("arithmetic", repeat=True)
    assert not repeated.find_by_type(Negation)
    assert repeated.find_rewrites("arithmetic") == []
    assert repeated.evaluate(2, 3, 7, 5) == graph.evaluate(2, 3, 7, 5) == 29


@pytest.mark.parametrize("negated_input", [0, 1])
@pytest.mark.parametrize(
    "root_params", [{"mul_j": True}, {"in0_scale": 1}, {"in1_scale": 1}]
)
def test_noncommutative_addition_ports_require_explicit_variants(
    negated_input, root_params
):
    product_input = 1
    graph = product_graph(negated_input=negated_input, product_input=product_input)
    for name, value in root_params.items():
        graph.find_by_name("sum")[0].set_param(name, value)
    assert graph.find_rewrites("arithmetic.negated_product") == []

    def canonical(a, b, c):
        return Addition(Multiplication(Negation(a), b), c, **root_params)

    exact_rule = RewriteRule.from_builders(
        "test.exact_addition",
        inputs=("a", "b", "c"),
        pattern=canonical,
        replacement=canonical,
    )
    assert graph.find_rewrites(exact_rule) == []

    def pattern(a, b, c):
        factors = [Negation(a), b]
        if negated_input:
            factors.reverse()
        product = Multiplication(*factors)
        terms = [product, c]
        if product_input:
            terms.reverse()
        return Addition(*terms, name="root", **root_params)

    rule = RewriteRule.from_builders(
        "test.variant",
        inputs=("a", "b", "c"),
        pattern=pattern,
        replacement=lambda a, b, c: Subtraction(c, Multiplication(a, b), **root_params),
    )
    assert len(graph.find_rewrites(rule)) == 1
    assert graph.transform(rule).evaluate(2, 3, 7, 0) == graph.evaluate(2, 3, 7, 0)


@pytest.mark.parametrize(("swap_left", "swap_right"), [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_multiplier_orders_respect_repeated_boundary_bindings(swap_left, swap_right):
    rule = RewriteRule.from_builders(
        "test.factor",
        inputs=("a", "b", "c"),
        pattern=lambda a, b, c: Subtraction(Multiplication(a, b), Multiplication(a, c)),
        replacement=lambda a, b, c: Multiplication(a, Subtraction(b, c)),
    )
    a, b, c = Input(), Input(), Input()
    left = Multiplication(b, a) if swap_left else Multiplication(a, b)
    right = Multiplication(c, a) if swap_right else Multiplication(a, c)
    graph = SFG([a, b, c], [Output(Subtraction(left, right))])

    (match,) = graph.find_rewrites(rule)

    assert match.inputs["a"] is graph.input_operations[0].output(0)
    result = graph.apply_rewrites(match)
    assert len(result.find_by_type(Multiplication)) == 1
    assert result.evaluate(2, 3, 7) == graph.evaluate(2, 3, 7) == -8


def test_multiplier_order_can_be_selected_by_a_guard():
    rule = RewriteRule.from_builders(
        "test.constant_factor",
        inputs=("a", "b"),
        pattern=Multiplication,
        replacement=Multiplication,
        condition=lambda match: isinstance(match.inputs["a"].operation, Constant),
    )
    source = Input()
    graph = SFG([source], [Output(Multiplication(source, Constant(3)))])

    (match,) = graph.find_rewrites(rule)

    assert isinstance(match.inputs["a"].operation, Constant)
    assert graph.apply_rewrites(match).evaluate(7) == 21


@pytest.mark.parametrize(
    "selection", ["id", "instance", "type", "iterator", "mixed", "empty"]
)
def test_anchor_selection_and_region_scope(selection):
    graph = product_graph()
    root = graph.find_by_name("sum")[0]
    targets = {
        "id": root.graph_id,
        "instance": root,
        "type": Addition,
        "iterator": iter([root.graph_id]),
        "mixed": [root.graph_id, Addition],
        "empty": [],
    }
    matches = graph.find_rewrites(
        "arithmetic.negated_product", target=targets[selection]
    )
    assert len(matches) == (0 if selection == "empty" else 1)
    assert not graph.find_rewrites("arithmetic.negated_product", target=Multiplication)
    region = [
        graph.find_by_name(name)[0].graph_id for name in ("negative", "product", "sum")
    ]
    assert (
        len(graph.find_rewrites("arithmetic.negated_product", within=iter(region))) == 1
    )
    assert graph.find_rewrites("arithmetic.negated_product", within=region[1:]) == []
    assert graph.find_rewrites("arithmetic.negated_product", within=[]) == []


def test_distinct_boundary_placeholders_can_bind_the_same_source():
    source = Input()
    graph = SFG(
        [source], [Output(Addition(Multiplication(Negation(source), source), source))]
    )
    (match,) = graph.find_rewrites("arithmetic.negated_product")
    assert match.inputs["a"] is match.inputs["b"] is match.inputs["c"]
    assert graph.apply_rewrites(match).evaluate(3) == graph.evaluate(3) == -6


def test_repeated_boundary_placeholder_requires_the_same_source():
    rule = RewriteRule.from_builders(
        "test.double",
        inputs=("a",),
        pattern=lambda a: Addition(a, a),
        replacement=lambda a: ConstantMultiplication(2, a),
    )
    left, right = Input(), Input()
    graph = SFG([left, right], [Output(Addition(left, right))])
    assert graph.find_rewrites(rule) == []
    source = Input()
    repeated = SFG([source], [Output(Addition(source, source))])
    assert repeated.transform(rule).evaluate(3) == 6


def test_multiple_outputs_are_reconnected_by_name_and_port():
    def pattern(a, b):
        butterfly = R2Butterfly(a, b, name="root")
        return {"sum": butterfly.output(0), "difference": butterfly.output(1)}

    rule = RewriteRule.from_builders(
        "test.butterfly",
        inputs=("a", "b"),
        pattern=pattern,
        replacement=lambda a, b: {
            "difference": Subtraction(a, b),
            "sum": Addition(a, b),
        },
    )
    left, right = Input(), Input()
    butterfly = R2Butterfly(left, right)
    graph = SFG(
        [left, right], [Output(butterfly.output(0)), Output(butterfly.output(1))]
    )
    wires = [output.input(0).signals[0].graph_id for output in graph.output_operations]

    result = graph.transform(rule)

    assert not result.find_by_type(R2Butterfly)
    assert result.evaluate(7, 2) == graph.evaluate(7, 2) == [9, 5]
    assert [
        output.input(0).signals[0].graph_id for output in result.output_operations
    ] == wires


def test_computational_parameters_are_exact_but_timing_and_names_are_not():
    graph = product_graph()
    assert len(graph.find_rewrites("arithmetic.negated_product")) == 1
    graph.find_by_name("sum")[0].set_param("in0_scale", 1)
    assert graph.find_rewrites("arithmetic.negated_product") == []


def test_parameter_predicate_factory_and_guard():
    source = Input("a")
    pattern = SFG(
        [source],
        [
            Output(
                ConstantMultiplication(
                    0, ConstantMultiplication(0, source, name="inner"), name="root"
                )
            )
        ],
    )

    def replacement(match):
        argument = Input("a")
        coefficient = match.operations["inner"].value * match.operations["root"].value
        return SFG(
            [argument],
            [Output(ConstantMultiplication(coefficient, argument, name="root"))],
        )

    rule = RewriteRule(
        "test.coefficients",
        pattern,
        replacement,
        preserve={"root": "root"},
        node_match=lambda template, operation: True,
        condition=lambda match: match.operations["root"].value != 0,
    )
    argument = Input()
    graph = SFG(
        [argument],
        [Output(ConstantMultiplication(3, ConstantMultiplication(2, argument)))],
    )
    result = graph.transform(rule)
    assert len(result.find_by_type(ConstantMultiplication)) == 1
    assert result.find_by_type(ConstantMultiplication)[0].value == 6
    assert result.evaluate(4) == graph.evaluate(4) == 24
    (match,) = graph.find_rewrites(rule)
    match.operations["root"].value = 0
    assert graph.find_rewrites(rule) == []


@pytest.mark.parametrize("change", ["parameter", "boundary", "fanout", "internal"])
def test_stale_matches_are_rejected(change):
    graph = product_graph()
    matches = graph.find_rewrites("arithmetic.negated_product")
    if change == "parameter":
        graph.find_by_name("sum")[0].set_param("out0_scale", 1)
    elif change == "boundary":
        graph.find_by_name("negative")[0].input(0).signals[0].set_source(
            graph.input_operations[2]
        )
    elif change == "fanout":
        Sink(graph.find_by_name("product")[0])
    else:
        graph.find_by_name("product")[0].input(0).signals[0].set_source(
            graph.input_operations[0]
        )
    with pytest.raises(ValueError, match="stale"):
        graph.apply_rewrites(matches)


def test_foreign_matches_and_invalid_match_values_are_rejected():
    graph = product_graph()
    matches = graph.find_rewrites("arithmetic.negated_product")
    other = graph()
    with pytest.raises(ValueError, match="belong"):
        other.apply_rewrites(matches)
    with pytest.raises(TypeError, match="RewriteMatch"):
        graph.apply_rewrites([42])
    assert graph.apply_rewrites([]) is not graph


def test_overlaps_are_skipped_and_adjacent_disjoint_matches_are_rebound():
    source = Input()
    node = source
    for _ in range(4):
        node = Negation(node)
    graph = SFG([source], [Output(node)])
    matches = graph.find_rewrites("arithmetic.double_negation")
    assert len(matches) == 3
    result = graph.apply_rewrites(matches)
    assert not result.find_by_type(Negation)
    assert result.evaluate(3) == graph.evaluate(3) == 3


def test_repeated_passes_and_single_use_selector_iterators():
    source = Input()
    node = source
    for _ in range(5):
        node = Negation(node)
    graph = SFG([source], [Output(node)])
    rule = triple_rule()
    assert len(graph.transform(rule).find_by_type(Negation)) == 3
    result = graph.transform(
        iter([rule]), target=iter([Negation]), repeat=True, max_iterations=2
    )
    assert len(result.find_by_type(Negation)) == 1
    assert result.evaluate(3) == graph.evaluate(3) == -3


def test_repeated_explicit_anchor_can_be_preserved():
    source = Input()
    node = source
    for _ in range(5):
        node = Negation(node)
    graph = SFG([source], [Output(node)])
    anchor = graph.output_operations[0].input(0).connected_source.operation
    result = graph.transform(triple_rule(preserve=True), target=anchor, repeat=True)
    assert len(result.find_by_type(Negation)) == 1
    assert result.find_by_id(anchor.graph_id) is not None


def test_iteration_limit_stops_nonconvergent_rules_without_mutating_original():
    rule = RewriteRule.from_builders(
        "test.identity",
        inputs=("a",),
        pattern=lambda a: Negation(a, name="root"),
        replacement=lambda a: Negation(a, name="root"),
        preserve={"root": "root"},
    )
    source = Input()
    graph = SFG([source], [Output(Negation(source))])
    with pytest.raises(RuntimeError, match="iteration limit"):
        graph.transform(rule, repeat=True, max_iterations=2)
    assert len(graph.find_by_type(Negation)) == 1
    assert graph.evaluate(3) == -3


def test_registry_names_collections_duplicates_and_template_isolation():
    registry = RewriteRegistry()
    first = get_rewrite("arithmetic.negated_product")
    second = get_rewrite("arithmetic.double_negation")
    registry.register(first, collections=["arithmetic", "signs"])
    registry.register(second, collections="signs")
    assert registry.names() == (first.name, second.name)
    assert registry.select(["signs", first]) == [first, second]
    assert registry.select("arithmetic") == [first]
    assert registry.get(first.name) is first
    with pytest.raises(ValueError, match="already"):
        registry.register(first)
    with pytest.raises(KeyError):
        registry.select("missing")
    with pytest.raises(TypeError):
        registry.select([42])
    copied_pattern = first.pattern
    copied_pattern.find_by_type(Addition)[0].set_param("mul_j", True)
    assert len(product_graph().find_rewrites(first)) == 1
    assert set(available_rewrites()) >= {
        first.name,
        second.name,
        "arithmetic.add_negation",
    }


@pytest.mark.parametrize(
    "invalid", ["unknown", "signal", "foreign", "wrong_type", "wrong_class"]
)
def test_invalid_operation_selection(invalid):
    graph = product_graph()
    root = graph.find_by_name("sum")[0]
    values = {
        "unknown": "missing",
        "signal": root.input(0).signals[0].graph_id,
        "foreign": root.copy(),
        "wrong_type": 42,
        "wrong_class": str,
    }
    with pytest.raises(ValueError if invalid in {"unknown", "foreign"} else TypeError):
        graph.find_rewrites(target=values[invalid])


def test_empty_rule_and_target_selections_return_copies():
    graph = product_graph()
    assert graph.find_rewrites([]) == []
    assert graph.find_rewrites(target=[]) == []
    assert graph.transform([]) is not graph
    assert SFG().transform().operations == []
    assert product_graph().find_rewrites("arithmetic")


def test_stateful_templates_and_incompatible_boundaries_are_rejected():
    with pytest.raises(ValueError, match="combinational"):
        RewriteRule.from_builders(
            "test.delay",
            inputs=("a",),
            pattern=Delay,
            replacement=lambda a: a,
        )
    with pytest.raises(ValueError, match="boundaries"):
        RewriteRule.from_builders(
            "test.outputs",
            inputs=("a",),
            pattern=Negation,
            replacement=lambda a: [a, Negation(a)],
        )
    with pytest.raises(ValueError, match="anchor"):
        RewriteRule.from_builders(
            "test.anchor",
            inputs=("a",),
            pattern=Negation,
            replacement=lambda a: a,
            anchor="missing",
        )
    with pytest.raises(ValueError, match="Preserved"):
        RewriteRule.from_builders(
            "test.preserve",
            inputs=("a",),
            pattern=Negation,
            replacement=lambda a: a,
            preserve={"missing": "missing"},
        )


def test_host_delays_and_nested_graphs_are_preserved_as_boundaries():
    source = Input()
    delayed = Delay(source, initial_value=5)
    graph = SFG([source], [Output(Negation(Negation(delayed)))])
    result = graph.transform("arithmetic.double_negation")
    assert result.find_by_type(Delay)[0].initial_value == 5
    inner_source = Input()
    inner = SFG([inner_source], [Output(Negation(Negation(inner_source)))])
    outer_source = Input()
    outer = SFG([outer_source], [Output(inner(outer_source))])
    assert outer.find_rewrites() == []
    assert len(outer.transform().find_by_type(SFG)[0].find_by_type(Negation)) == 2


def test_replacement_previews_are_independent_and_factories_are_validated():
    rule = get_rewrite("arithmetic.negated_product")
    preview = rule.build_replacement()
    preview.find_by_type(Subtraction)[0].set_param("out0_scale", 3)
    assert rule.build_replacement().find_by_type(Subtraction)[0].out0_scale == 0

    source = Input("a")
    pattern = SFG([source], [Output(Negation(source))])
    invalid = RewriteRule(
        "test.invalid_factory",
        pattern,
        lambda match: SFG(outputs=[Output(Constant(0))]),
    )
    argument = Input()
    graph = SFG([argument], [Output(Negation(argument))])
    with pytest.raises(ValueError, match="requires a match"):
        invalid.build_replacement()
    with pytest.raises(ValueError, match="boundaries"):
        graph.transform(invalid)
    assert len(graph.find_by_type(Negation)) == 1
    assert graph.evaluate(3) == -3


def test_internal_multioutput_port_indices_are_significant():
    def pattern(a, b):
        operation = R2Butterfly(a, b, name="butterfly")
        return {
            "negative": Negation(operation.output(0), name="root"),
            "other": operation.output(1),
        }

    rule = RewriteRule.from_builders(
        "test.output_ports", inputs=("a", "b"), pattern=pattern, replacement=pattern
    )
    left, right = Input(), Input()
    butterfly = R2Butterfly(left, right)
    graph = SFG(
        [left, right],
        [Output(Negation(butterfly.output(1))), Output(butterfly.output(0))],
    )
    assert graph.find_rewrites(rule) == []


def test_pattern_outputs_cannot_rewrite_external_boundary_sources():
    with pytest.raises(ValueError, match="originate from matched"):
        RewriteRule.from_builders(
            "test.external_output",
            inputs=("a",),
            pattern=lambda a: {"inside": Negation(a), "external": a},
            replacement=lambda a: {"inside": Negation(a), "external": Negation(a)},
        )


def test_builders_can_return_sfg_templates():
    def pattern(a):
        return SFG([a], [Output(Negation(Negation(a)), name="value")])

    def replacement(a):
        return SFG([a], [Output(a, name="value")])

    rule = RewriteRule.from_builders(
        "test.sfg_builders", inputs=("a",), pattern=pattern, replacement=replacement
    )
    source = Input()
    graph = SFG([source], [Output(Negation(Negation(source)))])
    result = graph.transform(rule)
    assert not result.find_by_type(Negation)
    assert result.evaluate(3) == graph.evaluate(3) == 3


@pytest.mark.parametrize("limit", [0, -1, True, "2"])
def test_invalid_iteration_limits(limit):
    with pytest.raises(ValueError, match="positive integer"):
        product_graph().transform(max_iterations=limit)


def test_global_registry_helpers_and_collection_selection(monkeypatch):
    from b_asic import rewrites

    registry = RewriteRegistry()
    monkeypatch.setattr(rewrites, "_default_registry", lambda: registry)
    rule = triple_rule()
    rewrites.register_rewrite(rule, collections="custom")
    assert rewrites.get_rewrite(rule.name) is rule
    assert rewrites.available_rewrites() == (rule.name,)
    source = Input()
    graph = SFG([source], [Output(Negation(Negation(Negation(source))))])
    assert len(graph.find_rewrites("custom")) == 1
    assert len(graph.transform("custom").find_by_type(Negation)) == 1


@pytest.mark.parametrize(
    ("arithmetic", "rule"),
    [
        (Addition, "arithmetic.factor_addition"),
        (Subtraction, "arithmetic.factor_subtraction"),
    ],
)
@pytest.mark.parametrize("swap_left", [False, True])
@pytest.mark.parametrize("swap_right", [False, True])
@pytest.mark.parametrize("swap_terms", [False, True])
def test_common_factor_extraction(arithmetic, rule, swap_left, swap_right, swap_terms):
    a, b, c = Input("a"), Input("b"), Input("c")
    left = Multiplication(
        b if swap_left else a,
        a if swap_left else b,
        name="left",
        latency=3,
        execution_time=2,
    )
    right = Multiplication(c, a) if swap_right else Multiplication(a, c)
    root = arithmetic(
        right if swap_terms else left,
        left if swap_terms else right,
        name="root",
        latency=5,
        execution_time=4,
    )
    graph = SFG([a, b, c], [Output(root), Output(a)])
    original_root = graph.find_by_name("root")[0]
    wire_ids = [
        output.input(0).signals[0].graph_id for output in graph.output_operations
    ]
    matches = graph.find_rewrites(rule)
    assert matches
    original_product = matches[0].operations["left"]

    result = graph.apply_rewrites(matches)

    assert len(result.find_by_type(Multiplication)) == 1
    assert len(result.find_by_type(arithmetic)) == 1
    retained_root = result.find_by_id(original_root.graph_id)
    assert type(retained_root) is arithmetic
    assert retained_root.execution_time == 4
    assert retained_root.output(0).latency_offset == 5
    retained_product = result.find_by_id(original_product.graph_id)
    assert type(retained_product) is Multiplication
    assert retained_product.execution_time == original_product.execution_time
    assert [
        output.input(0).signals[0].graph_id for output in result.output_operations
    ] == wire_ids
    for values in [(2, 3, 7), (-2, 0, 5), (2 + 3j, 1 - 2j, 5j)]:
        assert result.evaluate_outputs(values) == pytest.approx(
            graph.evaluate_outputs(values)
        )
    assert len(graph.find_by_type(Multiplication)) == 2


@pytest.mark.parametrize("arithmetic", [Addition, Subtraction])
@pytest.mark.parametrize(
    ("left", "right"), [(2, 3), (2, -2), (3, 2), (0.5, 0.25), (2j, 1 - 2j)]
)
def test_coefficient_collection(arithmetic, left, right):
    source = Input("x")
    graph = SFG(
        [source],
        [
            Output(
                arithmetic(
                    ConstantMultiplication(left, source),
                    ConstantMultiplication(right, source),
                )
            )
        ],
    )
    coefficient = left + right if arithmetic is Addition else left - right

    result = graph.transform("coefficients", repeat=True)

    multipliers = result.find_by_type(ConstantMultiplication)
    assert len(multipliers) == 1
    assert multipliers[0].value == coefficient
    assert not result.find_by_type(arithmetic)
    for value in [0, -3, 2 + 3j]:
        assert result.evaluate(value) == pytest.approx(graph.evaluate(value))
    assert len(graph.find_by_type(ConstantMultiplication)) == 2


@pytest.mark.parametrize(("left", "right"), [(2, -2), (3, -2)])
def test_collected_zero_and_unit_coefficients_use_existing_constant_propagation(
    left, right
):
    source = Input()
    graph = SFG(
        [source],
        [
            Output(
                Addition(
                    ConstantMultiplication(left, source),
                    ConstantMultiplication(right, source),
                )
            )
        ],
    )

    collected = graph.transform("coefficients", repeat=True)
    result = collected.constant_propagation(assume_zero_initial_state=False)

    assert not result.find_by_type(ConstantMultiplication)
    assert result.evaluate(7) == graph.evaluate(7)


@pytest.mark.parametrize("arithmetic", [Addition, Subtraction])
@pytest.mark.parametrize("swap_terms", [False, True])
@pytest.mark.parametrize("coefficient", [2, 0, 1, -1, 0.5, 2j])
def test_coefficient_collection_with_implicit_unit(arithmetic, swap_terms, coefficient):
    source = Input()
    scaled = ConstantMultiplication(coefficient, source)
    root = arithmetic(source, scaled) if swap_terms else arithmetic(scaled, source)
    graph = SFG([source], [Output(root)])

    result = graph.transform("coefficients")

    assert not result.find_by_type(arithmetic)
    assert len(result.find_by_type(ConstantMultiplication)) <= 1
    assert result.evaluate(2 + 3j) == pytest.approx(graph.evaluate(2 + 3j))


def arithmetic_tree(terms, arithmetic, shape):
    if len(terms) == 1:
        return terms[0]
    split = (
        len(terms) // 2
        if shape == "balanced"
        else 1
        if shape == "right"
        else len(terms) - 1
    )
    return arithmetic(
        arithmetic_tree(terms[:split], arithmetic, shape),
        arithmetic_tree(terms[split:], arithmetic, shape),
    )


@pytest.mark.parametrize("arithmetic", [Addition, Subtraction])
@pytest.mark.parametrize("shape", ["left", "right", "balanced"])
def test_repeated_factoring_extracts_common_factor_from_five_terms(arithmetic, shape):
    inputs = [Input(name) for name in ("a", "b", "c", "d", "e", "f")]
    terms = [Multiplication(inputs[0], source) for source in inputs[1:]]
    graph = SFG(inputs, [Output(arithmetic_tree(terms, arithmetic, shape))])

    single = graph.transform("factoring")
    result = graph.transform("factoring", repeat=True)

    assert len(single.find_by_type(Multiplication)) > 1
    assert len(result.find_by_type(Multiplication)) == 1
    assert result.find_rewrites("factoring") == []
    values = [2 + 3j, 1 - 2j, 5, -7, 0.5, 11]
    assert result.evaluate_outputs(values) == pytest.approx(
        graph.evaluate_outputs(values)
    )


@pytest.mark.parametrize("arithmetic", [Addition, Subtraction])
@pytest.mark.parametrize("shape", ["left", "right", "balanced"])
def test_repeated_coefficient_collection_combines_five_terms(arithmetic, shape):
    source = Input()
    terms = [ConstantMultiplication(value, source) for value in (2, 3, 5, 7, 11)]
    graph = SFG([source], [Output(arithmetic_tree(terms, arithmetic, shape))])

    single = graph.transform("coefficients")
    result = graph.transform("coefficients", repeat=True)

    assert len(single.find_by_type(ConstantMultiplication)) > 1
    assert len(result.find_by_type(ConstantMultiplication)) == 1
    assert not result.find_by_type(arithmetic)
    assert result.find_rewrites("coefficients") == []
    assert result.evaluate(2 + 3j) == pytest.approx(graph.evaluate(2 + 3j))


def test_repeated_coefficient_collection_includes_unit_terms():
    source = Input()
    graph = SFG(
        [source],
        [
            Output(
                Subtraction(
                    Addition(
                        Addition(ConstantMultiplication(2, source), source),
                        ConstantMultiplication(3, source),
                    ),
                    source,
                )
            )
        ],
    )

    result = graph.transform("coefficients", repeat=True)

    assert len(result.find_by_type(ConstantMultiplication)) == 1
    assert result.find_by_type(ConstantMultiplication)[0].value == 5
    assert result.evaluate(7) == graph.evaluate(7) == 35


@pytest.mark.parametrize("arithmetic", [Addition, Subtraction])
@pytest.mark.parametrize("shape", ["left", "right", "balanced"])
@pytest.mark.parametrize("coefficients", [(2, -2, 3), (3, 2, -2), (2, 2, 3), (1, 0, 0)])
def test_repeated_coefficient_collection_handles_zero_and_unit_subtotals(
    arithmetic, shape, coefficients
):
    source = Input()
    terms = [
        ConstantMultiplication(coefficient, source) for coefficient in coefficients
    ]
    graph = SFG([source], [Output(arithmetic_tree(terms, arithmetic, shape))])

    result = graph.transform("coefficients", repeat=True)

    assert not result.find_by_type(arithmetic)
    assert len(result.find_by_type(ConstantMultiplication)) <= 1
    assert result.evaluate(2 + 3j) == pytest.approx(graph.evaluate(2 + 3j))


def test_coefficient_collection_does_not_reassociate_unrelated_terms():
    x, y = Input(), Input()
    graph = SFG(
        [x, y],
        [
            Output(
                Addition(
                    Addition(ConstantMultiplication(2, x), y),
                    ConstantMultiplication(3, x),
                )
            )
        ],
    )

    result = graph.transform("coefficients", repeat=True)

    assert len(result.find_by_type(ConstantMultiplication)) == 2
    assert result.evaluate(3, 7) == graph.evaluate(3, 7) == 22


@pytest.mark.parametrize(
    ("rule", "builder", "expected"),
    [
        ("subtract_self", lambda x, y: Subtraction(x, x), lambda x, y: 0),
        ("cancel_addend", lambda x, y: Subtraction(Addition(x, y), x), lambda x, y: y),
        ("cancel_addend", lambda x, y: Subtraction(Addition(y, x), x), lambda x, y: y),
        (
            "cancel_subtrahend",
            lambda x, y: Addition(Subtraction(x, y), y),
            lambda x, y: x,
        ),
        (
            "cancel_subtrahend",
            lambda x, y: Addition(y, Subtraction(x, y)),
            lambda x, y: x,
        ),
        (
            "subtract_difference",
            lambda x, y: Subtraction(x, Subtraction(x, y)),
            lambda x, y: y,
        ),
        (
            "cancel_minuend",
            lambda x, y: Subtraction(Subtraction(x, y), x),
            lambda x, y: -y,
        ),
        ("subtract_sum", lambda x, y: Subtraction(x, Addition(x, y)), lambda x, y: -y),
        ("subtract_sum", lambda x, y: Subtraction(x, Addition(y, x)), lambda x, y: -y),
    ],
)
def test_repeated_input_cancellation(rule, builder, expected):
    x, y = Input("x"), Input("y")
    graph = SFG([x, y], [Output(builder(x, y))])
    wire_id = graph.output_operations[0].input(0).signals[0].graph_id

    result = graph.transform(f"arithmetic.{rule}")

    assert not result.find_by_type(Addition)
    assert not result.find_by_type(Subtraction)
    assert [source.name for source in result.input_operations] == ["x", "y"]
    assert result.output_operations[0].input(0).signals[0].graph_id == wire_id
    for values in [(2, 7), (0, -3), (2 + 3j, 1 - 2j)]:
        assert result.evaluate(*values) == pytest.approx(expected(*values))
        assert result.evaluate(*values) == pytest.approx(graph.evaluate(*values))


@pytest.mark.parametrize("collection", ["factoring", "coefficients", "cancellations"])
def test_repeated_bindings_distinguish_output_ports(collection):
    a, b = Input(), Input()
    butterfly = R2Butterfly(a, b)
    x, y = butterfly.output(0), butterfly.output(1)
    roots = {
        "factoring": lambda: Addition(Multiplication(x, a), Multiplication(y, b)),
        "coefficients": lambda: Addition(
            ConstantMultiplication(2, x), ConstantMultiplication(3, y)
        ),
        "cancellations": lambda: Subtraction(x, y),
    }
    graph = SFG([a, b], [Output(roots[collection]())])

    assert graph.find_rewrites(collection) == []


def family_graph(collection, *, shared=False):
    a, b, c = Input("a"), Input("b"), Input("c")
    if collection == "factoring":
        inner = Multiplication(a, b, name="inner")
        root = Addition(inner, Multiplication(a, c), name="root")
    elif collection == "coefficients":
        inner = ConstantMultiplication(2, a, name="inner")
        root = Addition(inner, ConstantMultiplication(3, a), name="root")
    elif collection == "cancellations":
        inner = Addition(a, b, name="inner")
        root = Subtraction(inner, a, name="root")
    elif collection == "complex":
        inner = ComplexConjugate(a, name="inner")
        root = Addition(inner, ComplexConjugate(b), name="root")
    else:
        inner = LeftShift(1, a, name="inner")
        root = RightShift(3, inner, name="root")
    outputs = [Output(root)]
    if shared:
        outputs.append(Output(inner))
    return SFG([a, b, c], outputs)


@pytest.mark.parametrize(
    "collection", ["factoring", "coefficients", "cancellations", "complex", "shifts"]
)
def test_new_collections_reject_shared_internal_results(collection):
    assert family_graph(collection).find_rewrites(collection)
    graph = family_graph(collection, shared=True)

    assert graph.find_rewrites(collection) == []
    assert graph.transform(collection).evaluate(2, 3, 7) == graph.evaluate(2, 3, 7)


@pytest.mark.parametrize(
    "collection", ["factoring", "coefficients", "cancellations", "complex"]
)
@pytest.mark.parametrize("parameter", ["in0_scale", "in1_scale", "out0_scale", "mul_j"])
def test_algebraic_collections_require_ordinary_arithmetic(collection, parameter):
    graph = family_graph(collection)
    graph.find_by_name("root")[0].set_param(
        parameter, True if parameter == "mul_j" else 1
    )

    assert graph.find_rewrites(collection) == []


@pytest.mark.parametrize("parameter", ["in0_scale", "in1_scale", "out0_scale", "mul_j"])
def test_cancellation_checks_inner_arithmetic_parameters(parameter):
    graph = family_graph("cancellations")
    graph.find_by_name("inner")[0].set_param(
        parameter, True if parameter == "mul_j" else 1
    )

    assert graph.find_rewrites("cancellations") == []


@pytest.mark.parametrize("collection", ["coefficients", "shifts"])
def test_parameterized_builtin_rules_keep_other_parameters_exact(collection):
    graph = family_graph(collection)
    graph.find_by_name("inner")[0].set_param("custom", 1)

    assert graph.find_rewrites(collection) == []


@pytest.mark.parametrize(
    ("operation", "rule", "sign"),
    [
        (ComplexConjugate, "complex.double_conjugate", 1),
        (ImaginaryMultiplication, "complex.double_imaginary_multiplication", -1),
    ],
)
def test_complex_operation_cancellation(operation, rule, sign):
    source = Input()
    graph = SFG([source], [Output(operation(operation(source)))])

    result = graph.transform(rule)

    assert not result.find_by_type(operation)
    assert result.evaluate(2 + 3j) == sign * (2 + 3j)
    assert result.evaluate(2 + 3j) == graph.evaluate(2 + 3j)


@pytest.mark.parametrize("operation", [Addition, Subtraction, Multiplication])
def test_complex_conjugate_sharing(operation):
    a, b = Input(), Input()
    root = operation(ComplexConjugate(a), ComplexConjugate(b), name="root", latency=3)
    graph = SFG([a, b], [Output(root)])
    original_root = graph.find_by_name("root")[0]

    result = graph.transform("complex")

    assert len(result.find_by_type(ComplexConjugate)) == 1
    assert len(result.find_by_type(operation)) == 1
    retained = result.find_by_id(original_root.graph_id)
    assert type(retained) is operation
    assert retained.output(0).latency_offset == 3
    assert result.evaluate(2 + 3j, 1 - 2j) == pytest.approx(
        graph.evaluate(2 + 3j, 1 - 2j)
    )


@pytest.mark.parametrize("operation", [Addition, Subtraction, Multiplication])
@pytest.mark.parametrize("shape", ["left", "right", "balanced"])
def test_repeated_conjugate_sharing(operation, shape):
    inputs = [Input() for _ in range(5)]
    graph = SFG(
        inputs,
        [
            Output(
                arithmetic_tree(
                    [ComplexConjugate(source) for source in inputs], operation, shape
                )
            )
        ],
    )

    result = graph.transform("complex", repeat=True)

    assert len(result.find_by_type(ComplexConjugate)) == 1
    assert result.find_rewrites("complex") == []
    values = [2 + 3j, 1 - 2j, 0.5, -7j, 11]
    assert result.evaluate_outputs(values) == pytest.approx(
        graph.evaluate_outputs(values)
    )


def test_repeated_imaginary_multiplications_cancel_resulting_double_negation():
    source = Input()
    root = source
    for _ in range(8):
        root = ImaginaryMultiplication(root)
    graph = SFG([source], [Output(root)])

    result = graph.transform("complex", repeat=True)

    assert not result.find_by_type(ImaginaryMultiplication)
    assert not result.find_by_type(Negation)
    assert result.evaluate(2 + 3j) == graph.evaluate(2 + 3j) == 2 + 3j


@pytest.mark.parametrize("outer", [LeftShift, RightShift, Shift])
@pytest.mark.parametrize("inner", [LeftShift, RightShift, Shift])
@pytest.mark.parametrize(
    ("outer_amount", "inner_amount"), [(0, 0), (0, 2), (2, 0), (2, 3), (3, 2), (2, 2)]
)
def test_shift_chain_folding(outer, inner, outer_amount, inner_amount):
    source = Input()
    graph = SFG([source], [Output(outer(outer_amount, inner(inner_amount, source)))])

    result = graph.transform(f"shifts.fold_{outer.type_name()}_{inner.type_name()}")

    shifts = sum(
        len(result.find_by_type(operation))
        for operation in (LeftShift, RightShift, Shift)
    )
    assert shifts == (0 if graph.evaluate(1) == 1 else 1)
    assert result.evaluate(8 + 2j) == graph.evaluate(8 + 2j)
    assert (
        sum(
            len(graph.find_by_type(operation))
            for operation in (LeftShift, RightShift, Shift)
        )
        == 2
    )


@pytest.mark.parametrize("other", [LeftShift, RightShift, Shift])
@pytest.mark.parametrize("swap", [False, True])
def test_signed_shift_chain_folding(other, swap):
    source = Input()
    root = other(3, Shift(-2, source)) if swap else Shift(-2, other(3, source))
    graph = SFG([source], [Output(root)])

    result = graph.transform("shifts", repeat=True)

    assert (
        sum(
            len(result.find_by_type(operation))
            for operation in (LeftShift, RightShift, Shift)
        )
        == 1
    )
    assert result.evaluate(8 + 2j) == graph.evaluate(8 + 2j)


@pytest.mark.parametrize("operation", [LeftShift, RightShift, Shift])
def test_zero_shift_removal(operation):
    source = Input()
    graph = SFG([source], [Output(operation(0, source))])

    result = graph.transform("shifts")

    assert not result.find_by_type(operation)
    assert result.output_operations[0].input(
        0
    ).connected_source is result.input_operations[0].output(0)


def test_repeated_shift_folding_combines_five_shifts():
    source = Input()
    root = RightShift(3, LeftShift(1, Shift(-2, LeftShift(4, RightShift(2, source)))))
    graph = SFG([source], [Output(root)])

    single = graph.transform("shifts")
    result = graph.transform("shifts", repeat=True)

    assert (
        sum(
            len(single.find_by_type(operation))
            for operation in (LeftShift, RightShift, Shift)
        )
        > 1
    )
    assert len(result.find_by_type(LeftShift)) == 1
    assert not result.find_by_type(RightShift)
    assert not result.find_by_type(Shift)
    assert result.find_rewrites("shifts") == []
    assert result.evaluate(8 + 2j) == graph.evaluate(8 + 2j)


@pytest.mark.parametrize(
    "collection", ["factoring", "coefficients", "cancellations", "complex", "shifts"]
)
@pytest.mark.parametrize("selection", [None, "arithmetic"])
def test_new_collections_are_in_default_arithmetic_rules(collection, selection):
    graph = family_graph(collection)
    names = {match.rule.name for match in graph.find_rewrites(collection)}

    assert names
    assert names <= {match.rule.name for match in graph.find_rewrites(selection)}


def complex_product_graph(
    *, swaps=0, swap_imag=False, reverse_outputs=False, extra=None
):
    inputs = [Input(name) for name in ("a", "b", "c", "d")]
    a, b, c, d = inputs
    operations = dict(zip(("a", "b", "c", "d"), inputs, strict=True))
    for index, (name, left, right) in enumerate(
        (("ac", a, c), ("bd", b, d), ("ad", a, d), ("bc", b, c))
    ):
        operands = (right, left) if swaps & (1 << index) else (left, right)
        operation = Multiplication(*operands, name=name, latency=3, execution_time=2)
        operation.input(0).latency_offset = 1
        operation.input(1).latency_offset = 2
        operations[name] = operation
    real = Subtraction(
        operations["ac"], operations["bd"], name="real", latency=5, execution_time=4
    )
    imag_terms = (
        (operations["bc"], operations["ad"])
        if swap_imag
        else (operations["ad"], operations["bc"])
    )
    imag = Addition(*imag_terms, name="imag", latency=6, execution_time=3)
    operations.update(real=real, imag=imag)
    outputs = [Output(real, name="real_result"), Output(imag, name="imag_result")]
    for output in outputs:
        signal = output.input(0).signals[0]
        signal.name = output.name + "_wire"
        signal.set_param("custom", [output.name])
    if reverse_outputs:
        outputs.reverse()
    if extra is not None:
        Sink(operations[extra], name="external_consumer")
    return SFG(inputs, outputs)


@pytest.mark.parametrize("swaps", range(16))
@pytest.mark.parametrize("swap_imag", [False, True])
@pytest.mark.parametrize("reverse_outputs", [False, True])
def test_real_complex_multiplier_rewrite(swaps, swap_imag, reverse_outputs):
    graph = complex_product_graph(
        swaps=swaps, swap_imag=swap_imag, reverse_outputs=reverse_outputs
    )
    retained_names = ("ac", "bd", "real", "imag")
    original_operations = {name: graph.find_by_name(name)[0] for name in retained_names}
    wire_ids = {
        output.name: output.input(0).signals[0].graph_id
        for output in graph.output_operations
    }

    matches = graph.find_rewrites(
        "complex.three_multiplication_product", target=original_operations["real"]
    )

    assert matches
    assert matches[0].anchor is original_operations["real"]
    assert set(matches[0].inputs) == {"a", "b", "c", "d"}
    assert set(matches[0].outputs) == {"real", "imag"}
    replacement = matches[0].rule.build_replacement(matches[0])
    assert len(replacement.find_by_type(Multiplication)) == 3

    result = graph.apply_rewrites(matches)

    assert len(result.find_by_type(Multiplication)) == 3
    assert (
        len(result.find_by_type(Addition)) + len(result.find_by_type(Subtraction)) == 5
    )
    assert [output.name for output in result.output_operations] == [
        output.name for output in graph.output_operations
    ]
    for name, original in original_operations.items():
        rewritten = result.find_by_name(original.name)[0]
        assert rewritten.name == name
        if name == "imag":
            assert result.find_by_id(original.graph_id) is None
            assert rewritten.graph_id.removeprefix("sub").isdigit()
        else:
            assert rewritten.graph_id == original.graph_id
        assert rewritten.execution_time == original.execution_time
        assert rewritten.output(0).latency_offset == original.output(0).latency_offset
        if name in {"ac", "bd"}:
            offsets = {
                port.connected_source.operation.graph_id: port.latency_offset
                for port in original.inputs
            }
            for port in rewritten.inputs:
                assert (
                    port.latency_offset
                    == offsets[port.connected_source.operation.graph_id]
                )
    for output in result.output_operations:
        signal = output.input(0).signals[0]
        assert signal.graph_id == wire_ids[output.name]
        assert signal.name == output.name + "_wire"
        assert signal.param("custom") == [output.name]
    for a, b, c, d in [(2, 3, 5, 7), (-1, 2, 3, -4), (0, 0, 0, 0), (0.5, 2, -0.25, 3)]:
        product = complex(a, b) * complex(c, d)
        expected = [product.real, product.imag]
        if reverse_outputs:
            expected.reverse()
        assert result.evaluate(a, b, c, d) == pytest.approx(expected)
        assert result.evaluate(a, b, c, d) == pytest.approx(graph.evaluate(a, b, c, d))
    assert len(graph.find_by_type(Multiplication)) == 4
    assert type(original_operations["imag"]) is Addition
    components = set(result.components)
    assert len({component.graph_id for component in components}) == len(components)
    assert result.find_rewrites("complex.three_multiplication_product") == []


@pytest.mark.parametrize("extra", ["ac", "bd", "ad", "bc"])
def test_real_complex_multiplier_rejects_shared_products(extra):
    graph = complex_product_graph(extra=extra)

    assert graph.find_rewrites("complex.three_multiplication_product") == []
    assert (
        len(
            graph.transform("complex.three_multiplication_product").find_by_type(
                Multiplication
            )
        )
        == 4
    )


@pytest.mark.parametrize("extra", ["a", "b", "c", "d", "real", "imag"])
def test_real_complex_multiplier_allows_boundary_fanout(extra):
    graph = complex_product_graph(extra=extra)
    original_source = (
        graph.find_by_name("external_consumer")[0].input(0).connected_source
    )

    result = graph.transform("complex.three_multiplication_product")

    assert len(result.find_by_type(Multiplication)) == 3
    source = result.find_by_name("external_consumer")[0].input(0).connected_source
    assert source.operation.name == original_source.operation.name
    if type(source.operation) is type(original_source.operation):
        assert source.operation.graph_id == original_source.operation.graph_id
    else:
        assert source.operation.graph_id != original_source.operation.graph_id
    assert source.index == original_source.index
    assert result.evaluate(2, 3, 5, 7) == graph.evaluate(2, 3, 5, 7)


@pytest.mark.parametrize("node", ["real", "imag"])
@pytest.mark.parametrize("parameter", ["in0_scale", "in1_scale", "out0_scale", "mul_j"])
def test_real_complex_multiplier_requires_ordinary_arithmetic(node, parameter):
    graph = complex_product_graph()
    graph.find_by_name(node)[0].set_param(
        parameter, True if parameter == "mul_j" else 1
    )

    assert graph.find_rewrites("complex.three_multiplication_product") == []


@pytest.mark.parametrize("name", ["ac", "bd", "ad", "bc"])
def test_real_complex_multiplier_requires_consistent_component_bindings(name):
    graph = complex_product_graph()
    graph.find_by_name(name)[0].input(1).signals[0].set_source(
        graph.input_operations[0]
    )

    assert graph.find_rewrites("complex.three_multiplication_product") == []


def test_real_complex_multiplier_does_not_pair_unrelated_real_and_imaginary_branches():
    inputs = [Input() for _ in range(8)]
    a, b, c, d, e, f, g, h = inputs
    graph = SFG(
        inputs,
        [
            Output(Subtraction(Multiplication(a, c), Multiplication(b, d))),
            Output(Addition(Multiplication(e, h), Multiplication(f, g))),
        ],
    )

    assert graph.find_rewrites("complex.three_multiplication_product") == []


def test_real_complex_multiplier_selection_covers_both_output_branches():
    graph = complex_product_graph()
    rule = "complex.three_multiplication_product"
    matches = graph.find_rewrites(rule, target=Subtraction)
    assert matches
    assert graph.find_rewrites(rule, target=Addition) == []
    region = [operation.graph_id for operation in matches[0].operations.values()]
    assert graph.find_rewrites(rule, within=region)
    assert graph.find_rewrites(rule, within=region[:-1]) == []


@pytest.mark.parametrize(
    "rules", [None, "arithmetic", "complex", "complex.three_multiplication_product"]
)
@pytest.mark.parametrize("split_io", [False, True])
def test_real_complex_multiplier_matches_complex_to_real_graphs(rules, split_io):
    a, b = Input(), Input()
    original = SFG([a, b], [Output(Multiplication(a, b))])
    graph = original.complex_to_real(multiplication_method="four", split_io=split_io)

    result = graph.transform(rules, repeat=True)

    assert len(result.find_by_type(Multiplication)) == 3
    assert len(graph.find_by_type(Multiplication)) == 4
    values = [2, 3, 5, 7] if split_io else [2 + 3j, 5 + 7j]
    expected = [-11, 29] if split_io else [-11 + 29j]
    assert result.evaluate_outputs(values) == pytest.approx(expected)
    assert result.evaluate_outputs(values) == pytest.approx(
        graph.evaluate_outputs(values)
    )


def test_pattern_regions_without_shared_inputs_remain_invalid():
    with pytest.raises(ValueError, match="connected region"):
        RewriteRule.from_builders(
            "test.unrelated_regions",
            inputs=("a", "b"),
            pattern=lambda a, b: [Negation(a), Negation(b)],
            replacement=lambda a, b: [a, b],
        )


def shared_arithmetic_graph(
    *,
    shared_type=Subtraction,
    inner_type=Subtraction,
    root_type=Addition,
    input_order=(2, 0, 1),
    inner_index=1,
    reverse_outputs=False,
    extra=None,
):
    inputs = [Input(name) for name in ("a", "b", "c")]
    shared = shared_type(
        inputs[0], inputs[1], name="shared", latency=3, execution_time=2
    )
    shared.input(0).latency_offset = 1
    shared.input(1).latency_offset = 2
    inner = inner_type(inputs[input_order[0]], inputs[input_order[1]], name="inner")
    other = inputs[input_order[2]]
    operands = (inner, other) if inner_index == 0 else (other, inner)
    root = root_type(*operands, name="root", latency=5, execution_time=4)
    outputs = [Output(shared, name="shared_result"), Output(root, name="result")]
    for output in outputs:
        signal = output.input(0).signals[0]
        signal.name = output.name + "_wire"
        signal.set_param("custom", [output.name])
    if reverse_outputs:
        outputs.reverse()
    if extra is not None:
        operations = dict(zip(("a", "b", "c"), inputs, strict=True))
        operations.update(shared=shared, inner=inner, root=root)
        Sink(operations[extra], name="external_consumer")
    return SFG(inputs, outputs)


@pytest.mark.parametrize("rules", [None, "arithmetic", "sharing"])
@pytest.mark.parametrize("inner_index", [0, 1])
@pytest.mark.parametrize("reverse_outputs", [False, True])
def test_shared_difference_is_reused_across_reassociated_inputs(
    rules, inner_index, reverse_outputs
):
    graph = shared_arithmetic_graph(
        inner_index=inner_index, reverse_outputs=reverse_outputs
    )
    original_shared = graph.find_by_name("shared")[0]
    original_root = graph.find_by_name("root")[0]
    wire_ids = {
        output.name: output.input(0).signals[0].graph_id
        for output in graph.output_operations
    }

    result = graph.transform(rules, target=original_root, repeat=True)

    shared = result.find_by_id(original_shared.graph_id)
    root = result.find_by_name(original_root.name)[0]
    assert type(shared) is Subtraction
    assert type(root) is Subtraction
    assert result.find_by_id(original_root.graph_id) is None
    assert root.graph_id.removeprefix("sub").isdigit()
    assert root.input(0).connected_source is result.input_operations[2].output(0)
    assert root.input(1).connected_source is shared.output(0)
    assert len(result.find_by_type(Subtraction)) == 2
    assert not result.find_by_type(Addition)
    assert result.find_by_name("inner") == []
    assert shared.name == "shared"
    assert shared.execution_time == 2
    assert [port.latency_offset for port in shared.inputs] == [1, 2]
    assert shared.output(0).latency_offset == 3
    assert root.name == "root"
    assert root.execution_time == 4
    assert root.output(0).latency_offset == 5
    assert len(shared.output(0).signals) == 2
    for output in result.output_operations:
        signal = output.input(0).signals[0]
        assert signal.graph_id == wire_ids[output.name]
        assert signal.name == output.name + "_wire"
        assert signal.param("custom") == [output.name]
    for values in [(2, 3, 7), (-3, 5, 1), (2 + 3j, 1 - 2j, 5j)]:
        assert result.evaluate_outputs(values) == pytest.approx(
            graph.evaluate_outputs(values)
        )
    assert len(graph.find_by_type(Subtraction)) == 2
    assert len(graph.find_by_type(Addition)) == 1
    assert result.find_rewrites("sharing") == []


@pytest.mark.parametrize("shared_type", [Addition, Subtraction])
@pytest.mark.parametrize("inner_type", [Addition, Subtraction])
@pytest.mark.parametrize("root_type", [Addition, Subtraction])
@pytest.mark.parametrize("input_order", list(permutations(range(3))))
@pytest.mark.parametrize("inner_index", [0, 1])
def test_arithmetic_sharing_handles_all_operand_positions_and_signs(
    shared_type, inner_type, root_type, input_order, inner_index
):
    graph = shared_arithmetic_graph(
        shared_type=shared_type,
        inner_type=inner_type,
        root_type=root_type,
        input_order=input_order,
        inner_index=inner_index,
    )
    # Probe the actual expressions on basis inputs to determine whether the two
    # repeated terms form this shared result or its negative.
    basis = [
        graph.evaluate(*(int(index == active) for index in range(3)))
        for active in range(3)
    ]
    compatible = basis[0][1] * basis[1][0] == basis[1][1] * basis[0][0]

    matches = graph.find_rewrites("sharing")
    result = graph.transform("sharing", repeat=True)

    assert bool(matches) == compatible
    count = len(result.find_by_type(Addition)) + len(result.find_by_type(Subtraction))
    assert count == (2 if compatible else 3)
    for values in [(2, 3, 7), (-5, 0.5, 11), (2 + 3j, 1 - 2j, 5j)]:
        assert result.evaluate_outputs(values) == pytest.approx(
            graph.evaluate_outputs(values)
        )
    if compatible:
        shared = result.find_by_id(graph.find_by_name("shared")[0].graph_id)
        original_root = graph.find_by_name("root")[0]
        root = result.find_by_name("root")[0]
        if type(root) is type(original_root):
            assert root.graph_id == original_root.graph_id
        else:
            assert result.find_by_id(original_root.graph_id) is None
            assert root.graph_id.removeprefix(root.type_name()).isdigit()
        assert any(port.connected_source is shared.output(0) for port in root.inputs)
        assert len(result.find_by_type(Negation)) == int(
            basis[0][1] < 0 and basis[2][1] < 0
        )
        assert result.find_rewrites("sharing") == []


def test_repeated_sharing_reuses_one_difference_in_multiple_consumers():
    a, b, c, d, e = [Input() for _ in range(5)]
    shared = Subtraction(a, b, name="shared")
    graph = SFG(
        [a, b, c, d, e],
        [
            Output(shared),
            Output(Addition(b, Subtraction(c, a))),
            Output(Addition(a, Subtraction(d, b))),
            Output(Subtraction(Addition(e, b), a)),
        ],
    )

    single = graph.transform("sharing")
    result = graph.transform("sharing", repeat=True)

    assert (
        len(single.find_by_type(Addition)) + len(single.find_by_type(Subtraction)) == 6
    )
    assert (
        len(result.find_by_type(Addition)) + len(result.find_by_type(Subtraction)) == 4
    )
    retained_shared = result.find_by_name("shared")[0]
    assert len(retained_shared.output(0).signals) == 4
    assert result.find_rewrites("sharing") == []
    assert result.evaluate(2, 3, 7, 11, 13) == graph.evaluate(2, 3, 7, 11, 13)


@pytest.mark.parametrize("extra", ["shared", "root", "a", "b", "c"])
def test_arithmetic_sharing_preserves_external_boundary_consumers(extra):
    graph = shared_arithmetic_graph(extra=extra)
    original_source = (
        graph.find_by_name("external_consumer")[0].input(0).connected_source
    )

    result = graph.transform("sharing")

    assert len(result.find_by_type(Subtraction)) == 2
    assert not result.find_by_type(Addition)
    source = result.find_by_name("external_consumer")[0].input(0).connected_source
    assert source.operation.name == original_source.operation.name
    if type(source.operation) is type(original_source.operation):
        assert source.operation.graph_id == original_source.operation.graph_id
    else:
        assert source.operation.graph_id != original_source.operation.graph_id
    assert source.index == original_source.index
    assert result.evaluate(2, 3, 7) == graph.evaluate(2, 3, 7)


def test_arithmetic_sharing_rejects_shared_intermediate_result():
    graph = shared_arithmetic_graph(extra="inner")

    assert graph.find_rewrites("sharing") == []


@pytest.mark.parametrize("node", ["shared", "inner", "root"])
@pytest.mark.parametrize("parameter", ["in0_scale", "in1_scale", "out0_scale", "mul_j"])
def test_arithmetic_sharing_requires_ordinary_arithmetic(node, parameter):
    graph = shared_arithmetic_graph()
    graph.find_by_name(node)[0].set_param(
        parameter, True if parameter == "mul_j" else 1
    )

    assert graph.find_rewrites("sharing") == []


def test_arithmetic_sharing_can_reuse_an_internal_result():
    a, b, c = Input(), Input(), Input()
    shared = Subtraction(a, b, name="shared")
    graph = SFG(
        [a, b, c],
        [
            Output(Multiplication(shared, Constant(2))),
            Output(Addition(b, Subtraction(c, a))),
        ],
    )
    original_id = graph.find_by_name("shared")[0].graph_id

    result = graph.transform("sharing")

    shared = result.find_by_id(original_id)
    assert len(shared.output(0).signals) == 2
    assert len(result.find_by_type(Subtraction)) == 2
    assert not result.find_by_type(Addition)
    assert result.evaluate(2, 3, 7) == graph.evaluate(2, 3, 7) == [-2, 8]


def test_arithmetic_sharing_accepts_arbitrary_boundary_source_ports():
    x, y, z = Input(), Input(), Input()
    butterfly = R2Butterfly(x, y)
    a, b = butterfly.output(0), butterfly.output(1)
    c = Delay(z, initial_value=7)
    graph = SFG(
        [x, y, z],
        [Output(Subtraction(a, b)), Output(Addition(b, Subtraction(c, a)))],
    )

    result = graph.transform("sharing")

    assert len(result.find_by_type(Subtraction)) == 2
    assert not result.find_by_type(Addition)
    assert result.find_by_type(Delay)[0].initial_value == 7
    assert result.evaluate(2, 3, 11) == graph.evaluate(2, 3, 11)


def test_arithmetic_sharing_distinguishes_ports_of_the_same_source_operation():
    x, y, b, c = [Input() for _ in range(4)]
    butterfly = R2Butterfly(x, y)
    graph = SFG(
        [x, y, b, c],
        [
            Output(Subtraction(butterfly.output(0), b)),
            Output(Addition(b, Subtraction(c, butterfly.output(1)))),
        ],
    )

    assert graph.find_rewrites("sharing") == []


def test_arithmetic_sharing_targets_the_consumer_and_scopes_both_branches():
    graph = shared_arithmetic_graph()
    root = graph.find_by_name("root")[0]
    shared = graph.find_by_name("shared")[0]
    region = [
        graph.find_by_name(name)[0].graph_id for name in ("shared", "inner", "root")
    ]

    assert graph.find_rewrites("sharing", target=root, within=region)
    assert graph.find_rewrites("sharing", target=shared) == []
    assert graph.find_rewrites("sharing", within=region[1:]) == []


@pytest.mark.parametrize(
    "rule_name",
    [name for name in available_rewrites() if get_rewrite(name).preserve],
)
def test_all_builtin_rewrites_refresh_ids_when_preserved_operation_types_change(
    rule_name,
):
    rule = get_rewrite(rule_name)
    graph = rule.pattern
    for index, operation in enumerate(graph.operations):
        if not isinstance(operation, (Input, Output)):
            operation.name = f"candidate_{index}"
            operation.execution_time = index + 1
            operation.output(0).latency_offset = index + 2
    match = graph.find_rewrites(rule)[0]
    replacement = rule.build_replacement(match)

    result = graph.apply_rewrites(match)

    for pattern_alias, replacement_alias in rule.preserve.items():
        original = match.operations[pattern_alias]
        expected_type = next(
            type(operation)
            for operation in replacement.find_by_name(replacement_alias)
            if not isinstance(operation, (Input, Output))
        )
        current = result.find_by_name(original.name)[0]
        assert type(current) is expected_type
        assert current.execution_time == original.execution_time
        assert current.output(0).latency_offset == original.output(0).latency_offset
        if type(current) is type(original):
            assert current.graph_id == original.graph_id
        else:
            assert current.graph_id != original.graph_id
            assert result.find_by_id(original.graph_id) is None
            assert current.graph_id.removeprefix(current.type_name()).isdigit()


def test_preserved_operation_subclass_change_with_same_type_name_refreshes_id():
    class SpecializedAddition(Addition):
        __slots__ = ()

    rule = RewriteRule.from_builders(
        "test.specialized_addition",
        inputs=("a", "b"),
        pattern=lambda a, b: SpecializedAddition(a, b, name="root"),
        replacement=lambda a, b: Addition(a, b, name="root"),
        preserve={"root": "root"},
    )
    graph = rule.pattern
    original_id = graph.find_by_name("root")[0].graph_id

    result = graph.transform(rule)

    root = result.find_by_name("root")[0]
    assert type(root) is Addition
    assert root.graph_id != original_id
    assert result.find_by_id(original_id) is None
    assert root.graph_id.removeprefix("add").isdigit()
    assert result.evaluate(2, 3) == graph.evaluate(2, 3) == 5


def test_sharing_add40_reuses_sub31_and_assigns_a_subtraction_id():
    a, b, c = Input(), Input(), Input()
    shared = Subtraction(a, b, name="shared")
    shared.graph_id = "sub31"
    inner = Subtraction(c, a, name="inner")
    inner.graph_id = "sub19"
    consumer = Addition(inner, b, name="consumer")
    consumer.graph_id = "add40"
    graph = SFG([a, b, c], [Output(shared), Output(consumer)])
    assert type(graph.find_by_id("add40")) is Addition

    result = graph.transform("sharing", target="add40")

    shared = result.find_by_id("sub31")
    consumer = result.find_by_name("consumer")[0]
    assert type(consumer) is Subtraction
    assert consumer.graph_id.removeprefix("sub").isdigit()
    assert result.find_by_id("add40") is None
    assert result.find_by_id("sub19") is None
    assert consumer.input(0).connected_source is result.input_operations[2].output(0)
    assert consumer.input(1).connected_source is shared.output(0)
    assert len(shared.output(0).signals) == 2
    assert result.evaluate(2, 3, 7) == graph.evaluate(2, 3, 7) == [-1, 8]
