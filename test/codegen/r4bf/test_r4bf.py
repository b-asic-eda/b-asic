from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.data_type import VhdlDataType


def test_r4bf_compile(tmp_path, arch_r4bf):
    runner = get_runner()
    dt = VhdlDataType(32, is_complex=True)
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

    dt = VhdlDataType(32, is_complex=True)
    printer = VhdlPrinter(dt)
    printer.print(arch_r4bf, path=tmp_path)

    sources = [tmp_path / filename for filename in printer.get_compile_order(arch_r4bf)]

    runner.build(
        sources=sources,
        hdl_toplevel="r4bf",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="r4bf", test_module="test_r4bf")


@cocotb_test()
async def r4bf_test(dut):
    import cocotb
    from cocotb.triggers import Timer

    cocotb.start_soon(_generate_clk(dut))

    dut.rst.value = 1
    await Timer(2, "ns")
    dut.rst.value = 0
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
