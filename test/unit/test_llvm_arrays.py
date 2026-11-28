"""Constant-address array interfaces and persistent LLVM state."""

import re
import shutil

import pytest

from b_asic import (
    Delay,
    Input,
    LLVMArray,
    LLVMImportWarning,
    MemoryRead,
    MemoryWrite,
    Output,
    Simulation,
    UnsupportedLLVMError,
    c_to_sfg,
    cpp_to_sfg,
    llvm_file_to_sfg,
    llvm_to_sfg,
)

pytest.importorskip("llvmlite.binding")


@pytest.fixture
def clang():
    compiler = shutil.which("clang")
    if compiler is None:
        pytest.skip("Clang is not installed")
    return compiler


BUFFER_IR = """
define void @kernel(ptr noalias %src, ptr noalias %dst, float %gain) {
  %a = load float, ptr %src
  %p = getelementptr float, ptr %src, i64 1
  %b = load float, ptr %p
  %y = fmul float %a, %gain
  %z = fadd float %b, %gain
  %q = getelementptr float, ptr %dst, i64 1
  store float %z, ptr %q
  store float %y, ptr %dst
  ret void
}
"""


@pytest.mark.parametrize("interface", ["memory", "stream"])
def test_array_interfaces_and_port_order(interface):
    sfg = llvm_to_sfg(
        BUFFER_IR,
        arrays={
            "src": LLVMArray("input", 2, interface=interface),
            "dst": LLVMArray("output", 2, interface=interface),
        },
    )
    assert sfg.evaluate(3.0, 4.0, 2.0) == [6.0, 6.0]
    read, write = (
        (MemoryRead, MemoryWrite) if interface == "memory" else (Input, Output)
    )
    assert [type(op) for op in sfg.input_operations] == [read, read, Input]
    assert [type(op) for op in sfg.output_operations] == [write, write]
    assert [op.name for op in sfg.input_operations] == ["src[0]", "src[1]", "gain"]
    assert [op.name for op in sfg.output_operations] == ["dst[0]", "dst[1]"]
    assert not sfg.find_by_type(Delay)
    if interface == "memory":
        assert [(op.memory_name, op.address) for op in sfg.input_operations[:2]] == [
            ("src", 0),
            ("src", 1),
        ]
        assert [(op.memory_name, op.address) for op in sfg.output_operations] == [
            ("dst", 0),
            ("dst", 1),
        ]


def test_mixed_interfaces_and_scalar_return():
    ir = BUFFER_IR.replace("define void", "define float").replace(
        "ret void", "ret float %a"
    )
    sfg = llvm_to_sfg(
        ir,
        arrays={
            "src": LLVMArray("input", 2, interface="stream"),
            "dst": LLVMArray("output", 2),
        },
    )
    assert sfg.evaluate(3.0, 4.0, 2.0) == [3.0, 6.0, 6.0]
    assert type(sfg.output_operations[0]) is Output
    assert all(type(op) is MemoryWrite for op in sfg.output_operations[1:])


@pytest.mark.parametrize("interface", ["memory", "stream"])
def test_inplace_butterfly_is_not_persistent_state(interface):
    graph = llvm_to_sfg(
        """
define void @butterfly(ptr %data) {
  %p = getelementptr float, ptr %data, i64 1
  %a = load float, ptr %data
  %b = load float, ptr %p
  %sum = fadd float %a, %b
  %difference = fsub float %a, %b
  store float %sum, ptr %data
  store float %difference, ptr %p
  ret void
}
""",
        arrays={"data": LLVMArray("inout", 2, interface=interface)},
    )
    assert graph.evaluate(3.0, 1.0) == [4.0, 2.0]
    assert graph.evaluate(10.0, 4.0) == [14.0, 6.0]
    assert not graph.find_by_type(Delay)
    simulation = Simulation(graph, [3.0, 1.0])
    assert [simulation.step() for _ in range(2)] == [[4.0, 2.0], [4.0, 2.0]]


@pytest.mark.parametrize("width", [32, 64])
def test_gep_signed_indices(width):
    graph = llvm_to_sfg(
        f"""
define float @get(ptr %data) {{
  %end = getelementptr float, ptr %data, i{width} 2
  %back = getelementptr float, ptr %end, i{width} -1
  %value = load float, ptr %back
  ret float %value
}}
""",
        arrays={"data": LLVMArray("input", 2)},
    )
    assert graph.evaluate(1.0, 2.0) == 2.0


@pytest.mark.parametrize(("element_type", "width"), [("float", 4), ("double", 8)])
def test_byte_gep_addresses_are_element_addresses(element_type, width):
    graph = llvm_to_sfg(
        f"""
define {element_type} @get(ptr %data) {{
  %p = getelementptr i8, ptr %data, i64 {width}
  %value = load {element_type}, ptr %p
  ret {element_type} %value
}}
""",
        arrays={"data": LLVMArray("input", 2, element_type=element_type)},
    )
    assert graph.evaluate(1.0, 2.0) == 2.0


def test_abi_copy_pointer_rejected():
    with (
        pytest.warns(LLVMImportWarning, match="ABI copy"),
        pytest.raises(UnsupportedLLVMError),
    ):
        llvm_to_sfg(
            "define float @get(ptr byval(float) %data) { %v = load float, ptr %data\n ret float %v }",
            arrays={"data": LLVMArray("input", 1)},
        )


def test_nested_arrays_are_row_major():
    sfg = llvm_to_sfg(
        """
define float @get(ptr %a) {
  %p = getelementptr [2 x [3 x float]], ptr %a, i64 0, i64 1, i64 2
  %v = load float, ptr %p
  ret float %v
}
""",
        arrays={"a": LLVMArray("input", 6)},
    )
    assert sfg.evaluate(*range(6)) == 5
    assert [op.address for op in sfg.input_operations] == list(range(6))


def test_repeated_loads_share_input_and_stores_forward():
    sfg = llvm_to_sfg(
        """
define float @kernel(ptr %src, ptr %dst) {
  %a = load float, ptr %src
  %b = load float, ptr %src
  %sum = fadd float %a, %b
  store float %sum, ptr %dst
  %c = load float, ptr %dst
  %twice = fadd float %c, %c
  store float %twice, ptr %dst
  ret float %c
}
""",
        arrays={"src": LLVMArray("input", 1), "dst": LLVMArray("output", 1)},
    )
    assert sfg.evaluate(3.0) == [6.0, 12.0]
    assert sfg.input_count == 1
    assert sfg.output_count == 2


def test_pointer_state_delays_and_store_forwarding():
    sfg = llvm_to_sfg(
        """
define float @accumulate(ptr %state, float %x) {
  %old = load float, ptr %state
  %next = fadd float %old, %x
  store float %next, ptr %state
  %new = load float, ptr %state
  %result = fadd float %old, %new
  ret float %result
}
""",
        arrays={"state": LLVMArray("state", 1, initial_values=[2.0])},
    )
    assert sfg.input_count == sfg.output_count == 1
    assert not sfg.find_by_type(MemoryRead)
    assert not sfg.find_by_type(MemoryWrite)
    assert len(sfg.find_by_type(Delay)) == 1
    simulation = Simulation(sfg, [1.0])
    assert [simulation.step()[0] for _ in range(3)] == [5.0, 7.0, 9.0]


def test_state_array_updates_are_simultaneous():
    sfg = llvm_to_sfg(
        """
define float @swap(ptr %s) {
  %p = getelementptr float, ptr %s, i64 1
  %a = load float, ptr %s
  %b = load float, ptr %p
  store float %b, ptr %s
  store float %a, ptr %p
  %result = fsub float %a, %b
  ret float %result
}
""",
        arrays={"s": LLVMArray("state", 2, initial_values=[2.0, 5.0])},
    )
    simulation = Simulation(sfg)
    assert [simulation.step()[0] for _ in range(4)] == [-3.0, 3.0, -3.0, 3.0]


def test_unwritten_state_is_held():
    sfg = llvm_to_sfg(
        "define float @get(ptr %s) { %v = load float, ptr %s\n ret float %v }",
        arrays={"s": LLVMArray("state", 1, initial_values=[4.0])},
    )
    simulation = Simulation(sfg)
    assert [simulation.step()[0] for _ in range(3)] == [4.0, 4.0, 4.0]


def test_global_state_constant_gep():
    sfg = llvm_to_sfg(
        """
@history = internal global [2 x float] [float 1.0, float 2.0]
define float @previous(float %x) {
  %old = load float, ptr getelementptr inbounds ([2 x float], ptr @history, i64 0, i64 1)
  store float %x, ptr getelementptr inbounds ([2 x float], ptr @history, i64 0, i64 1)
  ret float %old
}
""",
        arrays={"@history": LLVMArray("state", 2, initial_values=[1.0, 2.0])},
    )
    simulation = Simulation(sfg, [lambda n: float(n + 3)])
    assert [simulation.step()[0] for _ in range(3)] == [2.0, 3.0, 4.0]


def test_input_output_globals():
    sfg = llvm_to_sfg(
        """
@src = external global float
@dst = external global float
define void @copy() {
  %x = load float, ptr @src
  store float %x, ptr @dst
  ret void
}
""",
        arrays={"@src": LLVMArray("input", 1), "@dst": LLVMArray("output", 1)},
    )
    assert sfg.evaluate(7.0) == 7.0
    assert sfg.input_operations[0].memory_name == "@src"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("%p = getelementptr float, ptr %a, i64 %i", "compile-time constants"),
        ("%p = getelementptr float, ptr %a, i64 -1", "outside.*bounds"),
        ("%p = getelementptr double, ptr %a, i64 1", "element type"),
        ("%p = getelementptr i8, ptr %a, i64 1", "whole floating-point elements"),
        ("%p = getelementptr float, ptr %a, i64 3", "outside.*bounds"),
        ("%v = load volatile float, ptr %a", "Volatile and atomic"),
        ("%v = load atomic float, ptr %a monotonic, align 4", "Volatile and atomic"),
        ("%v = load i32, ptr %a", "Access type"),
        ("store float 2.0, ptr %a", "Cannot write input"),
    ],
)
def test_unsupported_array_accesses(body, message):
    parameters = "ptr %a, i64 %i" if "%i" in body else "ptr %a"
    with (
        pytest.warns(LLVMImportWarning) as caught,
        pytest.raises(UnsupportedLLVMError),
    ):
        llvm_to_sfg(
            f"define float @bad({parameters}) {{ {body}\n ret float 0.0 }}",
            arrays={"a": LLVMArray("input", 2)},
        )
    assert any(re.search(message, str(warning.message)) for warning in caught)


def test_one_past_end_may_not_be_loaded():
    with (
        pytest.warns(LLVMImportWarning, match="out of bounds"),
        pytest.raises(UnsupportedLLVMError),
    ):
        llvm_to_sfg(
            """
define float @bad(ptr %a) {
  %p = getelementptr float, ptr %a, i64 2
  %v = load float, ptr %p
  ret float %v
}
""",
            arrays={"a": LLVMArray("input", 2)},
        )


def test_output_cannot_be_read_before_write():
    with (
        pytest.warns(LLVMImportWarning, match="read before"),
        pytest.raises(UnsupportedLLVMError),
    ):
        llvm_to_sfg(
            "define float @bad(ptr %a) { %v = load float, ptr %a\n ret float %v }",
            arrays={"a": LLVMArray("output", 1)},
        )


def test_state_and_external_array_combination_rejected():
    with (
        pytest.warns(LLVMImportWarning, match="Combining state"),
        pytest.raises(UnsupportedLLVMError),
    ):
        llvm_to_sfg(
            "define float @bad(ptr %a, ptr %s) { ret float 0.0 }",
            arrays={"a": LLVMArray("input", 1), "s": LLVMArray("state", 1)},
        )


def test_global_state_requires_explicit_reset():
    with (
        pytest.warns(LLVMImportWarning, match="explicit initial_values"),
        pytest.raises(UnsupportedLLVMError),
    ):
        llvm_to_sfg(
            "@s = global float 7.0\ndefine float @get() { %v = load float, ptr @s\n ret float %v }",
            arrays={"@s": LLVMArray("state", 1)},
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"role": "unknown", "size": 1},
        {"role": "input", "size": 0},
        {"role": "input", "size": True},
        {"role": "input", "size": 1, "initial_values": [0.0]},
        {"role": "state", "size": 2, "initial_values": [0.0]},
        {"role": "input", "size": 1, "interface": "unknown"},
        {"role": "input", "size": 1, "element_type": "i32"},
    ],
)
def test_invalid_array_configuration(kwargs):
    with pytest.raises(ValueError, match=r"Array|Only state|State initial_values"):
        LLVMArray(**kwargs)


def test_unknown_array_name():
    with pytest.raises(ValueError, match="Unknown LLVM array"):
        llvm_to_sfg(
            "define float @get() { ret float 0.0 }",
            arrays={"typo": LLVMArray("input", 1)},
        )


def test_c_memory_and_streaming_arrays(tmp_path, clang):
    path = tmp_path / "array.c"
    path.write_text(
        """
void kernel(const float *restrict src, float *restrict dst) {
    for (int i = 0; i < 4; ++i) dst[i] = 2.0f * src[i];
}
""",
        encoding="utf-8",
    )
    for interface in ["memory", "stream"]:
        graph = c_to_sfg(
            path,
            arrays={
                "src": LLVMArray("input", 4, interface=interface),
                "dst": LLVMArray("output", 4, interface=interface),
            },
            clang=clang,
        )
        assert graph.evaluate(1.0, 2.0, 3.0, 4.0) == [2.0, 4.0, 6.0, 8.0]


def test_c_static_state(tmp_path, clang):
    path = tmp_path / "state.c"
    path.write_text(
        """
float kernel(float x) {
    static float history = 1.5f;
    float y = history + x;
    history = x;
    return y;
}
""",
        encoding="utf-8",
    )
    graph = c_to_sfg(
        path,
        arrays={"@kernel.history": LLVMArray("state", 1, initial_values=[1.5])},
        clang=clang,
    )
    simulation = Simulation(graph, [2.0])
    assert [simulation.step()[0] for _ in range(3)] == [3.5, 4.0, 4.0]


def test_cpp_pointer_state(tmp_path, clang):
    path = tmp_path / "state.cpp"
    path.write_text(
        'extern "C" float kernel(float *s, float x) { *s += x; return *s; }',
        encoding="utf-8",
    )
    graph = cpp_to_sfg(path, arrays={"s": LLVMArray("state", 1)}, clang=clang)
    simulation = Simulation(graph, [2.0])
    assert [simulation.step()[0] for _ in range(3)] == [2.0, 4.0, 6.0]


def test_file_reader_array_configuration(tmp_path):
    path = tmp_path / "kernel.ll"
    path.write_text(BUFFER_IR, encoding="utf-8")
    graph = llvm_file_to_sfg(
        path, arrays={"src": LLVMArray("input", 2), "dst": LLVMArray("output", 2)}
    )
    assert graph.evaluate(3.0, 4.0, 2.0) == [6.0, 6.0]
