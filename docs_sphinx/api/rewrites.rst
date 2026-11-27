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

Choose a complex-multiplication implementation without listing the other rules:

.. code-block:: python

    result = sfg.transform(multiplication_method="threealt", repeat=True)
    matches = sfg.find_rewrites(multiplication_method="threealt")

The keyword selects one complex-product rewrite variant while retaining all
other selected rules. ``"three"`` uses the original three-product algorithm;
``"threealt"`` uses the alternative with an imaginary component in its shared
product. ``"four"`` disables complex-product reduction. The default, None,
uses an explicitly named product variant if supplied, or ``"three"`` for
collections and the complete rule set. Explicit rule objects work the same
way as names. Selecting both variants explicitly, or supplying a conflicting
keyword, raises ValueError. Choices are local to each call and resolved before
matching, so registration order does not choose the algorithm.

Each applied rewrite logs its rule name, anchor graph ID, and matched operation
IDs at DEBUG level through the package logger. Enable these messages with
``b_asic.logger.getLogger("DEBUG")``. Finding matches and skipping overlapping
or invalidated matches do not produce application messages.

Node compatibility checks are cached within each search, including built-in
coefficient and shift matching. Each search starts with a fresh cache, so later
passes and calls observe changes to operation parameters and connections.
Before constructing a matcher, rules are skipped if their exact operation types
and required counts are unavailable in ``within``, or no eligible ``target``
has the anchor's type. This check runs afresh on every pass, so rules become
eligible when earlier replacements introduce the required operation types.
For default and built-in node predicates, compatible candidates are filtered
before structural checks, and boundary source ports are checked as partial
matches grow. All valid commutative input orders remain available. Unguarded
rules using these predicates start matching from their anchor. Custom
``node_match`` callbacks retain their original traversal and uncached evaluation;
guarded rules retain their traversal order and evaluate conditions on complete
matches. Returned matches keep their usual deterministic order.
Component copying also reuses constructor signatures through a bounded
cache; constructor arguments and parameter values are bound afresh for each copy.

Both ``apply_rewrites`` and ``transform`` copy the host SFG once, then apply
replacements sequentially in place on that copy. With ``repeat=True``, all passes
reuse the same copy. Matches are rebound against the updated graph before each
replacement, and component indices and traversal caches are refreshed without
copying components. IDs allocated in earlier passes remain reserved.
Overlapping or invalidated matches are still skipped, and
the caller's graph is unchanged even if a replacement fails.

In the table, ``C_k(x)`` denotes a
:class:`~b_asic.core_operations.ConstantMultiplication` with coefficient ``k``;
``conj(x)`` denotes :class:`~b_asic.core_operations.ComplexConjugate`;
``j*x`` denotes :class:`~b_asic.core_operations.ImaginaryMultiplication`;
``S(x)`` denotes a shift with a common effective scale.
Rows with ``*`` group rule families with generated variants;
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
   * - ``arithmetic.negated_product_chain``
     - ``arithmetic``, ``negations``
     - ``d + (((-a) * b) * c)``
     - ``d - ((a * b) * c)``
   * - ``arithmetic.subtract_negated_product_chain``
     - ``arithmetic``, ``negations``
     - ``d - (((-a) * b) * c)``
     - ``d + ((a * b) * c)``
   * - ``arithmetic.negated_product_difference``
     - ``arithmetic``, ``negations``
     - ``((-a) * b - c) + d``
     - ``d - (a * b + c)``
   * - ``arithmetic.negated_product_minus_difference``
     - ``arithmetic``, ``negations``
     - ``(-a) * b - (c - d)``
     - ``(d - c) - (a * b)``
   * - ``arithmetic.subtract_negated_product_difference``
     - ``arithmetic``, ``negations``
     - ``d - ((-a) * b - c)``
     - ``d + (a * b + c)``
   * - ``arithmetic.negated_sum_product``
     - ``arithmetic``, ``negations``
     - ``((-a) - b) * c + d``
     - ``d - (a + b) * c``
   * - ``arithmetic.subtract_negated_sum_product``
     - ``arithmetic``, ``negations``
     - ``d - ((-a) - b) * c``
     - ``d + (a + b) * c``
   * - ``arithmetic.double_negation``
     - ``arithmetic``, ``negations``, ``complex``
     - ``-(-a)``
     - ``a``
   * - ``arithmetic.add_negation``
     - ``arithmetic``, ``negations``
     - ``a + (-b)``
     - ``a - b``
   * - ``arithmetic.negated_difference``
     - ``arithmetic``, ``negations``
     - ``-(a - b)``
     - ``b - a``
   * - ``arithmetic.factor_addition``
     - ``arithmetic``, ``factoring``
     - ``a * b + a * c``
     - ``a * (b + c)``
   * - ``arithmetic.factor_subtraction``
     - ``arithmetic``, ``factoring``
     - ``a * b - a * c``
     - ``a * (b - c)``
   * - ``arithmetic.factor_addition_sum``
     - ``arithmetic``, ``factoring``
     - ``(a*b + c) + (a*d + e)``
     - ``a*(b + d) + (c + e)``
   * - ``arithmetic.factor_subtraction_sum``
     - ``arithmetic``, ``factoring``
     - ``(a*b + c) - (a*d + e)``
     - ``a*(b - d) + (c - e)``
   * - ``arithmetic.factor_constant_addition``
     - ``arithmetic``, ``factoring``
     - ``C_k(a) + C_k(b)``
     - ``C_k(a + b)``
   * - ``arithmetic.factor_constant_subtraction``
     - ``arithmetic``, ``factoring``
     - ``C_k(a) - C_k(b)``
     - ``C_k(a - b)``
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
   * - ``arithmetic.collect_separated_addition_coefficients``
     - ``arithmetic``, ``coefficients``
     - ``(C_k(x) + y) + C_m(x)``
     - ``C_(k+m)(x) + y``
   * - ``arithmetic.collect_separated_subtraction_coefficients``
     - ``arithmetic``, ``coefficients``
     - ``(C_k(x) + y) - C_m(x)``
     - ``C_(k-m)(x) + y``
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
   * - ``arithmetic.share_opposite_difference``
     - ``arithmetic``, ``sharing``
     - ``(a-b, b-a)``
     - ``(u, -u)``, where ``u=a-b`` is computed once
   * - ``arithmetic.share_negated_product``
     - ``arithmetic``, ``sharing``
     - ``(a*b, (-a)*b)``
     - ``(u, -u)``, where ``u=a*b`` is computed once
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
   * - ``complex.share_imaginary_addition``
     - ``arithmetic``, ``complex``
     - ``j*a + j*b``
     - ``j*(a + b)``
   * - ``complex.share_imaginary_subtraction``
     - ``arithmetic``, ``complex``
     - ``j*a - j*b``
     - ``j*(a - b)``
   * - ``complex.three_multiplication_product``
     - ``arithmetic``, ``complex``
     - ``(a*c - b*d, a*d + b*c)``
     - ``(p - q, t - p - q)``, where ``p=a*c``, ``q=b*d``, ``t=(a+b)*(c+d)``
   * - ``complex.threealt_multiplication_product``
     - ``arithmetic``, ``complex``
     - ``(a*c - b*d, a*d + b*c)``
     - ``(k2 - k1, k1 + k3)``, where ``k1=d*(a+b)``, ``k2=a*(c+d)``, ``k3=b*(c-d)``
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
   * - ``shifts.share_*_addition``
     - ``arithmetic``, ``shifts``
     - ``S(a) + S(b)``
     - ``S(a + b)``
   * - ``shifts.share_*_subtraction``
     - ``arithmetic``, ``shifts``
     - ``S(a) - S(b)``
     - ``S(a - b)``

Product patterns also match ``b * (-a)`` in place of ``(-a) * b``.
The addition in ``arithmetic.negated_product`` also accepts the product on
either input, so ``c + (-a) * b`` matches as well. More generally,
multiplication inputs match in either order, and addition inputs do so when
their scales are equal and ``mul_j=False``. This applies to custom rules too.
Other operation inputs retain their specified order. Addition and subtraction
in these patterns use :class:`~b_asic.core_operations.Addition` and
:class:`~b_asic.core_operations.Subtraction` with default computational parameters.
In particular, the factoring, collection, cancellation, arithmetic-sharing,
and unary-factor-sharing rules do not match scaled arithmetic or arithmetic with
``mul_j=True``.

``arithmetic.negated_product`` and ``arithmetic.subtract_negated_product``
also handle a multiplier shared by several compatible consumers. All consumers
are included in one atomic match and transformed together: for ``p=(-a)*b``,
``p+c`` becomes ``c-a*b`` and ``d-p`` becomes ``d+a*b``. The multiplier remains
shared and retains its ID; each addition/subtraction receives a fresh ID and
retains its name and timing. Previewing the returned match's replacement shows
the entire consumer group.

This requires every multiplier output connection to feed an ordinary unscaled
Addition, or the second input of an ordinary unscaled Subtraction. Each consumer
must use the product exactly once. Any other consumer, including a direct SFG
output, Sink, scaled operation, or a subtraction using the product on its first
input, prevents the whole transformation. The input negation must have just one
connection to the multiplier. Consumer results may have arbitrary fanout,
including connections to other consumers in the same group. ``target`` selects
a representative consumer of the chosen rule's type; ``within`` must include
the negation, multiplier, and every consumer, even consumers outside ``target``.
One pass transforms the whole group; multiplier duplication is not needed.

The ``negated_product_chain`` and ``subtract_negated_product_chain`` rules
absorb a sign through two successive multiplications into their addition or
subtraction consumer. Both multipliers accept swapped inputs, and the addition
accepts the product on either input. The subtraction requires the product on
its second input. The negation and multiplier results must have no other
consumers; the root result and boundary inputs may have arbitrary fanout.
Both multipliers keep their IDs, names, and timing. The changed addition or
subtraction gets a fresh graph ID while retaining its name and timing.

The two product-difference rules extend ``(-a) * b - c`` through its consumer.
They change the inner subtraction to addition and absorb its negative sign
into an outer addition or the subtraction input of an outer subtraction.
Their anchor is that consumer, so ``target`` selects the downstream addition
or subtraction. The multiplier retains its ID. Arithmetic operations that
change type receive fresh IDs; all three operations retain their names and
timing through the rules' ``preserve`` mappings.

The ``negated_sum_product`` and ``subtract_negated_sum_product`` rules absorb
the sign of ``(-a) - b`` through a multiplication into its consumer, replacing
the inner subtraction with ``a + b``. Multiplication and addition operands may
be swapped; a subtraction consumer requires the product on its second input.
The input negation, inner subtraction, and multiplier must have no other
consumers. Boundary inputs and the final result may have arbitrary fanout.
The multiplier retains its ID, name, and timing. The changed arithmetic
operations receive fresh IDs and retain their names and timing.
With ``repeat=True``, the negation rules also normalize
``((-a) + (-b)) * c + d`` to ``d - (a + b) * c``.

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

The original factoring and coefficient collection rules use two-term patterns.
Repeated passes also handle larger trees whose terms share the same source
port. For example,
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

The ``collect_separated_*_coefficients`` and ``factor_*_sum`` rules also
reassociate ordinary addition/subtraction trees of arbitrary size. Their names
select the root operation's type; internal nodes may mix additions and
subtractions. They collect all eligible occurrences of one source or product
factor per match, including their signs, even when unrelated terms intervene.
For example, ``(C_2(x) + y) + C_3(x)`` becomes ``C_5(x) + y``, and
``(a*b + c) - (a*d + e)`` becomes ``a*(b-d) + (c-e)``. Coefficient collection
includes implicit unit terms. Further groups are handled with ``repeat=True``.
Factoring uses explicit :class:`~b_asic.core_operations.Multiplication` nodes;
collection uses explicit :class:`~b_asic.core_operations.ConstantMultiplication`
nodes. Common constant factors are handled by ``factor_constant_*`` instead.

Sum-tree expansion stops at shared intermediate results, scoped-out nodes,
and arithmetic with nondefault computational parameters. These remain boundary
sources and keep their other consumers. Collected multipliers must have a
single connection into the tree. Boundary sources and the root result may have
arbitrary fanout. Matches expose the complete concrete pattern and replacement
for preview and use the usual snapshot, scope, and metadata handling. Retained
operations preserve names and timing; changing an operation type gives it a
fresh graph ID. Each larger-sum collection reduces the number of sum operations,
and each product-factor extraction reduces the number of multipliers.

Common constant factors, imaginary factors, and shifts can be moved outside an
addition or subtraction. Repeated passes handle larger trees of these factors.
The two original unary operations must not feed outside consumers. Constant
coefficients must compare equal. Shift-sharing names have the form
``shifts.share_<left-type>_<right-type>_<addition-or-subtraction>`` and cover
same-type pairs of :class:`~b_asic.core_operations.LeftShift`,
:class:`~b_asic.core_operations.RightShift`, or
:class:`~b_asic.core_operations.Shift`, plus compatible pairs of a signed shift
with an explicit left or right shift. The effective scales must be equal.
Addition accepts either input order, with the explicit shift type retained
for mixed pairs. Subtraction provides both input orders and retains the left
shift's type and parameters. Zero shifts are handled by the
``shifts.remove_zero_*`` rules.

These algebraic rewrites do not model rounding or overflow at intermediate
operations. Moving scales or reassociating arithmetic may change quantized
results, just as existing factoring rules may change floating-point rounding.

The ``sharing`` collection reuses existing two-input sums and differences.
The ``share_sum_*`` and ``share_difference_*`` families cover all operand
positions and compatible sign combinations in another two-operation
addition/subtraction tree. For example,
``(a-b, b + (c-a))`` becomes ``(u, c-u)``, where ``u=a-b`` is computed once.
Similarly, ``(a+b, a + (c+b))`` becomes ``(u, u+c)``. The shared inputs must
have the same signs for a sum, or opposite signs for a difference, allowing
the shared result to appear with either sign in the replacement.

.. code-block:: python

    result = sfg.transform("sharing", repeat=True)

Each match removes one binary addition/subtraction. When the coefficients of
both the shared result and the remaining input are negative, the replacement
adds a negation, for example ``(a-b, (b-c)-a) -> (u, -c-u)``.
For these tree patterns, both retained arithmetic operations preserve their
names and timing. The shared operation retains its ID; the consumer receives
a fresh ID if its operation type changes.
The consumer's root is the anchor; ``within`` must include the existing shared
operation and both consumer operations. The shared value may feed any other
consumers and need not be an SFG output, while the removed intermediate must
not feed outside consumers. All three inputs may bind arbitrary source ports,
including outputs of larger subgraphs. Repeated passes let several consumers
reuse the same shared result; overlapping matches use it once per pass.

``arithmetic.share_opposite_difference`` handles ``(a-b, b-a)`` directly,
replacing the opposite subtraction with a negation of the shared result.
Its anchor is the subtraction to retain, so ``target`` selects the result
to reuse. Both subtraction results may feed arbitrary outside consumers;
neither needs to be an SFG output. ``within`` must include both subtractions.
The retained subtraction keeps its ID, name, and timing, while the new negation
receives a fresh ID. Repeated passes reuse one subtraction across several
opposite differences.

``arithmetic.share_negated_product`` similarly reuses ``a*b`` when ``(-a)*b``
is also computed. Multiplier inputs may be swapped, so negating either factor
is supported. The anchor is the product to retain; ``within`` must include
both multipliers and the input negation. Both product results may feed
arbitrary outside consumers. The input negation must feed only the removed
multiplier. The retained multiplier and the negation moved to its output keep
their IDs, names, and timing; the redundant multiplier is removed.
The default and ``arithmetic`` selections try this sharing before absorbing
product signs into consumer additions/subtractions.

Conjugate sharing likewise handles larger trees with repeated passes.
The ``complex`` collection includes double-negation cancellation so four
successive imaginary multiplications reduce to wiring with ``repeat=True``.
Factoring and conjugate sharing retain the arithmetic operation and one
multiplier/conjugate operation through their ``preserve`` mappings.

``complex.three_multiplication_product`` and
``complex.threealt_multiplication_product`` detect the real arithmetic network
implementing ``(a + j*b) * (c + j*d)``. They match the separate real and
imaginary branches together, replacing four multiplications and two additions/
subtractions with three multiplications and five additions/subtractions.
Both outputs are reconnected by name, including when their consumers appear
in a different order. Multiplier inputs and the imaginary addition may be
commuted. All four component source ports must bind consistently across the
two branches. Products with outside consumers prevent the rule from matching;
fanout of component inputs and real/imaginary results is unrestricted.

.. code-block:: python

    result = sfg.transform("complex.three_multiplication_product")
    alternative = sfg.transform(multiplication_method="threealt", repeat=True)

The anchor is the real-output subtraction. ``target`` therefore selects that
operation, while ``within`` must cover both branches. For ``"three"``, the
``a*c`` and ``b*d``
multipliers and real-output subtraction retain their IDs. The imaginary-output
addition becomes a subtraction with a fresh ID. All four retained operations
keep their names and timing.
The same three-multiplication decomposition is used by
``complex_to_real(multiplication_method="three")``. Both rules also recognize
an existing real SFG built independently of complex-to-real conversion.

For ``"threealt"``, the ``a*c`` multiplier's metadata is retained on ``k2``
and the ``b*d`` multiplier's metadata on ``k1``. The real subtraction and
imaginary addition retain their operation types and IDs. The same formula is
used by ``complex_to_real(multiplication_method="threealt")``. If either
operand has a known-zero imaginary component, matching prefers to place it at
``d`` so that ``k1`` vanishes. Subsequent constant propagation then leaves two
multiplications and no additions/subtractions for a product with a real operand.

These rewrites change rounding and intermediate ranges, so apply them before
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
The two basic negated-product rules can expand their patterns to include every
compatible multiplier consumer, declaring all consumer results as outputs.
An internal negation shared with another branch, or any unsupported multiplier
consumer, still prevents them from matching. Fanout on boundary input sources
and declared boundary outputs is unrestricted. For ``c - (-a) * b``, the sources
of ``a``, ``b``, and ``c`` may feed other branches; the negation and multiplication
belong to the matched region. The product-difference rules retain their fixed
patterns and reject outside consumers of their negation, multiplication, or
intermediate arithmetic result. The engine does not implicitly duplicate shared
internal producers.

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
