import json
import os

import apytypes as apy
import pytest

from b_asic.architecture import Architecture, ProcessingElement
from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.core_operations import ShiftAddSub
from b_asic.data_type import VhdlDataType
from b_asic.quantization import OverflowMode, QuantizationMode
from b_asic.schedule import Schedule
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output

# Test parameters: (data_type, latency, is_add, shift, mul_j, shift_output, test_cases)
# test_cases: list of (input0, input1) tuples
TEST_PARAMS = [
    pytest.param(
        VhdlDataType(wl=8),
        1,
        True,
        0,
        False,
        0,
        [(16, 8), (32, 16), (-8, -4), (20, 10)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        True,
        1,
        False,
        0,
        [(16, 8), (32, 16), (-8, -4), (20, 10)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        True,
        2,
        False,
        0,
        [(32, 16), (64, 32), (-16, -8), (40, 20)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        4,
        True,
        1,
        False,
        0,
        [(16, 8), (32, 16), (-8, -4), (20, 10)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        False,
        0,
        False,
        0,
        [(20, 10), (127, 50), (100, 27), (50, 25)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        False,
        1,
        False,
        0,
        [(20, 10), (100, 8), (-10, -10), (127, 50), (100, 27), (50, 25)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        False,
        2,
        False,
        0,
        [(40, 20), (127, 100), (100, 80), (60, 50)],
    ),
    pytest.param(
        VhdlDataType(wl=8, is_complex=True),
        1,
        True,
        1,
        False,
        0,
        [(16, 8), (32, 16), (-8, -4), (20, 10), (16 + 8j, 8 + 4j), (32 - 16j, 16 - 8j)],
    ),
    pytest.param(
        VhdlDataType(wl=8, is_complex=True),
        2,
        False,
        2,
        False,
        0,
        [
            (40, 20),
            (127, 100),
            (100, 80),
            (60, 50),
            (64 + 32j, 32 + 16j),
            (127 - 64j, 64 - 32j),
        ],
    ),
    pytest.param(
        VhdlDataType(wl=(2, 6), is_complex=True),
        1,
        True,
        1,
        True,
        0,
        [(16, 8), (32, 16), (-8, -4), (20, 10), (16 + 8j, 8 + 4j), (32 - 16j, 16 - 8j)],
    ),
    pytest.param(
        VhdlDataType(wl=16),
        1,
        True,
        3,
        False,
        0,
        [(1000, 2000), (32767, 1000), (5000, 3000)],
    ),
    pytest.param(
        VhdlDataType(
            wl=(4, 4),
            quantization_mode=QuantizationMode.TRUNCATION,
            overflow_mode=OverflowMode.WRAPPING,
        ),
        1,
        True,
        1,
        False,
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
        10,
        True,
        2,
        False,
        0,
        [
            (56, 40),
            (120, 16),
            (-120, -8),
            (-120, -9),
        ],
    ),
    # Tests with shift_output
    pytest.param(
        VhdlDataType(wl=8),
        1,
        True,
        1,
        False,
        1,
        [(1, 77), (-34, 15), (-8, -4), (21, 12)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        4,
        True,
        2,
        False,
        2,
        [(32, 16), (64, 32), (-16, -8), (40, 20)],
    ),
]


@pytest.mark.parametrize(
    ("data_type", "latency", "is_add", "shift", "mul_j", "shift_output", "test_cases"),
    TEST_PARAMS,
)
def test_shiftaddsub(
    tmp_path, data_type, latency, is_add, shift, mul_j, shift_output, test_cases
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

        # Apply the shift to b and cast back to data type
        b_shifted = (b >> shift).cast(
            data_type.wl[0],
            data_type.wl[1],
            data_type.quantization_mode.to_apytypes(),
            data_type.overflow_mode.to_apytypes(),
        )
        # Apply mul_j if needed
        if mul_j:
            b_shifted *= 1j

        res = a + b_shifted if is_add else a - b_shifted

        # Apply shift_output
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

        tcs.append(
            (
                a.to_bits(),
                b.to_bits(),
                is_add,
                shift,
                mul_j,
                shift_output,
                res.to_bits(),
            )
        )

    in0 = Input()
    in1 = Input()
    op0 = ShiftAddSub(
        in0,
        in1,
        is_add=is_add,
        shift=shift,
        latency=latency,
        execution_time=1,
        mul_j=mul_j,
        shift_output=shift_output,
    )
    out0 = Output(op0)
    sfg = SFG(inputs=[in0, in1], outputs=[out0])

    schedule = Schedule(sfg)

    operations = schedule.get_operations()
    shiftaddsubs = operations.get_by_type_name("shiftaddsub")
    in_ops = operations.get_by_type_name("in")
    in_ops = in_ops.split_on_execution_time()
    out_ops = operations.get_by_type_name("out")

    shiftaddsub = ProcessingElement(shiftaddsubs, entity_name="shiftaddsub")
    input_pe_0 = ProcessingElement(in_ops[0], entity_name="in0")
    input_pe_1 = ProcessingElement(in_ops[1], entity_name="in1")
    output_pe = ProcessingElement(out_ops, entity_name="output")

    mem_vars = schedule.get_memory_variables()
    direct, _ = mem_vars.split_on_length()

    arch = Architecture(
        {shiftaddsub, input_pe_0, input_pe_1, output_pe},
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
    runner.test(hdl_toplevel="top", test_module="test_shiftaddsub")


@cocotb_test()
async def shiftaddsub_test(dut):
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

    for i, (in0, in1, is_add, shift, mul_j, shift_output, expected) in enumerate(
        test_cases, 1
    ):
        is_complex = isinstance(in0, list) and len(in0) == 2

        if is_complex:
            print("Complex case:", in0, in1)
            dut.in0_0_in_re.value = in0[0]
            dut.in0_0_in_im.value = in0[1]
            dut.in1_0_in_re.value = in1[0]
            dut.in1_0_in_im.value = in1[1]
        # Real case
        else:
            dut.in0_0_in.value = in0
            dut.in1_0_in.value = in1

        # Wait for the operation latency
        for _ in range(latency):
            await FallingEdge(dut.clk)

        if is_complex:
            actual_re = dut.output_0_out_re.value.to_unsigned()
            actual_im = dut.output_0_out_im.value.to_unsigned()
            expected_re = expected[0]
            expected_im = expected[1]
            op_str = "+" if is_add else "-"
            mul_j_str = " * j" if mul_j else ""
            assert actual_re == expected_re
            assert actual_im == expected_im
            cocotb.log.info(
                f"✓ Test {i}: (({in0[0]}{op_str}(({in1[0]}{mul_j_str})>>{shift}))>>{shift_output}) +j(({in0[1]}{op_str}(({in1[1]}{mul_j_str})>>{shift}))>>{shift_output}) = "
                f"({actual_re} + j{actual_im})"
            )
        else:
            actual = dut.output_0_out.value.to_unsigned()
            op_str = "+" if is_add else "-"
            assert actual == expected
            cocotb.log.info(
                f"✓ Test {i}: ({in0} {op_str} ({in1} >> {shift})) >> {shift_output} = {actual}"
            )

    await Timer(2 * 10, "ns")
