import os
import shutil

import pytest

from b_asic.code_printer.test import cocotb_test
from b_asic.code_printer.vhdl.vhdl_printer import VhdlPrinter
from b_asic.data_type import VhdlDataType


def test_r4bf_compile(tmp_path, arch_r4bf):
    pytest.importorskip("cocotb_tools")
    dt = VhdlDataType(32, is_complex=True)
    printer = VhdlPrinter(dt)
    printer.print(tmp_path, arch_r4bf, vhdl_tb=True)

    sim = os.getenv("SIM", "ghdl")
    if not shutil.which(sim):
        pytest.skip(f"Simulator {sim} not available in PATH")
    sources = list((tmp_path / "r4bf_0").glob("*.vhd"))
    from cocotb_tools.runner import get_runner

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="r4bf_tb",
        build_dir=tmp_path,
    )


def test_r4bf_simulate(tmp_path, arch_r4bf):
    pytest.importorskip("cocotb_tools")
    dt = VhdlDataType(32, is_complex=True)
    printer = VhdlPrinter(dt)
    printer.print(tmp_path, arch_r4bf)

    sim = os.getenv("SIM", "ghdl")
    if not shutil.which(sim):
        pytest.skip(f"Simulator {sim} not available in PATH")
    sources = list((tmp_path / "r4bf_0").glob("*.vhd"))
    from cocotb_tools.runner import get_runner

    runner = get_runner(sim)
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
    dut.input_0_in.value = 1

    await Timer(2, "ns")
    dut.input_0_in.value = 0

    await Timer(2, "ns")
    dut.input_0_in.value = 0

    await Timer(2, "ns")
    dut.input_0_in.value = 0

    await Timer(2, "ns")
    dut.input_0_in.value = 2**16

    # Iteration 2
    await Timer(2, "ns")
    assert dut.output_0_out.value == 1

    await Timer(2, "ns")
    assert dut.output_0_out.value == 1

    await Timer(2, "ns")
    assert dut.output_0_out.value == 1

    await Timer(2, "ns")
    assert dut.output_0_out.value == 1

    # Iteration 2
    await Timer(2, "ns")
    assert dut.output_0_out.value == 4 * 2**16

    await Timer(2, "ns")
    assert dut.output_0_out.value == 0

    await Timer(2, "ns")
    assert dut.output_0_out.value == 0

    await Timer(2, "ns")
    assert dut.output_0_out.value == 0


async def _generate_clk(dut):
    from cocotb.triggers import Timer

    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
