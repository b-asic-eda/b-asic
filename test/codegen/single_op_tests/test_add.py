from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.data_type import VhdlDataType


def test_add_compile(tmp_path, arch_add):
    runner = get_runner()
    dt = VhdlDataType(wl=(3, 2))
    printer = VhdlPrinter(dt)
    printer.print(arch_add, path=tmp_path)

    sources = list((tmp_path).glob("*.vhdl"))
    runner.build(
        sources=sources,
        hdl_toplevel="top",
        build_dir=tmp_path,
    )


def test_add_simulate(tmp_path, arch_add):
    runner = get_runner()
    dt = VhdlDataType(wl=(3, 2))
    printer = VhdlPrinter(dt)
    printer.print(arch_add, path=tmp_path)

    sources = [
        tmp_path / filename for filename in printer.get_compile_order(arch_add)
    ]

    runner.build(
        sources=sources,
        hdl_toplevel="top",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="top", test_module="test_add")


@cocotb_test()
async def add_test(dut):
    import cocotb
    from cocotb.triggers import Timer

    cocotb.start_soon(_generate_clk(dut))

    dut.rst.value = 1
    await Timer(2, "ns")
    dut.rst.value = 0
    dut.in0_0_in.value = 7
    dut.in1_0_in.value = 5

    await Timer(2, "ns")
    assert dut.out0_0_out.value == 12

    await Timer(2 * 10, "ns")


async def _generate_clk(dut):
    from cocotb.triggers import Timer

    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
