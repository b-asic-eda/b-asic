"""LLVM importer validation and C/C++ compiler integration tests."""

import shutil
import subprocess
import warnings

import pytest

from b_asic import (
    Constant,
    LLVMImportWarning,
    UnsupportedLLVMError,
    c_to_sfg,
    cpp_to_sfg,
    llvm_file_to_sfg,
    llvm_to_sfg,
)

pytest.importorskip("llvmlite.binding")


def test_arithmetic_and_argument_order():
    sfg = llvm_to_sfg("""
define float @arithmetic(float %x, float %y, float %unused) {
  %a = fadd float %x, 2.0
  %b = fsub float %a, %y
  %c = fmul float %b, %x
  %d = fdiv float %c, %y
  %e = fneg float %d
  ret float %e
}
""")
    assert sfg.input_count == 3
    assert sfg.output_count == 1
    assert sfg.evaluate(4.0, 2.0, 99.0) == -8.0
    assert sfg.name == "arithmetic"
    constants = sfg.find_by_type(Constant)
    assert constants
    assert all(isinstance(op.value, float) for op in constants)


@pytest.mark.parametrize("precision", ["float", "double"])
def test_constant_and_identity(precision):
    constant = llvm_to_sfg(f"define {precision} @constant() {{ ret {precision} 2.5 }}")
    assert constant.evaluate() == 2.5
    identity = llvm_to_sfg(
        f"define {precision} @identity({precision} %x) {{ ret {precision} %x }}"
    )
    assert identity.evaluate(-3.0) == -3.0


@pytest.mark.parametrize(("precision", "suffix"), [("float", "f32"), ("double", "f64")])
def test_math_intrinsics(precision, suffix):
    sfg = llvm_to_sfg(f"""
declare {precision} @llvm.sqrt.{suffix}({precision})
declare {precision} @llvm.fabs.{suffix}({precision})
define {precision} @math({precision} %x) {{
  %a = call {precision} @llvm.fabs.{suffix}({precision} %x)
  %b = call {precision} @llvm.sqrt.{suffix}({precision} %a)
  ret {precision} %b
}}
""")
    assert sfg.evaluate(-9.0) == 3.0


@pytest.mark.parametrize("value", ["undef", "poison"])
def test_undefined_values_are_rejected(value):
    with (
        pytest.warns(LLVMImportWarning, match="Unsupported operand"),
        pytest.raises(UnsupportedLLVMError),
    ):
        llvm_to_sfg(f"define float @bad() {{ ret float {value} }}")


@pytest.mark.parametrize(
    "instruction",
    [
        "%v = frem float %x, 2.0",
        "%v = fptosi float %x to i32",
        "%v = fcmp ogt float %x, 0.0",
        "%v = select i1 true, float %x, float 0.0",
        "%v = fpext float %x to double",
    ],
)
def test_unsupported_instructions_even_when_unused(instruction):
    with (
        pytest.warns(LLVMImportWarning, match="Unsupported LLVM instruction"),
        pytest.raises(UnsupportedLLVMError),
    ):
        llvm_to_sfg(f"define float @bad(float %x) {{ {instruction}\n ret float %x }}")


def test_reports_all_unsupported_instructions():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", LLVMImportWarning)
        with pytest.raises(UnsupportedLLVMError):
            llvm_to_sfg("""
define float @bad(float %x) {
  %a = alloca float
  store float %x, ptr %a
  %v = load float, ptr %a
  ret float %v
}
""")
    assert len(caught) == 3
    assert all(issubclass(w.category, LLVMImportWarning) for w in caught)


@pytest.mark.parametrize(
    ("signature", "body"),
    [
        ("i32 %x", "ret float 0.0"),
        ("ptr %x", "ret float 0.0"),
        ("<2 x float> %x", "ret float 0.0"),
        ("float %x, ...", "ret float %x"),
    ],
)
def test_unsupported_signature(signature, body):
    with pytest.warns(LLVMImportWarning), pytest.raises(UnsupportedLLVMError):
        llvm_to_sfg(f"define float @bad({signature}) {{ {body} }}")


def test_control_flow_rejected():
    with pytest.warns(LLVMImportWarning), pytest.raises(UnsupportedLLVMError):
        llvm_to_sfg("""
define float @branch(float %x, float %y) {
entry:
  %c = fcmp ogt float %x, %y
  br i1 %c, label %yes, label %no
yes:
  ret float %x
no:
  ret float %y
}
""")


def test_unknown_call_rejected():
    with (
        pytest.warns(LLVMImportWarning, match="Unsupported LLVM instruction"),
        pytest.raises(UnsupportedLLVMError),
    ):
        llvm_to_sfg("""
declare float @external(float)
define float @caller(float %x) {
  %v = call float @external(float %x)
  ret float %v
}
""")


def test_selection_and_file(tmp_path):
    ir = """
define float @one(float %x) { ret float %x }
define float @two() { ret float 2.0 }
"""
    with pytest.raises(ValueError, match="Specify function_name"):
        llvm_to_sfg(ir)
    with pytest.raises(ValueError, match="No LLVM function definition"):
        llvm_to_sfg(ir, "absent")
    path = tmp_path / "module.ll"
    path.write_text(ir, encoding="utf-8")
    assert llvm_file_to_sfg(path, "two").evaluate() == 2.0


def test_invalid_ir():
    with pytest.raises(ValueError, match="Cannot parse LLVM IR"):
        llvm_to_sfg("invalid llvm assembly")
    with pytest.raises(ValueError, match="Invalid LLVM IR"):
        llvm_to_sfg("define float @bad() { entry: br label %entry }")


@pytest.fixture
def clang():
    compiler = shutil.which("clang")
    if compiler is None:
        pytest.skip("Clang is not installed")
    return compiler


def test_c_loop_and_compile_time_branch(tmp_path, clang):
    path = tmp_path / "constant loop.c"
    path.write_text(
        """
float kernel(float x, float y) {
    float result = x;
    for (int i = 0; i < 4; ++i) {
        if (i % 2 == 0) result = result * y;
        else result = result + x;
    }
    return result;
}
""",
        encoding="utf-8",
    )
    sfg = c_to_sfg(path, "kernel", clang=clang)
    assert sfg.evaluate(2.0, 3.0) == 26.0


def test_cpp_constexpr_template_and_if_constexpr(tmp_path, clang):
    path = tmp_path / "constexpr.cpp"
    path.write_text(
        """
constexpr float gain(int n) { return n == 0 ? 1.0f : 2.0f * gain(n - 1); }
template<bool Scale> float transform(float x) {
    constexpr float scale = gain(3);
    if constexpr (Scale) return x * scale;
    else return x;
}
extern "C" float kernel(float x) { return transform<true>(x) + 1.0f; }
""",
        encoding="utf-8",
    )
    assert cpp_to_sfg(path, "kernel", clang=clang).evaluate(2.0) == 17.0
    assert c_to_sfg(path, "kernel", clang=clang).evaluate(2.0) == 17.0


def test_runtime_loop_rejected(tmp_path, clang):
    path = tmp_path / "dynamic.c"
    path.write_text(
        """
float kernel(float x) {
    while (x > 1.0f) x = x / 2.0f;
    return x;
}
""",
        encoding="utf-8",
    )
    with pytest.warns(LLVMImportWarning), pytest.raises(UnsupportedLLVMError):
        c_to_sfg(path, "kernel", clang=clang)


def test_compiler_failure(tmp_path, clang):
    path = tmp_path / "invalid.c"
    path.write_text("this is invalid C", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Clang failed"):
        c_to_sfg(path, clang=clang)


def test_compiler_diagnostics_and_arguments(tmp_path, monkeypatch):
    path = tmp_path / "source.cpp"
    path.touch()
    commands = []

    def compile_ir(command, **kwargs):
        commands.append(command)
        from pathlib import Path

        Path(command[command.index("-o") + 1]).write_text(
            "define float @kernel(float %x) { ret float %x }", encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, "", "compiler warning")

    monkeypatch.setattr(subprocess, "run", compile_ir)
    with pytest.warns(LLVMImportWarning, match="compiler warning"):
        sfg = cpp_to_sfg(path, clang="custom-clang", extra_args=["-DCOUNT=4"])
    assert sfg.evaluate(5.0) == 5.0
    assert commands[0][0] == "custom-clang"
    assert "-DCOUNT=4" in commands[0]
    assert "-funroll-loops" in commands[0]
    assert "-ffp-contract=off" in commands[0]
