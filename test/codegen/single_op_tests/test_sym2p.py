import json
import os

import apytypes as apy
import pytest

from b_asic.architecture import Architecture, ProcessingElement, _fixed_point_bits
from b_asic.code_printer import VhdlPrinter
from b_asic.code_printer.test import cocotb_test, get_runner
from b_asic.core_operations import SymmetricTwoportAdaptor
from b_asic.data_type import VhdlDataType
from b_asic.quantization import OverflowMode, QuantizationMode
from b_asic.schedule import Schedule
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output

# Test parameters: (data_type, latency, coefficient, test_cases)
# test_cases: list of (input0, input1) tuples
TEST_PARAMS = [
    pytest.param(
        VhdlDataType(wl=(1, 13)),
        1,
        0.375,
        [
            (50, 75),
            (40, 40),
            (-131, 57),
            (0, 0),
            (1234, 5678),
        ],
    ),
    pytest.param(
        VhdlDataType(wl=(1, 3)),
        1,
        0.5,
        [
            (1, 2),
            (5, 8),
            (-2, 1),
            (20, -40),
        ],
    ),
    pytest.param(
        VhdlDataType(wl=16),
        1,
        -0.25,
        [
            (200, 600),
            (1000, 3000),
            (-500, 400),
            (8192, 16384),
        ],
    ),
    pytest.param(
        VhdlDataType(wl=8),
        1,
        0.625,
        [
            (10, 20),
            (50, 75),
            (-40, 30),
            (127, -128),
        ],
    ),
    pytest.param(
        VhdlDataType(wl=16),
        4,
        -0.375,
        [
            (789, -2345),
            (3210, 7890),
            (-2468, -1357),
        ],
    ),
    pytest.param(
        VhdlDataType(
            wl=(4, 4),
            quantization_mode=QuantizationMode.TRUNCATION,
            overflow_mode=OverflowMode.WRAPPING,
        ),
        1,
        0.5,
        [
            (56, 40),
            (120, 16),
            (-120, -8),
        ],
    ),
    pytest.param(
        VhdlDataType(
            wl=(4, 4),
            quantization_mode=QuantizationMode.MAGNITUDE_TRUNCATION,
            overflow_mode=OverflowMode.WRAPPING,
        ),
        1,
        -0.5,
        [
            (56, 40),
            (120, 16),
            (-120, -8),
            (120, -54),
            (-54, -145),
            (249, 248),
            (255, 255),
            (-255, -255),
            (-255, 0),
            (0, -256),
        ],
    ),
]


def compute_sym2p_expected(in0, in1, coefficient, data_type):
    """
    Compute expected outputs using apytypes for bit-accurate calculation.

    Equations:
        out0 = in1 + coeff * (in1 - in0)
        out1 = in0 + coeff * (in1 - in0)
    """
    wl = data_type.wl if isinstance(data_type.wl, tuple) else (1, data_type.wl - 1)

    # Create fixed-point values
    a = apy.APyFixed(in0, int_bits=wl[0], frac_bits=wl[1])
    b = apy.APyFixed(in1, int_bits=wl[0], frac_bits=wl[1])

    # Get exact bits for coefficient
    coeff_int_bits, coeff_frac_bits = _fixed_point_bits(
        float(coefficient), data_type.is_signed
    )
    coeff = apy.APyFixed.from_float(
        float(coefficient), int_bits=coeff_int_bits, frac_bits=coeff_frac_bits
    )

    # Compute: tmp = coeff * (b - a)
    tmp = coeff * (b - a)

    # Compute outputs
    out0 = b + tmp
    out1 = a + tmp

    # Cast to match data type overflow/quantization behavior
    out0 = out0.cast(
        wl[0],
        wl[1],
        quantization=data_type.quantization_mode.to_apytypes(),
        overflow=data_type.overflow_mode.to_apytypes(),
    )
    out1 = out1.cast(
        wl[0],
        wl[1],
        quantization=data_type.quantization_mode.to_apytypes(),
        overflow=data_type.overflow_mode.to_apytypes(),
    )

    return out0.to_bits(), out1.to_bits()


@pytest.mark.parametrize(
    ("data_type", "latency", "coefficient", "test_cases"), TEST_PARAMS
)
def test_sym2p(tmp_path, data_type, latency, coefficient, test_cases):
    # Compute expected outputs using apytypes
    tcs = []
    for in0, in1 in test_cases:
        wl = data_type.wl if isinstance(data_type.wl, tuple) else (1, data_type.wl - 1)
        in0_apy = apy.APyFixed(in0, int_bits=wl[0], frac_bits=wl[1])
        in1_apy = apy.APyFixed(in1, int_bits=wl[0], frac_bits=wl[1])
        out0_bits, out1_bits = compute_sym2p_expected(in0, in1, coefficient, data_type)

        tcs.append((in0_apy.to_bits(), in1_apy.to_bits(), out0_bits, out1_bits))

    # Build SFG and architecture
    in0 = Input()
    in1 = Input()
    op0 = SymmetricTwoportAdaptor(
        coefficient, in0, in1, latency=latency, execution_time=1
    )
    out0 = Output(op0.output(0))
    out1 = Output(op0.output(1))
    sfg = SFG(inputs=[in0, in1], outputs=[out0, out1])

    schedule = Schedule(sfg)

    operations = schedule.get_operations()
    sym2ps = operations.get_by_type_name("sym2p")
    in_ops = operations.get_by_type_name("in")
    in_ops = in_ops.split_on_execution_time()
    out_ops = operations.get_by_type_name("out")
    out_ops = out_ops.split_on_execution_time()

    sym2p = ProcessingElement(sym2ps, entity_name="sym2p")
    input_pe_0 = ProcessingElement(in_ops[0], entity_name="in0")
    input_pe_1 = ProcessingElement(in_ops[1], entity_name="in1")
    output_pe_0 = ProcessingElement(out_ops[0], entity_name="out0")
    output_pe_1 = ProcessingElement(out_ops[1], entity_name="out1")

    mem_vars = schedule.get_memory_variables()
    direct, _ = mem_vars.split_on_length()

    arch = Architecture(
        {sym2p, input_pe_0, input_pe_1, output_pe_0, output_pe_1},
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
    runner.test(hdl_toplevel="top", test_module="test_sym2p")


@cocotb_test()
async def sym2p_test(dut):
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

    for i, (in0_bits, in1_bits, expected_out0, expected_out1) in enumerate(
        test_cases, 1
    ):
        dut.in0_0_in.value = in0_bits
        dut.in1_0_in.value = in1_bits

        # Wait for the operation latency
        for _ in range(latency):
            await FallingEdge(dut.clk)

        actual_out0 = dut.out0_0_out.value.to_unsigned()
        actual_out1 = dut.out1_0_out.value.to_unsigned()

        assert actual_out0 == expected_out0, (
            f"Test {i} out0: got {actual_out0}, expected {expected_out0}"
        )
        assert actual_out1 == expected_out1, (
            f"Test {i} out1: got {actual_out1}, expected {expected_out1}"
        )

        cocotb.log.info(
            f"✓ Test {i}: ({in0_bits}, {in1_bits}) -> ({actual_out0}, {actual_out1})"
        )

    await Timer(2 * 10, "ns")
