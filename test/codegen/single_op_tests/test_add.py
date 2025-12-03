import json
import os

import apytypes as apy
import pytest

from b_asic.architecture import Architecture, ProcessingElement
from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.core_operations import Addition
from b_asic.data_type import VhdlDataType
from b_asic.quantization import OverflowMode, QuantizationMode
from b_asic.schedule import Schedule
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output

# Test parameters: (data_type, latency, shift_output, test_cases)
# test_cases: list of (input0, input1) tuples
TEST_PARAMS = [
    pytest.param(
        VhdlDataType(wl=4),
        1,
        0,
        [(3, 2), (7, 5), (-1, -2)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        0,
        [(10, 20), (127, 0), (100, 27)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        1,
        [(16, 8), (32, 16), (-8, -4), (20, 10)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        2,
        [(32, 16), (64, 32), (-16, -8), (40, 20)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        3,
        [(64, 32), (128, 64), (-32, -16), (80, 40)],
    ),
    pytest.param(
        VhdlDataType(wl=16),
        1,
        0,
        [(1000, 2000), (32767, 0)],
    ),
    pytest.param(
        VhdlDataType(wl=16),
        1,
        2,
        [(1000, 2000), (32767, 1000), (5000, 3000)],
    ),
    pytest.param(
        VhdlDataType(
            wl=(4, 4),
            quantization_mode=QuantizationMode.TRUNCATION,
            overflow_mode=OverflowMode.WRAPPING,
        ),
        1,
        0,
        [
            (56, 40),
            (120, 16),
            (-120, -8),
            (-120, -9),
        ],
    ),
    pytest.param(
        VhdlDataType(
            wl=(4, 4),
            quantization_mode=QuantizationMode.TRUNCATION,
            overflow_mode=OverflowMode.WRAPPING,
        ),
        1,
        1,
        [
            (56, 40),
            (120, 16),
            (-120, -8),
            (-120, -9),
        ],
    ),
]


@pytest.mark.parametrize(
    ("data_type", "latency", "shift_output", "test_cases"), TEST_PARAMS
)
def test_add(tmp_path, data_type, latency, shift_output, test_cases):
    tcs = []
    for tc in test_cases:
        a = apy.APyFixed(tc[0], int_bits=data_type.wl[0], frac_bits=data_type.wl[1])
        b = apy.APyFixed(tc[1], int_bits=data_type.wl[0], frac_bits=data_type.wl[1])

        # Apply shift_output to the result
        res = a + b
        if shift_output > 0:
            res = (res >> shift_output).cast(
                data_type.wl[0],
                data_type.wl[1],
                data_type.quantization_mode.to_apytypes(),
                data_type.overflow_mode.to_apytypes(),
            )
        else:
            res = res.cast(
                data_type.wl[0],
                data_type.wl[1],
                data_type.quantization_mode.to_apytypes(),
                data_type.overflow_mode.to_apytypes(),
            )

        tcs.append((a.to_bits(), b.to_bits(), shift_output, res.to_bits()))

    in0 = Input()
    in1 = Input()
    op0 = Addition(
        in0, in1, latency=latency, execution_time=1, shift_output=shift_output
    )
    out0 = Output(op0)
    sfg = SFG(inputs=[in0, in1], outputs=[out0])

    schedule = Schedule(sfg)

    operations = schedule.get_operations()
    adds = operations.get_by_type_name("add")
    in_ops = operations.get_by_type_name("in")
    in_ops = in_ops.split_on_execution_time()
    out_ops = operations.get_by_type_name("out")

    adder = ProcessingElement(adds, entity_name="adder")
    input_pe_0 = ProcessingElement(in_ops[0], entity_name="in0")
    input_pe_1 = ProcessingElement(in_ops[1], entity_name="in1")
    output_pe = ProcessingElement(out_ops, entity_name="output")

    mem_vars = schedule.get_memory_variables()
    direct, _ = mem_vars.split_on_length()

    arch = Architecture(
        {adder, input_pe_0, input_pe_1, output_pe},
        [],
        entity_name="top",
        direct_interconnects=direct,
    )

    runner = get_runner()
    printer = VhdlPrinter(data_type)
    printer.print(arch, path=tmp_path)

    sources = [tmp_path / filename for filename in printer.get_compile_order(arch)]

    runner.build(
        sources=sources,
        hdl_toplevel="top",
        build_dir=tmp_path,
    )

    os.environ["TEST_CASES"] = json.dumps(tcs)
    os.environ["LATENCY"] = str(latency)
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
    latency = int(os.environ.get("LATENCY", "1"))

    cocotb.log.info(f"Running {len(test_cases)} test cases with latency={latency}")

    for i, (in0, in1, shift_output, expected) in enumerate(test_cases, 1):
        dut.in0_0_in.value = in0
        dut.in1_0_in.value = in1

        # Wait for the operation latency
        for _ in range(latency):
            await FallingEdge(dut.clk)

        actual = dut.output_0_out.value.to_unsigned()
        if shift_output > 0:
            assert actual == expected
            cocotb.log.info(f"✓ Test {i}: ({in0} + {in1}) >> {shift_output} = {actual}")
        else:
            assert actual == expected
            cocotb.log.info(f"✓ Test {i}: {in0} + {in1} = {actual}")

    await Timer(2 * 10, "ns")
