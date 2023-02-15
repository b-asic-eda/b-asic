"""
B-ASIC signal flow graph generators.

This module contains a number of functions generating SFGs for specific functions.
"""
from typing import Dict, Optional, Sequence, Union

import numpy as np

from b_asic.core_operations import (
    Addition,
    ConstantMultiplication,
    Name,
    SymmetricTwoportAdaptor,
)
from b_asic.port import InputPort, OutputPort
from b_asic.signal import Signal
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Delay, Input, Output


def wdf_allpass(
    coefficients: Sequence[float],
    input_op: Optional[Union[Input, Signal, InputPort]] = None,
    output: Optional[Union[Output, Signal, OutputPort]] = None,
    name: Optional[str] = None,
    latency: Optional[int] = None,
    latency_offsets: Optional[Dict[str, int]] = None,
    execution_time: Optional[int] = None,
) -> SFG:
    """
    Generate a signal flow graph of a WDF allpass section based on symmetric two-port
    adaptors.

    Parameters
    ----------
    coefficients : 1D-array
        Coefficients to use for the allpass section

    input_op : Input, optional
        The Input to connect the SFG to. If not provided, one will be generated.

    output : Output, optional
        The Output to connect the SFG to. If not provided, one will be generated.

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
    np_coefficients = np.squeeze(np.asarray(coefficients))
    if np_coefficients.ndim != 1:
        raise TypeError("coefficients must be a 1D-array")
    if input_op is None:
        input_op = Input()
    if output is None:
        output = Output()
    if name is None:
        name = "WDF allpass section"
    order = len(np_coefficients)
    odd_order = order % 2
    if odd_order:
        # First-order section
        coeff = np_coefficients[0]
        adaptor0 = SymmetricTwoportAdaptor(
            coeff,
            input_op,
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        signal_out = Signal(adaptor0.output(0))
        delay = Delay(adaptor0.output(1))
        Signal(delay, adaptor0.input(1))
    else:
        signal_out = Signal(input_op)

    # Second-order sections
    sos_count = (order - 1) // 2 if odd_order else order // 2
    offset1, offset2 = (1, 2) if odd_order else (0, 1)
    for n in range(sos_count):
        adaptor1 = SymmetricTwoportAdaptor(
            np_coefficients[2 * n + offset1],
            signal_out,
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        # Signal(prev_adaptor., adaptor1.input(0), name="Previous-stage to next")
        delay1 = Delay(adaptor1.output(1))
        delay2 = Delay()
        adaptor2 = SymmetricTwoportAdaptor(
            np_coefficients[2 * n + offset2],
            delay1,
            delay2,
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        Signal(adaptor2.output(1), adaptor1.input(1))
        Signal(adaptor2.output(0), delay2)
        signal_out = Signal(adaptor1.output(0))

    output << signal_out
    return SFG([input_op], [output], name=Name(name))


def direct_form_fir(
    coefficients: Sequence[complex],
    input_op: Optional[Union[Input, Signal, InputPort]] = None,
    output: Optional[Union[Output, Signal, OutputPort]] = None,
    name: Optional[str] = None,
    mult_properties: Optional[
        Union[Dict[str, int], Dict[str, Dict[str, int]]]
    ] = None,
    add_properties: Optional[
        Union[Dict[str, int], Dict[str, Dict[str, int]]]
    ] = None,
):
    r"""
    Generate a signal flow graph of a direct form FIR filter. The *coefficients* parameter is a
    sequence of impulse response values::

        coefficients = [h0, h1, h2, ..., hN]

    Leading to the transfer function:

    .. math:: \sum_{i=0}^N h_iz^{-i}

    Parameters
    ----------
    coefficients : 1D-array
        Coefficients to use for the FIR filter section

    input_op : Input, optional
        The Input to connect the SFG to. If not provided, one will be generated.

    output : Output, optional
        The Output to connect the SFG to. If not provided, one will be generated.

    name : Name, optional
        The name of the SFG. If None, "WDF allpass section".

    mult_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.ConstantMultiplication`.

    add_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.Addition`.

    Returns
    -------
        Signal flow graph

    See also
    --------
    transposed_direct_form_fir
    """
    np_coefficients = np.squeeze(np.asarray(coefficients))
    if np_coefficients.ndim != 1:
        raise TypeError("coefficients must be a 1D-array")
    if input_op is None:
        input_op = Input()
    if output is None:
        output = Output()
    if name is None:
        name = "Direct-form FIR filter"
    if mult_properties is None:
        mult_properties = {}
    if add_properties is None:
        add_properties = {}

    taps = len(np_coefficients)
    prev_delay = input_op
    prev_add = None
    for i, coeff in enumerate(np_coefficients):
        tmp_mul = ConstantMultiplication(coeff, prev_delay, **mult_properties)
        if prev_add is None:
            prev_add = tmp_mul
        else:
            prev_add = Addition(tmp_mul, prev_add, **add_properties)
        if i < taps - 1:
            prev_delay = Delay(prev_delay)

    output << prev_add

    return SFG([input_op], [output], name=Name(name))


def transposed_direct_form_fir(
    coefficients: Sequence[complex],
    input_op: Optional[Union[Input, Signal, InputPort]] = None,
    output: Optional[Union[Output, Signal, OutputPort]] = None,
    name: Optional[str] = None,
    mult_properties: Optional[
        Union[Dict[str, int], Dict[str, Dict[str, int]]]
    ] = None,
    add_properties: Optional[
        Union[Dict[str, int], Dict[str, Dict[str, int]]]
    ] = None,
):
    r"""
    Generate a signal flow graph of a transposed direct form FIR filter. The *coefficients* parameter is a
    sequence of impulse response values::

        coefficients = [h0, h1, h2, ..., hN]

    Leading to the transfer function:

    .. math:: \sum_{i=0}^N h_iz^{-i}

    Parameters
    ----------
    coefficients : 1D-array
        Coefficients to use for the FIR filter section

    input_op : Input, optional
        The Input to connect the SFG to. If not provided, one will be generated.

    output : Output, optional
        The Output to connect the SFG to. If not provided, one will be generated.

    name : Name, optional
        The name of the SFG. If None, "WDF allpass section".

    mult_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.ConstantMultiplication`.

    add_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.Addition`.

    Returns
    -------
        Signal flow graph

    See also
    --------
    direct_form_fir
    """
    np_coefficients = np.squeeze(np.asarray(coefficients))
    if np_coefficients.ndim != 1:
        raise TypeError("coefficients must be a 1D-array")
    if input_op is None:
        input_op = Input()
    if output is None:
        output = Output()
    if name is None:
        name = "Transposed direct-form FIR filter"
    if mult_properties is None:
        mult_properties = {}
    if add_properties is None:
        add_properties = {}

    taps = len(np_coefficients)
    prev_delay = None
    prev_add = None
    for i, coeff in enumerate(reversed(np_coefficients)):
        tmp_mul = ConstantMultiplication(coeff, input_op, **mult_properties)
        if prev_delay is None:
            tmp_add = tmp_mul
        else:
            tmp_add = Addition(tmp_mul, prev_delay, **add_properties)
        if i < taps - 1:
            prev_delay = Delay(tmp_add)

    output << tmp_add

    return SFG([input_op], [output], name=Name(name))