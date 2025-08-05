import os
import shutil
from pathlib import Path

import cocotb
from cocotb.runner import get_runner
from cocotb.triggers import Timer


def test_first_order_iir_compile(tmp_path, arch_first_order_iir):
    arch_first_order_iir.write_code(tmp_path, 16, 16, 16)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "first_order_iir_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="first_order_iir",
        build_dir=tmp_path,
    )


def test_first_order_iir_simulate(tmp_path, arch_first_order_iir):
    arch_first_order_iir.write_code(tmp_path, 16, 16, 16)

    # Override the generated file with the ones specified in the directory "overrides"
    override_dir = Path(__file__).resolve().parent / "overrides"
    override_files = [f for f in override_dir.iterdir() if f.is_file()]
    for file in override_files:
        shutil.copy(file, tmp_path / "first_order_iir_0" / file.name)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "first_order_iir_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="first_order_iir",
        build_dir=tmp_path,
    )

    os.environ["SIM_ARGS"] = "--vcd=wave.vcd"

    runner.test(hdl_toplevel="first_order_iir", test_module="test_first_order_iir")


@cocotb.test()
async def first_order_iir_test(dut):
    # Validate the impulse response of the first order IIR filter
    # Assume Q1.15 unsigned
    cocotb.start_soon(_generate_clk(dut))

    dut.rst = 1
    await Timer(2, "ns")
    dut.rst = 0
    dut.input_0_in.value = 32768

    await Timer(2 * 2, "ns")
    dut.input_0_in.value = 0
    assert all(bit == "X" for bit in dut.output_0_out.value.binstr)

    await Timer(2 * 3, "ns")
    assert all(bit == "X" for bit in dut.output_0_out.value.binstr)

    await Timer(2 * 3, "ns")
    assert dut.output_0_out.value == 13573

    await Timer(2 * 3, "ns")
    assert dut.output_0_out.value == 5621

    await Timer(2 * 3, "ns")
    assert dut.output_0_out.value == 2327


async def _generate_clk(dut):
    for _ in range(30):
        dut.clk.value = 0
        await Timer(1, units="ns")
        dut.clk.value = 1
        await Timer(1, units="ns")
