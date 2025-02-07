"""
B-ASIC signal flow graph generators.

This module contains a number of functions generating SFGs for specific functions.
"""

from typing import TYPE_CHECKING, Dict, Optional, Sequence, Union

import numpy as np

from b_asic.core_operations import (
    Addition,
    Butterfly,
    ConstantMultiplication,
    Name,
    SymmetricTwoportAdaptor,
)
from b_asic.signal import Signal
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Delay, Input, Output

if TYPE_CHECKING:
    from b_asic.port import OutputPort


def wdf_allpass(
    coefficients: Sequence[float],
    name: Optional[str] = None,
    latency: Optional[int] = None,
    latency_offsets: Optional[Dict[str, int]] = None,
    execution_time: Optional[int] = None,
) -> SFG:
    """
    Generate a signal flow graph of a WDF allpass section based on symmetric two-port\
 adaptors.

    Simplifies the SFG in case an adaptor operation is 0.

    Parameters
    ----------
    coefficients : 1D-array
        Coefficients to use for the allpass section.

    name : Name, optional
        The name of the SFG. If None, "WDF allpass section".

    latency : int, optional
        Latency of the symmetric two-port adaptors.

    latency_offsets : optional
        Latency offsets of the symmetric two-port adaptors.

    execution_time : int, optional
        Execution time of the symmetric two-port adaptors.

    Returns
    -------
        Signal flow graph
    """
    np_coefficients = np.atleast_1d(np.squeeze(np.asarray(coefficients)))
    order = len(np_coefficients)
    if not order:
        raise ValueError("Coefficients cannot be empty")
    if np_coefficients.ndim != 1:
        raise TypeError("coefficients must be a 1D-array")
    if name is None:
        name = "WDF allpass section"
    input_op = Input()
    output = Output()
    odd_order = order % 2
    if odd_order:
        if np_coefficients[0]:
            # First-order section
            adaptor0 = SymmetricTwoportAdaptor(
                np_coefficients[0],
                input_op,
                latency=latency,
                latency_offsets=latency_offsets,
                execution_time=execution_time,
            )
            signal_out = Signal(adaptor0.output(0))
            delay = Delay(adaptor0.output(1))
            Signal(delay, adaptor0.input(1))
        else:
            signal_out = Delay(input_op)
    else:
        signal_out = Signal(input_op)

    # Second-order sections
    sos_count = (order - 1) // 2 if odd_order else order // 2
    offset1, offset2 = (1, 2) if odd_order else (0, 1)
    for n in range(sos_count):
        if np_coefficients[2 * n + offset1]:
            adaptor1 = SymmetricTwoportAdaptor(
                np_coefficients[2 * n + offset1],
                signal_out,
                latency=latency,
                latency_offsets=latency_offsets,
                execution_time=execution_time,
            )
            # Signal(prev_adaptor., adaptor1.input(0), name="Previous-stage to next")
            delay1 = Delay(adaptor1.output(1))
        else:
            delay1 = Delay(signal_out)
        if np_coefficients[2 * n + offset2]:
            delay2 = Delay()
            adaptor2 = SymmetricTwoportAdaptor(
                np_coefficients[2 * n + offset2],
                delay1,
                delay2,
                latency=latency,
                latency_offsets=latency_offsets,
                execution_time=execution_time,
            )
            Signal(adaptor2.output(0), adaptor1.input(1))
            Signal(adaptor2.output(1), delay2)
            signal_out = Signal(adaptor1.output(0))
        else:
            delay2 = Delay(delay1)
            if np_coefficients[2 * n + offset1]:
                Signal(delay2, adaptor1.input(1))
                signal_out = Signal(adaptor1.output(0))
            else:
                signal_out = Signal(delay2)
    output <<= signal_out
    return SFG([input_op], [output], name=Name(name))


def direct_form_fir(
    coefficients: Sequence[complex],
    name: Optional[str] = None,
    mult_properties: Optional[Union[Dict[str, int], Dict[str, Dict[str, int]]]] = None,
    add_properties: Optional[Union[Dict[str, int], Dict[str, Dict[str, int]]]] = None,
) -> SFG:
    r"""
    Generate a signal flow graph of a direct form FIR filter.

    The *coefficients* parameter is a sequence of impulse response values::

        coefficients = [h0, h1, h2, ..., hN]

    Leading to the transfer function:

    .. math:: \sum_{i=0}^N h_iz^{-i}

    Parameters
    ----------
    coefficients : 1D-array
        Coefficients to use for the FIR filter section.
    name : Name, optional
        The name of the SFG. If None, "Direct-form FIR filter".
    mult_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.ConstantMultiplication`.
    add_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.Addition`.

    Returns
    -------
    Signal flow graph

    See Also
    --------
    transposed_direct_form_fir
    """
    np_coefficients = np.atleast_1d(np.squeeze(np.asarray(coefficients)))
    taps = len(np_coefficients)
    if not taps:
        raise ValueError("Coefficients cannot be empty")
    if np_coefficients.ndim != 1:
        raise TypeError("coefficients must be a 1D-array")
    if name is None:
        name = "Direct-form FIR filter"
    if mult_properties is None:
        mult_properties = {}
    if add_properties is None:
        add_properties = {}
    input_op = Input()
    output = Output()

    prev_delay = input_op
    prev_add = None
    for i, coefficient in enumerate(np_coefficients):
        tmp_mul = ConstantMultiplication(coefficient, prev_delay, **mult_properties)
        prev_add = (
            tmp_mul
            if prev_add is None
            else Addition(tmp_mul, prev_add, **add_properties)
        )
        if i < taps - 1:
            prev_delay = Delay(prev_delay)

    output <<= prev_add

    return SFG([input_op], [output], name=Name(name))


def transposed_direct_form_fir(
    coefficients: Sequence[complex],
    name: Optional[str] = None,
    mult_properties: Optional[Union[Dict[str, int], Dict[str, Dict[str, int]]]] = None,
    add_properties: Optional[Union[Dict[str, int], Dict[str, Dict[str, int]]]] = None,
) -> SFG:
    r"""
    Generate a signal flow graph of a transposed direct form FIR filter.

    The *coefficients* parameter is a sequence of impulse response values::

        coefficients = [h0, h1, h2, ..., hN]

    Leading to the transfer function:

    .. math:: \sum_{i=0}^N h_iz^{-i}

    Parameters
    ----------
    coefficients : 1D-array
        Coefficients to use for the FIR filter section.
    name : Name, optional
        The name of the SFG. If None, "Transposed direct-form FIR filter".
    mult_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.ConstantMultiplication`.
    add_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.Addition`.

    Returns
    -------
    Signal flow graph

    See Also
    --------
    direct_form_fir
    """
    np_coefficients = np.atleast_1d(np.squeeze(np.asarray(coefficients)))
    taps = len(np_coefficients)
    if not taps:
        raise ValueError("Coefficients cannot be empty")
    if np_coefficients.ndim != 1:
        raise TypeError("coefficients must be a 1D-array")
    if name is None:
        name = "Transposed direct-form FIR filter"
    if mult_properties is None:
        mult_properties = {}
    if add_properties is None:
        add_properties = {}
    input_op = Input()
    output = Output()

    prev_delay = None
    for i, coefficient in enumerate(reversed(np_coefficients)):
        tmp_mul = ConstantMultiplication(coefficient, input_op, **mult_properties)
        tmp_add = (
            tmp_mul
            if prev_delay is None
            else Addition(tmp_mul, prev_delay, **add_properties)
        )
        if i < taps - 1:
            prev_delay = Delay(tmp_add)

    output <<= tmp_add

    return SFG([input_op], [output], name=Name(name))


def direct_form_1_iir(
    b: Sequence[complex],
    a: Sequence[complex],
    name: Optional[str] = None,
    mult_properties: Optional[Union[Dict[str, int], Dict[str, Dict[str, int]]]] = None,
    add_properties: Optional[Union[Dict[str, int], Dict[str, Dict[str, int]]]] = None,
) -> SFG:
    """Generates a direct-form IIR filter of type I with coefficients a and b."""
    if len(a) != len(b):
        raise ValueError("size of coefficient lists a and b are not the same")
    if name is None:
        name = "Direct-form I IIR filter"
    if mult_properties is None:
        mult_properties = {}
    if add_properties is None:
        add_properties = {}

    # construct the feed-forward part
    input_op = Input()
    muls = [ConstantMultiplication(b[0], input_op, **mult_properties)]
    delays = []
    prev_delay = input_op
    for i, coeff in enumerate(b[1:]):
        prev_delay = Delay(prev_delay)
        delays.append(prev_delay)
        if i < len(b) - 1:
            muls.append(ConstantMultiplication(coeff, prev_delay, **mult_properties))

    op_a = muls[-1]
    for i in range(len(muls) - 1):
        op_a = Addition(op_a, muls[-i - 2], **add_properties)

    # construct the feedback part
    tmp_add = Addition(op_a, None, **add_properties)
    muls = []
    output = Output()
    output <<= tmp_add

    delays = []
    prev_delay = tmp_add
    for i, coeff in enumerate(a[1:]):
        prev_delay = Delay(prev_delay)
        delays.append(prev_delay)
        if i < len(a) - 1:
            muls.append(ConstantMultiplication(-coeff, prev_delay, **mult_properties))

    op_a = muls[-1]
    for i in range(len(muls) - 1):
        op_a = Addition(op_a, muls[-i - 2], **add_properties)

    tmp_add.input(1).connect(op_a)

    return SFG([input_op], [output], name=Name(name))


def direct_form_2_iir(
    b: Sequence[complex],
    a: Sequence[complex],
    name: Optional[str] = None,
    mult_properties: Optional[Union[Dict[str, int], Dict[str, Dict[str, int]]]] = None,
    add_properties: Optional[Union[Dict[str, int], Dict[str, Dict[str, int]]]] = None,
) -> SFG:
    """Generates a direct-form IIR filter of type II with coefficients a and b."""
    if len(a) != len(b):
        raise ValueError("size of coefficient lists a and b are not the same")
    if name is None:
        name = "Direct-form II IIR filter"
    if mult_properties is None:
        mult_properties = {}
    if add_properties is None:
        add_properties = {}

    # construct the repeated part of the SFG
    left_adds = []
    right_adds = []
    left_muls = []
    right_muls = []
    delays = [Delay()]
    op_a_left = None
    op_a_right = None
    for i in range(len(a) - 1):
        a_coeff = a[-i - 1]
        b_coeff = b[-i - 1]
        if len(left_muls) != 0:  # not first iteration
            new_delay = Delay()
            delays[-1] <<= new_delay
            delays.append(new_delay)
        left_muls.append(
            ConstantMultiplication(-a_coeff, delays[-1], **mult_properties)
        )
        right_muls.append(
            ConstantMultiplication(b_coeff, delays[-1], **mult_properties)
        )
        if len(left_muls) > 1:  # not first iteration
            left_adds.append(Addition(op_a_left, left_muls[-1], **add_properties))
            right_adds.append(Addition(op_a_right, right_muls[-1], **add_properties))
            op_a_left = left_adds[-1]
            op_a_right = right_adds[-1]
        else:
            op_a_left = left_muls[-1]
            op_a_right = right_muls[-1]

    # finalize the SFG
    input_op = Input()
    if left_adds:
        left_adds.append(Addition(input_op, left_adds[-1], **add_properties))
    else:
        left_adds.append(Addition(input_op, left_muls[-1], **add_properties))
    delays[-1] <<= left_adds[-1]
    mul = ConstantMultiplication(b[0], left_adds[-1], **mult_properties)
    add = Addition(mul, right_adds[-1], **add_properties)
    output = Output()
    output <<= add
    return SFG([input_op], [output], name=Name(name))


def radix_2_dif_fft(points: int) -> SFG:
    """Generates a radix-2 decimation-in-frequency FFT structure.

    Parameters
    ----------
    points : int
        Number of points for the FFT, needs to be a positive power of 2.

    Returns
    -------
    SFG
        Signal Flow Graph
    """
    if points < 0:
        raise ValueError("Points must be positive number.")
    if points & (points - 1) != 0:
        raise ValueError("Points must be a power of two.")

    inputs = []
    for i in range(points):
        inputs.append(Input(name=f"Input: {i}"))

    ports = inputs
    number_of_stages = int(np.log2(points))

    twiddles = _generate_twiddles(points, number_of_stages)

    for stage in range(number_of_stages):
        ports = _construct_dif_fft_stage(
            ports, number_of_stages, stage, twiddles[stage]
        )

    ports = _get_bit_reversed_ports(ports)
    outputs = []
    for i, port in enumerate(ports):
        outputs.append(Output(port, name=f"Output: {i}"))

    return SFG(inputs=inputs, outputs=outputs)


def _construct_dif_fft_stage(
    ports_from_previous_stage: list["OutputPort"],
    number_of_stages: int,
    stage: int,
    twiddles: list[np.complex128],
):
    ports = ports_from_previous_stage.copy()
    number_of_butterflies = len(ports) // 2
    number_of_groups = 2**stage
    group_size = number_of_butterflies // number_of_groups

    for group_index in range(number_of_groups):
        for bf_index in range(group_size):
            input1_index = group_index * 2 * group_size + bf_index
            input2_index = input1_index + group_size

            input1 = ports[input1_index]
            input2 = ports[input2_index]

            butterfly = Butterfly(input1, input2)
            output1, output2 = butterfly.outputs

            twiddle_factor = twiddles[bf_index]
            if twiddle_factor != 1:
                name = _get_formatted_complex_number(twiddle_factor, 2)
                twiddle_mul = ConstantMultiplication(
                    twiddles[bf_index], output2, name=name
                )
                output2 = twiddle_mul.output(0)

            ports[input1_index] = output1
            ports[input2_index] = output2

    return ports


def _get_formatted_complex_number(number: np.complex128, digits: int) -> str:
    real_str = str(np.round(number.real, digits))
    imag_str = str(np.round(number.imag, digits))
    if number.imag == 0:
        return real_str
    elif number.imag > 0:
        return f"{real_str} + j{imag_str}"
    else:
        return f"{real_str} - j{str(-np.round(number.imag, digits))}"


def _get_bit_reversed_number(number: int, number_of_bits: int) -> int:
    reversed_number = 0
    for i in range(number_of_bits):
        # mask out the current bit
        shift_num = number
        current_bit = (shift_num >> i) & 1
        # compute the position of the current bit in the reversed string
        reversed_pos = number_of_bits - 1 - i
        # place the current bit in that position
        reversed_number |= current_bit << reversed_pos
    return reversed_number


def _get_bit_reversed_ports(ports: list["OutputPort"]) -> list["OutputPort"]:
    num_of_ports = len(ports)
    bits = int(np.log2(num_of_ports))
    return [ports[_get_bit_reversed_number(i, bits)] for i in range(num_of_ports)]


def _generate_twiddles(points: int, number_of_stages: int) -> list[np.complex128]:
    twiddles = []
    for stage in range(1, number_of_stages + 1):
        stage_twiddles = []
        for k in range(points // 2 ** (stage)):
            a = 2 ** (stage - 1)
            twiddle = np.exp(-1j * 2 * np.pi * a * k / points)
            stage_twiddles.append(twiddle)
        twiddles.append(stage_twiddles)
    return twiddles
