import os
import shutil
from pathlib import Path

import cocotb
from cocotb.triggers import Timer
from cocotb_tools.runner import get_runner


def test_r4bf_compile(tmp_path, arch_r4bf):
    arch_r4bf.write_code(tmp_path, 32, 32, 32)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "r4bf_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="r4bf_tb",
        build_dir=tmp_path,
    )


def test_r4bf_simulate(tmp_path, arch_r4bf):
    arch_r4bf.write_code(tmp_path, 32, 32, 32)

    # Override the generated file with the ones specified in the directory "overrides"
    override_dir = Path(__file__).resolve().parent / "overrides"
    override_files = [f for f in override_dir.iterdir() if f.is_file()]
    for file in override_files:
        shutil.copy(file, tmp_path / "r4bf_0" / file.name)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "r4bf_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="r4bf",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="r4bf", test_module="test_r4bf")


@cocotb.test()
async def r4bf_test(dut):
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
    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
