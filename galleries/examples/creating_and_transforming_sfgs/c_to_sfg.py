# ruff: noqa: D400, D415
"""
==========================
From C to an SFG with LLVM
==========================

Clang can turn a C function with fixed-length loops and compile-time branches
into static arithmetic. :func:`~b_asic.llvm.c_to_sfg` compiles the file to LLVM
IR and maps that arithmetic to B-ASIC operations.

Install ``b-asic[llvm]`` and a compatible Clang to run this example. If Clang or
llvmlite is unavailable, the example prints a message and skips conversion.
See :doc:`/llvm` for the supported subset and C++/``constexpr`` examples.
"""

import sys
from importlib.util import find_spec
from pathlib import Path
from shutil import which

from b_asic import c_to_sfg

# %%
# The C source
# ------------
#
# The :download:`C file <llvm_kernel.c>` below takes two floating-point inputs
# and returns one floating-point result. The loop has a constant trip count,
# and each ``if`` condition becomes constant after unrolling. No runtime
# branches remain in the optimized LLVM IR.
#
# .. literalinclude:: llvm_kernel.c
#    :language: c

source_path = Path("llvm_kernel.c")
if not source_path.is_file():
    source_path = Path(sys.argv[0]).resolve().with_name("llvm_kernel.c")

# %%
# Compile and import
# ------------------
#
# The helper requests optimization and full loop unrolling, then checks that
# the resulting LLVM function contains only supported operations. Unsupported
# constructs produce warnings and an error instead of a partial SFG.

clang = which("clang")
sfg = None
if clang is None:
    print("Skipping C-to-SFG conversion: Clang is not installed or not on PATH.")
elif find_spec("llvmlite") is None:
    print(
        'Skipping C-to-SFG conversion: install llvmlite with pip install "b-asic[llvm]".'
    )
else:
    sfg = c_to_sfg(source_path, function_name="kernel", clang=clang)
    print(f"kernel(2.0, 3.0) = {sfg.evaluate(2.0, 3.0)}")

# %%
# The resulting SFG
# -----------------
#
# The two inputs follow the C argument order, and the return value becomes
# the output. Constants and operations use B-ASIC's generic data type, which
# can be configured later. When compilation is available, the graph is shown
# below; otherwise this section has no graph.

sfg  # noqa: B018 - Sphinx-Gallery captures this expression as a graph.
