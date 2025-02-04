from typing import Optional

import pytest

from b_asic import (
    SFG,
    AbstractOperation,
    Addition,
    Butterfly,
    Constant,
    ConstantMultiplication,
    Delay,
    Input,
    Name,
    Output,
    Signal,
    SignalSourceProvider,
    TypeName,
)


@pytest.fixture
def sfg_two_inputs_two_outputs():
    """
    Valid SFG with two inputs and two outputs.
         .               .
    in1-------+  +--------->out1
         .    |  |       .
         .    v  |       .
         .   add1+--+    .
         .    ^     |    .
         .    |     v    .
    in2+------+    add2---->out2
       | .          ^    .
       | .          |    .
       +------------+    .
         .               .
    out1 = in1 + in2
    out2 = in1 + 2 * in2
    """
    in1 = Input("IN1")
    in2 = Input("IN2")
    add1 = Addition(in1, in2, "ADD1")
    add2 = Addition(add1, in2, "ADD2")
    out1 = Output(add1, "OUT1")
    out2 = Output(add2, "OUT2")
    return SFG(inputs=[in1, in2], outputs=[out1, out2])


@pytest.fixture
def sfg_two_inputs_two_outputs_independent():
    """
    Valid SFG with two inputs and two outputs, where the first output only depends
    on the first input and the second output only depends on the second input.
         .               .
    in1-------------------->out1
         .               .
         .               .
         .      c1--+    .
         .          |    .
         .          v    .
    in2------+     add1---->out2
         .   |      ^    .
         .   |      |    .
         .   +------+    .
         .               .
    out1 = in1
    out2 = in2 + 3
    """
    in1 = Input("IN1")
    in2 = Input("IN2")
    c1 = Constant(3, "C1")
    add1 = Addition(in2, c1, "ADD1")
    out1 = Output(in1, "OUT1")
    out2 = Output(add1, "OUT2")
    return SFG(inputs=[in1, in2], outputs=[out1, out2])


@pytest.fixture
def sfg_two_inputs_two_outputs_independent_with_cmul():
    """
    Valid SFG with two inputs and two outputs, where the first output only depends
    on the first input and the second output only depends on the second input.
        .                 .
    in1--->cmul1--->cmul2--->out1
        .                 .
        .                 .
        .  c1             .
        .   |             .
        .   v             .
    in2--->add1---->cmul3--->out2
        .                 .
    """
    in1 = Input("IN1")
    in2 = Input("IN2")
    c1 = Constant(3, "C1")
    add1 = Addition(in2, c1, "ADD1", 7, execution_time=2)
    cmul3 = ConstantMultiplication(2, add1, "CMUL3", 3, execution_time=1)
    cmul1 = ConstantMultiplication(5, in1, "CMUL1", 5, execution_time=3)
    cmul2 = ConstantMultiplication(4, cmul1, "CMUL2", 4, execution_time=1)
    out1 = Output(cmul2, "OUT1")
    out2 = Output(cmul3, "OUT2")
    return SFG(inputs=[in1, in2], outputs=[out1, out2])


@pytest.fixture
def sfg_nested():
    """
    Valid SFG with two inputs and one output.
    out1 = in1 + (in1 + in1 * in2) * (in1 + in2 * (in1 + in1 * in2))
    """
    mac_in1 = Input()
    mac_in2 = Input()
    mac_in3 = Input()
    mac_out1 = Output(mac_in1 + mac_in2 * mac_in3)
    MAC = SFG(inputs=[mac_in1, mac_in2, mac_in3], outputs=[mac_out1])

    in1 = Input()
    in2 = Input()
    mac1 = MAC(in1, in1, in2)
    mac2 = MAC(in1, in2, mac1)
    mac3 = MAC(in1, mac1, mac2)
    out1 = Output(mac3)
    return SFG(inputs=[in1, in2], outputs=[out1])


@pytest.fixture
def sfg_delay():
    """
    Valid SFG with one input and one output.
    out1 = in1'
    """
    in1 = Input()
    t1 = Delay(in1)
    out1 = Output(t1)
    return SFG(inputs=[in1], outputs=[out1])


@pytest.fixture
def sfg_accumulator():
    """
    Valid SFG with two inputs and one output.
    data_out = (data_in' + data_in) * (1 - reset)
    """
    data_in = Input()
    reset = Input()
    t = Delay()
    t <<= (t + data_in) * (1 - reset)
    data_out = Output(t)
    return SFG(inputs=[data_in, reset], outputs=[data_out])


@pytest.fixture
def sfg_simple_accumulator():
    """
    Valid SFG with two inputs and one output.
         .                .
    in1----->add1-----+----->out1
         .    ^       |   .
         .    |       |   .
         .    +--t1<--+   .
         .                .
    """
    in1 = Input()
    t1 = Delay()
    add1 = in1 + t1
    t1 <<= add1
    out1 = Output(add1)
    return SFG(inputs=[in1], outputs=[out1])


@pytest.fixture
def sfg_simple_filter():
    """
    A valid SFG that is used as a filter in the first lab for TSTE87.
         .                 .
         .   +--cmul1<--+  .
         .   |          |  .
         .   v          |  .
    in1---->add1----->t1+---->out1
         .                 .
    """
    in1 = Input("IN")
    cmul1 = ConstantMultiplication(0.5, name="CMUL")
    add1 = Addition(in1, cmul1, "ADD")
    add1.input(1).signals[0].name = "S2"
    t1 = Delay(add1, name="T")
    cmul1.input(0).connect(t1, "S1")
    out1 = Output(t1, "OUT")
    return SFG(inputs=[in1], outputs=[out1], name="simple_filter")


@pytest.fixture
def sfg_custom_operation():
    """A valid SFG containing a custom operation."""

    class CustomOperation(AbstractOperation):
        def __init__(
            self, src0: Optional[SignalSourceProvider] = None, name: Name = ""
        ):
            super().__init__(
                input_count=1, output_count=2, name=name, input_sources=[src0]
            )

        @classmethod
        def type_name(self) -> TypeName:
            return "custom"

        def evaluate(self, a):
            return a * 2, 2**a

    in1 = Input()
    custom1 = CustomOperation(in1)
    out1 = Output(custom1.output(0))
    out2 = Output(custom1.output(1))
    return SFG(inputs=[in1], outputs=[out1, out2])


@pytest.fixture
def precedence_sfg_delays():
    """
    A sfg with delays and interesting layout for precedence list generation.
         .                                          .
    IN1>--->C0>--->ADD1>--->Q1>---+--->A0>--->ADD4>--->OUT1
         .           ^            |            ^    .
         .           |            T1           |    .
         .           |            |            |    .
         .         ADD2<---<B1<---+--->A1>--->ADD3  .
         .           ^            |            ^    .
         .           |            T2           |    .
         .           |            |            |    .
         .           +-----<B2<---+--->A2>-----+    .
    """
    in1 = Input("IN1")
    c0 = ConstantMultiplication(5, in1, "C0")
    add1 = Addition(c0, None, "ADD1")
    # Not sure what operation "Q" is supposed to be in the example
    Q1 = ConstantMultiplication(1, add1, "Q1")
    T1 = Delay(Q1, 0, "T1")
    T2 = Delay(T1, 0, "T2")
    b2 = ConstantMultiplication(2, T2, "B2")
    b1 = ConstantMultiplication(3, T1, "B1")
    add2 = Addition(b1, b2, "ADD2")
    add1.input(1).connect(add2)
    a1 = ConstantMultiplication(4, T1, "A1")
    a2 = ConstantMultiplication(6, T2, "A2")
    add3 = Addition(a1, a2, "ADD3")
    a0 = ConstantMultiplication(7, Q1, "A0")
    add4 = Addition(a0, add3, "ADD4")
    out1 = Output(add4, "OUT1")

    return SFG(inputs=[in1], outputs=[out1], name="SFG")


@pytest.fixture
def precedence_sfg_delays_and_constants():
    in1 = Input("IN1")
    c0 = ConstantMultiplication(5, in1, "C0")
    add1 = Addition(c0, None, "ADD1")
    # Not sure what operation "Q" is supposed to be in the example
    Q1 = ConstantMultiplication(1, add1, "Q1")
    T1 = Delay(Q1, 0, "T1")
    const1 = Constant(10, "CONST1")  # Replace T2 delay with a constant
    b2 = ConstantMultiplication(2, const1, "B2")
    b1 = ConstantMultiplication(3, T1, "B1")
    add2 = Addition(b1, b2, "ADD2")
    add1.input(1).connect(add2)
    a1 = ConstantMultiplication(4, T1, "A1")
    a2 = ConstantMultiplication(10, const1, "A2")
    add3 = Addition(a1, a2, "ADD3")
    a0 = ConstantMultiplication(7, Q1, "A0")
    # Replace ADD4 with a butterfly to test multiple output ports
    bfly1 = Butterfly(a0, add3, "BFLY1")
    out1 = Output(bfly1.output(0), "OUT1")
    Output(bfly1.output(1), "OUT2")

    return SFG(inputs=[in1], outputs=[out1], name="SFG")


@pytest.fixture
def sfg_two_tap_fir():
    # Inputs:
    in1 = Input(name="in1")

    # Outputs:
    out1 = Output(name="out1")

    # Operations:
    t1 = Delay(initial_value=0, name="t1")
    cmul1 = ConstantMultiplication(
        value=0.5, name="cmul1", latency_offsets={'in0': None, 'out0': None}
    )
    add1 = Addition(
        name="add1", latency_offsets={'in0': None, 'in1': None, 'out0': None}
    )
    cmul2 = ConstantMultiplication(
        value=0.5, name="cmul2", latency_offsets={'in0': None, 'out0': None}
    )

    # Signals:

    Signal(source=t1.output(0), destination=cmul1.input(0))
    Signal(source=in1.output(0), destination=t1.input(0))
    Signal(source=in1.output(0), destination=cmul2.input(0))
    Signal(source=cmul1.output(0), destination=add1.input(0))
    Signal(source=add1.output(0), destination=out1.input(0))
    Signal(source=cmul2.output(0), destination=add1.input(1))
    return SFG(inputs=[in1], outputs=[out1], name='twotapfir')


@pytest.fixture
def sfg_direct_form_iir_lp_filter():
    """
    Signal flow graph of the second-order direct form 2 IIR filter used in the
    first lab in the TSTE87 lab series.

    IN1>---->ADD1>----------+--->a0>--->ADD4>---->OUT1
               ^            |            ^
               |            T1           |
               |            |            |
             ADD2<---<a1<---+--->a1>--->ADD3
               ^            |            ^
               |            T2           |
               |            |            |
               +-----<a2<---+--->a2>-----+
    """
    a0, a1, a2, b1, b2 = 57 / 256, 55 / 128, 57 / 256, 179 / 512, -171 / 512
    x, y = Input(name="x"), Output(name="y")
    d0, d1 = Delay(), Delay()
    top_node = d0 * b1 + d1 * b2 + x
    d0.input(0).connect(top_node)
    d1.input(0).connect(d0)
    y <<= a1 * d0 + a2 * d1 + a0 * top_node
    return SFG(inputs=[x], outputs=[y], name='Direct Form 2 IIR Lowpass filter')


@pytest.fixture
def sfg_empty():
    """Empty SFG consisting of an Input followed by an Output."""
    in0 = Input()
    out0 = Output(in0)
    return SFG(inputs=[in0], outputs=[out0])
