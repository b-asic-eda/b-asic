"""Algebraic conversion from complex signals to pairs of real signals."""

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, cast

from b_asic.core_operations import (
    Absolute,
    Addition,
    Constant,
    Division,
    Min,
    Multiplication,
    Negation,
    Reciprocal,
    RightShift,
    SquareRoot,
    Subtraction,
)
from b_asic.operation import Operation, _ComplexPair
from b_asic.port import OutputPort, SignalSourceProvider
from b_asic.special_operations import Input, Output
from b_asic.types import GraphID
from b_asic.utility_operations import ComplexToReal, RealToComplex, Sink

if TYPE_CHECKING:
    from b_asic.sfg import SFG


def _product(left: _ComplexPair, right: _ComplexPair, method: str) -> _ComplexPair:
    a, b = left.re, left.im
    c, d = right.re, right.im
    if method == "threealt":
        k1 = Multiplication(d, Addition(a, b))
        k2 = Multiplication(a, Addition(c, d))
        k3 = Multiplication(b, Subtraction(c, d))
        return _ComplexPair(Subtraction(k2, k1), Addition(k1, k3))
    ac, bd = Multiplication(a, c), Multiplication(b, d)
    real = Subtraction(ac, bd)
    imag: SignalSourceProvider
    if method == "three":
        imag = Subtraction(
            Multiplication(Addition(a, b), Addition(c, d)), Addition(ac, bd)
        )
    else:
        imag = Addition(Multiplication(a, d), Multiplication(b, c))
    return _ComplexPair(real, imag)


def _safe_norm(norm: SignalSourceProvider) -> SignalSourceProvider:
    """Keep a squared norm unchanged except for replacing zero with one."""
    # Division returns infinity at zero. This gives 1 for nonzero norm and
    # 0 at zero, allowing the imaginary result to remain zero at the origin.
    nonzero = Reciprocal(Division(norm, norm), real_valued=True)
    return Addition(norm, Subtraction(Constant(1), nonzero))


def _reciprocal(value: _ComplexPair) -> _ComplexPair:
    a, b = value.re, value.im
    norm = Addition(Multiplication(a, a), Multiplication(b, b))
    return _ComplexPair(
        Division(a, norm, real_valued=True),
        Negation(Division(b, _safe_norm(norm), real_valued=True)),
    )


def _square_root(value: _ComplexPair) -> _ComplexPair:
    a, b = value.re, value.im
    radius = SquareRoot(
        Addition(Multiplication(a, a), Multiplication(b, b)), real_valued=True
    )
    real = SquareRoot(RightShift(1, Addition(radius, a)), real_valued=True)
    magnitude = SquareRoot(RightShift(1, Subtraction(radius, a)), real_valued=True)
    # b / |b| is +/-1, or infinity at zero: clamp to +1 on the real axis
    # to select the principal square root, including negative real inputs.
    sign = Min(Constant(1), Division(b, Absolute(b, real_valued=True)))
    return _ComplexPair(real, Multiplication(sign, magnitude))


def _real_valued(
    operation: Operation, inputs: Sequence[_ComplexPair], sinks: list[Sink]
) -> list[_ComplexPair]:
    real_op = cast(Operation, operation.copy())
    for port, pair in zip(real_op.inputs, inputs, strict=True):
        port.connect(pair.re)
        sinks.append(Sink(pair.im))
    return [_ComplexPair(port, Constant(0)) for port in real_op.outputs]


def _componentwise(
    operation: Operation, inputs: Sequence[_ComplexPair], sinks: list[Sink]
) -> list[_ComplexPair]:
    result = []
    for parts in ([pair.re for pair in inputs], [pair.im for pair in inputs]):
        replacement = cast(Operation, operation.copy())
        for port, value in zip(replacement.inputs, parts, strict=True):
            port.connect(value)
        result.append(replacement)
    return [_ComplexPair(*result)]


def _select_operations(
    sfg: "SFG",
    operations: type[Operation] | GraphID | Iterable[type[Operation] | GraphID] | None,
) -> tuple["SFG", set[GraphID]]:
    """Resolve selectors before flattening, retaining hierarchical graph IDs."""
    from b_asic.sfg import SFG  # noqa: PLC0415

    if operations is None:
        graph = sfg.flatten()
        return graph, {op.graph_id for op in graph.operations}
    if isinstance(operations, str | type):
        selectors = [operations]
    elif isinstance(operations, Iterable):
        selectors = list(operations)
    else:
        raise TypeError("operations must contain Operation types or GraphIDs")
    for selector in selectors:
        if not isinstance(selector, str) and not (
            isinstance(selector, type) and issubclass(selector, Operation)
        ):
            raise TypeError("operations must contain Operation types or GraphIDs")
    types = tuple(item for item in selectors if isinstance(item, type))
    ids = {item for item in selectors if isinstance(item, str)}
    found = set()
    selected: set[GraphID] = set()

    def visit(graph: SFG, prefix: str = "", inherited: bool = False) -> None:
        for operation in graph.operations:
            local_id = operation.graph_id
            graph_id = GraphID(prefix + local_id)
            matches = ids & {graph_id}
            found.update(matches)
            convert = inherited or bool(matches) or isinstance(operation, types)
            operation.graph_id = graph_id
            if isinstance(operation, SFG):
                visit(operation, graph_id + ".", convert)
            elif convert:
                selected.add(graph_id)

    graph = sfg()
    visit(graph)
    if missing := ids - found:
        raise ValueError(f"No operation with GraphID {sorted(missing)!r} found in SFG")
    return graph.flatten(), selected


def _detach_inputs(operation: Operation) -> None:
    for port in operation.inputs:
        for signal in list(port.signals):
            signal.remove_source()
            signal.remove_destination()


def _remove_inverse_pairs(graph: "SFG") -> "SFG":
    """Cancel split/join pairs in both directions without disturbing fanout."""
    while True:
        changed = False
        for splitter in graph.find_by_type(ComplexToReal):
            source = splitter.input(0).connected_source
            if source is None or not isinstance(source.operation, RealToComplex):
                continue
            joiner = source.operation
            parts = [port.connected_source for port in joiner.inputs]
            if any(part is None for part in parts):
                continue
            for port, part in zip(splitter.outputs, parts, strict=True):
                for signal in list(port.signals):
                    signal.set_source(part)
            _detach_inputs(splitter)
            if not joiner.output(0).signals:
                _detach_inputs(joiner)
            changed = True
        for joiner in graph.find_by_type(RealToComplex):
            real = joiner.input(0).connected_source
            imag = joiner.input(1).connected_source
            if (
                real is None
                or imag is None
                or not isinstance(real.operation, ComplexToReal)
                or real.operation is not imag.operation
                or real.index != 0
                or imag.index != 1
            ):
                continue
            splitter = real.operation
            source = splitter.input(0).connected_source
            if source is None:
                continue
            for signal in list(joiner.output(0).signals):
                signal.set_source(source)
            _detach_inputs(joiner)
            if not any(port.signals for port in splitter.outputs):
                _detach_inputs(splitter)
            changed = True
        # Different selected regions can share an existing boundary. Reuse
        # identical converters, including those inserted by earlier calls.
        for operation_type in (ComplexToReal, RealToComplex):
            shared = {}
            for operation in graph.find_by_type(operation_type):
                key = tuple(port.connected_source for port in operation.inputs)
                if any(source is None for source in key):
                    continue
                if key not in shared:
                    shared[key] = operation
                    continue
                for port, kept in zip(
                    operation.outputs, shared[key].outputs, strict=True
                ):
                    for signal in list(port.signals):
                        signal.set_source(kept)
                _detach_inputs(operation)
                changed = True
        if not changed:
            return graph
        graph = graph()


def _preserve_ids(
    roots: Sequence[Operation], preserved: set[Operation], used: set[GraphID]
) -> None:
    """Give new nodes unique IDs so they cannot displace unselected operations."""
    from b_asic.sfg import SFG  # noqa: PLC0415

    pending = list(roots)
    visited = set()
    index = 0
    while pending:
        operation = pending.pop()
        if operation in visited:
            continue
        visited.add(operation)
        if operation not in preserved:
            graph_id = GraphID(f"real_{operation.type_name()}{index}")
            while graph_id in used:
                index += 1
                graph_id = GraphID(f"real_{operation.type_name()}{index}")
            operation.graph_id = graph_id
            used.add(graph_id)
            index += 1
        pending.extend(
            source.operation
            for port in operation.inputs
            if (source := port.connected_source) is not None
        )
        for port in operation.outputs:
            pending.extend(
                signal.destination.operation
                for signal in port.signals
                if signal.destination is not None
            )
        if isinstance(operation, SFG):
            pending.extend(operation.operations)


def complex_to_real(
    sfg: "SFG",
    operations: type[Operation]
    | GraphID
    | Iterable[type[Operation] | GraphID]
    | None = None,
    **kwargs,
) -> "SFG":
    """Create output representations before wiring, permitting mixed domains and feedback."""
    from b_asic.sfg import SFG  # noqa: PLC0415

    multiplication_method = kwargs.get("multiplication_method", "four")
    if multiplication_method not in ("four", "three", "threealt"):
        raise ValueError('multiplication_method must be "four", "three", or "threealt"')
    split_io = kwargs.get("split_io", True)
    if not isinstance(split_io, bool):
        raise TypeError("split_io must be a bool")
    graph, selected = _select_operations(sfg, operations)
    sources: dict[OutputPort, OutputPort | _ComplexPair] = {}
    placeholders: dict[Operation, list[Input] | list[_ComplexPair]] = {}
    inputs: list[Input] = []
    output_by_operation: dict[Operation, list[Output]] = {}
    sinks: list[Sink] = []
    preserved: set[Operation] = set()
    for input_operation in graph.input_operations:
        original_input = cast(Input, input_operation)
        if split_io and original_input.graph_id in selected:
            real_input = Input(name=f"{original_input.name}_real", real_valued=True)
            imag_input = Input(name=f"{original_input.name}_imag", real_valued=True)
            inputs.extend((real_input, imag_input))
            if original_input.real_valued:
                sinks.append(Sink(imag_input))
                input_pair = _ComplexPair(real_input, Constant(0))
            else:
                input_pair = _ComplexPair(real_input, imag_input)
            sources[original_input.output(0)] = input_pair
        else:
            input_replacement = cast(Input, original_input.copy())
            preserved.add(input_replacement)
            inputs.append(input_replacement)
            if original_input.graph_id in selected and original_input.real_valued:
                splitter = ComplexToReal(input_replacement)
                sinks.append(Sink(splitter.output(1)))
                sources[original_input.output(0)] = _ComplexPair(
                    splitter.output(0), Constant(0)
                )
            else:
                sources[original_input.output(0)] = input_replacement.output(0)
    for operation in graph.operations:
        if isinstance(operation, Input):
            continue
        convert = operation.graph_id in selected
        if isinstance(operation, Output):
            convert = convert and (split_io or bool(operation.real_valued))
        if convert:
            local_pairs = [_ComplexPair(Input(), Input()) for _ in operation.inputs]
            placeholders[operation] = local_pairs
            if isinstance(operation, Output):
                pair = local_pairs[0]
                if operation.real_valued:
                    sinks.append(Sink(pair.im))
                    pair = _ComplexPair(pair.re, Constant(0))
                if split_io:
                    output_by_operation[operation] = [
                        Output(value, name=f"{operation.name}_{part}", real_valued=True)
                        for value, part in zip(pair, ("real", "imag"), strict=True)
                    ]
                else:
                    output_replacement = cast(Output, operation.copy())
                    preserved.add(output_replacement)
                    output_replacement.input(0).connect(RealToComplex(*pair))
                    output_by_operation[operation] = [output_replacement]
            else:
                pairs = operation._complex_to_real(local_pairs, sinks, **kwargs)
                sources.update(zip(operation.outputs, pairs, strict=True))
        else:
            replacement = cast(Operation, operation.copy())
            preserved.add(replacement)
            local_inputs = [Input() for _ in operation.inputs]
            placeholders[operation] = local_inputs
            for port, value in zip(replacement.inputs, local_inputs, strict=True):
                port.connect(value)
            if isinstance(operation, Output):
                output_by_operation[operation] = [cast(Output, replacement)]
            else:
                sources.update(zip(operation.outputs, replacement.outputs, strict=True))
                if isinstance(replacement, Sink):
                    sinks.append(replacement)
    outputs = [out for op in graph.output_operations for out in output_by_operation[op]]
    aliases: dict[OutputPort, OutputPort] = {}
    splitters: dict[OutputPort, _ComplexPair] = {}
    joiners: dict[_ComplexPair, OutputPort] = {}
    for operation, local_inputs in placeholders.items():
        for port, placeholder in zip(operation.inputs, local_inputs, strict=True):
            source = port.connected_source
            if source is None:
                raise ValueError("Missing source in signal.")
            value = sources[source]
            if isinstance(placeholder, _ComplexPair):
                if not isinstance(value, _ComplexPair):
                    if value not in splitters:
                        splitter = ComplexToReal(value)
                        splitters[value] = _ComplexPair(
                            splitter.output(0), splitter.output(1)
                        )
                    value = splitters[value]
                for part, source_part in zip(placeholder, value, strict=True):
                    aliases[part.source] = source_part.source
            else:
                if isinstance(value, _ComplexPair):
                    if value not in joiners:
                        joiners[value] = RealToComplex(value.re, value.im).output(0)
                    value = joiners[value]
                aliases[placeholder.output(0)] = value
    for placeholder, source in aliases.items():
        visited = {placeholder}
        while source in aliases:
            if source in visited:
                raise ValueError("Direct feedback loop through complex-to-real wiring.")
            visited.add(source)
            source = aliases[source]
        for signal in list(placeholder.signals):
            signal.set_source(source)
    if operations is not None:
        _preserve_ids(
            [*inputs, *outputs, *sinks],
            preserved,
            {op.graph_id for op in graph.operations},
        )
    result = SFG(inputs, outputs, name=sfg.name)
    for sink in sinks:
        if sink not in result._original_components_to_new:
            result._add_operation_connected_tree_copy(sink)
    return _remove_inverse_pairs(result.flatten())
