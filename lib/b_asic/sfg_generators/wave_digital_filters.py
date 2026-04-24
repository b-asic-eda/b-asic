"""
B-ASIC signal flow graph generators.

This module contains a number of functions generating SFGs for wave digital filters.
"""

from collections.abc import Sequence

import numpy as np

from b_asic.core_operations import (
    Name,
)
from b_asic.sfg import SFG
from b_asic.signal import Signal
from b_asic.special_operations import Delay, Input, Output
from b_asic.wdf_operations import SymmetricTwoportAdaptor


def wdf_allpass(
    coefficients: Sequence[float],
    name: str | None = None,
    latency: int | None = None,
    latency_offsets: dict[str, int] | None = None,
    execution_time: int | None = None,
) -> SFG:
    """
    Generate a signal flow graph of a WDF allpass section based on symmetric two-port adaptors.

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
    SFG
        Signal Flow Graph
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
