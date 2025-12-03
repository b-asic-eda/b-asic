import json
import os

import apytypes as apy
import pytest

from b_asic.architecture import Architecture, ProcessingElement
from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.core_operations import AddSub
from b_asic.data_type import VhdlDataType
from b_asic.quantization import OverflowMode, QuantizationMode
from b_asic.schedule import Schedule
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output

# Test parameters: (data_type, latency, is_add, shift_output, test_cases)
TEST_PARAMS = [
    pytest.param(
        VhdlDataType(wl=4),
        1,
        True,
        0,
        [(3, 2), (7, 5), (-1, -2), (5, 3)],
    ),
    pytest.param(
        VhdlDataType(wl=4, is_complex=True),
        1,
        True,
        0,
        [(3, 2), (7, 5), (-1, -2), (5, 3), (5 + 1j, 2 - 1j), (3 + 2j, 4 - 3j)],
    ),
    pytest.param(
        VhdlDataType(wl=4),
        4,
        True,
        0,
        [(3, 2), (7, 5), (-1, -2), (5, 3)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        False,
        0,
        [(10, 20), (127, 50), (100, 27), (50, 25)],
    ),
    pytest.param(
        VhdlDataType(wl=8, is_complex=True),
        2,
        False,
        0,
        [(10, 20), (127, 50), (100, 27), (50, 25), (127j, 32j), (64 + 64j, -65 + 67j)],
    ),
    pytest.param(
        VhdlDataType(wl=16),
        1,
        True,
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
            wl=(1, 3),
            quantization_mode=QuantizationMode.TRUNCATION,
            overflow_mode=OverflowMode.SATURATION,
        ),
        3,
        True,
        0,
        [
            (3, 2),
            (7, 1),
            (0, -1),
        ],
    ),
    # Tests with shift_output
    pytest.param(
        VhdlDataType(wl=8),
        1,
        True,
        1,
        [(16, 8), (32, 16), (-8, -4), (20, 10)],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        True,
        2,
        [(32, 16), (64, 32), (-16, -8), (40, 20)],
    ),
]


@pytest.mark.parametrize(
    ("data_type", "latency", "is_add", "shift_output", "test_cases"), TEST_PARAMS
)
def test_addsub(tmp_path, data_type, latency, is_add, shift_output, test_cases):
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

        res = a + b if is_add else a - b

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

        tcs.append((a.to_bits(), b.to_bits(), is_add, shift_output, res.to_bits()))

    in0 = Input()
    in1 = Input()
    op0 = AddSub(
        is_add, in0, in1, latency=latency, execution_time=1, shift_output=shift_output
    )
    out0 = Output(op0)
    sfg = SFG(inputs=[in0, in1], outputs=[out0])

    schedule = Schedule(sfg)

    operations = schedule.get_operations()
    addsubs = operations.get_by_type_name("addsub")
    in_ops = operations.get_by_type_name("in")
    in_ops = in_ops.split_on_execution_time()
    out_ops = operations.get_by_type_name("out")

    addsub = ProcessingElement(addsubs, entity_name="addsub")
    input_pe_0 = ProcessingElement(in_ops[0], entity_name="in0")
    input_pe_1 = ProcessingElement(in_ops[1], entity_name="in1")
    output_pe = ProcessingElement(out_ops, entity_name="output")

    mem_vars = schedule.get_memory_variables()
    direct, _ = mem_vars.split_on_length()

    arch = Architecture(
        {addsub, input_pe_0, input_pe_1, output_pe},
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
    runner.test(hdl_toplevel="top", test_module="test_addsub")


@cocotb_test()
async def addsub_test(dut):
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

    for i, (in0, in1, is_add, shift_output, expected) in enumerate(test_cases, 1):
        is_complex = False
        if isinstance(in0, list) and (in0[0] != 0 or in0[1] != 0):  # Complex case
            is_complex = True
            dut.in0_0_in_re.value = in0[0]
            dut.in0_0_in_im.value = in0[1]
            dut.in1_0_in_re.value = in1[0]
            dut.in1_0_in_im.value = in1[1]
        # imaginary case
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
            assert actual_re == expected_re
            assert actual_im == expected_im
            cocotb.log.info(
                f"✓ Test {i}: (({in0[0]}{op_str}{in1[0]}) >> {shift_output}) +j(({in0[1]}{op_str}{in1[1]}) >> {shift_output}) = "
                f"({actual_re} + j{actual_im})"
            )
        else:
            actual = dut.output_0_out.value.to_unsigned()
            op_str = "+" if is_add else "-"
            assert actual == expected
            cocotb.log.info(
                f"✓ Test {i}: ({in0} {op_str} {in1}) >> {shift_output} = {actual}"
            )

    await Timer(2 * 10, "ns")
