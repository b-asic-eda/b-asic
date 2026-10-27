import json
import os

import apytypes as apy
import pytest

from b_asic.architecture import Architecture, ProcessingElement
from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.core_operations import Addition, Subtraction
from b_asic.data_type import DataType
from b_asic.quantization import OverflowMode, QuantizationMode
from b_asic.schedule import Schedule
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output

# Test parameters: (data_type, latency, out0_scale, test_cases)
# test_cases: list of (input0, input1) tuples
TEST_PARAMS = [
    pytest.param(
        DataType(wl=4),
        1,
        0,
        [(3, 2), (7, 5), (-1, -2)],
    ),
    pytest.param(
        DataType(wl=8),
        1,
        0,
        [(10, 20), (127, 0), (100, 27)],
    ),
    pytest.param(
        DataType(wl=8),
        1,
        1,
        [(16, 8), (32, 16), (-8, -4), (20, 10)],
    ),
    pytest.param(
        DataType(wl=8),
        1,
        2,
        [(32, 16), (64, 32), (-16, -8), (40, 20)],
    ),
    pytest.param(
        DataType(wl=8),
        1,
        3,
        [(64, 32), (128, 64), (-32, -16), (80, 40)],
    ),
    pytest.param(
        DataType(wl=16),
        1,
        0,
        [(1000, 2000), (32767, 0)],
    ),
    pytest.param(
        DataType(wl=16),
        1,
        2,
        [(1000, 2000), (32767, 1000), (5000, 3000)],
    ),
    pytest.param(
        DataType(
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
        DataType(
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
    pytest.param(
        DataType(wl=4, is_complex=True),
        1,
        0,
        [(0, 0), (3, 2), (7 + 7j, 5 + 5j), (-1 - 2j, -2 + 1j)],
    ),
    pytest.param(
        DataType(wl=(4, 4), is_complex=True, overflow_mode=OverflowMode.SATURATION),
        3,
        1,
        [
            (0, 0),
            (56 + 40j, 120 - 8j),
            (-120 - 9j, -8 + 16j),
            (127 + 127j, -128 - 128j),
        ],
    ),
]


@pytest.mark.parametrize(
    ("data_type", "latency", "out0_scale", "test_cases", "operation_type", "mul_j"),
    [
        (*parameters.values, operation_type, mul_j)
        for parameters in TEST_PARAMS
        for operation_type in (Addition, Subtraction)
        for mul_j in ((False, True) if parameters.values[0].is_complex else (False,))
    ],
)
@pytest.mark.parametrize(("in0_scale", "in1_scale"), [(0, 0), (1, 0), (0, 2), (1, 2)])
def test_add(
    tmp_path,
    data_type,
    latency,
    out0_scale,
    test_cases,
    operation_type,
    mul_j,
    in0_scale,
    in1_scale,
):
    tcs = []
    for tc in test_cases:
        if data_type.is_complex:
            a = apy.APyCFixed(
                (int(tc[0].real), int(tc[0].imag)),
                int_bits=data_type.wl[0],
                frac_bits=data_type.wl[1],
            )
            b = apy.APyCFixed(
                (int(tc[1].real), int(tc[1].imag)),
                int_bits=data_type.wl[0],
                frac_bits=data_type.wl[1],
            )
        else:
            a = apy.APyFixed(tc[0], int_bits=data_type.wl[0], frac_bits=data_type.wl[1])
            b = apy.APyFixed(tc[1], int_bits=data_type.wl[0], frac_bits=data_type.wl[1])

        scaled_a = (
            (a >> in0_scale).cast(
                *data_type.wl,
                data_type.quantization_mode.to_apytypes(),
                data_type.overflow_mode.to_apytypes(),
            )
            if in0_scale
            else a
        )
        scaled_b = (
            (b >> in1_scale).cast(
                *data_type.wl,
                data_type.quantization_mode.to_apytypes(),
                data_type.overflow_mode.to_apytypes(),
            )
            if in1_scale
            else b
        )
        if mul_j:
            scaled_b *= apy.fx(1j, 2, 0)
        res = scaled_a + scaled_b if operation_type is Addition else scaled_a - scaled_b
        if out0_scale > 0:
            res = (res >> out0_scale).cast(
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

        tcs.append((a.to_bits(), b.to_bits(), out0_scale, res.to_bits()))

    in0 = Input()
    in1 = Input()
    op0 = operation_type(
        in0,
        in1,
        latency=latency,
        execution_time=1,
        mul_j=mul_j,
        out0_scale=out0_scale,
        in0_scale=in0_scale,
        in1_scale=in1_scale,
    )
    out0 = Output(op0)
    sfg = SFG(inputs=[in0, in1], outputs=[out0])

    schedule = Schedule(sfg)

    operations = schedule.get_operations()
    adds = operations.get_by_type(operation_type)
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
    dut.en.value = 0
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    dut.en.value = 1

    # Get test cases and latency from environment variables
    test_cases = json.loads(os.environ.get("TEST_CASES", "[]"))
    latency = int(os.environ.get("LATENCY", "1"))

    cocotb.log.info(f"Running {len(test_cases)} test cases with latency={latency}")

    for in0, in1, _, expected in test_cases:
        is_complex = isinstance(in0, list)
        if is_complex:
            dut.in0_0_in_re.value = in0[0]
            dut.in0_0_in_im.value = in0[1]
            dut.in1_0_in_re.value = in1[0]
            dut.in1_0_in_im.value = in1[1]
        else:
            dut.in0_0_in.value = in0
            dut.in1_0_in.value = in1

        # Wait for the operation latency
        for _ in range(latency):
            await FallingEdge(dut.clk)

        if is_complex:
            actual = [
                dut.output_0_out_re.value.to_unsigned(),
                dut.output_0_out_im.value.to_unsigned(),
            ]
        else:
            actual = dut.output_0_out.value.to_unsigned()
        assert actual == expected

    await Timer(2 * 10, "ns")
