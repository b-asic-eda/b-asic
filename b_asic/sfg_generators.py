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
from b_asic.signal import Signal
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Delay, Input, Output


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
        Coefficients to use for the allpass section

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
    output << signal_out
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
        Coefficients to use for the FIR filter section
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
    for i, coeff in enumerate(np_coefficients):
        tmp_mul = ConstantMultiplication(coeff, prev_delay, **mult_properties)
        prev_add = (
            tmp_mul
            if prev_add is None
            else Addition(tmp_mul, prev_add, **add_properties)
        )
        if i < taps - 1:
            prev_delay = Delay(prev_delay)

    output << prev_add

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
        Coefficients to use for the FIR filter section
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
    for i, coeff in enumerate(reversed(np_coefficients)):
        tmp_mul = ConstantMultiplication(coeff, input_op, **mult_properties)
        tmp_add = (
            tmp_mul
            if prev_delay is None
            else Addition(tmp_mul, prev_delay, **add_properties)
        )
        if i < taps - 1:
            prev_delay = Delay(tmp_add)

    output << tmp_add

    return SFG([input_op], [output], name=Name(name))
