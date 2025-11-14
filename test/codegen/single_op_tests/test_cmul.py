import json
import math
import os

import apytypes as apy
import pytest

from b_asic.architecture import Architecture, ProcessingElement, _fixed_point_bits
from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.core_operations import ConstantMultiplication
from b_asic.data_type import VhdlDataType
from b_asic.quantization import OverflowMode, QuantizationMode
from b_asic.schedule import Schedule
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output

# Test parameters: (data_type, latency, value, test_cases)
# test_cases: list of input values
TEST_PARAMS = [
    pytest.param(
        VhdlDataType(wl=8),
        1,
        0.5,
        [10, 20, 30, -5, 127],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        3,
        [10, 20, 30, -5, 42],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        -2,
        [10, 20, 30, -5, -20],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        4,
        5,
        [10, 20, 25, -5],
    ),
    pytest.param(
        VhdlDataType(wl=16),
        1,
        7,
        [1000, 2000, -500, 4000],
    ),
    pytest.param(
        VhdlDataType(wl=8, is_complex=True),
        1,
        2,
        [10, 20, -5, 10 + 5j, 20 - 10j],
    ),
    pytest.param(
        VhdlDataType(wl=8, is_complex=True),
        1,
        3 + 2j,
        [10, 20, 10 + 5j, 20 - 10j],
    ),
    pytest.param(
        VhdlDataType(wl=8, is_complex=True),
        2,
        2j,
        [10, 20, -5, 10 + 5j, 20 - 10j],
    ),
    pytest.param(
        VhdlDataType(wl=(4, 10), is_complex=True),
        5,
        math.sqrt(3) * 1j / 2,
        [100, -200, 300, -400, 500, -600, 700, -800, 900],
    ),
    pytest.param(
        VhdlDataType(
            wl=(4, 4),
            quantization_mode=QuantizationMode.TRUNCATION,
            overflow_mode=OverflowMode.WRAPPING,
        ),
        1,
        2,
        [56, 120, -120],
    ),
    pytest.param(
        VhdlDataType(
            wl=(4, 4),
            quantization_mode=QuantizationMode.TRUNCATION,
            overflow_mode=OverflowMode.WRAPPING,
        ),
        10,
        3,
        [56, 40, -80],
    ),
]


@pytest.mark.parametrize(("data_type", "latency", "value", "test_cases"), TEST_PARAMS)
def test_cmul(tmp_path, data_type, latency, value, test_cases):
    # Calculate exact int_bits and frac_bits needed for the value
    if data_type.is_complex:
        # For complex values, find the maximum bits needed for real and imaginary parts
        real_val = value.real if isinstance(value, complex) else float(value)
        imag_val = value.imag if isinstance(value, complex) else 0.0

        real_int_bits, real_frac_bits = _fixed_point_bits(real_val, data_type.is_signed)
        imag_int_bits, imag_frac_bits = _fixed_point_bits(imag_val, data_type.is_signed)

        val_int_bits = max(real_int_bits, imag_int_bits)
        val_frac_bits = max(real_frac_bits, imag_frac_bits)
    else:
        # For real values
        val_int_bits, val_frac_bits = _fixed_point_bits(
            float(value), data_type.is_signed
        )

    tcs = []
    for tc in test_cases:
        if data_type.is_complex:
            a = apy.APyCFixed(
                (int(tc.real), int(tc.imag)),
                int_bits=data_type.wl[0],
                frac_bits=data_type.wl[1],
            )
            # Convert value to APyCFixed with calculated exact bits
            val = apy.APyCFixed.from_complex(
                value if isinstance(value, complex) else complex(value, 0),
                int_bits=val_int_bits,
                frac_bits=val_frac_bits,
            )
        else:
            a = apy.APyFixed(tc, int_bits=data_type.wl[0], frac_bits=data_type.wl[1])
            # Convert value to APyFixed with calculated exact bits
            val = apy.APyFixed.from_float(
                float(value),
                int_bits=val_int_bits,
                frac_bits=val_frac_bits,
            )

        # Perform multiplication and cast to data type
        res = (a * val).cast(
            data_type.wl[0],
            data_type.wl[1],
            data_type.quantization_mode.to_apytypes(),
            data_type.overflow_mode.to_apytypes(),
        )

        tcs.append((a.to_bits(), val.to_bits(), res.to_bits()))

    in0 = Input()
    op0 = ConstantMultiplication(value, in0, latency=latency, execution_time=1)
    out0 = Output(op0)
    sfg = SFG(inputs=[in0], outputs=[out0])

    schedule = Schedule(sfg)

    operations = schedule.get_operations()
    cmuls = operations.get_by_type_name("cmul")
    in_ops = operations.get_by_type_name("in")
    out_ops = operations.get_by_type_name("out")

    cmul = ProcessingElement(cmuls, entity_name="cmul")
    input_pe = ProcessingElement(in_ops, entity_name="in0")
    output_pe = ProcessingElement(out_ops, entity_name="output")

    mem_vars = schedule.get_memory_variables()
    direct, _ = mem_vars.split_on_length()

    arch = Architecture(
        {cmul, input_pe, output_pe},
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
    runner.test(hdl_toplevel="top", test_module="test_cmul")


@cocotb_test()
async def cmul_test(dut):
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

    for i, (in0, value, expected) in enumerate(test_cases, 1):
        is_complex = isinstance(in0, list) and len(in0) == 2

        if is_complex:
            dut.in0_0_in_re.value = in0[0]
            dut.in0_0_in_im.value = in0[1]
        # Real case
        else:
            dut.in0_0_in.value = in0

        # Wait for the operation latency
        for _ in range(latency):
            await FallingEdge(dut.clk)

        if is_complex:
            actual_re = dut.output_0_out_re.value.to_unsigned()
            actual_im = dut.output_0_out_im.value.to_unsigned()
            expected_re = expected[0]
            expected_im = expected[1]
            assert actual_re == expected_re
            assert actual_im == expected_im
            cocotb.log.info(
                f"✓ Test {i}: ({in0[0]} + j{in0[1]}) * ({value[0]} + j{value[1]}) = "
                f"({actual_re} + j{actual_im})"
            )
        else:
            actual = dut.output_0_out.value.to_unsigned()
            assert actual == expected
            cocotb.log.info(f"✓ Test {i}: {in0} * {value} = {actual}")

    await Timer(2 * 10, "ns")
