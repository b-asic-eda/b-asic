# ruff: noqa: D400, D415
"""
=======================================
C arrays as memory, streams, or state
=======================================

An array in C does not determine the SFG interface. For example, an FFT can
read and write memory or expose scalar streaming ports. The same pointer can
also be used by a different algorithm to hold persistent state.
:class:`~b_asic.llvm.LLVMArray` makes these choices explicit.

This example skips conversion if Clang or llvmlite is unavailable.
See :doc:`/llvm` for details and the supported LLVM subset.
"""

import sys
from importlib.util import find_spec
from pathlib import Path
from shutil import which

from b_asic import LLVMArray, Simulation, c_to_sfg

# %%
# Two different uses of arrays
# ----------------------------
#
# The :download:`C source <llvm_array_kernel.c>` contains an in-place FFT
# butterfly and a separate stateful accumulator. Each butterfly invocation
# receives fresh data; the accumulator retains its state between invocations.
#
# .. literalinclude:: llvm_array_kernel.c
#    :language: c

source_path = Path("llvm_array_kernel.c")
if not source_path.is_file():
    source_path = Path(sys.argv[0]).resolve().with_name("llvm_array_kernel.c")

clang = which("clang")
available = clang is not None and find_spec("llvmlite") is not None
if not available:
    print('Skipping conversion: install Clang and the "b-asic[llvm]" extra.')

# %%
# An input/output memory
# ----------------------
#
# ``role="inout"`` creates reads and writes in the same named memory. It does
# not introduce feedback across SFG iterations. Constant C offsets become
# zero-based element addresses on MemoryRead and MemoryWrite operations.

memory_sfg = None
if available:
    memory_sfg = c_to_sfg(
        source_path,
        "butterfly",
        clang=clang,
        arrays={"data": LLVMArray("inout", 2, interface="memory")},
    )
    print(memory_sfg.evaluate(3.0, 1.0))

memory_sfg  # noqa: B018 - Display the SFG in the gallery.

# %%
# The same algorithm with ordinary ports
# ---------------------------------------
#
# Changing only ``interface`` creates ordinary Input/Output ports instead.
# Here, "stream" means one scalar port per element per SFG iteration; a serial
# streaming protocol and its scheduling are not inferred.

stream_sfg = None
if available:
    stream_sfg = c_to_sfg(
        source_path,
        "butterfly",
        clang=clang,
        arrays={"data": LLVMArray("inout", 2, interface="stream")},
    )
    print(stream_sfg.evaluate(3.0, 1.0))

stream_sfg  # noqa: B018 - Display the SFG in the gallery.

# %%
# Persistent state becomes a delay
# --------------------------------
#
# ``role="state"`` represents storage internal to the SFG. The array disappears
# from the external ports and its previous value comes from a Delay. This is
# a separate algorithm: combining state arrays with input/output arrays is
# currently unsupported. Scalar inputs and returns remain available.

state_sfg = None
if available:
    state_sfg = c_to_sfg(
        source_path,
        "accumulate",
        clang=clang,
        arrays={"state": LLVMArray("state", 1, initial_values=[0.0])},
    )
    simulation = Simulation(state_sfg, [2.0])
    print([simulation.step()[0] for _ in range(3)])

state_sfg  # noqa: B018 - Display the SFG in the gallery.
