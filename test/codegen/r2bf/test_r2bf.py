from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.data_type import VhdlDataType


def test_r2bf_compile(tmp_path, arch_r2bf):
    runner = get_runner()
    dt = VhdlDataType(16)
    printer = VhdlPrinter(dt)
    printer.print(arch_r2bf, path=tmp_path, tb=True)

    sources = list((tmp_path / "r2bf_0").glob("*.vhdl"))
    runner.build(
        sources=sources,
        hdl_toplevel="r2bf_tb",
        build_dir=tmp_path,
    )


def test_r2bf_simulate(tmp_path, arch_r2bf):
    runner = get_runner()
    dt = VhdlDataType(16)
    printer = VhdlPrinter(dt)
    printer.print(arch_r2bf, path=tmp_path)

    sources = list((tmp_path / "r2bf_0").glob("*.vhdl"))
    runner.build(
        sources=sources,
        hdl_toplevel="r2bf",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="r2bf", test_module="test_r2bf")


@cocotb_test()
async def r2bf_test(dut):
    import cocotb
    from cocotb.triggers import Timer

    cocotb.start_soon(_generate_clk(dut))

    dut.rst.value = 1
    await Timer(2, "ns")
    dut.rst.value = 0
    dut.input0_0_in.value = 5

    await Timer(2, "ns")
    dut.input0_0_in.value = 3

    await Timer(2, "ns")
    dut.input0_0_in.value = 19
    assert dut.output0_0_out.value == 8

    await Timer(2, "ns")
    dut.input0_0_in.value = 11
    assert dut.output0_0_out.value == 2

    await Timer(2, "ns")
    assert dut.output0_0_out.value == 30

    await Timer(2, "ns")
    assert dut.output0_0_out.value == 8


async def _generate_clk(dut):
    from cocotb.triggers import Timer

    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
