import os
import shutil
from pathlib import Path

import cocotb
from cocotb.runner import get_runner
from cocotb.triggers import Timer


def test_simple_compile(tmp_path, arch_simple):
    arch_simple.write_code(tmp_path, 7, 7, 7)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "simple_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="simple",
        build_dir=tmp_path,
    )


def test_simple_simulate(tmp_path, arch_simple):
    arch_simple.write_code(tmp_path, 7, 7, 7)

    # Override the generated file for mult and adder with one containing an architecture
    override_dir = Path(__file__).resolve().parent / "overrides"
    override_files = [f for f in override_dir.iterdir() if f.is_file()]
    for file in override_files:
        shutil.copy(file, tmp_path / "simple_0" / file.name)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "simple_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="simple",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="simple", test_module="test_simple")


def test_simple_simulate_different_word_lengths(tmp_path, arch_simple):
    arch_simple.write_code(tmp_path, 7, 3, 6)

    # Override the generated file for mult and adder with one containing an architecture
    override_dir = Path(__file__).resolve().parent / "overrides"
    override_files = [f for f in override_dir.iterdir() if f.is_file()]
    for file in override_files:
        shutil.copy(file, tmp_path / "simple_0" / file.name)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "simple_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="simple",
        build_dir=tmp_path,
    )

    runner.test(hdl_toplevel="simple", test_module="test_simple")


@cocotb.test()
async def simple_test(dut):
    cocotb.start_soon(_generate_clk(dut))

    dut.rst.value = 1
    await Timer(2, "ns")
    dut.rst.value = 0
    dut.input_0_in.value = 3

    await Timer(2, "ns")
    dut.input_0_in.value = 5

    await Timer(8, "ns")
    dut.input_0_in.value = 6
    assert dut.output_0_out.value == 32
    await Timer(2, "ns")
    dut.input_0_in.value = 4

    await Timer(8, "ns")
    assert dut.output_0_out.value == 40


async def _generate_clk(dut):
    for _ in range(20):
        dut.clk.value = 0
        await Timer(1, units="ns")
        dut.clk.value = 1
        await Timer(1, units="ns")
