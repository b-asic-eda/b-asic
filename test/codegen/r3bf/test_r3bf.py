import os
import shutil

import pytest

from b_asic.code_printer.test import cocotb_test
from b_asic.code_printer.vhdl.vhdl_printer import VhdlPrinter
from b_asic.data_type import VhdlDataType


def test_r3bf_compile(tmp_path, arch_r3bf):
    pytest.importorskip("cocotb_tools")
    dt = VhdlDataType(16, is_complex=True)
    printer = VhdlPrinter(dt)
    printer.print(tmp_path, arch_r3bf, vhdl_tb=True)

    sim = os.getenv("SIM", "ghdl")
    if not shutil.which(sim):
        pytest.skip(f"Simulator {sim} not available in PATH")
    sources = list((tmp_path / "r3bf_0").glob("*.vhd"))
    from cocotb_tools.runner import get_runner

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="r3bf_tb",
        build_dir=tmp_path,
    )


def test_r3bf_simulate(tmp_path, arch_r3bf):
    pytest.importorskip("cocotb_tools")
    dt = VhdlDataType(16, is_complex=True)
    printer = VhdlPrinter(dt)
    printer.print(tmp_path, arch_r3bf)

    sim = os.getenv("SIM", "ghdl")
    if not shutil.which(sim):
        pytest.skip(f"Simulator {sim} not available in PATH")
    sources = list((tmp_path / "r3bf_0").glob("*.vhd"))
    from cocotb_tools.runner import get_runner

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="r3bf",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="r3bf", test_module="test_r3bf", waves=True)


@cocotb_test()
async def r3bf_test(dut):
    import cocotb
    from cocotb.triggers import Timer

    cocotb.start_soon(_generate_clk(dut))

    dut.rst.value = 1
    await Timer(2, "ns")
    dut.rst.value = 0

    dut.input_0_in.value = 8192 * 2**16
    await Timer(2, "ns")
    dut.input_0_in.value = 0
    await Timer(2 * 2, "ns")

    dut.input_0_in.value = 4096 * 2**16

    await Timer(3 * 2, "ns")
    dut.input_0_in.value = 4096
    await Timer(2, "ns")
    assert dut.output_0_out.value == 8192 * 2**16
    await Timer(2, "ns")
    assert dut.output_0_out.value == 8192 * 2**16
    await Timer(2, "ns")
    assert dut.output_0_out.value == 8192 * 2**16

    dut.input_0_in.value = 4096
    await Timer(2, "ns")
    dut.input_0_in.value = 0
    assert dut.output_0_out.value == 3 * 4096 * 2**16
    await Timer(2, "ns")
    assert dut.output_0_out.value == 0
    await Timer(2, "ns")
    assert dut.output_0_out.value == 0

    await Timer(2, "ns")
    assert dut.output_0_out.value == 3 * 4096
    await Timer(2, "ns")
    assert dut.output_0_out.value == 0
    await Timer(2, "ns")
    assert dut.output_0_out.value == 0

    await Timer(2, "ns")
    assert dut.output_0_out.value == 4096
    await Timer(2, "ns")
    assert dut.output_0_out.value == 4096
    await Timer(2, "ns")
    assert dut.output_0_out.value == 4096


async def _generate_clk(dut):
    from cocotb.triggers import Timer

    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
