import os

import cocotb
from cocotb.triggers import Timer
from cocotb.types import LogicArray
from cocotb_tools.runner import get_runner


def test_mat_inv_compile(tmp_path, arch_mat_inv):
    arch_mat_inv.write_code(tmp_path, 7, 7, 7, write_pe_archs=True)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "mat_inv_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="mat_inv",
        build_dir=tmp_path,
    )


def test_mat_inv_simulate(tmp_path, arch_mat_inv):
    arch_mat_inv.write_code(tmp_path, (3, 13), write_pe_archs=True)

    sim = os.getenv("SIM", "ghdl")
    sources = list((tmp_path / "mat_inv_0").glob("*.vhd"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="mat_inv",
        build_dir=tmp_path,
    )

    runner.test(
        hdl_toplevel="mat_inv", test_module="test_mat_inv", waves=True, verbose=True
    )


@cocotb.test()
async def mat_inv_test(dut):
    cocotb.start_soon(_generate_clk(dut))
    # 3x3 matrix inversion, input in natural order, output in reversed order
    dut.rst.value = 1
    await Timer(2, "ns")
    dut.rst.value = 0

    # ROW 1
    dut.input_0_in.value = LogicArray.from_signed((1 * 2**13), 16)

    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed((0 * 2**13), 16)

    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed((0 * 2**13), 16)

    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed((0 * 2**13), 16)

    # ROW 2
    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed((2 * 2**13), 16)

    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed((1 * 2**10), 16)

    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed((0 * 2**13), 16)

    # ROW 3
    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed((3 * 2**13), 16)

    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed((0 * 2**13), 16)

    # ROW 4
    await Timer(2, "ns")
    dut.input_0_in.value = LogicArray.from_signed((4 * 2**12), 16)

    # Validate outputs
    # ROW 4
    await Timer(27 * 2, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(4096, 16)

    # ROW 3
    await Timer(2, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(0, 16)

    await Timer(2, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(2737, 16)

    # ROW 2
    await Timer(2, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(0, 16)

    await Timer(2, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(-171, 16)

    await Timer(2, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(4107, 16)

    # ROW 1
    await Timer(2, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(0, 16)

    await Timer(2, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(0, 16)

    await Timer(2, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(0, 16)

    await Timer(2, "ns")
    assert dut.output_0_out.value == LogicArray.from_signed(8192, 16)


async def _generate_clk(dut):
    for _ in range(100):
        dut.clk.value = 0
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
