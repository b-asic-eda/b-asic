Importing C, C++, and LLVM IR
===========================

The :mod:`b_asic.llvm` module converts a static scalar LLVM function into an
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

Writing code that becomes a static SFG
-------------------------------------

* Use scalar floating-point inputs and a scalar floating-point return. Both
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
* Local scalar variables and temporary arrays are useful when optimization can
  eliminate every load, store, allocation, and address calculation. Pointer or
  array arguments, global memory accesses, volatile data, and persistent state
  are unsupported. For a small fixed-size input, expose separate scalar
  arguments and create any temporary array inside the function.
* Small helper functions must inline. Avoid recursion depending on runtime
  values and external calls. ``sqrtf`` and ``fabsf`` can work when Clang lowers
  them to the supported LLVM intrinsics; inspect the IR if a call remains.
* Keep I/O, assertions that survive optimization, allocation, and other side
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

The selected function must have exactly one basic block, fixed scalar
``float``/``double`` arguments, and one scalar floating-point return. Supported
instructions are ``fadd``, ``fsub``, ``fmul``, ``fdiv``, ``fneg``, and calls to
``llvm.sqrt.f32``, ``llvm.sqrt.f64``, ``llvm.fabs.f32``, or ``llvm.fabs.f64``.
Floating-point constants become Python ``float`` constants. Integer data,
casts, vectors, aggregates, undefined/poison values, memory, runtime control
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
This frontend does not infer delays, state, or a streaming memory interface.

Importing LLVM directly
----------------------

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
