import os
import shutil
from pathlib import Path

import cocotb
from cocotb.runner import get_runner
from cocotb.triggers import Timer


def test_r2bf_compile(tmp_path, arch_r2bf):
    arch_r2bf.write_code(tmp_path, 16, 16, 16)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "r2bf_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="r2bf",
        build_dir=tmp_path,
    )


def test_r2bf_simulate(tmp_path, arch_r2bf):
    arch_r2bf.write_code(tmp_path, 16, 16, 16)

    # Override the generated file with the ones specified in the directory "overrides"
    override_dir = Path(__file__).resolve().parent / "overrides"
    override_files = [f for f in override_dir.iterdir() if f.is_file()]
    for file in override_files:
        shutil.copy(file, tmp_path / "r2bf_0" / file.name)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "r2bf_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="r2bf",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="r2bf", test_module="test_r2bf")


@cocotb.test()
async def r2bf_test(dut):
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
    for _ in range(10):
        dut.clk.value = 0
        await Timer(1, units="ns")
        dut.clk.value = 1
        await Timer(1, units="ns")
