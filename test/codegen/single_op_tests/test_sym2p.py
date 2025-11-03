from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.data_type import VhdlDataType


def test_sym2p_compile(tmp_path, arch_sym2p):
    runner = get_runner()
    dt = VhdlDataType(16)
    printer = VhdlPrinter(dt)
    printer.print(arch_sym2p, path=tmp_path)

    sources = list((tmp_path).glob("*.vhdl"))
    runner.build(
        sources=sources,
        hdl_toplevel="top",
        build_dir=tmp_path,
    )


def test_sym2p_simulate(tmp_path, arch_sym2p):
    runner = get_runner()
    dt = VhdlDataType(16)
    printer = VhdlPrinter(dt)
    printer.print(arch_sym2p, path=tmp_path)

    sources = [
        tmp_path / filename for filename in printer.get_compile_order(arch_sym2p)
    ]

    runner.build(
        sources=sources,
        hdl_toplevel="top",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="top", test_module="test_sym2p")


@cocotb_test()
async def sym2p_test(dut):
    import cocotb
    from cocotb.triggers import Timer

    cocotb.start_soon(_generate_clk(dut))

    dut.rst.value = 1
    await Timer(2, "ns")
    dut.rst.value = 0
    dut.in0_0_in.value = 50
    dut.in1_0_in.value = 75

    await Timer(2, "ns")
    assert dut.out0_0_out.value == 84
    assert dut.out1_0_out.value == 59
    dut.in0_0_in.value = 40
    dut.in1_0_in.value = 40

    await Timer(2, "ns")
    assert dut.out0_0_out.value == 40
    assert dut.out1_0_out.value == 40
    dut.in0_0_in.value = -131
    dut.in1_0_in.value = 57

    await Timer(2, "ns")
    assert dut.out0_0_out.value == 127
    assert dut.out1_0_out.value == 65475
    dut.in0_0_in.value = 0
    dut.in1_0_in.value = 0

    await Timer(2, "ns")
    assert dut.out0_0_out.value == 0
    assert dut.out1_0_out.value == 0

    await Timer(2 * 10, "ns")


async def _generate_clk(dut):
    from cocotb.triggers import Timer

    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
