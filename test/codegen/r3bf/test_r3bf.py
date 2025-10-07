from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.data_type import VhdlDataType


def test_r3bf_compile(tmp_path, arch_r3bf):
    runner = get_runner()
    dt = VhdlDataType(16, is_complex=True)
    printer = VhdlPrinter(dt)
    printer.print(arch_r3bf, path=tmp_path)

    sources = list((tmp_path).glob("*.vhdl"))

    runner.build(
        sources=sources,
        hdl_toplevel="r3bf",
        build_dir=tmp_path,
    )


def test_r3bf_simulate(tmp_path, arch_r3bf):
    runner = get_runner()
    dt = VhdlDataType(16, is_complex=True)
    printer = VhdlPrinter(dt)
    printer.print(arch_r3bf, path=tmp_path)

    sources = list((tmp_path).glob("*.vhdl"))

    runner.build(
        sources=sources,
        hdl_toplevel="r3bf",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="r3bf", test_module="test_r3bf")


@cocotb_test()
async def r3bf_test(dut):
    import cocotb
    from cocotb.triggers import Timer

    cocotb.start_soon(_generate_clk(dut))

    dut.rst.value = 1
    await Timer(2, "ns")
    dut.rst.value = 0

    dut.input_0_in_re.value = 8192
    dut.input_0_in_im.value = 0
    await Timer(2, "ns")
    dut.input_0_in_re.value = 0
    dut.input_0_in_im.value = 0
    await Timer(2 * 2, "ns")

    dut.input_0_in_re.value = 4096
    dut.input_0_in_im.value = 0

    await Timer(3 * 2, "ns")
    dut.input_0_in_re.value = 0
    dut.input_0_in_im.value = 4096
    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 8192
    assert dut.output_0_out_im.value == 0
    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 8192
    assert dut.output_0_out_im.value == 0
    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 8192
    assert dut.output_0_out_im.value == 0

    dut.input_0_in_re.value = 0
    dut.input_0_in_im.value = 4096
    await Timer(2, "ns")
    dut.input_0_in_re.value = 0
    dut.input_0_in_im.value = 0
    assert dut.output_0_out_re.value == 3 * 4096
    assert dut.output_0_out_im.value == 0
    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 0
    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 0

    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 3 * 4096
    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 0
    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 0

    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 4096
    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 4096
    await Timer(2, "ns")
    assert dut.output_0_out_re.value == 0
    assert dut.output_0_out_im.value == 4096


async def _generate_clk(dut):
    from cocotb.triggers import Timer

    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
