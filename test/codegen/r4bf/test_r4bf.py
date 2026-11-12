import pytest

from b_asic.architecture import Architecture, Memory
from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.data_type import DataType


def test_r4bf_compile(tmp_path, arch_r4bf):
    runner = get_runner()
    dt = DataType(32, is_complex=True)
    printer = VhdlPrinter(dt)
    printer.print(arch_r4bf, path=tmp_path)

    sources = [tmp_path / filename for filename in printer.get_compile_order(arch_r4bf)]

    runner.build(
        sources=sources,
        hdl_toplevel="r4bf",
        build_dir=tmp_path,
    )


def test_r4bf_simulate(tmp_path, arch_r4bf):
    runner = get_runner()

    dt = DataType(32, is_complex=True)
    printer = VhdlPrinter(dt)
    printer.print(arch_r4bf, path=tmp_path)

    sources = [tmp_path / filename for filename in printer.get_compile_order(arch_r4bf)]

    runner.build(
        sources=sources,
        hdl_toplevel="r4bf",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="r4bf", test_module="test_r4bf")


@pytest.mark.parametrize("pipeline_control", [False, True])
def test_r4bf_register_memory_simulate(tmp_path, arch_r4bf, pipeline_control):
    memories = [
        Memory(
            memory.collection,
            memory_type="register",
            entity_name=memory.entity_name,
            assign=True,
        )
        for memory in arch_r4bf.memories
    ]
    assert memories
    arch = Architecture(
        arch_r4bf.processing_elements, memories, "r4bf", arch_r4bf.direct_interconnects
    )
    printer = VhdlPrinter(DataType(32, is_complex=True))
    printer.print(arch, path=tmp_path, pipeline_control=pipeline_control)
    for memory in memories:
        code = (tmp_path / f"{memory.entity_name}.vhdl").read_text()
        assert "shift_reg_type" in code
        assert "schedule_cnt" not in code
        assert "ctrl_back_edge" in code
        assert "ctrl_output" in code

    runner = get_runner()
    runner.build(
        sources=[tmp_path / filename for filename in printer.get_compile_order(arch)],
        hdl_toplevel="r4bf",
        build_dir=tmp_path,
    )
    runner.test(hdl_toplevel="r4bf", test_module="test_r4bf", testcase="r4bf_test")


@cocotb_test()
async def r4bf_test(dut):
    import cocotb
    from cocotb.triggers import Timer

    cocotb.start_soon(_generate_clk(dut))

    dut.rst.value = 1
    dut.en.value = 0
    await Timer(2, "ns")
    dut.rst.value = 0
    dut.en.value = 1
    # Iteration 1
    dut.input_0_in_re.value = 0
    dut.input_0_in_im.value = 1

    await Timer(2, "ns")
    dut.input_0_in_re.value = 0
    dut.input_0_in_im.value = 0

    await Timer(2, "ns")
    dut.input_0_in_re.value = 0
    dut.input_0_in_im.value = 0

    await Timer(2, "ns")
    dut.input_0_in_re.value = 0
    dut.input_0_in_im.value = 0

    await Timer(2, "ns")
    dut.input_0_in_re.value = 1
    dut.input_0_in_im.value = 0

    # Iteration 2
    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 1

    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 1

    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 1

    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 1

    # Iteration 2
    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 4
    assert dut.output_0_out_im.value == 0

    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 0

    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 0

    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 0


async def _generate_clk(dut):
    from cocotb.triggers import Timer

    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
