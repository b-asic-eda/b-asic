"""
Import static floating-point LLVM functions as signal flow graphs.

The optional ``llvm`` extra supplies llvmlite. Compiling C or C++ additionally
requires a separately installed Clang; its LLVM version must be compatible with
llvmlite. See :doc:`/llvm` for the supported subset and source-writing guidance.
"""

import os
import re
import subprocess
import warnings
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from b_asic.core_operations import (
    Absolute,
    Addition,
    Constant,
    Division,
    Multiplication,
    Negation,
    SquareRoot,
    Subtraction,
)
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output

if TYPE_CHECKING:
    from llvmlite.binding import ValueRef

    from b_asic.port import SignalSourceProvider

__all__ = [
    "LLVMImportWarning",
    "UnsupportedLLVMError",
    "c_to_sfg",
    "cpp_to_sfg",
    "llvm_file_to_sfg",
    "llvm_to_sfg",
]

_BINARY = {
    "fadd": Addition,
    "fsub": Subtraction,
    "fmul": Multiplication,
    "fdiv": Division,
}
_INTRINSICS = {
    "llvm.sqrt.f32": SquareRoot,
    "llvm.sqrt.f64": SquareRoot,
    "llvm.fabs.f32": Absolute,
    "llvm.fabs.f64": Absolute,
}
_FLOAT_TYPES = {"float", "double"}


class LLVMImportWarning(UserWarning):
    """Unsupported LLVM features or diagnostics emitted by Clang."""


class UnsupportedLLVMError(ValueError):
    """The selected function cannot be translated completely to an SFG."""


def _binding():
    """Load the optional dependency only when an importer is used."""
    try:
        from llvmlite import binding  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "LLVM import requires llvmlite; install B-ASIC with 'pip install b-asic[llvm]'."
        ) from exc
    return binding


def llvm_to_sfg(ir: str, function_name: str | None = None) -> SFG:
    """
    Convert textual LLVM IR to an SFG using llvmlite.

    Parameters
    ----------
    ir : str
        LLVM assembly text, already optimized to scalar straight-line code.
    function_name : str, optional
        Exact LLVM symbol to import. Required if several definitions exist.

    Returns
    -------
    SFG
        One input per argument, in declaration order, and one return output.
        Constants are Python floats; LLVM precision is not retained as a
        simulation data type. Unused arguments remain SFG inputs.

    Raises
    ------
    UnsupportedLLVMError
        After warning about each unsupported construct in the selected function.
        No partial graph is returned.
    ValueError
        If LLVM parsing/verification or function selection fails.
    ImportError
        If llvmlite is not installed.

    Notes
    -----
    Supports scalar ``float``/``double`` arguments, return values and constants,
    ``fadd``, ``fsub``, ``fmul``, ``fdiv``, ``fneg``, and ``llvm.sqrt``/``llvm.fabs``.
    Runtime control flow, memory, vectors, integer data, conversions, and other
    calls are rejected, including unsupported instructions whose results are
    unused. Other functions in the module are not imported or inspected.
    """
    binding = _binding()
    try:
        module = binding.parse_assembly(ir)
    except RuntimeError as exc:
        raise ValueError(f"Cannot parse LLVM IR: {exc}") from exc
    with module:
        try:
            module.verify()
        except RuntimeError as exc:
            raise ValueError(f"Invalid LLVM IR: {exc}") from exc
        functions = [fn for fn in module.functions if not fn.is_declaration]
        if function_name is None:
            if len(functions) != 1:
                raise ValueError(
                    "Specify function_name when the module does not have exactly "
                    f"one function definition; found {[fn.name for fn in functions]}."
                )
            function = functions[0]
        else:
            function = next((fn for fn in functions if fn.name == function_name), None)
            if function is None:
                raise ValueError(
                    f"No LLVM function definition named {function_name!r}."
                )
        return _function_to_sfg(function)


def _function_to_sfg(function: "ValueRef") -> SFG:
    """Validate the entire function before constructing any graph."""
    issues = []
    signature = function.global_value_type
    if signature.is_function_vararg:
        issues.append("Variadic functions are unsupported.")
    if str(signature.get_function_return()) not in _FLOAT_TYPES:
        issues.append("The function must return one scalar float or double.")
    arguments = list(function.arguments)
    issues.extend(
        f"Unsupported argument {argument}: expected float or double."
        for argument in arguments
        if str(argument.type) not in _FLOAT_TYPES
    )
    blocks = list(function.blocks)
    if len(blocks) != 1:
        issues.append(
            "Control flow is unsupported: expected a single basic block. "
            "Fully unroll loops and resolve branches at compile time."
        )
    instructions = [inst for block in blocks for inst in block.instructions]
    for inst in instructions:
        operands = list(inst.operands)
        opcode = inst.opcode
        if opcode == "call":
            supported = (
                operands[-1].name in _INTRINSICS
                and operands[-1].value_kind.name == "function"
                and len(operands) == 2
            )
            data_operands = operands[:-1]
        else:
            supported = opcode in {*_BINARY, "fneg", "ret"}
            data_operands = operands
        if not supported:
            issues.append(f"Unsupported LLVM instruction: {str(inst).strip()}")
            continue
        if opcode != "ret" and str(inst.type) not in _FLOAT_TYPES:
            issues.append(f"Unsupported result type: {str(inst).strip()}")
        issues.extend(
            f"Unsupported operand {operand} in {str(inst).strip()}"
            for operand in data_operands
            if str(operand.type) not in _FLOAT_TYPES
            or operand.value_kind.name
            not in {
                "argument",
                "instruction",
                "constant_fp",
            }
        )
        # Operand bundles could otherwise be mistaken for ordinary call arguments.
        if opcode == "call" and re.search(r"\]\s*(?:,\s*!.*)?$", str(inst)):
            issues.append(f"Call operand bundles are unsupported: {str(inst).strip()}")
    if issues:
        for issue in issues:
            warnings.warn(f"{function.name}: {issue}", LLVMImportWarning, stacklevel=3)
        raise UnsupportedLLVMError(
            f"Cannot import {function.name!r}: {len(issues)} unsupported construct(s)."
        )

    inputs = [
        Input(name=arg.name or f"arg{index}", real_valued=True)
        for index, arg in enumerate(arguments)
    ]
    values: dict[ValueRef, SignalSourceProvider] = dict(
        zip(arguments, inputs, strict=True)
    )

    def source(value: "ValueRef") -> "SignalSourceProvider":
        if value not in values:
            values[value] = Constant(float(value.get_constant_value()))
        return values[value]

    for inst in instructions:
        operands = list(inst.operands)
        if inst.opcode == "ret":
            return SFG(
                inputs,
                [Output(source(operands[0]), real_valued=True)],
                name=function.name,
            )
        if inst.opcode == "call":
            operation = _INTRINSICS[operands[-1].name]
            operands = operands[:-1]
        elif inst.opcode == "fneg":
            operation = Negation
        else:
            operation = _BINARY[inst.opcode]
        values[inst] = operation(*(source(arg) for arg in operands), name=inst.name)
    # Verified LLVM requires a terminator; validation excludes every other kind.
    raise UnsupportedLLVMError("The function has no scalar return.")


def llvm_file_to_sfg(
    path: str | os.PathLike[str], function_name: str | None = None
) -> SFG:
    """Read a textual LLVM IR file and import it with :func:`llvm_to_sfg`."""
    return llvm_to_sfg(Path(path).read_text(encoding="utf-8"), function_name)


def c_to_sfg(
    path: str | os.PathLike[str],
    function_name: str | None = None,
    *,
    clang: str | os.PathLike[str] = "clang",
    language: str | None = None,
    extra_args: Sequence[str] = (),
) -> SFG:
    """
    Compile a C or C++ file to optimized LLVM IR, then attempt SFG import.

    Parameters
    ----------
    path : path-like
        Source file. ``.c`` selects C; other suffixes select C++.
    function_name : str, optional
        Exact LLVM function symbol; C++ entry points should use ``extern "C"``.
    clang : path-like, default: "clang"
        Clang executable compatible with llvmlite's LLVM reader.
    language : {"c", "c++"}, optional
        Override language detection. Defaults to C11 or C++17 respectively.
    extra_args : sequence of str
        Additional compiler arguments, for example ``["-Iinclude", "-DCOUNT=4"]``
        or ``["-std=c++20"]``. Paths are relative to the current working directory.
        Passed as individual arguments without a shell.

    Returns
    -------
    SFG
        The translated function. Compilation occurs in a temporary directory.

    Raises
    ------
    RuntimeError
        If Clang fails; includes the compiler diagnostics.
    UnsupportedLLVMError
        If optimization leaves unsupported constructs in the selected function.
    FileNotFoundError
        If the source file or compiler cannot be found.

    Notes
    -----
    Requests O3 optimization, aggressive full loop unrolling and inlining, and
    disables vectorization and floating-point contraction. These are requests,
    not guarantees: the importer checks the resulting IR. Compiler diagnostics
    are surfaced as :class:`LLVMImportWarning`. No fast-math flags are enabled.
    """
    _binding()  # Fail before invoking a compiler if the extra is missing.
    path = Path(path).resolve(strict=True)
    if language is None:
        language = "c" if path.suffix == ".c" else "c++"
    if language not in {"c", "c++"}:
        raise ValueError("language must be 'c' or 'c++'.")
    with TemporaryDirectory(prefix="b-asic-llvm-") as directory:
        output = Path(directory) / "module.ll"
        command = [
            os.fspath(clang),
            "-x",
            language,
            "-std=c11" if language == "c" else "-std=c++17",
            *extra_args,
            "-O3",
            "-S",
            "-emit-llvm",
            "-fno-vectorize",
            "-fno-slp-vectorize",
            "-ffp-contract=off",
            "-fno-math-errno",
            "-funroll-loops",
            "-mllvm",
            "-unroll-threshold=1000000",
            "-mllvm",
            "-inline-threshold=1000000",
            "-fno-discard-value-names",
            "-o",
            str(output),
            str(path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(
                f"Clang failed (exit {result.returncode}):\n{result.stderr or result.stdout}"
            )
        if result.stderr.strip():
            warnings.warn(result.stderr.strip(), LLVMImportWarning, stacklevel=2)
        return llvm_file_to_sfg(output, function_name)


def cpp_to_sfg(
    path: str | os.PathLike[str],
    function_name: str | None = None,
    *,
    clang: str | os.PathLike[str] = "clang",
    extra_args: Sequence[str] = (),
) -> SFG:
    """Compile C++ (including constexpr) using :func:`c_to_sfg` in C++ mode."""
    return c_to_sfg(
        path, function_name, clang=clang, language="c++", extra_args=extra_args
    )
