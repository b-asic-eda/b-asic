import re

from b_asic import QuantizationMode
from b_asic.data_type import DataType
from b_asic.simulation import Simulation
from b_asic.tb_printer import VhdlTbPrinter


def _parse_assignments(content: str) -> dict:
    """
    Parse VHDL signal assignments from a stimulus process and return
    a dict of {cycle: {signal: value}}, mirroring CocotbPrinter SEQUENCE.
    """
    # Match:  signal <= std_logic_vector(to_unsigned(VALUE, BITS));
    value_re = re.compile(
        r"        (\w+) <= std_logic_vector\(to_unsigned\((\d+), \d+\)\);"
    )

    # Collect all input assignments grouped by cycle
    cycle_re = re.compile(r"-- Cycle (\d+)\n(.*?)(?=-- Cycle|\Z)", re.DOTALL)
    assert_re = re.compile(
        r"assert (\w+) = std_logic_vector\(to_unsigned\((\d+), \d+\)\)"
    )

    result: dict = {}

    for m in cycle_re.finditer(content):
        cycle = int(m.group(1))
        block = m.group(2)

        entries: dict = {}
        for am in assert_re.finditer(block):
            entries[am.group(1)] = int(am.group(2))
        for vm in value_re.finditer(block):
            entries[vm.group(1)] = int(vm.group(2))

        if entries:
            result[cycle] = entries

    return result


def test_simple_loop(tmp_path, arch_simple_loop, sfg_simple_loop):
    dt = DataType(
        wl=(3, 7),
        quantization_mode=QuantizationMode.TRUNCATION,
    )

    sim = Simulation(sfg_simple_loop, [lambda n: n / 16], dt)
    sim.run_for(20)

    tb_printer = VhdlTbPrinter(sim.results)
    tb_printer.print(arch_simple_loop, dt, path=tmp_path)

    vhdl_files = list(tmp_path.rglob("*.vhdl"))
    assert vhdl_files, f"No VHDL testbench generated in {tmp_path}"

    tb_file = max(vhdl_files, key=lambda p: p.stat().st_mtime)
    content = tb_file.read_text()

    # Basic structural checks
    assert "entity tb is" in content
    assert "architecture sim of tb is" in content
    assert "entity work." in content
    assert "clk <= not clk after CLK_PERIOD / 2;" in content
    assert "rst <= '1'" in content
    assert "rst <= '0'" in content
    assert "stimulus : process" in content

    # Signal declarations for inputs and outputs
    assert "in0_0_in" in content
    assert "out0_0_out" in content
    assert "std_logic_vector" in content

    sequence = _parse_assignments(content)

    assert sequence == {
        # input assignments
        0: {"in0_0_in": 0},
        2: {"in0_0_in": 8},
        4: {"in0_0_in": 16},
        6: {"in0_0_in": 24},
        8: {"in0_0_in": 32},
        10: {"in0_0_in": 40},
        12: {"in0_0_in": 48},
        14: {"in0_0_in": 56},
        16: {"in0_0_in": 64},
        18: {"in0_0_in": 72},
        20: {"in0_0_in": 80},
        22: {"in0_0_in": 88},
        24: {"in0_0_in": 96},
        26: {"in0_0_in": 104},
        28: {"in0_0_in": 112},
        30: {"in0_0_in": 120},
        32: {"in0_0_in": 128},
        34: {"in0_0_in": 136},
        36: {"in0_0_in": 144},
        38: {"in0_0_in": 152},
        # output assertions
        1: {"out0_0_out": 0},
        3: {"out0_0_out": 0},
        5: {"out0_0_out": 4},
        7: {"out0_0_out": 10},
        9: {"out0_0_out": 17},
        11: {"out0_0_out": 24},
        13: {"out0_0_out": 32},
        15: {"out0_0_out": 40},
        17: {"out0_0_out": 48},
        19: {"out0_0_out": 56},
        21: {"out0_0_out": 64},
        23: {"out0_0_out": 72},
        25: {"out0_0_out": 80},
        27: {"out0_0_out": 88},
        29: {"out0_0_out": 96},
        31: {"out0_0_out": 104},
        33: {"out0_0_out": 112},
        35: {"out0_0_out": 120},
        37: {"out0_0_out": 128},
        39: {"out0_0_out": 136},
    }


def test_output_file_named_tb_vhdl(tmp_path, arch_simple_loop, sfg_simple_loop):
    dt = DataType(wl=(3, 7), quantization_mode=QuantizationMode.TRUNCATION)
    sim = Simulation(sfg_simple_loop, [lambda n: n / 16], dt)
    sim.run_for(5)

    VhdlTbPrinter(sim.results).print(arch_simple_loop, dt, path=tmp_path)

    assert (tmp_path / "tb.vhdl").exists()


def test_dut_entity_name_in_instantiation(tmp_path, arch_simple_loop, sfg_simple_loop):
    dt = DataType(wl=(3, 7), quantization_mode=QuantizationMode.TRUNCATION)
    sim = Simulation(sfg_simple_loop, [lambda n: n / 16], dt)
    sim.run_for(5)

    VhdlTbPrinter(sim.results).print(arch_simple_loop, dt, path=tmp_path)

    content = (tmp_path / "tb.vhdl").read_text()
    assert f"entity work.{arch_simple_loop.entity_name}" in content
