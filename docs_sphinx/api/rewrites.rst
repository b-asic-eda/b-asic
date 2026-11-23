Subgraph rewrites
=================

Named, directed rules replace connected combinational regions of an SFG.
Pattern inputs bind arbitrary source ports in the host graph. Pattern outputs
identify the region's externally visible results. Operation names identify
nodes within a rule; they do not constrain host operation names.

Finding and applying rules
--------------------------

The built-in ``arithmetic.negated_product`` rule implements
``(-a) * b + c -> c - a * b``. Preview its matches before applying them:

.. code-block:: python

    matches = sfg.find_rewrites(
        rules="arithmetic.negated_product",
        target=["add7", "add12"],
    )
    for match in matches:
        print(match.rule.name, match.anchor.graph_id, match.operations)
        replacement_sfg = match.rule.build_replacement(match)
    result = sfg.apply_rewrites(matches)

The original SFG is unchanged. ``target`` selects candidate anchor operations;
it accepts graph IDs, operation instances belonging to the graph, operation
types, or an iterable mixing these selectors. ``within`` optionally restricts
every internal matched operation to a selected region. Boundary sources and
consumers may remain outside it.

``sfg.transform(rules="arithmetic", repeat=True)`` combines discovery and
application, repeating passes until no match remains. The ``arithmetic`` and
``negations`` collections contain the following built-in rules:

.. list-table:: Built-in rewrite rules
   :header-rows: 1
   :widths: 50 25 25

   * - Name
     - Pattern
     - Replacement
   * - ``arithmetic.negated_product``
     - ``(-a) * b + c``
     - ``c - a * b``
   * - ``arithmetic.subtract_negated_product``
     - ``c - (-a) * b``
     - ``c + a * b``
   * - ``arithmetic.negated_product_difference``
     - ``((-a) * b - c) + d``
     - ``d - (a * b + c)``
   * - ``arithmetic.subtract_negated_product_difference``
     - ``d - ((-a) * b - c)``
     - ``d + (a * b + c)``
   * - ``arithmetic.double_negation``
     - ``-(-a)``
     - ``a``
   * - ``arithmetic.add_negation``
     - ``a + (-b)``
     - ``a - b``

Product patterns also match ``b * (-a)`` in place of ``(-a) * b``.
The addition in ``arithmetic.negated_product`` also accepts the product on
either input, so ``c + (-a) * b`` matches as well. More generally,
multiplication inputs match in either order, and addition inputs do so when
their scales are equal and ``mul_j=False``. This applies to custom rules too.
Other operation inputs retain their specified order. Addition and subtraction
in these patterns use :class:`~b_asic.core_operations.Addition` and
:class:`~b_asic.core_operations.Subtraction` with default computational parameters.

The two product-difference rules extend ``(-a) * b - c`` through its consumer.
They change the inner subtraction to addition and absorb its negative sign
into an outer addition or the subtraction input of an outer subtraction.
Their anchor is that consumer, so ``target`` selects the downstream addition
or subtraction. The multiplier and both arithmetic operations retain their
IDs and timing through the rules' ``preserve`` mappings.

Select a rule explicitly, for example with
``sfg.transform("arithmetic.subtract_negated_product")``.

Use :func:`~b_asic.rewrites.available_rewrites` to list registered rule names.
Repeated transformations have a positive ``max_iterations`` limit and raise
``RuntimeError`` if matches still remain at that limit. Explicit graph ID
selections remain fixed; type selections can include newly generated nodes.
A single pass may expose further matches. For example, rewriting
``(-a) * b - (-c) * d`` first produces ``(-a) * b + c * d``; a second pass
can then produce ``c * d - a * b``. Use ``repeat=True`` to continue until no
selected rule matches.

Defining rules
--------------

Builders use ordinary B-ASIC operations and fresh input placeholders:

.. code-block:: python

    from b_asic import Addition, Multiplication, Negation, Subtraction
    from b_asic.rewrites import RewriteRule, register_rewrite

    rule = RewriteRule.from_builders(
        name="custom.negated_product",
        inputs=("a", "b", "c"),
        pattern=lambda a, b, c: Addition(
            Multiplication(Negation(a), b, name="product"),
            c,
            name="root",
        ),
        replacement=lambda a, b, c: Subtraction(
            c,
            Multiplication(a, b, name="product"),
            name="root",
        ),
        anchor="root",
        preserve={"product": "product", "root": "root"},
    )
    register_rewrite(rule, collections=["custom"])
    result = sfg.transform("custom")

A builder can return one signal source, a sequence of sources, a mapping of
output names to sources, or an SFG. A rule can also be constructed directly
from pattern and replacement SFGs. Matching boundary names must agree; unnamed
SFG boundaries fall back to ``in0``, ``out0``, etc. Multi-output rules reconnect
by boundary name rather than positional ordering. Different input placeholders
can bind the same source; repeated uses of one placeholder must bind the same
source port.

The ``preserve`` mapping retains named operations' IDs, names, execution times,
and port timing. Computational parameters come from the replacement. Input
timing follows corresponding boundary/preserved sources where identifiable,
otherwise corresponding port indices. External output signals retain their
IDs and metadata. Incoming boundary signals are reused where possible; all
other generated components receive fresh IDs.

Types, port counts, computational parameters, and port indices match exactly
by default, except that multiplier inputs and commutative addition inputs can
be exchanged. Boundary bindings, signal metadata, and preserved input timing
follow the matched operands.
For parameterized rules, ``node_match(pattern_op, host_op)`` can
customize parameter matching, ``condition(match)`` can reject a complete match,
and a replacement factory supplied to ``RewriteRule`` can build an SFG from
``match.operations`` and their parameter values. Callbacks must not mutate
their host graph. Templates are copied when rules are constructed.

Applicability and conflicts
---------------------------

An internal output with outside consumers must be a declared pattern output.
In particular, an internal negation or product shared with another branch
prevents the simple negated-product rules from matching. Fanout on boundary
input sources and declared boundary outputs is unrestricted. For
``c - (-a) * b``, the sources of ``a``, ``b``, and ``c`` may feed other
branches; the negation and multiplication belong to the matched region.
A branch from either of their outputs to an outside consumer prevents this
single-output rule from matching. This version does not implicitly duplicate
shared internal producers.

Matches are ordered by selected rule order and anchor depth-first order.
Application skips overlapping matches and revalidates later matches after
each replacement. Matches from a different graph, or whose original structure
or computational parameters have changed, are rejected. Empty selections return
a graph copy without rewriting.

Templates are combinational and single-rate. Delays, rate-changing operations,
and nested SFG operations cannot appear inside templates. They can remain
outside matched regions, including as boundary sources. Input permutations
other than multiplier or commutative addition swaps need explicit rule variants.
Mathematical equivalence is asserted by each rule's author; the engine checks
structure and boundaries, not algebra or quantization equivalence. Apply
algebraic rules before scheduling and quantization.

Reference
---------

.. automodule:: b_asic.rewrites
   :members:
   :undoc-members:
