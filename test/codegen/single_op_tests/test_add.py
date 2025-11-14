import apytypes as apy
import pytest

from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.data_type import VhdlDataType
from b_asic.quantization import OverflowMode, QuantizationMode

# Test parameters: (data_type, test_cases)
# test_cases: list of (input0, input1, expected_output)
TEST_PARAMS = [
    pytest.param(
        VhdlDataType(wl=4),
        [(3, 2), (7, 5), (-1, -2)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        [(10, 20), (127, 0), (100, 27)],
    ),
    pytest.param(
        VhdlDataType(wl=16),
        [(1000, 2000), (32767, 0)],
    ),
    pytest.param(
        VhdlDataType(
            wl=(4, 4),
            quantization_mode=QuantizationMode.TRUNCATION,
            overflow_mode=OverflowMode.WRAPPING,
        ),
        [
            (56, 40),
            (120, 16),
            (-120, -8),
            (-120, -9),
        ],
    ),
]


@pytest.mark.parametrize(("data_type", "test_cases"), TEST_PARAMS)
def test_add_compile(tmp_path, arch_add, data_type, test_cases):
    runner = get_runner()
    printer = VhdlPrinter(data_type)
    printer.print(arch_add, path=tmp_path)

    sources = list((tmp_path).glob("*.vhdl"))
    runner.build(
        sources=sources,
        hdl_toplevel="top",
        build_dir=tmp_path,
    )


@pytest.mark.parametrize(("data_type", "test_cases"), TEST_PARAMS)
def test_add_simulate(tmp_path, arch_add, data_type, test_cases):
    runner = get_runner()
    printer = VhdlPrinter(data_type)
    printer.print(arch_add, path=tmp_path)

    sources = [tmp_path / filename for filename in printer.get_compile_order(arch_add)]

    runner.build(
        sources=sources,
        hdl_toplevel="top",
        build_dir=tmp_path,
    )

    # Pass test cases via environment variable (JSON encoded)
    import json
    import os

    tcs = []
    for tc in test_cases:
        a = apy.APyFixed(tc[0], int_bits=data_type.wl[0], frac_bits=data_type.wl[1])
        b = apy.APyFixed(tc[1], int_bits=data_type.wl[0], frac_bits=data_type.wl[1])
        res = (a + b).cast(
            data_type.wl[0],
            data_type.wl[1],
            data_type.quantization_mode.to_apytypes(),
            data_type.overflow_mode.to_apytypes(),
        )
        tcs.append((a.to_bits(), b.to_bits(), res.to_bits()))

    os.environ["TEST_CASES"] = json.dumps(tcs)
    os.environ["OPERATION_LATENCY"] = "1"

    runner.test(hdl_toplevel="top", test_module="test_add")


@cocotb_test()
async def add_test(dut):
    import json
    import os

    import cocotb
    from cocotb.clock import Clock
    from cocotb.triggers import FallingEdge, Timer

    cocotb.start_soon(Clock(dut.clk, 2, unit="ns").start())

    dut.rst.value = 1
    await FallingEdge(dut.clk)
    dut.rst.value = 0

    # Get test cases and latency from environment variables
    test_cases = json.loads(os.environ.get("TEST_CASES", "[]"))
    latency = int(os.environ.get("OPERATION_LATENCY", "1"))

    cocotb.log.info(f"Running {len(test_cases)} test cases with latency={latency}")

    for i, (in0, in1, expected) in enumerate(test_cases, 1):
        dut.in0_0_in.value = in0
        dut.in1_0_in.value = in1

        # Wait for the operation latency
        for _ in range(latency):
            await FallingEdge(dut.clk)

        actual = dut.output_0_out.value.to_unsigned()
        assert actual == expected, (
            f"Test {i}: {in0} + {in1} = {actual}, expected {expected}"
        )
        cocotb.log.info(f"✓ Test {i}: {in0} + {in1} = {actual}")

    await Timer(2 * 10, "ns")
