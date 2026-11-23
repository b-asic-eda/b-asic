"""Generic port-aware subgraph matching and replacement."""

import pytest

from b_asic import (
    SFG,
    Addition,
    Constant,
    ConstantMultiplication,
    Input,
    Multiplication,
    Negation,
    Output,
    RewriteRegistry,
    RewriteRule,
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
    root = rewritten.find_by_id(original_root.graph_id)
    product = rewritten.find_by_id(original_product.graph_id)
    assert type(root) is Subtraction
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

    root = rewritten.find_by_id(original_root.graph_id)
    product = rewritten.find_by_id(original_product.graph_id)
    assert type(root) is Addition
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
    root = result.find_by_id(old_root.graph_id)
    inner = result.find_by_id(old_inner.graph_id)
    product = result.find_by_id(old_product.graph_id)
    assert isinstance(root, (Addition, Subtraction))
    assert type(root) is replacement_type
    assert type(inner) is Addition
    assert type(product) is Multiplication
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
