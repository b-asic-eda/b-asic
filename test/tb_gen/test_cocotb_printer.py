import ast

import pytest

from b_asic import QuantizationMode
from b_asic.data_type import VhdlDataType
from b_asic.simulation import Simulation
from b_asic.tb_printer import CocotbPrinter


def test_simple_loop(tmp_path, arch_simple_loop, sfg_simple_loop):
    dt = VhdlDataType(
        wl=(3, 7),
        quantization_mode=QuantizationMode.TRUNCATION,
    )

    sim = Simulation(sfg_simple_loop, [lambda n: n / 16], dt)
    sim.run_for(20)

    tb_printer = CocotbPrinter(sim.results)
    tb_printer.print(arch_simple_loop, path=tmp_path)

    # find python testbench file(s)
    py_files = [p for p in list(tmp_path.rglob("*")) if p.suffix == ".py"]
    assert py_files, f"No Python testbench generated in {tmp_path}"

    # pick the most-recent python file and check contents for cocotb patterns
    tb_file = max(py_files, key=lambda p: p.stat().st_mtime)
    content = tb_file.read_text()

    # locate SEQUENCE assignment via AST to handle nested/multiline dicts robustly
    sequence = None
    try:
        module = ast.parse(content)
    except SyntaxError:
        pytest.fail("Generated file contains invalid Python")

    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SEQUENCE":
                    try:
                        sequence = ast.literal_eval(node.value)
                    except Exception as e:
                        pytest.fail(f"Could not evaluate SEQUENCE: {e}")
                    break
        if sequence is not None:
            break

    assert sequence is not None, "Generated file does not define SEQUENCE"

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
        # output assignments
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


def test_multiple_io(
    tmp_path,
    sfg_two_inputs_two_outputs_independent_with_cmul_scaled,
    arch_two_inputs_two_outputs_independent_with_cmul_scaled,
):
    dt = VhdlDataType(
        wl=(1, 7),
        quantization_mode=QuantizationMode.TRUNCATION,
    )

    sim = Simulation(
        sfg_two_inputs_two_outputs_independent_with_cmul_scaled,
        [lambda n: n / 16, lambda n: n / 32],
        dt,
    )
    sim.run_for(20)

    tb_printer = CocotbPrinter(sim.results)
    tb_printer.print(
        arch_two_inputs_two_outputs_independent_with_cmul_scaled, path=tmp_path
    )

    # find python testbench file(s)
    py_files = [p for p in list(tmp_path.rglob("*")) if p.suffix == ".py"]
    assert py_files, f"No Python testbench generated in {tmp_path}"

    # pick the most-recent python file and check contents for cocotb patterns
    tb_file = max(py_files, key=lambda p: p.stat().st_mtime)
    content = tb_file.read_text()

    # locate SEQUENCE assignment via AST to handle nested/multiline dicts robustly
    sequence = None
    try:
        module = ast.parse(content)
    except SyntaxError:
        pytest.fail("Generated file contains invalid Python")

    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SEQUENCE":
                    try:
                        sequence = ast.literal_eval(node.value)
                    except Exception as e:
                        pytest.fail(f"Could not evaluate SEQUENCE: {e}")
                    break
        if sequence is not None:
            break

    assert sequence is not None, "Generated file does not define SEQUENCE"

    assert sequence == {
        0: {"in0_0_in": 0, "in1_0_in": 0},
        6: {"output_0_out": 0},
        10: {"output_0_out": 48, "in1_0_in": 4, "in0_0_in": 8},
        16: {"output_0_out": 0},
        20: {"output_0_out": 50, "in1_0_in": 8, "in0_0_in": 16},
        26: {"output_0_out": 1},
        30: {"output_0_out": 52, "in1_0_in": 12, "in0_0_in": 24},
        36: {"output_0_out": 1},
        40: {"output_0_out": 54, "in1_0_in": 16, "in0_0_in": 32},
        46: {"output_0_out": 2},
        50: {"output_0_out": 56, "in1_0_in": 20, "in0_0_in": 40},
        56: {"output_0_out": 2},
        60: {"output_0_out": 58, "in1_0_in": 24, "in0_0_in": 48},
        66: {"output_0_out": 3},
        70: {"output_0_out": 60, "in1_0_in": 28, "in0_0_in": 56},
        76: {"output_0_out": 3},
        80: {"output_0_out": 62, "in1_0_in": 32, "in0_0_in": 64},
        86: {"output_0_out": 4},
        90: {"output_0_out": 192, "in1_0_in": 36, "in0_0_in": 72},
        96: {"output_0_out": 4},
        100: {"output_0_out": 194, "in1_0_in": 40, "in0_0_in": 80},
        106: {"output_0_out": 5},
        110: {"output_0_out": 196, "in1_0_in": 44, "in0_0_in": 88},
        116: {"output_0_out": 5},
        120: {"output_0_out": 198, "in1_0_in": 48, "in0_0_in": 96},
        126: {"output_0_out": 6},
        130: {"output_0_out": 200, "in1_0_in": 52, "in0_0_in": 104},
        136: {"output_0_out": 6},
        140: {"output_0_out": 202, "in1_0_in": 56, "in0_0_in": 112},
        146: {"output_0_out": 7},
        150: {"output_0_out": 204, "in1_0_in": 60, "in0_0_in": 120},
        156: {"output_0_out": 7},
        160: {"output_0_out": 206, "in1_0_in": 64, "in0_0_in": 128},
        166: {"output_0_out": 248},
        170: {"output_0_out": 208, "in1_0_in": 68, "in0_0_in": 136},
        176: {"output_0_out": 248},
        180: {"output_0_out": 210, "in1_0_in": 72, "in0_0_in": 144},
        186: {"output_0_out": 249},
        190: {"output_0_out": 212, "in1_0_in": 76, "in0_0_in": 152},
        196: {"output_0_out": 249},
        200: {"output_0_out": 214},
    }

    a = [sequence[10 * k + 6]["output_0_out"] for k in range(20)]
    b = [e.to_bits() for e in sim.results["out0"]]
    assert a == b

    a = [sequence[10 * k]["output_0_out"] for k in range(1, 20)]
    b = [e.to_bits() for e in sim.results["out1"][:-1]]
    assert a == b

    a = [sequence[10 * k]["in0_0_in"] for k in range(20)]
    b = [e.to_bits() for e in sim.results["in0"]]
    assert a == b

    a = [sequence[10 * k]["in1_0_in"] for k in range(20)]
    b = [e.to_bits() for e in sim.results["in1"]]
    assert a == b
