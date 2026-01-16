"""End-to-end smoke tests that generates and runs cocotb testbenches."""

import shutil
import subprocess
from pathlib import Path

import pytest

from b_asic import QuantizationMode
from b_asic.code_printer import VhdlPrinter
from b_asic.data_type import VhdlDataType
from b_asic.simulation import Simulation
from b_asic.tb_printer import CocotbPrinter


@pytest.mark.skipif(shutil.which("ghdl") is None, reason="GHDL simulator not available")
def test_cocotb_testbench_execution(tmp_path, arch_simple_loop, sfg_simple_loop):
    # Generate VHDL code
    dt = VhdlDataType(
        wl=(3, 7),
        quantization_mode=QuantizationMode.TRUNCATION,
    )
    vhdl_printer = VhdlPrinter(dt)
    vhdl_printer.print(arch_simple_loop, path=tmp_path)

    # Run simulation to get expected results
    sim = Simulation(sfg_simple_loop, [lambda n: n / 16], dt)
    sim.run_for(20)

    # Generate cocotb testbench
    tb_printer = CocotbPrinter(sim.results)
    tb_printer.print(arch_simple_loop, path=tmp_path, simulator="ghdl", waves=False)

    # Verify testbench was generated
    tb_file = tmp_path / "tb.py"
    assert tb_file.exists(), "Testbench file not generated"

    # Verify testbench is valid Python
    with Path.open(tb_file) as f:
        content = f.read()
        compile(content, str(tb_file), "exec")  # Will raise SyntaxError if invalid

    # Run the testbench
    result = subprocess.run(
        ["python", "tb.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    # Check execution succeeded
    assert result.returncode == 0, (
        f"Testbench execution failed with return code {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    # Check for cocotb success indicators in output
    assert "passed" in result.stdout.lower() or "test_one" in result.stdout


@pytest.mark.skipif(shutil.which("ghdl") is None, reason="GHDL simulator not available")
def test_cocotb_testbench_with_csv_output(tmp_path, arch_simple_loop, sfg_simple_loop):
    # Generate VHDL code
    dt = VhdlDataType(
        wl=(3, 7),
        quantization_mode=QuantizationMode.TRUNCATION,
    )
    vhdl_printer = VhdlPrinter(dt)
    vhdl_printer.print(arch_simple_loop, path=tmp_path)

    # Run simulation
    sim = Simulation(sfg_simple_loop, [lambda n: n / 16], dt)
    sim.run_for(10)

    # Generate cocotb testbench with CSV enabled
    tb_printer = CocotbPrinter(sim.results)
    tb_printer.print(
        arch_simple_loop, path=tmp_path, simulator="ghdl", waves=False, csv=True
    )

    # Run the testbench
    result = subprocess.run(
        ["python", "tb.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    # Check execution succeeded
    assert result.returncode == 0, (
        f"Testbench execution failed\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    # Verify CSV file was created (in the sim_build directory)
    csv_location = tmp_path / "sim_build" / "waveform.csv"

    csv_file = None
    if csv_location.exists():
        csv_file = csv_location

    assert csv_file is not None, (
        f"CSV waveform file not generated in any expected location\n"
        f"Checked: {csv_location!s}\n"
        f"Directory contents: {list(tmp_path.rglob('*'))}"
    )

    # Verify CSV has content
    csv_content = csv_file.read_text()
    assert "port_name" in csv_content, "CSV header not found"
    assert "cycle" in csv_content, "CSV header missing cycle column"
    assert "value" in csv_content, "CSV header missing value column"
    lines = csv_content.strip().split("\n")
    assert len(lines) > 1, "CSV file has no data rows"
