import os
import shutil
from pathlib import Path

import cocotb
from cocotb.triggers import Timer
from cocotb_tools.runner import get_runner


def test_r3bf_compile(tmp_path, arch_r3bf):
    arch_r3bf.write_code(tmp_path, 32, 32, 32)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "r3bf_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="r3bf_tb",
        build_dir=tmp_path,
    )


def test_r3bf_simulate(tmp_path, arch_r3bf):
    arch_r3bf.write_code(tmp_path, 32, 32, 32)

    # Override the generated file with the ones specified in the directory "overrides"
    override_dir = Path(__file__).resolve().parent / "overrides"
    override_files = [f for f in override_dir.iterdir() if f.is_file()]
    for file in override_files:
        shutil.copy(file, tmp_path / "r3bf_0" / file.name)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "r3bf_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="r3bf",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="r3bf", test_module="test_r3bf")


@cocotb.test()
async def r3bf_test(dut):
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
    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
