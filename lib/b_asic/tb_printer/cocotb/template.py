"""Template for cocotb testbench."""

import csv
import shutil
import sys
from contextlib import nullcontext
from pathlib import Path

import cocotb
import pytest
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge
from cocotb_tools.runner import get_runner


def test_start():
    proj_path = Path(__file__).resolve().parent

    sources = [proj_path / "dff.vhdl"]

    if not shutil.which(SIMULATOR):
        pytest.skip(f"Simulator {SIMULATOR} not available in PATH")
    sources = list(Path().glob("*.vhdl"))

    runner = get_runner(SIMULATOR)
    runner.build(
        sources=sources,
        hdl_toplevel=ENTITY_NAME,
    )

    runner.test(hdl_toplevel=ENTITY_NAME, test_module="tb", waves=WAVES, gui=GUI)


SIMULATOR = ""
WAVES = False
GUI = False
CSV = False
ENTITY_NAME = ""
SEQUENCE = {}


@cocotb.test()
async def test_one(dut):
    clk = Clock(dut.clk, 2, unit="ns")
    cocotb.start_soon(clk.start())

    max_cycle = max(SEQUENCE.keys())

    await FallingEdge(dut.clk)

    # Context manager that does nothing if CSV is False
    csv_context = Path("waveform.csv").open("w", newline="") if CSV else nullcontext()  # noqa: SIM115

    with csv_context as f:
        writer = csv.writer(f) if CSV else None
        if CSV:
            writer.writerow(["port_name", "cycle", "value"])

        for cycle in range(max_cycle + 1):
            if cycle in SEQUENCE:
                step = SEQUENCE[cycle]
                # Drive inputs and check outputs based on the sequence map
                for signal_name, value in step.items():
                    if CSV:
                        hw_val = getattr(dut, signal_name).value
                    if signal_name.startswith("in"):
                        writer.writerow([signal_name, cycle, value]) if CSV else None
                        getattr(dut, signal_name).value = value
                    else:
                        if CSV and hw_val.is_resolvable:
                            writer.writerow([signal_name, cycle, int(hw_val)])
                        assert getattr(dut, signal_name).value == value, (
                            f"Cycle {cycle}: Expected {signal_name} to be {value}, "
                            f"but got {int(getattr(dut, signal_name).value)}"
                        )

            await FallingEdge(dut.clk)


if __name__ == "__main__":
    # forward command-line pytest options (e.g. -k, -q, -s) to allow running this file directly
    sys.exit(pytest.main([__file__, *sys.argv[1:]]))
