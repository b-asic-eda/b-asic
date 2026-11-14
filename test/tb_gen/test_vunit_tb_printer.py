"""Tests for optional VUnit support in generated VHDL testbenches."""

import pytest

from b_asic import QuantizationMode
from b_asic.data_type import DataType
from b_asic.simulation import Simulation
from b_asic.tb_printer import VhdlTbPrinter


@pytest.mark.parametrize(
    ("asserts", "abs_tol", "enable_pin"),
    [(True, None, True), (True, 0.01, False), (False, None, True)],
)
def test_vunit_testbench(
    tmp_path, arch_simple_loop, schedule_simple_loop, asserts, abs_tol, enable_pin
):
    dt = DataType(wl=(3, 7), quantization_mode=QuantizationMode.TRUNCATION)
    sim = Simulation(schedule_simple_loop.sfg, [lambda n: n / 16], dt)
    sim.run_for(5)
    printer = VhdlTbPrinter(sim.results)
    options = {
        "path": tmp_path,
        "asserts": asserts,
        "abs_tol": abs_tol,
        "enable_pin": enable_pin,
    }

    printer.print(arch_simple_loop, dt, **options)
    standalone = (tmp_path / "tb.vhdl").read_text()
    printer.print(arch_simple_loop, dt, vunit=False, **options)
    assert (tmp_path / "tb.vhdl").read_text() == standalone
    assert "vunit" not in standalone
    assert "runner_cfg" not in standalone
    assert "use std.env.all;" in standalone
    assert "        stop(0);" in standalone

    printer.print(arch_simple_loop, dt, vunit=True, **options)
    content = (tmp_path / "tb.vhdl").read_text()
    assert "library vunit_lib;\ncontext vunit_lib.vunit_context;" in content
    assert "entity tb is\n    generic (\n        runner_cfg : string\n    );" in content
    assert "use std.env.all;" not in content
    assert "stop(0);" not in content

    # The runner must cover the entire stimulus sequence and terminate via VUnit.
    setup = "        test_runner_setup(runner, runner_cfg);\n"
    cleanup = "        test_runner_cleanup(runner);\n        wait;"
    assert content.index(setup) < content.index("        rst <= '1';")
    assert content.index("        -- Cycle 0") < content.index(cleanup)

    # All stimuli, timing, assertions and DUT connections remain identical.
    normalized = content.replace(
        "library vunit_lib;\ncontext vunit_lib.vunit_context;", "use std.env.all;"
    )
    normalized = normalized.replace(
        "    generic (\n        runner_cfg : string\n    );\n", ""
    )
    normalized = normalized.replace(setup, "").replace(cleanup, "        stop(0);")
    assert normalized == standalone
