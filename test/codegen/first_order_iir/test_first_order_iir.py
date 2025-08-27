import os
import shutil

import pytest

from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test
from b_asic.data_type import VhdlDataType


def test_first_order_iir_compile(tmp_path, arch_first_order_iir):
    pytest.importorskip("cocotb_tools")
    dt = VhdlDataType(3)
    printer = VhdlPrinter(dt)
    printer.print(tmp_path, arch_first_order_iir, vhdl_tb=True)

    sim = os.getenv("SIM", "ghdl")
    if not shutil.which(sim):
        pytest.skip(f"Simulator {sim} not available in PATH")
    sources = list((tmp_path / "first_order_iir_0").glob("*.vhd"))
    from cocotb_tools.runner import get_runner

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="first_order_iir_tb",
        build_dir=tmp_path,
    )


def test_first_order_iir_simulate(tmp_path, arch_first_order_iir):
    pytest.importorskip("cocotb_tools")
    dt = VhdlDataType(17)
    printer = VhdlPrinter(dt)
    printer.print(tmp_path, arch_first_order_iir)

    sim = os.getenv("SIM", "ghdl")
    if not shutil.which(sim):
        pytest.skip(f"Simulator {sim} not available in PATH")
    sources = list((tmp_path / "first_order_iir_0").glob("*.vhd"))
    from cocotb_tools.runner import get_runner

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="first_order_iir",
        build_dir=tmp_path,
    )

    runner.test(
        hdl_toplevel="first_order_iir",
        test_module="test_first_order_iir",
    )


@cocotb_test()
async def first_order_iir_test(dut):
    # Validate the impulse response of the first order IIR filter
    # Assume Q1.15 signed
    import cocotb
    from cocotb.triggers import Timer
    from cocotb.types import LogicArray

    cocotb.start_soon(_generate_clk(dut))
    dut.rst.value = 1
    await Timer(2, "ns")
    dut.rst.value = 0
    dut.input_0_in.value = LogicArray.from_signed(32768, 17)

    await Timer(2 * 2, "ns")
    dut.input_0_in.value = 0
    assert all(bit == "X" for bit in dut.output_0_out.value)

    await Timer(2 * 3, "ns")
    assert all(bit == "X" for bit in dut.output_0_out.value)

    await Timer(2 * 3, "ns")
    assert dut.output_0_out.value == 13572

    await Timer(2 * 3, "ns")
    assert dut.output_0_out.value == 5621

    await Timer(2 * 3, "ns")
    assert dut.output_0_out.value == 2327


async def _generate_clk(dut):
    from cocotb.triggers import Timer

    for _ in range(30):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
