from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.data_type import VhdlDataType


def test_lwdf_allpass_compile(tmp_path, arch_lwdf_allpass):
    runner = get_runner()
    dt = VhdlDataType(16)
    printer = VhdlPrinter(dt)
    printer.print(arch_lwdf_allpass, path=tmp_path)

    sources = list((tmp_path).glob("*.vhdl"))
    runner.build(
        sources=sources,
        hdl_toplevel="lwdf_allpass",
        build_dir=tmp_path,
    )


def test_lwdf_allpass_simulate(tmp_path, arch_lwdf_allpass):
    runner = get_runner()
    dt = VhdlDataType(16)
    printer = VhdlPrinter(dt)
    printer.print(arch_lwdf_allpass, path=tmp_path)

    sources = list((tmp_path).glob("*.vhdl"))
    runner.build(
        sources=sources,
        hdl_toplevel="lwdf_allpass",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="lwdf_allpass", test_module="test_lwdf_allpass")


@cocotb_test()
async def lwdf_allpass_test(dut):
    import cocotb

    cocotb.start_soon(_generate_clk(dut))

    # TODO: Add tests..


async def _generate_clk(dut):
    from cocotb.triggers import Timer

    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
