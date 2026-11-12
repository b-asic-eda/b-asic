import pytest

from b_asic.architecture import Architecture, Memory
from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.data_type import DataType


@pytest.mark.parametrize("is_complex", [False, True])
@pytest.mark.parametrize("centralize_control", [False, True])
def test_generated_vhdl_ends_with_one_newline(
    tmp_path, arch_simple, is_complex, centralize_control
):
    printer = VhdlPrinter(DataType(7, is_complex=is_complex))
    printer.print(arch_simple, path=tmp_path, centralize_control=centralize_control)
    for filename in printer.get_compile_order(arch_simple):
        code = (tmp_path / filename).read_text()
        assert code.endswith(";\n")
        assert not code.endswith("\n\n")

    code = printer.print_Architecture(
        arch_simple, centralize_control=centralize_control
    )
    assert code.endswith(";\n")
    assert not code.endswith("\n\n")
    for component in arch_simple.processing_elements:
        code = printer.print_ProcessingElement(component)
        assert code.endswith(";\n")
        assert not code.endswith("\n\n")
    for memory in arch_simple.memories:
        code = printer.print_Memory(memory)
        assert code.endswith(";\n")
        assert not code.endswith("\n\n")


def test_simple_centralized_control(tmp_path, arch_simple):
    printer = VhdlPrinter(DataType(7))
    printer.print(arch_simple, path=tmp_path, io_registers=True)

    top_level = (tmp_path / "simple.vhdl").read_text()
    assert "control_rom" in top_level.lower()
    assert "control_rom" in printer.print_Architecture(arch_simple).lower()
    assert "    -- Control signals\n    type control_rom_type" in top_level
    assert "\n\n    -- Internal signals for pipelined I/O" in top_level
    assert "\n\n    -- Component declaration" in top_level
    assert "-- Component interconnect and schedule counter signals" in top_level
    assert "\n\n    -- Centralized control" in top_level
    assert "alias mem0_ctrl_write_en_0 : std_logic is control_word(" in top_level
    assert "alias mem0_ctrl_write_adr_0 : std_logic_vector(" in top_level
    assert "ctrl_write_adr_0 => unsigned(mem0_ctrl_write_adr_0)" in top_level
    assert "mem0_ctrl_write_adr_0 <=" not in top_level
    for component in (*arch_simple.processing_elements, *arch_simple.memories):
        code = (tmp_path / f"{component.entity_name}.vhdl").read_text()
        assert "with schedule_cnt select" not in code.lower()
        assert "case schedule_cnt" not in code.lower()
    for memory in arch_simple.memories:
        code = (tmp_path / f"{memory.entity_name}.vhdl").read_text()
        assert "schedule_cnt" not in code.lower()
        assert "signal read_adr_0_0_0" not in code
        assert "signal write_adr_0_0_0" not in code
        assert "signal write_en_0_0_0" not in code
        declaration = top_level.split(f"component {memory.entity_name}\n", 1)[1].split(
            "end component;", 1
        )[0]
        assert "schedule_cnt" not in declaration
        instance = top_level.split(f"{memory.entity_name}_inst:", 1)[1].split(");", 1)[
            0
        ]
        assert "schedule_cnt" not in instance


def test_simple_distributed_control(tmp_path, arch_simple):
    printer = VhdlPrinter(DataType(7))
    printer.print(arch_simple, path=tmp_path, centralize_control=False)

    assert "control_rom" not in (tmp_path / "simple.vhdl").read_text().lower()
    for memory in arch_simple.memories:
        code = (tmp_path / f"{memory.entity_name}.vhdl").read_text().lower()
        assert "case schedule_cnt" in code
        assert "schedule_cnt : in" in code


def test_standalone_components_keep_local_control(arch_simple):
    printer = VhdlPrinter(DataType(7))
    for component in arch_simple.processing_elements:
        code = printer.print_ProcessingElement(component, centralize_control=True)
        assert "control_rom" not in code.lower()
    for component in arch_simple.memories:
        code = printer.print_Memory(component, centralize_control=True)
        assert "case schedule_cnt" in code.lower()
        code = printer.print_Memory(component, external_schedule_counter=False)
        assert "schedule_cnt_proc" in code.lower()
        assert "rst : in std_logic" in code.lower()


@pytest.mark.parametrize("centralize_control", [False, True])
def test_simple_compile(tmp_path, arch_simple, centralize_control):
    runner = get_runner()
    dt = DataType(7)
    printer = VhdlPrinter(dt)
    printer.print(arch_simple, path=tmp_path, centralize_control=centralize_control)

    sources = [
        tmp_path / filename for filename in printer.get_compile_order(arch_simple)
    ]

    runner.build(
        sources=sources,
        hdl_toplevel="simple",
        build_dir=tmp_path,
    )


def test_centralized_internal_memory_counter_option(tmp_path, arch_simple):
    printer = VhdlPrinter(DataType(7))
    printer.print(
        arch_simple,
        path=tmp_path,
        centralize_control=True,
        external_schedule_counter=False,
        output_sync=False,
        enable_pin=False,
    )
    for memory in arch_simple.memories:
        code = (tmp_path / f"{memory.entity_name}.vhdl").read_text().lower()
        assert "schedule_cnt" not in code
        assert "rst : in" not in code
    runner = get_runner()
    runner.build(
        sources=[tmp_path / name for name in printer.get_compile_order(arch_simple)],
        hdl_toplevel="simple",
        build_dir=tmp_path,
    )


@pytest.mark.parametrize("centralize_control", [False, True])
def test_simple_simulate(tmp_path, arch_simple, centralize_control):
    runner = get_runner()
    dt = DataType(8, 4, 7)
    printer = VhdlPrinter(dt)
    printer.print(arch_simple, path=tmp_path, centralize_control=centralize_control)

    sources = [
        tmp_path / filename for filename in printer.get_compile_order(arch_simple)
    ]

    runner.build(
        sources=sources,
        hdl_toplevel="simple",
        build_dir=tmp_path,
    )

    runner.test(
        hdl_toplevel="simple",
        test_module="test_simple",
        testcase="simple_test",
    )


def test_simple_pipelined_control_simulate(tmp_path, arch_simple):
    printer = VhdlPrinter(DataType(8, 4, 7))
    printer.print(
        arch_simple,
        path=tmp_path,
        pipeline_control=True,
    )
    code = (tmp_path / "simple.vhdl").read_text()
    assert "control_word_reg <= control_rom(to_integer(schedule_cnt));" in code
    assert "control_word <= control_rom" not in code
    runner = get_runner()
    runner.build(
        sources=[tmp_path / name for name in printer.get_compile_order(arch_simple)],
        hdl_toplevel="simple",
        build_dir=tmp_path,
    )
    runner.test(
        hdl_toplevel="simple", test_module="test_simple", testcase="simple_test"
    )


def test_legacy_pipeline_options(tmp_path, arch_simple):
    printer = VhdlPrinter(DataType(7))
    printer.print(
        arch_simple,
        path=tmp_path,
        pipeline_pe_control=True,
        pipeline_mem_control=True,
        multiplexer_control_registered=True,
    )
    code = (tmp_path / "simple.vhdl").read_text()
    assert "control_word_reg <= control_rom(to_integer(schedule_cnt));" in code
    assert "control_word <= control_rom" not in code


@pytest.mark.parametrize(
    "option",
    [
        "pipeline_pe_control",
        "pipeline_mem_control",
        "pipeline_output_mux",
        "pipeline_back_edge_mux",
        "multiplexer_control_registered",
    ],
)
@pytest.mark.parametrize("registered", [False, True])
def test_central_control_rejects_conflicting_pipeline_options(
    tmp_path, arch_simple, option, registered
):
    printer = VhdlPrinter(DataType(7))
    options = {"pipeline_control": registered, option: not registered}
    with pytest.raises(ValueError, match=option):
        printer.print(arch_simple, path=tmp_path, **options)
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError, match=option):
        printer.print_Architecture(arch_simple, **options)


def test_registered_rom_requires_central_control(tmp_path, arch_simple):
    printer = VhdlPrinter(DataType(7))
    with pytest.raises(ValueError, match="requires centralize_control"):
        printer.print(
            arch_simple,
            path=tmp_path,
            centralize_control=False,
            pipeline_control=True,
        )


@pytest.mark.parametrize("memory_type", ["RAM", "register"])
@pytest.mark.parametrize(
    ("pe_pipeline", "memory_pipeline", "mux_pipeline"),
    [
        (False, False, False),
        (True, True, True),
        (True, False, True),
        (False, True, False),
    ],
)
def test_control_modes_match(
    tmp_path, arch_simple, memory_type, pe_pipeline, memory_pipeline, mux_pipeline
):
    memories = [
        Memory(
            mem.collection,
            memory_type=memory_type,
            entity_name=mem.entity_name,
            assign=True,
        )
        for mem in arch_simple.memories
    ]
    arch = Architecture(
        arch_simple.processing_elements,
        memories,
        "simple",
        arch_simple.direct_interconnects,
    )
    traces = []
    for centralized in (False, True):
        directory = tmp_path / str(centralized)
        printer = VhdlPrinter(DataType(8, 4, 7))
        printer.print(
            arch,
            path=directory,
            centralize_control=centralized,
            pipeline_pe_control=pe_pipeline,
            pipeline_mem_control=memory_pipeline,
            pipeline_output_mux=memory_pipeline,
            pipeline_back_edge_mux=memory_pipeline,
            multiplexer_control_registered=mux_pipeline,
        )
        if centralized:
            for memory in arch.memories:
                assert (
                    "schedule_cnt"
                    not in (directory / f"{memory.entity_name}.vhdl")
                    .read_text()
                    .lower()
                )
            if memory_type == "RAM":
                word = "control_word_reg" if memory_pipeline else "control_word"
                code = (directory / "simple.vhdl").read_text()
                assert f"alias mem0_ctrl_write_en_0 : std_logic is {word}(" in code
        runner = get_runner()
        runner.build(
            sources=[directory / name for name in printer.get_compile_order(arch)],
            hdl_toplevel="simple",
            build_dir=directory,
        )
        trace = directory / "trace.txt"
        runner.test(
            hdl_toplevel="simple",
            test_module="test_simple",
            testcase="control_trace",
            extra_env={"CONTROL_TRACE": str(trace)},
        )
        traces.append(trace.read_text())
    assert traces[0] == traces[1]


@cocotb_test()
async def control_trace(dut):
    import os
    from pathlib import Path

    from cocotb.triggers import Timer

    dut.clk.value = 0
    dut.rst.value = 1
    dut.en.value = 0
    dut.input_0_in.value = 0
    await Timer(1, unit="ns")
    dut.clk.value = 1
    await Timer(1, unit="ns")
    dut.rst.value = 0
    trace = []
    for cycle in range(40):
        dut.clk.value = 0
        dut.en.value = int(cycle not in (13, 14, 27))
        dut.input_0_in.value = cycle % 8
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
        if cycle >= 10:
            trace.append(str(dut.output_0_out.value))
    Path(os.environ["CONTROL_TRACE"]).write_text("\n".join(trace))


@cocotb_test()
async def simple_test(dut):
    import cocotb
    from cocotb.triggers import Timer
    from cocotb.types import LogicArray

    cocotb.start_soon(_generate_clk(dut))

    dut.rst.value = 1
    dut.en.value = 0
    await Timer(2, "ns")
    dut.rst.value = 0
    dut.en.value = 1
    dut.input_0_in.value = LogicArray.from_signed(3, 4)

    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed(5, 4)

    await Timer(8, "ns")
    dut.input_0_in.value = LogicArray.from_signed(6, 4)
    assert dut.output_0_out.value == LogicArray.from_signed(16, 7)
    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed(4, 4)

    await Timer(8, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(20, 7)


async def _generate_clk(dut):
    from cocotb.triggers import Timer

    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")


def test_simple_io_registers_compile(tmp_path, arch_simple):
    runner = get_runner()
    dt = DataType(7)
    printer = VhdlPrinter(dt)
    printer.print(arch_simple, path=tmp_path, io_registers=True)

    sources = [
        tmp_path / filename for filename in printer.get_compile_order(arch_simple)
    ]

    runner.build(
        sources=sources,
        hdl_toplevel="simple",
        build_dir=tmp_path,
    )


def test_simple_io_registers_simulate(tmp_path, arch_simple):
    runner = get_runner()
    dt = DataType(8, 4, 7)
    printer = VhdlPrinter(dt)
    printer.print(arch_simple, path=tmp_path, io_registers=True)

    sources = [
        tmp_path / filename for filename in printer.get_compile_order(arch_simple)
    ]

    runner.build(
        sources=sources,
        hdl_toplevel="simple",
        build_dir=tmp_path,
    )

    runner.test(
        hdl_toplevel="simple",
        test_module="test_simple",
        testcase="simple_io_registers_test",
    )


@cocotb_test()
async def simple_io_registers_test(dut):
    import cocotb
    from cocotb.triggers import Timer
    from cocotb.types import LogicArray

    cocotb.start_soon(_generate_clk(dut))

    dut.rst.value = 1
    dut.en.value = 0
    await Timer(2, "ns")
    dut.rst.value = 0
    dut.en.value = 1
    dut.input_0_in.value = LogicArray.from_signed(3, 4)

    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed(5, 4)

    # Wait for computation + I/O registers (8 + 4 = 12 ns)
    await Timer(12, "ns")
    dut.input_0_in.value = LogicArray.from_signed(6, 4)
    assert dut.output_0_out.value == LogicArray.from_signed(16, 7)
    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed(4, 4)

    await Timer(8, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(20, 7)
