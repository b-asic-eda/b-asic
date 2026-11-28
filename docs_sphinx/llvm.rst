Importing C, C++, and LLVM IR
=============================

The :mod:`b_asic.llvm` module converts a static LLVM function into an
:class:`~b_asic.sfg.SFG`. Clang can serve as a frontend for both C and C++:
constant expressions, templates, local variables, and loops are resolved by the
compiler before B-ASIC reads the resulting IR.

For a downloadable C file and its rendered SFG, see the
:doc:`C-to-SFG gallery example <examples/creating_and_transforming_sfgs/c_to_sfg>`.

Installation
------------

Install the optional LLVM reader::

    pip install "b-asic[llvm]"

For C/C++, also install `Clang <https://releases.llvm.org/>`_ separately and put
it on your executable search path, or pass its path as ``clang=...``. Its emitted
LLVM IR must be compatible with the LLVM version bundled with llvmlite. Check
``clang --version`` and ``llvmlite.binding.llvm_version_info`` when investigating
parser errors; installing llvmlite does not install a C/C++ compiler.

A C example
-----------

Write a pure function with scalar ``float`` inputs and one ``float`` return.
Use ``f`` suffixes on constants to avoid implicit double-precision conversions:

.. code-block:: c

    // kernel.c
    float kernel(float x, float gain) {
        float result = x;
        for (int i = 0; i < 4; ++i) {
            if (i % 2 == 0)
                result = result * gain;
            else
                result = result + x;
        }
        return result;
    }

The loop count and each ``if`` condition depend only on compile-time values.
After unrolling and constant folding the function contains only arithmetic:

.. code-block:: python

    from b_asic import c_to_sfg

    sfg = c_to_sfg("kernel.c", function_name="kernel")
    assert sfg.evaluate(2.0, 3.0) == 26.0

Inputs follow the original argument order, including arguments optimized out
by Clang. The return value becomes the graph's single output. LLVM value names
are used as operation names where available.

C++ and constexpr
-----------------

C++17 is enabled for C++ files. ``constexpr``, templates, and ``if constexpr``
are useful for generating arithmetic with a fixed structure:

.. code-block:: cpp

    // kernel.cpp
    constexpr float gain(int n) {
        return n == 0 ? 1.0f : 2.0f * gain(n - 1);
    }

    template<bool Scale>
    float transform(float x) {
        constexpr float scale = gain(3);
        if constexpr (Scale)
            return x * scale;
        else
            return x;
    }

    extern "C" float kernel(float x) {
        return transform<true>(x) + 1.0f;
    }

.. code-block:: python

    from b_asic import cpp_to_sfg

    sfg = cpp_to_sfg("kernel.cpp", "kernel")
    assert sfg.evaluate(2.0) == 17.0

``c_to_sfg`` also detects C++ from any suffix other than ``.c``; ``language="c++"``
overrides this. ``cpp_to_sfg`` always selects C++. Use ``extra_args=["-std=c++20"]``
for a newer language standard. ``extern "C"`` avoids name mangling on entry
points. Otherwise, supply the exact mangled LLVM symbol as ``function_name``.
The compiler still needs to emit a definition: unused templates and functions
evaluated exclusively at compile time may have no standalone LLVM definition.

``constexpr`` permits compile-time evaluation; it does not force every call to
be evaluated at compile time. Store computed coefficients in ``constexpr``
variables, as above, to require constant evaluation. Calls that depend on runtime inputs must inline
and reduce to supported arithmetic. C++ runtime machinery such as allocation,
exceptions, virtual dispatch, and remaining library calls is unsupported.

Array interfaces: memory or streams
-----------------------------------

Pointer syntax does not specify whether an algorithm's arrays belong in a
memory or on ordinary SFG ports. For example, the same FFT can use either
interface. Supply an ``arrays`` mapping to any of the import helpers to make
the interpretation explicit. Keys are LLVM argument names; prefix global
symbols with ``@``. Array sizes count scalar elements, not bytes.

Consider a two-point FFT butterfly operating in place:

.. code-block:: c

    void butterfly(float data[2]) {
        float a = data[0];
        float b = data[1];
        data[0] = a + b;
        data[1] = a - b;
    }

.. code-block:: python

    from b_asic import LLVMArray, c_to_sfg

    memory_sfg = c_to_sfg(
        "butterfly.c", "butterfly",
        arrays={"data": LLVMArray("inout", 2, interface="memory")},
    )
    stream_sfg = c_to_sfg(
        "butterfly.c", "butterfly",
        arrays={"data": LLVMArray("inout", 2, interface="stream")},
    )
    assert memory_sfg.evaluate(3.0, 1.0) == [4.0, 2.0]
    assert stream_sfg.evaluate(3.0, 1.0) == [4.0, 2.0]

``interface="memory"`` creates named
:class:`~b_asic.special_operations.MemoryRead` and
:class:`~b_asic.special_operations.MemoryWrite` operations with constant element
addresses. These operations behave as SFG inputs and outputs during simulation;
the importer does not allocate a Python RAM or feed outputs back automatically.

``interface="stream"`` creates ordinary :class:`~b_asic.special_operations.Input`
and :class:`~b_asic.special_operations.Output` ports. Each array element has a
separate scalar port in the same SFG iteration. This is the ordinary B-ASIC
dataflow interface; a serialized, one-sample-per-clock protocol is not inferred.
Different input/output arrays may independently choose either interface.

The ``role`` controls lifetime and access permissions:

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Role
     - Interpretation
   * - ``input``
     - Fresh values supplied each iteration. Stores are rejected.
   * - ``output``
     - Final stored values become outputs. Reads require an earlier store
       to the same location in the current invocation.
   * - ``inout``
     - Fresh input values and final output values share the same array name.
       This models an in-place transform without introducing persistent state.
   * - ``state``
     - Internal values persist across SFG iterations through Delay operations.
       There are no external array ports.

All input/inout array elements become input ports, in ascending address order.
Pointer arguments are expanded at their position in the function signature;
scalar arguments keep their original positions. Configured global inputs follow
arguments, ordered by global symbol name. A scalar return, when present, is the
first output; output/inout arrays then follow argument/global order and ascending
written address. Only locations actually written produce output ports.

Within one invocation, loads after stores use the latest value, repeated loads
share an input, and repeated stores to a location expose only its final value.
Thus the graph models the computed transform, not a bus trace of every access.
Untouched output locations are not overwritten. C functions with array outputs
can return ``void``.

All indices must resolve to constant addresses after optimization. Nested arrays
are flattened in row-major order. Clang's constant byte-offset GEPs are accepted
when they land on whole elements. Set ``element_type="double"`` for arrays of
LLVM doubles; it defaults to ``"float"``. The importer validates access widths
and bounds against the configured size. Values still use B-ASIC's generic data
type, and reset values and constants are Python floats.

Different configured names denote disjoint storage. Use C ``restrict`` or C++
``__restrict`` where appropriate to express the same non-aliasing contract to
Clang. An in-place algorithm should use one ``inout`` array rather than two
names for overlapping buffers. Dynamic addresses, partial-element accesses,
pointer reinterpretation to other element widths, volatile/atomic accesses,
and memory-copy intrinsics are unsupported. Local scratch allocations must
still be optimized away.

Persistent state with delays
----------------------------

Use ``role="state"`` when values belong to the algorithm across calls, rather
than arriving in a new input buffer. For example:

.. code-block:: c

    float accumulate(float x, float *state) {
        *state = *state + x;
        return *state;
    }

.. code-block:: python

    from b_asic import LLVMArray, Simulation, c_to_sfg

    state_sfg = c_to_sfg(
        "accumulate.c", "accumulate",
        arrays={"state": LLVMArray("state", 1, initial_values=[0.0])},
    )
    simulation = Simulation(state_sfg, [2.0])
    assert [simulation.step()[0] for _ in range(3)] == [2.0, 4.0, 6.0]

The state pointer is removed from the external interface. A
:class:`~b_asic.special_operations.Delay` holds each used state element's
previous-iteration value, with its input connected to the final store for that
element. A location without a store retains its value. Stores are visible to
later loads in the same invocation, while delay updates take effect together
at the iteration boundary. Use :class:`~b_asic.simulation.Simulation` to retain
state across iterations; standalone ``sfg.evaluate`` starts from reset values.

Pointer state defaults to zero initialization. ``initial_values`` can specify
one reset value per element. A mapped C global or static variable requires
explicit reset values, since LLVM initializers are not inferred. For example,
Clang may emit a local static named ``@kernel.history``; configure it with
``arrays={"@kernel.history": LLVMArray("state", 1, initial_values=[1.5])}``.
Use the exact emitted LLVM symbol, including any C++ name mangling. The supplied
reset values define the SFG initialization independently of the C initializer.

State arrays and external input/output/inout arrays cannot currently be combined
in one imported function. Scalar arguments and scalar returns may accompany
either mode. Unknown or unconfigured pointer accesses produce warnings and are
rejected rather than guessed to be state.

The :doc:`array gallery example <examples/creating_and_transforming_sfgs/c_arrays_to_sfg>`
shows the same butterfly with memory and ordinary ports, plus a separate
stateful accumulator and its delay feedback.

Writing code that becomes a static SFG
--------------------------------------

* Use scalar floating-point inputs/returns or explicitly configured arrays. Both
  LLVM ``float`` and ``double`` are accepted. Prefer consistent C ``float``
  arithmetic; mixed precision can introduce unsupported conversion instructions.
* Loops must have a fixed, compile-time trip count and be fully unrolled by
  Clang. Integer loop counters are fine if optimization removes them. A
  constant bound alone does not guarantee successful unrolling. Nested loops
  can produce very large graphs.
* ``if``, ``switch``, and the conditional operator are fine in source code when
  their conditions resolve at compile time. Runtime comparisons, branches,
  selects, and phi nodes are rejected, even if they could be represented by a
  more general hardware implementation.
* Configure pointer arguments and globals with ``LLVMArray``. Keep their
  addresses constant after loop unrolling, and distinguish input/output buffers
  from persistent state. Local temporary arrays are useful when optimization
  can eliminate their allocations and accesses.
* Small helper functions must inline. Avoid recursion depending on runtime
  values and external calls. ``sqrtf`` and ``fabsf`` can work when Clang lowers
  them to the supported LLVM intrinsics; inspect the IR if a call remains.
* Keep device/file I/O, assertions that survive optimization, allocation, and other side
  effects outside the imported function. Use ``extra_args`` for include paths
  and compile-time definitions, e.g. ``["-Iinclude", "-DCOUNT=4"]``. These paths
  are relative to the Python process's current working directory.

The helper requests ``-O3``, loop unrolling with a high threshold, and aggressive
inlining. It disables loop/SLP vectorization and floating-point contraction and
allows math intrinsics without preserving C ``errno`` effects. These flags are
requests to the optimizer, not a guarantee of acceptable IR. No fast-math flags
are enabled by default. Custom compiler options can affect numerical behavior;
the importer always checks the final result.

Supported LLVM and diagnostics
------------------------------

The selected function must have exactly one basic block, scalar
``float``/``double`` arguments or configured pointers, and a scalar
floating-point or ``void`` return. Supported arithmetic
instructions are ``fadd``, ``fsub``, ``fmul``, ``fdiv``, ``fneg``, and calls to
``llvm.sqrt.f32``, ``llvm.sqrt.f64``, ``llvm.fabs.f32``, or ``llvm.fabs.f64``.
Constant-address ``getelementptr``, scalar ``load``, and scalar ``store`` are
also supported for configured arrays. Floating-point constants become Python
``float`` constants. Integer signal data,
casts, vectors, aggregates, undefined/poison values, runtime control
flow, and other calls (including fused multiply-add) are unsupported.

Each unsupported construct in the selected function produces an
:class:`~b_asic.llvm.LLVMImportWarning`, followed by
:class:`~b_asic.llvm.UnsupportedLLVMError`. No partial graph is returned.
Instructions with unused results are also checked; side effects cannot silently
disappear. Other functions in the module are outside the import scope.
Compiler warnings are forwarded, and compiler errors include Clang's diagnostic
text. Malformed or unverifiable LLVM raises ``ValueError``.

The graph represents arithmetic using B-ASIC operations and its generic data
type. LLVM widths, rounding at individual instructions, fast-math assumptions,
NaN/poison semantics, and C exception/``errno`` behavior are not reproduced as a
bit-exact model. Select a B-ASIC simulation data type later as appropriate.
Array roles and interfaces are explicit; the frontend does not infer a hardware
bus protocol, memory arbitration, or serialization schedule.

Importing LLVM directly
-----------------------

.. code-block:: python

    from b_asic import llvm_file_to_sfg, llvm_to_sfg

    sfg = llvm_file_to_sfg("kernel.ll", function_name="kernel")
    identity = llvm_to_sfg(
        "define float @identity(float %x) { ret float %x }"
    )

Omit ``function_name`` only when the module contains exactly one function
definition; declarations of intrinsics or external functions do not count.
Direct LLVM import parses and verifies the IR but does not optimize it. Use
Clang or LLVM's ``opt`` beforehand to simplify independently generated IR.

To inspect compiler output manually, start with::

    clang -O3 -S -emit-llvm -fno-vectorize -fno-slp-vectorize -ffp-contract=off -fno-math-errno -funroll-loops -mllvm -unroll-threshold=1000000 -mllvm -inline-threshold=1000000 kernel.c -o kernel.ll

Use ``clang -x c++ -std=c++17`` with the same optimization flags for C++.
The Python helper keeps its generated IR in a temporary directory that is
removed after import.
