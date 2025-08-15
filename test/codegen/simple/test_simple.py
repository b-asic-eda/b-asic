import os
import shutil

import pytest

from b_asic.codegen.test import cocotb_test


def test_simple_compile(tmp_path, arch_simple):
    pytest.importorskip("cocotb_tools")
    arch_simple.write_code(tmp_path, 7, 7, 7)

    sim = os.getenv("SIM", "ghdl")
    if not shutil.which(sim):
        pytest.skip(f"Simulator {sim} not available in PATH")
    sources = list((tmp_path / "simple_0").glob("*.vhd"))
    from cocotb_tools.runner import get_runner

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="simple_tb",
        build_dir=tmp_path,
    )


def test_simple_simulate(tmp_path, arch_simple):
    pytest.importorskip("cocotb_tools")
    arch_simple.write_code(tmp_path, 8, 4, 7, write_pe_archs=True)

    sim = os.getenv("SIM", "ghdl")
    if not shutil.which(sim):
        pytest.skip(f"Simulator {sim} not available in PATH")
    sources = list((tmp_path / "simple_0").glob("*.vhd"))
    from cocotb_tools.runner import get_runner

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="simple",
        build_dir=tmp_path,
    )

    runner.test(
        hdl_toplevel="simple", test_module="test_simple", waves=True, verbose=True
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
    assert dut.output_0_out.value == LogicArray.from_signed(32, 7)
    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed(4, 4)

    await Timer(8, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(40, 7)


async def _generate_clk(dut):
    from cocotb.triggers import Timer

    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
