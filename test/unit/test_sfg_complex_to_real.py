"""Verify complex decompositions numerically and structurally."""

import apytypes as apy
import numpy as np
import pytest

from b_asic.core_operations import (
    MAD,
    MADS,
    Absolute,
    Addition,
    AddSub,
    Comparator,
    ComplexConjugate,
    Constant,
    ConstantMultiplication,
    Division,
    ImaginaryMultiplication,
    Max,
    Min,
    Multiplication,
    Negation,
    Reciprocal,
    ReciprocalSquareRoot,
    Shift,
    SquareRoot,
    Subtraction,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.operation import AbstractOperation, _ComplexPair
from b_asic.sfg import SFG
from b_asic.sfg_generators import block_cholesky_matrix_inverse, cholesky_matrix_inverse
from b_asic.special_operations import Delay, Input, MemoryRead, MemoryWrite, Output
from b_asic.types import GraphID
from b_asic.utility_operations import ComplexToReal, RealToComplex, Sink


def split(values):
    return [part for value in values for part in (value.real, value.imag)]


@pytest.mark.parametrize("operation_type", [Min, Max, Comparator])
def test_ordering_operations_reject_complex_conversion(operation_type):
    operation = operation_type()
    with pytest.raises(NotImplementedError, match=operation_type.__name__):
        operation.complex_to_real()
    a, b = Input(), Input()
    operation.input(0).connect(a)
    operation.input(1).connect(b)
    graph = SFG([a, b], [Output(port) for port in operation.outputs])
    graph_id = graph.find_by_type(operation_type)[0].graph_id
    for selector in (None, operation_type, graph_id):
        with pytest.raises(NotImplementedError, match=operation_type.__name__):
            graph.complex_to_real(operations=selector)


@pytest.mark.parametrize("operation_type", [Min, Max, Comparator])
def test_unselected_ordering_operations_are_preserved(operation_type):
    a, b = Input(), Input()
    operation = operation_type(a, b)
    graph = SFG([a, b], [Output(Multiplication(operation.output(0), b))])
    converted = graph.complex_to_real(operations=Multiplication)
    assert len(converted.find_by_type(operation_type)) == 1
    assert converted.evaluate(2, 3) == graph.evaluate(2, 3)


@pytest.mark.parametrize(("method", "count"), [("four", 4), ("three", 3)])
@pytest.mark.parametrize(
    "operation",
    [
        Multiplication(),
        MAD(),
        MAD(do_add=False),
        MADS(),
        MADS(is_add=False),
        MADS(do_addsub=False),
        MADS(is_add=False, do_addsub=False),
    ],
)
def test_complex_products(operation, method, count):
    operation = operation.copy()
    inputs = [Input() for _ in operation.inputs]
    for port, source in zip(operation.inputs, inputs, strict=True):
        port.connect(source)
    original = SFG(inputs, [Output(operation)])
    converted = original.complex_to_real(multiplication_method=method)

    assert len(converted.find_by_type(Multiplication)) == count
    rng = np.random.default_rng(1234)
    for _ in range(10):
        values = list(rng.normal(size=len(inputs)) + 1j * rng.normal(size=len(inputs)))
        assert converted.evaluate(*split(values)) == pytest.approx(
            split([original.evaluate(*values)])
        )
    assert original.input_count == len(inputs)
    assert original.output_count == 1


@pytest.mark.parametrize("method", ["three", "four"])
@pytest.mark.parametrize(
    ("operation", "values"),
    [
        (
            Addition(mul_j=True, in0_scale=1, in1_scale=2, out0_scale=1),
            [2 + 3j, 4 - 5j],
        ),
        (Subtraction(mul_j=True), [2 + 3j, 4 - 5j]),
        (AddSub(is_add=False, mul_j=True), [2 + 3j, 4 - 5j]),
        (Negation(), [2 + 3j]),
        (Shift(-2), [2 + 3j]),
        (ImaginaryMultiplication(), [2 + 3j]),
        (ComplexConjugate(), [2 + 3j]),
        (ConstantMultiplication(2 + 3j), [4 - 5j]),
        (ConstantMultiplication(3j), [4 - 5j]),
        (ConstantMultiplication(2), [4 - 5j]),
        (Reciprocal(), [2 + 3j]),
        (Reciprocal(), [0j]),
        (Division(), [2 + 3j, 4 - 5j]),
        (Division(), [2 + 3j, 0j]),
        (Absolute(), [-2 + 3j]),
        (SquareRoot(), [-2 + 3j]),
        (SquareRoot(), [-2 - 3j]),
        (SquareRoot(), [-4 + 0j]),
        (SquareRoot(), [0j]),
        (ReciprocalSquareRoot(), [-2 - 3j]),
        (ReciprocalSquareRoot(), [-4 + 0j]),
        (ReciprocalSquareRoot(), [0j]),
        (Constant(2 + 3j), []),
    ],
)
def test_core_operations(operation, values, method):
    converted = operation.complex_to_real(multiplication_method=method)
    expected = operation.evaluate(*values)
    actual = converted.evaluate(*split(values))
    assert actual == pytest.approx(split([expected]))
    assert all(not isinstance(value, complex) for value in actual)


@pytest.mark.parametrize(
    "operation_type", [Reciprocal, ReciprocalSquareRoot, SquareRoot, Absolute, Division]
)
def test_real_valued(operation_type):
    operation = operation_type(real_valued=True)
    values = [4 + 7j] * operation.input_count
    graph = operation.complex_to_real()
    assert operation.copy().real_valued is True
    assert graph.evaluate(*split(values)) == pytest.approx(
        split([operation.evaluate(*values)])
    )
    assert len(graph.find_by_type(Sink)) == operation.input_count
    assert graph.output_operations[1].input(0).connected_source.operation.value == 0
    assert len(graph.find_by_type(operation_type)) == 1


@pytest.mark.parametrize(
    "operation_type", [Reciprocal, ReciprocalSquareRoot, SquareRoot, Absolute]
)
def test_real_valued_apy_input(operation_type):
    value = apy.APyCFixed.from_complex(4 + 7j, int_bits=5, frac_bits=4)
    operation = operation_type(real_valued=True)
    assert operation.evaluate(value) == pytest.approx(operation.evaluate(4.0))


@pytest.mark.parametrize("split_io", [True, False])
def test_feedback_and_shared_sources(split_io):
    source = Input(name="x")
    delay = Delay(initial_value=2 + 3j)
    total = Addition(source, ConstantMultiplication(0.25 + 0.5j, delay))
    delay <<= total
    original = SFG([source], [Output(total), Output(delay)], name="feedback")
    converted = original.complex_to_real(
        multiplication_method="three", split_io=split_io
    )
    assert converted.name == original.name
    assert [op.name for op in converted.input_operations] == (
        ["x_real", "x_imag"] if split_io else ["x"]
    )
    original_delays, converted_delays = {}, {}
    for value in (1 + 2j, -3 + 1j, 2 - 4j, 0j):
        expected = original.evaluate_outputs(
            [value], results={}, delays=original_delays
        )
        actual = converted.evaluate_outputs(
            split([value]) if split_io else [value], results={}, delays=converted_delays
        )
        assert actual == pytest.approx(split(expected) if split_io else expected)


def test_nested_composite_and_sink():
    a, b = Input(), Input()
    butterfly = R2Butterfly(a, b)
    inner = SFG([a, b], [Output(butterfly.output(0)), Output(butterfly.output(1))])
    x, y = Input(), Input()
    nested = inner(x, y)
    Sink(nested.output(1))
    graph = SFG([x, y], [Output(nested.output(0))])
    converted = graph.complex_to_real()
    assert converted.evaluate(2, 3, 4, -5) == pytest.approx([6, -2])
    assert len(converted.find_by_type(Sink)) == 2
    assert not converted.find_by_type(SFG)


def test_invalid_multiplication_method():
    with pytest.raises(ValueError, match="multiplication_method"):
        Multiplication().complex_to_real(multiplication_method="invalid")


@pytest.mark.parametrize("split_io", [True, False])
def test_custom_hook_keyword_options(split_io):
    class CustomConjugate(ComplexConjugate):
        def _complex_to_real(self, inputs, sinks, **kwargs):
            assert kwargs["multiplication_method"] == "three"
            pairs = super()._complex_to_real(inputs, sinks, **kwargs)
            return [
                _ComplexPair(
                    ConstantMultiplication(kwargs["scale"], pair.re),
                    ConstantMultiplication(kwargs["scale"], pair.im),
                )
                for pair in pairs
            ]

    class Composite(AbstractOperation):
        def __init__(self):
            super().__init__(input_count=1, output_count=1)

        @classmethod
        def type_name(cls):
            return "custom_composite"

        def evaluate(self, a, data_type=None):
            return a.conjugate()

        def to_sfg(self):
            source = Input()
            return SFG([source], [Output(CustomConjugate(source))])

    for operation in (CustomConjugate(), Composite()):
        graph = operation.complex_to_real(
            multiplication_method="three", scale=2, split_io=split_io
        )
        if split_io:
            assert graph.evaluate(3, 4) == pytest.approx([6, -8])
        else:
            assert graph.evaluate(3 + 4j) == pytest.approx(6 - 8j)


@pytest.mark.parametrize("method", ["three", "four"])
def test_preserve_complex_interfaces(method):
    a, b = Input(name="a"), Input(name="b")
    graph = SFG(
        [a, b], [Output(Multiplication(a, b), name="product"), Output(a, name="a")]
    )
    converted = graph.complex_to_real(split_io=False, multiplication_method=method)
    assert converted.input_count == graph.input_count
    assert converted.output_count == graph.output_count
    assert [op.name for op in converted.input_operations] == ["a", "b"]
    assert [op.name for op in converted.output_operations] == ["product", "a"]
    assert len(converted.find_by_type(ComplexToReal)) == 2
    # The passthrough output no longer needs a split/join round trip.
    assert len(converted.find_by_type(RealToComplex)) == 1
    assert len(converted.find_by_type(Multiplication)) == (
        3 if method == "three" else 4
    )
    results = {}
    values = [2 + 3j, -4 + 5j]
    assert converted.evaluate_outputs(values, results=results) == pytest.approx(
        graph.evaluate_outputs(values)
    )
    for operation in converted.operations:
        if isinstance(operation, Input | Output | RealToComplex):
            continue
        for index in range(operation.output_count):
            assert not isinstance(
                results[operation.key(index, operation.graph_id)], complex
            )


def test_preserve_memory_interfaces():
    a = MemoryRead(3, memory_name="A", name="a", latency=2)
    b = MemoryRead(7, memory_name="B", name="b", latency=1)
    graph = SFG(
        [a, b],
        [
            MemoryWrite(9, Multiplication(a, b), memory_name="C", name="product"),
            MemoryWrite(2, a, memory_name="D", name="copy"),
        ],
    )
    converted = graph.complex_to_real(split_io=False)
    assert [
        (type(op), op.address, op.memory_name, op.name, op.latency)
        for op in converted.input_operations
    ] == [(MemoryRead, 3, "A", "a", 2), (MemoryRead, 7, "B", "b", 1)]
    assert [
        (type(op), op.address, op.memory_name, op.name)
        for op in converted.output_operations
    ] == [(MemoryWrite, 9, "C", "product"), (MemoryWrite, 2, "D", "copy")]
    assert converted.evaluate(2 + 3j, -4 + 5j) == pytest.approx(
        graph.evaluate(2 + 3j, -4 + 5j)
    )


def test_preserve_constant_interface():
    graph = Constant(2 + 3j).complex_to_real(split_io=False)
    assert graph.input_count == 0
    assert graph.output_count == 1
    assert graph.evaluate() == 2 + 3j


def test_invalid_split_io():
    with pytest.raises(TypeError, match="split_io"):
        Multiplication().complex_to_real(split_io="false")


def product_chain():
    a, b = Input(name="a"), Input(name="b")
    first = Multiplication(a, b, name="first")
    second = Multiplication(first, b, name="second")
    graph = SFG([a, b], [Output(second)])
    ids = {op.name: op.graph_id for op in graph.find_by_type(Multiplication)}
    return graph, ids


@pytest.mark.parametrize("selector_kind", ["type", "types", "id", "ids", "mixed"])
def test_operation_selectors(selector_kind):
    graph, ids = product_chain()
    selectors = {
        "type": Multiplication,
        "types": iter([Multiplication]),
        "id": GraphID(ids["first"]),
        "ids": iter([ids["first"], ids["second"]]),
        "mixed": (ids["first"], Multiplication),
    }
    converted = graph.complex_to_real(
        selectors[selector_kind], multiplication_method="three"
    )
    assert converted.input_count == 2
    assert converted.output_count == 1
    assert converted.evaluate(2 + 3j, -4 + 5j) == pytest.approx(
        graph.evaluate(2 + 3j, -4 + 5j)
    )
    if selector_kind == "id":
        assert len(converted.find_by_type(Multiplication)) == 4
        assert converted.find_by_id(ids["second"]).name == "second"
    else:
        assert len(converted.find_by_type(Multiplication)) == 6
    assert len(graph.find_by_type(Multiplication)) == 2


def test_successive_conversion_settings_and_boundary_cancellation():
    graph, ids = product_chain()
    first = graph.complex_to_real(ids["first"], multiplication_method="three")
    assert isinstance(first.find_by_id(ids["second"]), Multiplication)
    converted = first.complex_to_real(ids["second"], multiplication_method="four")
    assert len(converted.find_by_type(Multiplication)) == 7
    assert len(converted.find_by_type(ComplexToReal)) == 2
    assert len(converted.find_by_type(RealToComplex)) == 1
    assert converted.evaluate(2 + 3j, -4 + 5j) == pytest.approx(
        graph.evaluate(2 + 3j, -4 + 5j)
    )


def test_empty_selector_preserves_operations_and_interfaces():
    graph, ids = product_chain()
    converted = graph.complex_to_real(iter([]))
    assert converted.operation_counter() == graph.operation_counter()
    assert {op.graph_id for op in converted.operations} == {
        op.graph_id for op in graph.operations
    }
    assert all(
        isinstance(converted.find_by_id(graph_id), Multiplication)
        for graph_id in ids.values()
    )


@pytest.mark.parametrize("operation_type", [Addition, Delay])
def test_selective_feedback(operation_type):
    source = Input()
    delay = Delay(initial_value=2 + 3j)
    total = Addition(source, ConstantMultiplication(0.25 + 0.5j, delay))
    delay <<= total
    graph = SFG([source], [Output(total), Output(delay)])
    converted = graph.complex_to_real(operation_type)
    assert len(converted.find_by_type(Delay)) == (2 if operation_type is Delay else 1)
    original_delays, converted_delays = {}, {}
    for value in (1 + 2j, -3 + 1j, 2 - 4j, 0j):
        expected = graph.evaluate_outputs([value], results={}, delays=original_delays)
        actual = converted.evaluate_outputs(
            [value], results={}, delays=converted_delays
        )
        assert actual == pytest.approx(expected)


def test_unselected_custom_primitive_does_not_need_a_conversion_hook():
    class CustomSquare(AbstractOperation):
        def __init__(self):
            super().__init__(input_count=1, output_count=1)

        @classmethod
        def type_name(cls):
            return "custom_square"

        def evaluate(self, a, data_type=None):
            return a * a

    a, b = Input(), Input()
    custom = CustomSquare()
    custom.input(0).connect(a)
    graph = SFG([a, b], [Output(Multiplication(custom, b))])
    converted = graph.complex_to_real(Multiplication)
    assert len(converted.find_by_type(CustomSquare)) == 1
    assert converted.evaluate(2 + 3j, 4 - 5j) == pytest.approx(
        graph.evaluate(2 + 3j, 4 - 5j)
    )


@pytest.mark.parametrize("selector", [42, object, [Multiplication, 42]])
def test_invalid_operation_selector(selector):
    graph, _ = product_chain()
    with pytest.raises(TypeError, match="Operation types or GraphIDs"):
        graph.complex_to_real(selector)


def test_unknown_graph_id_selector():
    graph, _ = product_chain()
    with pytest.raises(ValueError, match="not_found"):
        graph.complex_to_real("not_found")


@pytest.mark.parametrize("operation_type", [Input, Output])
def test_select_interfaces_explicitly(operation_type):
    graph, ids = product_chain()
    converted = graph.complex_to_real(operation_type)
    assert all(
        isinstance(converted.find_by_id(graph_id), Multiplication)
        for graph_id in ids.values()
    )
    if operation_type is Input:
        assert (converted.input_count, converted.output_count) == (4, 1)
        actual = converted.evaluate(2, 3, -4, 5)
        expected = graph.evaluate(2 + 3j, -4 + 5j)
    else:
        assert (converted.input_count, converted.output_count) == (2, 2)
        actual = converted.evaluate(2 + 3j, -4 + 5j)
        expected = split([graph.evaluate(2 + 3j, -4 + 5j)])
    assert actual == pytest.approx(expected)


def test_select_nested_operation_by_hierarchical_id():
    inner, ids = product_chain()
    a, b = Input(), Input()
    nested = inner(a, b)
    graph = SFG([a, b], [Output(nested)])
    prefix = graph.find_by_type(SFG)[0].graph_id + "."
    converted = graph.complex_to_real(
        prefix + ids["first"], multiplication_method="three"
    )
    assert len(converted.find_by_type(Multiplication)) == 4
    assert converted.find_by_id(prefix + ids["second"]).name == "second"
    assert converted.evaluate(2 + 3j, -4 + 5j) == pytest.approx(
        graph.evaluate(2 + 3j, -4 + 5j)
    )


@pytest.mark.parametrize("selector_kind", ["composite_id", "nested_type"])
def test_select_nested_operations(selector_kind):
    inner, _ = product_chain()
    a, b = Input(), Input()
    graph = SFG([a, b], [Output(inner(a, b))])
    selector = (
        graph.find_by_type(SFG)[0].graph_id
        if selector_kind == "composite_id"
        else Multiplication
    )
    converted = graph.complex_to_real(selector, multiplication_method="three")
    assert len(converted.find_by_type(Multiplication)) == 6
    assert converted.evaluate(2 + 3j, -4 + 5j) == pytest.approx(
        graph.evaluate(2 + 3j, -4 + 5j)
    )


def test_join_split_cancellation_retains_complex_fanout():
    real, imag = Input(), Input()
    joiner = RealToComplex(real, imag)
    splitter = ComplexToReal(joiner)
    graph = SFG(
        [real, imag],
        [Output(splitter.output(0)), Output(splitter.output(1)), Output(joiner)],
    )
    converted = graph.complex_to_real([])
    assert not converted.find_by_type(ComplexToReal)
    assert len(converted.find_by_type(RealToComplex)) == 1
    assert converted.evaluate(2, 3) == [2, 3, 2 + 3j]


@pytest.mark.parametrize("swap", [False, True])
def test_split_join_cancellation_respects_ports_and_real_fanout(swap):
    source = Input()
    splitter = ComplexToReal(source)
    joiner = RealToComplex(splitter.output(int(swap)), splitter.output(int(not swap)))
    Sink(splitter.output(1))
    graph = SFG([source], [Output(joiner), Output(splitter.output(0))])
    converted = graph.complex_to_real([])
    assert len(converted.find_by_type(ComplexToReal)) == 1
    assert len(converted.find_by_type(RealToComplex)) == int(swap)
    assert len(converted.find_by_type(Sink)) == 1
    assert converted.evaluate(2 + 3j) == [3 + 2j if swap else 2 + 3j, 2]


@pytest.mark.parametrize(
    "generator", [cholesky_matrix_inverse, block_cholesky_matrix_inverse]
)
@pytest.mark.parametrize("method", ["three", "four"])
@pytest.mark.parametrize("pe", [None, "addsub", "mads"])
@pytest.mark.parametrize("mode", ["eqs", "mult"])
@pytest.mark.parametrize("split_io", [True, False])
def test_cholesky_inverse_conversion(generator, method, pe, mode, split_io):
    graph = generator(N=4, mode=mode, pe=pe, mem=not split_io)
    roots = graph.find_by_type(ReciprocalSquareRoot)
    assert len(roots) == 4
    assert all(op.real_valued for op in roots)
    converted = graph.complex_to_real(multiplication_method=method, split_io=split_io)
    rng = np.random.default_rng(42)
    factor = rng.normal(size=(4, 4))
    matrix = factor @ factor.T + np.eye(4)
    lower = np.tril_indices(4)
    packed = matrix[lower].astype(complex)
    expected = np.linalg.inv(matrix)[lower]
    actual = converted.evaluate(*(split(packed) if split_io else packed))
    assert actual == pytest.approx(split(expected) if split_io else expected, abs=1e-12)
    if not split_io:
        assert len(converted.find_by_type(MemoryRead)) == 10
        assert len(converted.find_by_type(MemoryWrite)) == 10
