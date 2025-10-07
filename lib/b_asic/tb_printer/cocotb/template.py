"""Template for cocotb testbench."""

import os
import shutil
from pathlib import Path

import cocotb
import pytest
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge
from cocotb_tools.runner import get_runner


def test_start():
    sim = os.getenv("SIM", "ghdl")

    proj_path = Path(__file__).resolve().parent

    sources = [proj_path / "dff.vhdl"]

    if not shutil.which(sim):
        pytest.skip(f"Simulator {sim} not available in PATH")
    sources = list(Path().glob("*.vhdl"))

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel=ENTITY_NAME,
    )

    runner.test(hdl_toplevel=ENTITY_NAME, test_module="tb", gui=GUI)


GUI = False
ENTITY_NAME = ""
SEQUENCE = {}


@cocotb.test()
async def test_one(dut):
    clk = Clock(dut.clk, 2, units="ns")
    cocotb.start_soon(clk.start())

    max_cycle = max(SEQUENCE.keys())

    await FallingEdge(dut.clk)

    for cycle in range(max_cycle + 1):
        if cycle in SEQUENCE:
            step = SEQUENCE[cycle]
            # Drive inputs based on the sequence map
            for signal_name, value in step.items():
                getattr(dut, signal_name).value = value

        await FallingEdge(dut.clk)

    for _ in range(20):
        await FallingEdge(dut.clk)
