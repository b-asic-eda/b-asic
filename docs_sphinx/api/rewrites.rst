Subgraph rewrites
=================

Named, directed rules replace connected combinational regions of an SFG.
Regions may be connected internally or through shared pattern inputs.
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
application, repeating passes until no match remains. The ``arithmetic``
collection contains all built-in rules. The smaller collections select
negation handling, factoring, coefficient collection, repeated-input
cancellation, shared arithmetic, complex arithmetic, or shift simplification
independently.
In the table, ``C_k(x)`` denotes a
:class:`~b_asic.core_operations.ConstantMultiplication` with coefficient ``k``;
``conj(x)`` denotes :class:`~b_asic.core_operations.ComplexConjugate`.
The sharing rows group rule families using ``*`` for the generated variants;
:func:`~b_asic.rewrites.available_rewrites` lists their individual names.

.. list-table:: Built-in rewrite rules
   :header-rows: 1
   :widths: 40 20 20 20

   * - Name
     - Collections
     - Pattern
     - Replacement
   * - ``arithmetic.negated_product``
     - ``arithmetic``, ``negations``
     - ``(-a) * b + c``
     - ``c - a * b``
   * - ``arithmetic.subtract_negated_product``
     - ``arithmetic``, ``negations``
     - ``c - (-a) * b``
     - ``c + a * b``
   * - ``arithmetic.negated_product_difference``
     - ``arithmetic``, ``negations``
     - ``((-a) * b - c) + d``
     - ``d - (a * b + c)``
   * - ``arithmetic.subtract_negated_product_difference``
     - ``arithmetic``, ``negations``
     - ``d - ((-a) * b - c)``
     - ``d + (a * b + c)``
   * - ``arithmetic.double_negation``
     - ``arithmetic``, ``negations``, ``complex``
     - ``-(-a)``
     - ``a``
   * - ``arithmetic.add_negation``
     - ``arithmetic``, ``negations``
     - ``a + (-b)``
     - ``a - b``
   * - ``arithmetic.factor_addition``
     - ``arithmetic``, ``factoring``
     - ``a * b + a * c``
     - ``a * (b + c)``
   * - ``arithmetic.factor_subtraction``
     - ``arithmetic``, ``factoring``
     - ``a * b - a * c``
     - ``a * (b - c)``
   * - ``arithmetic.collect_addition_coefficients``
     - ``arithmetic``, ``coefficients``
     - ``C_k(x) + C_m(x)``
     - ``C_(k+m)(x)``
   * - ``arithmetic.collect_subtraction_coefficients``
     - ``arithmetic``, ``coefficients``
     - ``C_k(x) - C_m(x)``
     - ``C_(k-m)(x)``
   * - ``arithmetic.collect_addition_unit_coefficient``
     - ``arithmetic``, ``coefficients``
     - ``C_k(x) + x``
     - ``C_(k+1)(x)``
   * - ``arithmetic.collect_subtraction_unit_coefficient``
     - ``arithmetic``, ``coefficients``
     - ``C_k(x) - x``
     - ``C_(k-1)(x)``
   * - ``arithmetic.collect_reverse_subtraction_unit_coefficient``
     - ``arithmetic``, ``coefficients``
     - ``x - C_k(x)``
     - ``C_(1-k)(x)``
   * - ``arithmetic.collect_repeated_input``
     - ``arithmetic``, ``coefficients``
     - ``x + x``
     - ``C_2(x)``
   * - ``arithmetic.subtract_self``
     - ``arithmetic``, ``cancellations``
     - ``x - x``
     - ``0``
   * - ``arithmetic.cancel_addend``
     - ``arithmetic``, ``cancellations``
     - ``(x + y) - x``
     - ``y``
   * - ``arithmetic.cancel_subtrahend``
     - ``arithmetic``, ``cancellations``
     - ``(x - y) + y``
     - ``x``
   * - ``arithmetic.subtract_difference``
     - ``arithmetic``, ``cancellations``
     - ``x - (x - y)``
     - ``y``
   * - ``arithmetic.cancel_minuend``
     - ``arithmetic``, ``cancellations``
     - ``(x - y) - x``
     - ``-y``
   * - ``arithmetic.subtract_sum``
     - ``arithmetic``, ``cancellations``
     - ``x - (x + y)``
     - ``-y``
   * - ``arithmetic.share_sum_*``
     - ``arithmetic``, ``sharing``
     - ``(a+b, s*a + s*b + t*c)``
     - ``(u, s*u + t*c)``, where ``u=a+b`` and ``s,t`` are signs
   * - ``arithmetic.share_difference_*``
     - ``arithmetic``, ``sharing``
     - ``(a-b, s*a - s*b + t*c)``
     - ``(u, s*u + t*c)``, where ``u=a-b`` and ``s,t`` are signs
   * - ``complex.double_conjugate``
     - ``arithmetic``, ``complex``
     - ``conj(conj(x))``
     - ``x``
   * - ``complex.double_imaginary_multiplication``
     - ``arithmetic``, ``complex``
     - ``j * (j * x)``
     - ``-x``
   * - ``complex.share_conjugate_addition``
     - ``arithmetic``, ``complex``
     - ``conj(a) + conj(b)``
     - ``conj(a + b)``
   * - ``complex.share_conjugate_subtraction``
     - ``arithmetic``, ``complex``
     - ``conj(a) - conj(b)``
     - ``conj(a - b)``
   * - ``complex.share_conjugate_multiplication``
     - ``arithmetic``, ``complex``
     - ``conj(a) * conj(b)``
     - ``conj(a * b)``
   * - ``complex.three_multiplication_product``
     - ``arithmetic``, ``complex``
     - ``(a*c - b*d, a*d + b*c)``
     - ``(p - q, t - p - q)``, where ``p=a*c``, ``q=b*d``, ``t=(a+b)*(c+d)``
   * - ``shifts.fold_lshift_lshift``
     - ``arithmetic``, ``shifts``
     - Two left shifts
     - One left shift with summed amounts, or wiring
   * - ``shifts.fold_lshift_rshift``
     - ``arithmetic``, ``shifts``
     - Right shift followed by left shift
     - One shift with the net scale, or wiring
   * - ``shifts.fold_rshift_lshift``
     - ``arithmetic``, ``shifts``
     - Left shift followed by right shift
     - One shift with the net scale, or wiring
   * - ``shifts.fold_rshift_rshift``
     - ``arithmetic``, ``shifts``
     - Two right shifts
     - One right shift with summed amounts, or wiring
   * - ``shifts.fold_shift_lshift``
     - ``arithmetic``, ``shifts``
     - Left shift followed by signed shift
     - One shift with the net scale, or wiring
   * - ``shifts.fold_shift_rshift``
     - ``arithmetic``, ``shifts``
     - Right shift followed by signed shift
     - One shift with the net scale, or wiring
   * - ``shifts.fold_lshift_shift``
     - ``arithmetic``, ``shifts``
     - Signed shift followed by left shift
     - One shift with the net scale, or wiring
   * - ``shifts.fold_rshift_shift``
     - ``arithmetic``, ``shifts``
     - Signed shift followed by right shift
     - One shift with the net scale, or wiring
   * - ``shifts.fold_shift_shift``
     - ``arithmetic``, ``shifts``
     - Two signed shifts
     - One shift with the net scale, or wiring
   * - ``shifts.remove_zero_lshift``
     - ``arithmetic``, ``shifts``
     - Left shift by zero
     - Wiring
   * - ``shifts.remove_zero_rshift``
     - ``arithmetic``, ``shifts``
     - Right shift by zero
     - Wiring
   * - ``shifts.remove_zero_shift``
     - ``arithmetic``, ``shifts``
     - Signed shift by zero
     - Wiring

Product patterns also match ``b * (-a)`` in place of ``(-a) * b``.
The addition in ``arithmetic.negated_product`` also accepts the product on
either input, so ``c + (-a) * b`` matches as well. More generally,
multiplication inputs match in either order, and addition inputs do so when
their scales are equal and ``mul_j=False``. This applies to custom rules too.
Other operation inputs retain their specified order. Addition and subtraction
in these patterns use :class:`~b_asic.core_operations.Addition` and
:class:`~b_asic.core_operations.Subtraction` with default computational parameters.
In particular, the factoring, collection, cancellation, arithmetic-sharing,
and conjugate-sharing rules do not match scaled arithmetic or arithmetic with
``mul_j=True``.

The two product-difference rules extend ``(-a) * b - c`` through its consumer.
They change the inner subtraction to addition and absorb its negative sign
into an outer addition or the subtraction input of an outer subtraction.
Their anchor is that consumer, so ``target`` selects the downstream addition
or subtraction. The multiplier retains its ID. Arithmetic operations that
change type receive fresh IDs; all three operations retain their names and
timing through the rules' ``preserve`` mappings.

Select a rule explicitly, for example with
``sfg.transform("arithmetic.subtract_negated_product")``.

Use :func:`~b_asic.rewrites.available_rewrites` to list registered rule names.
Repeated transformations have a positive ``max_iterations`` limit and raise
``RuntimeError`` if matches still remain at that limit. Explicit graph ID
selections remain fixed; type selections can include newly generated nodes.
When a selected operation changes type, its old ID no longer selects it.
A single pass may expose further matches. For example, rewriting
``(-a) * b - (-c) * d`` first produces ``(-a) * b + c * d``; a second pass
can then produce ``c * d - a * b``. Use ``repeat=True`` to continue until no
selected rule matches.

Factoring and coefficient collection use two-term patterns. Repeated passes
also handle larger trees whose terms share the same source port. For example,
``(a*b + a*c) + a*d`` becomes ``a*((b+c) + d)``, and
``(C_2(x) + C_3(x)) + C_4(x)`` becomes ``C_9(x)``. Both left- and right-nested
trees and balanced trees are supported, including subtraction trees and
implicit unit coefficients such as ``C_2(x) + x``. Collection retains a
``ConstantMultiplication`` even for zero and unit coefficients so subtotals
remain eligible for collection into the next term. To remove final zero/unit
multipliers, use the existing constant propagation pass afterwards:

.. code-block:: python

    collected = sfg.transform("coefficients", repeat=True)
    result = collected.constant_propagation(assume_zero_initial_state=False)

These patterns do not reassociate unrelated terms to find separated matches.
For example, ``(C_2(x) + y) + C_3(x)`` is left unchanged by the ``coefficients``
collection. Factoring uses explicit
:class:`~b_asic.core_operations.Multiplication` nodes; collection uses explicit
:class:`~b_asic.core_operations.ConstantMultiplication` nodes.

The ``sharing`` collection reuses an existing two-input sum or difference in
another two-operation addition/subtraction tree. It covers all operand
positions and compatible sign combinations. For example,
``(a-b, b + (c-a))`` becomes ``(u, c-u)``, where ``u=a-b`` is computed once.
Similarly, ``(a+b, a + (c+b))`` becomes ``(u, u+c)``. The shared inputs must
have the same signs for a sum, or opposite signs for a difference, allowing
the shared result to appear with either sign in the replacement.

.. code-block:: python

    result = sfg.transform("sharing", repeat=True)

Each match removes one binary addition/subtraction. When the coefficients of
both the shared result and the remaining input are negative, the replacement
adds a negation, for example ``(a-b, (b-c)-a) -> (u, -c-u)``.
Both retained arithmetic operations preserve their names and timing. The
shared operation retains its ID; the consumer receives a fresh ID if its
operation type changes.
The consumer's root is the anchor; ``within`` must include the existing shared
operation and both consumer operations. The shared value may feed any other
consumers and need not be an SFG output, while the removed intermediate must
not feed outside consumers. All three inputs may bind arbitrary source ports,
including outputs of larger subgraphs. Repeated passes let several consumers
reuse the same shared result; overlapping matches use it once per pass.

Conjugate sharing likewise handles larger trees with repeated passes.
The ``complex`` collection includes double-negation cancellation so four
successive imaginary multiplications reduce to wiring with ``repeat=True``.
Factoring and conjugate sharing retain the arithmetic operation and one
multiplier/conjugate operation through their ``preserve`` mappings.

``complex.three_multiplication_product`` detects the real arithmetic network
implementing ``(a + j*b) * (c + j*d)``. It matches the separate real and
imaginary branches together, replacing four multiplications and two additions/
subtractions with three multiplications and five additions/subtractions.
Both outputs are reconnected by name, including when their consumers appear
in a different order. Multiplier inputs and the imaginary addition may be
commuted. All four component source ports must bind consistently across the
two branches. Products with outside consumers prevent the rule from matching;
fanout of component inputs and real/imaginary results is unrestricted.

.. code-block:: python

    result = sfg.transform("complex.three_multiplication_product")

The anchor is the real-output subtraction. ``target`` therefore selects that
operation, while ``within`` must cover both branches. The ``a*c`` and ``b*d``
multipliers and real-output subtraction retain their IDs. The imaginary-output
addition becomes a subtraction with a fresh ID. All four retained operations
keep their names and timing.
The same three-multiplication decomposition is used by
``complex_to_real(multiplication_method="three")``; this rule also recognizes
an existing real SFG built independently of complex-to-real conversion.
The rewrite changes rounding and intermediate ranges, so apply it before
scheduling and quantization.

Shift folding handles every ordered pair of
:class:`~b_asic.core_operations.LeftShift`,
:class:`~b_asic.core_operations.RightShift`, and
:class:`~b_asic.core_operations.Shift`. Signed shift amounts follow the current
``Shift.evaluate`` convention: a positive amount divides by that power of two.
The result is an explicit left/right shift, or wiring if the net amount is
zero. Repeated passes fold longer chains. These are algebraic transformations;
in particular, canceling opposite shifts does not preserve intermediate
fixed-point rounding or overflow.

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

The ``preserve`` mapping retains named operations' names, execution times,
and port timing. Graph IDs are retained only when the operation type is
unchanged. A type change always receives a fresh ID generated for the new
type, even when the operation appears in ``preserve``. For example, an
``add40`` Addition rewritten as a Subtraction receives a new ``sub...`` ID.
Computational parameters come from the replacement. Input
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
Cancellation and reassociation assume ordinary finite algebra; they do not
guarantee identical floating-point rounding, signed zeros, or behavior for
NaNs and infinities.

Reference
---------

.. automodule:: b_asic.rewrites
   :members:
   :undoc-members:
