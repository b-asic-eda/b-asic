"""Directed replacement of combinational SFG regions using named templates."""

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import permutations, product
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

import networkx as nx
import numpy as np

from b_asic.core_operations import (
    Addition,
    ComplexConjugate,
    Constant,
    ConstantMultiplication,
    ImaginaryMultiplication,
    LeftShift,
    Multiplication,
    Negation,
    RightShift,
    Shift,
    Subtraction,
)
from b_asic.operation import Operation, _ComplexPair
from b_asic.port import OutputPort, SignalSourceProvider
from b_asic.signal import Signal
from b_asic.special_operations import Compression, Delay, Expansion, Input, Output
from b_asic.types import GraphID

if TYPE_CHECKING:
    from b_asic.sfg import SFG, OpSpecifier

__all__ = [
    "RewriteMatch",
    "RewriteRegistry",
    "RewriteRule",
    "available_rewrites",
    "get_rewrite",
    "register_rewrite",
]


def _equal(left: Any, right: Any) -> bool:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return left.keys() == right.keys() and all(
            _equal(value, right[key]) for key, value in left.items()
        )
    if isinstance(left, (list, tuple)) and type(left) is type(right):
        return len(left) == len(right) and all(
            _equal(a, b) for a, b in zip(left, right, strict=True)
        )
    try:
        return bool(np.all(left == right))
    except (TypeError, ValueError):
        return False


def _boundaries(operations: Sequence[Operation], prefix: str) -> dict[str, Operation]:
    result = {}
    for index, operation in enumerate(operations):
        name = operation.name or f"{prefix}{index}"
        if name in result:
            raise ValueError(f"Duplicate boundary name {name!r}")
        result[name] = operation
    return result


def _nodes(graph: "SFG") -> dict[str, Operation]:
    result = {}
    for operation in dict.fromkeys(graph.operations):
        if isinstance(operation, (Input, Output)):
            continue
        alias = operation.name or operation.graph_id
        if alias in result:
            raise ValueError(f"Duplicate template operation name {alias!r}")
        result[alias] = operation
    return result


def _network(operations: Iterable[Operation]) -> nx.MultiDiGraph:
    result = nx.MultiDiGraph()
    for operation in operations:
        result.add_node(operation, operation=operation)
    for operation in result:
        for port in operation.inputs:
            source = port.connected_source
            if source is not None and source.operation in result:
                result.add_edge(
                    source.operation,
                    operation,
                    source=source.index,
                    # Actual input positions and allowed swaps are bound later.
                    destination=-1
                    if type(operation) in (Addition, Multiplication)
                    else port.index,
                )
    return result


def _validate_template(graph: "SFG", *, pattern: bool) -> None:
    from b_asic.sfg import SFG  # noqa: PLC0415

    if not isinstance(graph, SFG):
        raise TypeError("Rewrite templates must be SFGs")
    nodes = _nodes(graph)
    if any(
        isinstance(op, (Delay, Compression, Expansion, SFG)) for op in nodes.values()
    ):
        raise ValueError(
            "Rewrite templates must be combinational and single-rate; nested SFGs are boundaries"
        )
    network = _network(nodes.values())
    if not nx.is_directed_acyclic_graph(network):
        raise ValueError("Rewrite templates cannot contain feedback")
    if pattern and (
        not nodes
        or not nx.is_weakly_connected(
            _network([*graph.input_operations, *nodes.values()])
        )
    ):
        raise ValueError(
            "A rewrite pattern must contain a connected region of operations"
        )
    _boundaries(graph.input_operations, "in")
    _boundaries(graph.output_operations, "out")
    if not graph.output_operations:
        raise ValueError("Rewrite templates must have an output")
    output_sources = []
    live = set()
    pending = []
    for output in graph.output_operations:
        source = output.input(0).connected_source
        if source is None:
            raise ValueError("Template outputs must be connected")
        if pattern and source.operation not in nodes.values():
            raise ValueError("Pattern outputs must originate from matched operations")
        output_sources.append(source)
        pending.append(source.operation)
    if pattern and len(set(output_sources)) != len(output_sources):
        raise ValueError("Pattern outputs must identify distinct source ports")
    while pending:
        operation = pending.pop()
        if operation in live:
            continue
        live.add(operation)
        for port in operation.inputs:
            source = port.connected_source
            if source is None:
                raise ValueError("Template inputs must be connected")
            pending.append(source.operation)
    if any(operation not in live for operation in nodes.values()):
        raise ValueError("All template operations must feed a declared output")
    if pattern and any(
        not any(
            signal.destination is not None
            and signal.destination.operation in nodes.values()
            for signal in operation.output(0).signals
        )
        for operation in graph.input_operations
    ):
        raise ValueError("Every pattern input must feed a matched operation")


def _build_template(inputs: Sequence[str], builder: Callable[..., Any]) -> "SFG":
    from b_asic.sfg import SFG  # noqa: PLC0415

    arguments = [Input(name) for name in inputs]
    value = builder(*arguments)
    if isinstance(value, SFG):
        result = cast(SFG, value.copy())
        if result.input_count != len(inputs):
            raise ValueError("Builder SFG has the wrong input count")
        for operation, name in zip(result.input_operations, inputs, strict=True):
            operation.name = name
        return result
    if isinstance(value, SignalSourceProvider):
        outputs = {"out0": value}
    elif isinstance(value, Mapping):
        outputs = dict(value)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        outputs = {f"out{index}": source for index, source in enumerate(value)}
    else:
        raise TypeError(
            "Builders must return a signal source, sequence, mapping, or SFG"
        )
    if any(
        not isinstance(name, str) or not isinstance(source, SignalSourceProvider)
        for name, source in outputs.items()
    ):
        raise TypeError("Builder outputs require string names and signal sources")
    return SFG(
        arguments, [Output(source, name=name) for name, source in outputs.items()]
    )


@dataclass(frozen=True, init=False, eq=False)
class RewriteRule:
    """
    A directed, guarded replacement of a combinational SFG region.

    Input/output names identify boundary ports, with unnamed ports falling back
    to ``in0``, ``out0``, etc. Internal operation names identify template nodes;
    unnamed operations use their template graph IDs. Names and timing do not
    constrain matching. Types, port counts, computational parameters, and port
    connections match exactly by default, including ``real_valued`` settings.
    Multiplication inputs match in either order, as do Addition inputs with
    equal input scales and ``mul_j=False``.

    ``preserve`` maps pattern aliases to replacement aliases whose names,
    execution times, and port latency offsets should survive. Graph IDs survive
    only when the operation type is unchanged; type changes receive fresh IDs.
    Parameters come from the replacement. ``node_match(pattern, candidate)``
    may customize parameter matching, and ``condition(match)`` may reject
    complete matches.
    A replacement factory receives the match and must return an independent
    SFG with the same named boundary. Callbacks must not mutate the host graph.
    """

    name: str
    anchor: str
    preserve: Mapping[str, str]
    condition: "Callable[[RewriteMatch], bool] | None"
    node_match: Callable[[Operation, Operation], bool] | None
    _pattern: "SFG" = field(repr=False)
    _replacement: "SFG | Callable[[RewriteMatch], SFG]" = field(repr=False)

    def __init__(
        self,
        name: str,
        pattern: "SFG",
        replacement: "SFG | Callable[[RewriteMatch], SFG]",
        *,
        anchor: str | None = None,
        preserve: Mapping[str, str] | None = None,
        condition: "Callable[[RewriteMatch], bool] | None" = None,
        node_match: Callable[[Operation, Operation], bool] | None = None,
    ) -> None:
        from b_asic.sfg import SFG  # noqa: PLC0415

        if not isinstance(name, str) or not name.strip():
            raise ValueError("Rewrite rules require a nonempty name")
        _validate_template(pattern, pattern=True)
        template = cast(SFG, pattern.copy())
        nodes = _nodes(template)
        if anchor is None:
            source = template.output_operations[0].input(0).connected_source
            anchor = next(
                (
                    alias
                    for alias, operation in nodes.items()
                    if source is not None and operation is source.operation
                ),
                next(iter(nodes)),
            )
        if anchor not in nodes:
            raise ValueError(f"Unknown pattern anchor {anchor!r}")
        correspondence = dict(preserve or {})
        if any(alias not in nodes for alias in correspondence):
            raise ValueError("Preserved pattern nodes must exist")
        if len(set(correspondence.values())) != len(correspondence):
            raise ValueError("Preserved replacement nodes must be distinct")
        if isinstance(replacement, SFG):
            _validate_replacement(template, replacement, correspondence)
            replacement = cast(SFG, replacement.copy())
        elif not callable(replacement):
            raise TypeError("replacement must be an SFG or a factory")
        if condition is not None and not callable(condition):
            raise TypeError("condition must be callable")
        if node_match is not None and not callable(node_match):
            raise TypeError("node_match must be callable")
        for key, value in {
            "name": name,
            "anchor": anchor,
            "preserve": MappingProxyType(correspondence),
            "condition": condition,
            "node_match": node_match,
            "_pattern": template,
            "_replacement": replacement,
        }.items():
            object.__setattr__(self, key, value)

    @classmethod
    def from_builders(
        cls,
        name: str,
        *,
        inputs: Sequence[str],
        pattern: Callable[..., Any],
        replacement: Callable[..., Any],
        **kwargs: Any,
    ) -> "RewriteRule":
        """Build both templates using fresh named Input placeholders."""
        if isinstance(inputs, str) or any(
            not isinstance(name, str) or not name for name in inputs
        ):
            raise TypeError("inputs must be a sequence of nonempty names")
        if len(set(inputs)) != len(inputs):
            raise ValueError("Input placeholder names must be distinct")
        return cls(
            name,
            _build_template(inputs, pattern),
            _build_template(inputs, replacement),
            **kwargs,
        )

    @property
    def pattern(self) -> "SFG":
        """Return a disconnected copy of the pattern template."""
        return cast("SFG", self._pattern.copy())

    def build_replacement(self, match: "RewriteMatch | None" = None) -> "SFG":
        """Return an independent replacement for preview or application."""
        from b_asic.sfg import SFG  # noqa: PLC0415

        if isinstance(self._replacement, SFG):
            template = self._replacement
        else:
            if match is None or match.rule is not self:
                raise ValueError("A replacement factory requires a match for this rule")
            template = self._replacement(match)
        _validate_replacement(self._pattern, template, self.preserve)
        return cast(SFG, template.copy())


@dataclass(frozen=True, eq=False)
class RewriteMatch:
    """An inspectable match belonging to one specific, unchanged host graph."""

    rule: RewriteRule
    operations: Mapping[str, Operation]
    inputs: Mapping[str, OutputPort]
    outputs: Mapping[str, OutputPort]
    _input_indices: Mapping[str, tuple[int, ...]] = field(repr=False)
    _graph: "SFG" = field(repr=False)
    _snapshot: Any = field(repr=False)

    @property
    def anchor(self) -> Operation:
        """Return the matched anchor operation."""
        return self.operations[self.rule.anchor]


def _validate_replacement(
    pattern: "SFG", replacement: "SFG", preserve: Mapping[str, str]
) -> None:
    _validate_template(replacement, pattern=False)
    for attribute, prefix in (("input_operations", "in"), ("output_operations", "out")):
        if (
            _boundaries(getattr(pattern, attribute), prefix).keys()
            != _boundaries(getattr(replacement, attribute), prefix).keys()
        ):
            raise ValueError("Replacement must preserve named input/output boundaries")
    old, new = _nodes(pattern), _nodes(replacement)
    for source, destination in preserve.items():
        if destination not in new:
            raise ValueError(f"Unknown preserved replacement node {destination!r}")
        if (old[source].input_count, old[source].output_count) != (
            new[destination].input_count,
            new[destination].output_count,
        ):
            raise ValueError("Preserved operations must have matching port counts")


class RewriteRegistry:
    """An ordered collection of named rules and explicitly named rule groups."""

    def __init__(self) -> None:
        self._rules: dict[str, RewriteRule] = {}
        self._collections: dict[str, list[str]] = {}

    def register(self, rule: RewriteRule, *, collections: Iterable[str] = ()) -> None:
        """Register a rule without overwriting an existing name."""
        if not isinstance(rule, RewriteRule):
            raise TypeError("Only RewriteRule objects can be registered")
        groups = [collections] if isinstance(collections, str) else list(collections)
        if rule.name in self._rules or rule.name in self._collections:
            raise ValueError(f"Rewrite name {rule.name!r} is already registered")
        if any(
            not isinstance(group, str)
            or not group
            or group == rule.name
            or group in self._rules
            for group in groups
        ):
            raise ValueError(
                "Collection names must be nonempty and distinct from rule names"
            )
        self._rules[rule.name] = rule
        for group in dict.fromkeys(groups):
            self._collections.setdefault(group, []).append(rule.name)

    def get(self, name: str) -> RewriteRule:
        """Look up one rule by name."""
        return self._rules[name]

    def names(self) -> tuple[str, ...]:
        """Return rule names in registration order."""
        return tuple(self._rules)

    def select(
        self, rules: RewriteRule | str | Iterable[RewriteRule | str] | None = None
    ) -> list[RewriteRule]:
        """Resolve rule objects, rule names, or collection names in order."""
        if rules is None:
            return list(self._rules.values())
        specifiers = [rules] if isinstance(rules, (RewriteRule, str)) else list(rules)
        selected: dict[str, RewriteRule] = {}
        for specifier in specifiers:
            if isinstance(specifier, RewriteRule):
                values = [specifier]
            elif isinstance(specifier, str):
                values = (
                    [self._rules[specifier]]
                    if specifier in self._rules
                    else [self._rules[name] for name in self._collections[specifier]]
                )
            else:
                raise TypeError("Rules must be RewriteRule objects or registered names")
            for rule in values:
                if rule.name in selected and selected[rule.name] is not rule:
                    raise ValueError(f"Different rules share the name {rule.name!r}")
                selected[rule.name] = rule
        return list(selected.values())


def _factor_rewrites() -> Iterator[RewriteRule]:
    for suffix, arithmetic in (("addition", Addition), ("subtraction", Subtraction)):
        yield RewriteRule.from_builders(
            f"arithmetic.factor_{suffix}",
            inputs=("a", "b", "c"),
            pattern=lambda a, b, c, arithmetic=arithmetic: arithmetic(
                Multiplication(a, b, name="left"),
                Multiplication(a, c, name="right"),
                name="root",
            ),
            replacement=lambda a, b, c, arithmetic=arithmetic: Multiplication(
                a, arithmetic(b, c, name="root"), name="left"
            ),
            preserve={"root": "root", "left": "left"},
        )


def _match_variable_value(pattern: Operation, operation: Operation) -> bool:
    """Capture coefficients or shift amounts without relaxing other parameters."""
    variable = isinstance(
        pattern, (ConstantMultiplication, LeftShift, RightShift, Shift)
    )
    return _equal(
        {
            key: value
            for key, value in pattern.params.items()
            if not variable or key != "value"
        },
        {
            key: value
            for key, value in operation.params.items()
            if not variable or key != "value"
        },
    ) and _equal(
        getattr(pattern, "real_valued", None), getattr(operation, "real_valued", None)
    )


def _collect_coefficients(match: RewriteMatch) -> "SFG":
    coefficients = [
        cast(ConstantMultiplication, match.operations[alias]).value
        if alias in match.operations
        else 1
        for alias in ("left", "right")
    ]
    left, right = coefficients
    coefficient = (
        left - right if isinstance(match.anchor, Subtraction) else left + right
    )
    # Keep even zero/unit coefficients available to collect into their consumers.
    # Constant propagation can simplify the final multiplier afterwards.
    return _build_template(("x",), lambda x: ConstantMultiplication(coefficient, x))


def _coefficient_rewrites() -> Iterator[RewriteRule]:
    for suffix, arithmetic, left, right in (
        ("addition_coefficients", Addition, True, True),
        ("subtraction_coefficients", Subtraction, True, True),
        ("addition_unit_coefficient", Addition, True, False),
        ("subtraction_unit_coefficient", Subtraction, True, False),
        ("reverse_subtraction_unit_coefficient", Subtraction, False, True),
        ("repeated_input", Addition, False, False),
    ):
        pattern = _build_template(
            ("x",),
            lambda x, arithmetic=arithmetic, left=left, right=right: arithmetic(
                ConstantMultiplication(0, x, name="left") if left else x,
                ConstantMultiplication(0, x, name="right") if right else x,
                name="root",
            ),
        )
        yield RewriteRule(
            f"arithmetic.collect_{suffix}",
            pattern,
            _collect_coefficients,
            node_match=_match_variable_value,
        )


def _cancellation_rewrites() -> Iterator[RewriteRule]:
    yield RewriteRule.from_builders(
        "arithmetic.subtract_self",
        inputs=("x",),
        pattern=lambda x: Subtraction(x, x),
        replacement=lambda x: Constant(0),
    )
    for name, pattern, replacement in (
        (
            "cancel_addend",
            lambda x, y: Subtraction(Addition(x, y), x),
            lambda x, y: y,
        ),
        (
            "cancel_subtrahend",
            lambda x, y: Addition(Subtraction(x, y), y),
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
            lambda x, y: Negation(y),
        ),
        (
            "subtract_sum",
            lambda x, y: Subtraction(x, Addition(x, y)),
            lambda x, y: Negation(y),
        ),
    ):
        yield RewriteRule.from_builders(
            f"arithmetic.{name}",
            inputs=("x", "y"),
            pattern=pattern,
            replacement=replacement,
        )


def _sharing_rule(
    shared_type: type[Addition | Subtraction],
    inner_type: type[Addition | Subtraction],
    root_type: type[Addition | Subtraction],
    input_order: tuple[int, ...],
    inner_index: int,
) -> RewriteRule | None:
    """Reuse a sum/difference when its two signed terms occur in another tree."""
    root_signs = (1, 1 if root_type is Addition else -1)
    inner_signs = (1, 1 if inner_type is Addition else -1)
    signs = [0, 0, 0]
    for index, sign in zip(input_order[:2], inner_signs, strict=True):
        signs[index] = root_signs[inner_index] * sign
    signs[input_order[2]] = root_signs[1 - inner_index]
    if signs[1] != signs[0] * (1 if shared_type is Addition else -1):
        return None

    def pattern(a, b, c):
        sources = (a, b, c)
        shared = shared_type(a, b, name="shared")
        inner = inner_type(
            sources[input_order[0]], sources[input_order[1]], name="inner"
        )
        other = sources[input_order[2]]
        operands = (inner, other) if inner_index == 0 else (other, inner)
        return {"shared": shared, "out": root_type(*operands, name="root")}

    def replacement(a, b, c):
        shared = shared_type(a, b, name="shared")
        if signs[0] > 0:
            arithmetic = Addition if signs[2] > 0 else Subtraction
            root = arithmetic(shared, c, name="root")
        elif signs[2] > 0:
            root = Subtraction(c, shared, name="root")
        else:
            root = Subtraction(Negation(c), shared, name="root")
        return {"shared": shared, "out": root}

    kind = "sum" if shared_type is Addition else "difference"
    inner_inputs = "".join("abc"[index] for index in input_order[:2])
    return RewriteRule.from_builders(
        f"arithmetic.share_{kind}_{inner_type.type_name()}_{inner_inputs}_{root_type.type_name()}_{inner_index}",
        inputs=("a", "b", "c"),
        pattern=pattern,
        replacement=replacement,
        anchor="root",
        preserve={"shared": "shared", "root": "root"},
    )


def _sharing_rewrites() -> Iterator[RewriteRule]:
    for shared_type, inner_type in product((Addition, Subtraction), repeat=2):
        for input_order in permutations(range(3)):
            # Addition matching already exchanges its inputs. A shared sum also
            # makes a and b interchangeable, so one outer operand is sufficient.
            if inner_type is Addition and input_order[0] > input_order[1]:
                continue
            if shared_type is Addition and input_order[2] == 0:
                continue
            for root_type, inner_index in (
                (Addition, 0),
                (Subtraction, 0),
                (Subtraction, 1),
            ):
                rule = _sharing_rule(
                    shared_type, inner_type, root_type, input_order, inner_index
                )
                if rule is not None:
                    yield rule


def _complex_product_template(
    a: SignalSourceProvider,
    b: SignalSourceProvider,
    c: SignalSourceProvider,
    d: SignalSourceProvider,
    method: str,
) -> dict[str, SignalSourceProvider]:
    from b_asic.complex_conversion import _product  # noqa: PLC0415

    real, imag = _product(_ComplexPair(a, b), _ComplexPair(c, d), method)
    real_operation = cast(Operation, real)
    real_operation.name = "real"
    cast(Operation, imag).name = "imag"
    for name, port in zip(("ac", "bd"), real_operation.inputs, strict=True):
        assert port.connected_source is not None
        port.connected_source.operation.name = name
    return {"real": real, "imag": imag}


def _complex_rewrites() -> Iterator[RewriteRule]:
    yield RewriteRule.from_builders(
        "complex.double_conjugate",
        inputs=("x",),
        pattern=lambda x: ComplexConjugate(ComplexConjugate(x)),
        replacement=lambda x: x,
    )
    yield RewriteRule.from_builders(
        "complex.double_imaginary_multiplication",
        inputs=("x",),
        pattern=lambda x: ImaginaryMultiplication(ImaginaryMultiplication(x)),
        replacement=Negation,
    )
    for suffix, arithmetic in (
        ("addition", Addition),
        ("subtraction", Subtraction),
        ("multiplication", Multiplication),
    ):
        yield RewriteRule.from_builders(
            f"complex.share_conjugate_{suffix}",
            inputs=("a", "b"),
            pattern=lambda a, b, arithmetic=arithmetic: arithmetic(
                ComplexConjugate(a, name="left"),
                ComplexConjugate(b, name="right"),
                name="root",
            ),
            replacement=lambda a, b, arithmetic=arithmetic: ComplexConjugate(
                arithmetic(a, b, name="root"), name="left"
            ),
            preserve={"root": "root", "left": "left"},
        )
    yield RewriteRule.from_builders(
        "complex.three_multiplication_product",
        inputs=("a", "b", "c", "d"),
        pattern=lambda a, b, c, d: _complex_product_template(a, b, c, d, "four"),
        replacement=lambda a, b, c, d: _complex_product_template(a, b, c, d, "three"),
        anchor="real",
        preserve={name: name for name in ("ac", "bd", "real", "imag")},
    )


def _fold_shifts(match: RewriteMatch) -> "SFG":
    amount = sum(
        -cast(LeftShift, operation).value
        if isinstance(operation, LeftShift)
        else cast(RightShift | Shift, operation).value
        for operation in match.operations.values()
    )
    return _build_template(
        ("x",),
        lambda x: (
            RightShift(amount, x)
            if amount > 0
            else LeftShift(-amount, x)
            if amount < 0
            else x
        ),
    )


def _shift_rewrites() -> Iterator[RewriteRule]:
    shifts = (LeftShift, RightShift, Shift)
    for outer, inner in product(shifts, repeat=2):
        yield RewriteRule(
            f"shifts.fold_{outer.type_name()}_{inner.type_name()}",
            _build_template(
                ("x",),
                lambda x, outer=outer, inner=inner: outer(
                    0, inner(0, x, name="inner"), name="root"
                ),
            ),
            _fold_shifts,
            node_match=_match_variable_value,
        )
    for shift in shifts:
        yield RewriteRule.from_builders(
            f"shifts.remove_zero_{shift.type_name()}",
            inputs=("x",),
            pattern=lambda x, shift=shift: shift(0, x),
            replacement=lambda x: x,
        )


@lru_cache(maxsize=1)
def _default_registry() -> RewriteRegistry:
    result = RewriteRegistry()
    result.register(
        RewriteRule.from_builders(
            "arithmetic.negated_product",
            inputs=("a", "b", "c"),
            pattern=lambda a, b, c: Addition(
                Multiplication(Negation(a), b, name="product"), c, name="root"
            ),
            replacement=lambda a, b, c: Subtraction(
                c, Multiplication(a, b, name="product"), name="root"
            ),
            anchor="root",
            preserve={"product": "product", "root": "root"},
        ),
        collections=("arithmetic", "negations"),
    )
    result.register(
        RewriteRule.from_builders(
            "arithmetic.subtract_negated_product",
            inputs=("a", "b", "c"),
            pattern=lambda a, b, c: Subtraction(
                c, Multiplication(Negation(a), b, name="product"), name="root"
            ),
            replacement=lambda a, b, c: Addition(
                c, Multiplication(a, b, name="product"), name="root"
            ),
            anchor="root",
            preserve={"product": "product", "root": "root"},
        ),
        collections=("arithmetic", "negations"),
    )
    result.register(
        RewriteRule.from_builders(
            "arithmetic.negated_product_difference",
            inputs=("a", "b", "c", "d"),
            pattern=lambda a, b, c, d: Addition(
                Subtraction(
                    Multiplication(Negation(a), b, name="product"), c, name="inner"
                ),
                d,
                name="root",
            ),
            replacement=lambda a, b, c, d: Subtraction(
                d,
                Addition(Multiplication(a, b, name="product"), c, name="inner"),
                name="root",
            ),
            anchor="root",
            preserve={"product": "product", "inner": "inner", "root": "root"},
        ),
        collections=("arithmetic", "negations"),
    )
    result.register(
        RewriteRule.from_builders(
            "arithmetic.subtract_negated_product_difference",
            inputs=("a", "b", "c", "d"),
            pattern=lambda a, b, c, d: Subtraction(
                d,
                Subtraction(
                    Multiplication(Negation(a), b, name="product"), c, name="inner"
                ),
                name="root",
            ),
            replacement=lambda a, b, c, d: Addition(
                d,
                Addition(Multiplication(a, b, name="product"), c, name="inner"),
                name="root",
            ),
            anchor="root",
            preserve={"product": "product", "inner": "inner", "root": "root"},
        ),
        collections=("arithmetic", "negations"),
    )
    result.register(
        RewriteRule.from_builders(
            "arithmetic.double_negation",
            inputs=("a",),
            pattern=lambda a: Negation(Negation(a), name="root"),
            replacement=lambda a: a,
        ),
        collections=("arithmetic", "negations", "complex"),
    )
    result.register(
        RewriteRule.from_builders(
            "arithmetic.add_negation",
            inputs=("a", "b"),
            pattern=lambda a, b: Addition(a, Negation(b), name="root"),
            replacement=lambda a, b: Subtraction(a, b, name="root"),
            preserve={"root": "root"},
        ),
        collections=("arithmetic", "negations"),
    )
    for collection, rules in (
        ("cancellations", _cancellation_rewrites()),
        ("coefficients", _coefficient_rewrites()),
        ("factoring", _factor_rewrites()),
        ("sharing", _sharing_rewrites()),
        ("complex", _complex_rewrites()),
        ("shifts", _shift_rewrites()),
    ):
        for rule in rules:
            result.register(rule, collections=("arithmetic", collection))
    return result


def register_rewrite(rule: RewriteRule, *, collections: Iterable[str] = ()) -> None:
    """Register a custom rule in the default registry."""
    _default_registry().register(rule, collections=collections)


def get_rewrite(name: str) -> RewriteRule:
    """Look up a built-in or registered custom rule."""
    return _default_registry().get(name)


def available_rewrites() -> tuple[str, ...]:
    """List the built-in and registered custom rule names."""
    return _default_registry().names()


def _normalize_specifiers(
    graph: "SFG", values: "OpSpecifier | Iterable[OpSpecifier] | None"
) -> tuple | None:
    if values is None:
        return None
    try:
        specifiers = (
            [values] if isinstance(values, (str, Operation, type)) else list(values)
        )
    except TypeError as exc:
        raise TypeError(
            "Operation selections must contain IDs, instances, or operation types"
        ) from exc
    result: list[GraphID | type[Operation]] = []
    for value in specifiers:
        if isinstance(value, type):
            if not issubclass(value, Operation):
                raise TypeError("Selected types must be Operation subclasses")
            result.append(value)
        elif isinstance(value, Operation):
            if graph.find_by_id(value.graph_id) is not value:
                raise ValueError("Selected operations must belong to this SFG")
            result.append(value.graph_id)
        elif isinstance(value, str):
            component = graph.find_by_id(value)
            if component is None:
                raise ValueError(f"Unknown operation graph ID {value!r}")
            if not isinstance(component, Operation):
                raise TypeError(f"Graph ID {value!r} identifies a signal")
            result.append(value)
        else:
            raise TypeError(
                "Operation selections must contain IDs, instances, or operation types"
            )
    return tuple(dict.fromkeys(result))


def _selection_ids(graph: "SFG", specifiers: tuple | None) -> set[GraphID]:
    if specifiers is None:
        return {op.graph_id for op in graph.operations}
    return {
        op.graph_id
        for op in graph.operations
        if any(
            isinstance(op, value) if isinstance(value, type) else op.graph_id == value
            for value in specifiers
        )
    }


def _node_matches(rule: RewriteRule, pattern: Operation, operation: Operation) -> bool:
    if type(pattern) is not type(operation) or (
        pattern.input_count,
        pattern.output_count,
    ) != (operation.input_count, operation.output_count):
        return False
    if rule.node_match is not None:
        return bool(rule.node_match(pattern, operation))
    return _equal(pattern.params, operation.params) and _equal(
        getattr(pattern, "real_valued", None), getattr(operation, "real_valued", None)
    )


def _snapshot(operations: Mapping[str, Operation]) -> dict:
    return {
        alias: (
            type(op),
            deepcopy(dict(op.params)),
            getattr(op, "real_valued", None),
            tuple(
                (port.connected_source.operation.graph_id, port.connected_source.index)
                if port.connected_source is not None
                else None
                for port in op.inputs
            ),
            tuple(
                tuple(
                    sorted(
                        (
                            signal.graph_id,
                            signal.destination.operation.graph_id
                            if signal.destination
                            else None,
                            signal.destination.index if signal.destination else None,
                        )
                        for signal in port.signals
                    )
                )
                for port in op.outputs
            ),
        )
        for alias, op in operations.items()
    }


def _input_bindings(
    template_nodes: Mapping[str, Operation],
    operations: Mapping[str, Operation],
    input_names: Mapping[Operation, str],
) -> Iterator[tuple[dict[str, tuple[int, ...]], dict[str, OutputPort]]]:
    """Bind inputs consistently, exchanging inputs of commutative operations."""
    pattern_to_host = {template_nodes[alias]: op for alias, op in operations.items()}
    matched = set(operations.values())
    options: list[list[tuple[tuple[int, ...], dict[str, OutputPort]]]] = []
    for alias, pattern in template_nodes.items():
        operation = operations[alias]
        orders = (
            ((0, 1), (1, 0))
            if type(pattern) in (Addition, Multiplication)
            and pattern.is_swappable
            and operation.is_swappable
            else (tuple(range(pattern.input_count)),)
        )
        choices = []
        for indices in orders:
            inputs: dict[str, OutputPort] = {}
            for port in pattern.inputs:
                expected = port.connected_source
                actual = operation.input(indices[port.index]).connected_source
                if expected is None or actual is None:
                    break
                if expected.operation in pattern_to_host:
                    if (
                        actual.operation is not pattern_to_host[expected.operation]
                        or actual.index != expected.index
                    ):
                        break
                elif expected.operation in input_names:
                    name = input_names[expected.operation]
                    if actual.operation in matched or (
                        name in inputs and inputs[name] is not actual
                    ):
                        break
                    inputs[name] = actual
                else:
                    break
            else:
                choices.append((indices, inputs))
        if not choices:
            return
        options.append(choices)
    for combination in product(*options):
        bound_inputs: dict[str, OutputPort] = {}
        for _, inputs in combination:
            if any(
                name in bound_inputs and bound_inputs[name] is not source
                for name, source in inputs.items()
            ):
                break
            bound_inputs.update(inputs)
        else:
            if bound_inputs.keys() == set(input_names.values()):
                yield (
                    {
                        alias: indices
                        for alias, (indices, _) in zip(
                            template_nodes, combination, strict=True
                        )
                    },
                    bound_inputs,
                )


def _bind_match(
    graph: "SFG", rule: RewriteRule, operations: Mapping[str, Operation]
) -> RewriteMatch | None:
    template_nodes = _nodes(rule._pattern)
    if operations.keys() != template_nodes.keys() or len(
        set(operations.values())
    ) != len(operations):
        return None
    if any(
        not _node_matches(rule, template_nodes[alias], op)
        for alias, op in operations.items()
    ):
        return None
    pattern_to_host = {template_nodes[alias]: op for alias, op in operations.items()}
    input_names = {
        op: name
        for name, op in _boundaries(rule._pattern.input_operations, "in").items()
    }
    bound_outputs: dict[str, OutputPort] = {}
    for name, output in _boundaries(rule._pattern.output_operations, "out").items():
        source = output.input(0).connected_source
        if source is None:
            return None
        if source.operation in pattern_to_host:
            bound_outputs[name] = pattern_to_host[source.operation].output(source.index)
        else:
            return None
    exposed = set(bound_outputs.values())
    matched = set(operations.values())
    for operation in matched:
        for output_port in operation.outputs:
            if any(signal.destination is None for signal in output_port.signals):
                return None
            if (
                any(
                    signal.destination is None
                    or signal.destination.operation not in matched
                    for signal in output_port.signals
                )
                and output_port not in exposed
            ):
                return None
    for indices, bound_inputs in _input_bindings(
        template_nodes, operations, input_names
    ):
        match = RewriteMatch(
            rule,
            MappingProxyType(dict(operations)),
            MappingProxyType(bound_inputs),
            MappingProxyType(bound_outputs),
            MappingProxyType(indices),
            graph,
            _snapshot(operations),
        )
        if rule.condition is None or rule.condition(match):
            return match
    return None


def _find(
    graph: "SFG",
    rules: Iterable[RewriteRule],
    targets: set[GraphID],
    within: set[GraphID],
) -> list[RewriteMatch]:
    network = _network(graph.operations)
    order = {op: index for index, op in enumerate(dict.fromkeys(graph.operations))}
    result = []
    for rule in rules:
        pattern_nodes = _nodes(rule._pattern)
        pattern_network = _network(pattern_nodes.values())
        anchor = pattern_nodes[rule.anchor]
        matcher = nx.algorithms.isomorphism.MultiDiGraphMatcher(
            network,
            pattern_network,
            node_match=lambda host, pattern, rule=rule, anchor=anchor: (
                host["operation"].graph_id in within
                and (
                    pattern["operation"] is not anchor
                    or host["operation"].graph_id in targets
                )
                and _node_matches(rule, pattern["operation"], host["operation"])
            ),
            edge_match=lambda host, pattern: (
                sorted((edge["source"], edge["destination"]) for edge in host.values())
                == sorted(
                    (edge["source"], edge["destination"]) for edge in pattern.values()
                )
            ),
        )
        matches = []
        seen = set()
        for mapping in matcher.subgraph_monomorphisms_iter():
            inverse = {pattern: host for host, pattern in mapping.items()}
            operations = {
                alias: inverse[operation] for alias, operation in pattern_nodes.items()
            }
            if operations[rule.anchor].graph_id not in targets or any(
                op.graph_id not in within for op in operations.values()
            ):
                continue
            key = tuple(op.graph_id for op in operations.values())
            if key in seen:
                continue
            seen.add(key)
            match = _bind_match(graph, rule, operations)
            if match is not None:
                matches.append(match)
        matches.sort(
            key=lambda match: (
                order[match.anchor],
                tuple(order[op] for op in match.operations.values()),
            )
        )
        result.extend(matches)
    return result


def find_rewrites(
    graph: "SFG", rules=None, target=None, *, within=None
) -> list[RewriteMatch]:
    """Find exact port-aware matches without modifying the graph."""
    selected_rules = _default_registry().select(rules)
    targets = _selection_ids(graph, _normalize_specifiers(graph, target))
    region = _selection_ids(graph, _normalize_specifiers(graph, within))
    return _find(graph, selected_rules, targets, region)


def _source_key(
    source: OutputPort | None,
    aliases: Mapping[Operation, str],
    inputs: Mapping[Operation, str],
    renames: Mapping[str, str],
) -> tuple:
    if source is None:
        raise ValueError("Template inputs must be connected")
    if source.operation in inputs:
        return "input", inputs[source.operation], source.index
    alias = aliases[source.operation]
    return "node", renames.get(alias, alias), source.index


def _replace(graph: "SFG", match: RewriteMatch) -> "SFG":
    from b_asic.sfg import SFG  # noqa: PLC0415

    rule = match.rule
    replacement = rule.build_replacement(match)
    new_nodes = _nodes(replacement)
    pattern_nodes = _nodes(rule._pattern)
    pattern_inputs = {
        op: name
        for name, op in _boundaries(rule._pattern.input_operations, "in").items()
    }
    new_inputs = {
        op: name for name, op in _boundaries(replacement.input_operations, "in").items()
    }
    old_aliases = {op: alias for alias, op in pattern_nodes.items()}
    new_aliases = {op: alias for alias, op in new_nodes.items()}
    preserved = {destination: source for source, destination in rule.preserve.items()}
    for alias, operation in new_nodes.items():
        if alias not in preserved:
            operation.graph_id = graph._graph_id_generator.next_id(
                operation.type_name(), graph._used_ids
            )
            continue
        source_alias = preserved[alias]
        old = match.operations[source_alias]
        operation.graph_id = (
            old.graph_id
            if type(operation) is type(old)
            else graph._graph_id_generator.next_id(
                operation.type_name(), graph._used_ids
            )
        )
        operation.name = old.name
        operation.execution_time = old.execution_time
        old_pattern = pattern_nodes[source_alias]
        input_keys = [
            _source_key(
                port.connected_source, old_aliases, pattern_inputs, rule.preserve
            )
            for port in old_pattern.inputs
        ]
        for index, port in enumerate(operation.inputs):
            key = _source_key(port.connected_source, new_aliases, new_inputs, {})
            indices = [i for i, old_key in enumerate(input_keys) if key == old_key]
            old_index = indices[0] if len(indices) == 1 else index
            port.latency_offset = old.input(
                match._input_indices[source_alias][old_index]
            ).latency_offset
        for index, output_port in enumerate(operation.outputs):
            output_port.latency_offset = old.output(index).latency_offset

    incoming: dict[str, list[Signal]] = {name: [] for name in match.inputs}
    for alias, pattern in pattern_nodes.items():
        for port in pattern.inputs:
            source = port.connected_source
            if source is None:
                raise ValueError("Template inputs must be connected")
            if source.operation in pattern_inputs:
                original_port = match.operations[alias].input(
                    match._input_indices[alias][port.index]
                )
                incoming[pattern_inputs[source.operation]].extend(original_port.signals)
    reused = set()
    for operation, name in new_inputs.items():
        originals = iter(incoming[name])
        for signal in list(operation.output(0).signals):
            destination = signal.destination
            if destination is None:
                raise ValueError("Replacement signals must have destinations")
            if destination.operation in replacement.output_operations:
                continue
            existing = next(originals, None)
            signal.remove_source()
            signal.remove_destination()
            if existing is None:
                existing = cast(Signal, incoming[name][0].copy())
                existing.graph_id = graph._graph_id_generator.next_id(
                    existing.type_name(), graph._used_ids
                )
                existing.set_source(match.inputs[name])
            existing.set_destination(destination)
            reused.add(existing)

    for name, output in _boundaries(replacement.output_operations, "out").items():
        source = output.input(0).connected_source
        if source is None:
            raise ValueError("Replacement outputs must be connected")
        if source.operation in new_inputs:
            source = match.inputs[new_inputs[source.operation]]
        old_port = match.outputs[name]
        for signal in list(old_port.signals):
            if (
                signal.destination is not None
                and signal.destination.operation not in match.operations.values()
            ):
                signal.set_source(source)
        for signal in list(output.input(0).signals):
            signal.remove_source()
            signal.remove_destination()
    for operation in match.operations.values():
        for port in operation.inputs:
            for signal in list(port.signals):
                signal.remove_source()
                signal.remove_destination()
    for operation in new_nodes.values():
        for port in operation.inputs:
            for signal in port.signals:
                if signal not in reused:
                    signal.graph_id = graph._graph_id_generator.next_id(
                        signal.type_name(), graph._used_ids
                    )
    rebuilt = cast(SFG, graph.copy())
    rebuilt._used_ids.update(graph._used_ids)
    return rebuilt


def apply_rewrites(
    graph: "SFG", matches: RewriteMatch | Iterable[RewriteMatch]
) -> "SFG":
    """Apply matches in order, skipping overlaps and invalidated later matches."""
    from b_asic.sfg import SFG  # noqa: PLC0415

    selected = [matches] if isinstance(matches, RewriteMatch) else list(matches)
    for match in selected:
        if not isinstance(match, RewriteMatch):
            raise TypeError("matches must contain RewriteMatch objects")
        if match._graph is not graph:
            raise ValueError("Rewrite matches must belong to this SFG")
        current = {
            alias: graph.find_by_id(op.graph_id)
            for alias, op in match.operations.items()
        }
        if any(not isinstance(op, Operation) for op in current.values()) or not _equal(
            _snapshot(cast(dict[str, Operation], current)), match._snapshot
        ):
            raise ValueError("Rewrite match is stale; find matches again")
    result = cast(SFG, graph.copy())
    occupied: set[GraphID] = set()
    for match in selected:
        ids = {op.graph_id for op in match.operations.values()}
        if occupied.intersection(ids):
            continue
        current = {
            alias: result.find_by_id(op.graph_id)
            for alias, op in match.operations.items()
        }
        if any(not isinstance(op, Operation) for op in current.values()):
            continue
        rebound = _bind_match(result, match.rule, cast(dict[str, Operation], current))
        if rebound is not None:
            result = _replace(result, rebound)
            occupied.update(ids)
    return result


def transform(
    graph: "SFG",
    rules=None,
    target=None,
    *,
    within=None,
    repeat: bool = False,
    max_iterations: int = 100,
) -> "SFG":
    """Find and apply rules in deterministic passes, optionally until stable."""
    from b_asic.sfg import SFG  # noqa: PLC0415

    if (
        not isinstance(max_iterations, int)
        or isinstance(max_iterations, bool)
        or max_iterations < 1
    ):
        raise ValueError("max_iterations must be a positive integer")
    selected_rules = _default_registry().select(rules)
    targets = _normalize_specifiers(graph, target)
    region = _normalize_specifiers(graph, within)
    result = cast(SFG, graph.copy())
    for _ in range(max_iterations):
        matches = _find(
            result,
            selected_rules,
            _selection_ids(result, targets),
            _selection_ids(result, region),
        )
        if not matches:
            return result
        result = apply_rewrites(result, matches)
        if not repeat:
            return result
    if _find(
        result,
        selected_rules,
        _selection_ids(result, targets),
        _selection_ids(result, region),
    ):
        raise RuntimeError("Rewrite iteration limit reached; rules may not converge")
    return result
