from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.data_type import VhdlDataType


def test_simple_compile(tmp_path, arch_simple):
    runner = get_runner()
    dt = VhdlDataType(7)
    printer = VhdlPrinter(dt)
    printer.print(arch_simple, path=tmp_path)

    sources = [
        tmp_path / filename for filename in printer.get_compile_order(arch_simple)
    ]

    runner.build(
        sources=sources,
        hdl_toplevel="simple",
        build_dir=tmp_path,
    )


def test_simple_simulate(tmp_path, arch_simple):
    runner = get_runner()
    dt = VhdlDataType(8, 4, 7)
    printer = VhdlPrinter(dt)
    printer.print(arch_simple, path=tmp_path)

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


@cocotb_test()
async def simple_test(dut):
    import cocotb
    from cocotb.triggers import Timer
    from cocotb.types import LogicArray

    cocotb.start_soon(_generate_clk(dut))

    dut.rst.value = 1
    await Timer(2, "ns")
    dut.rst.value = 0
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
    dt = VhdlDataType(7)
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
    dt = VhdlDataType(8, 4, 7)
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
    await Timer(2, "ns")
    dut.rst.value = 0
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
