"""
B-ASIC signal flow graph generators.

This module contains a number of functions generating SFGs for specific functions.
"""
from typing import Dict, Optional, Sequence, Union

import numpy as np

from b_asic.core_operations import Name, SymmetricTwoportAdaptor
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
    Generate a signal flow graph of a WDF allpass section based on symmetric two-port adaptors.

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
    np.asarray(coefficients)
    coefficients = np.squeeze(coefficients)
    if coefficients.ndim != 1:
        raise TypeError("coefficients must be a 1D-array")
    if input_op is None:
        input_op = Input()
    if output is None:
        output = Output()
    if name is None:
        name = "WDF allpass section"
    order = len(coefficients)
    odd_order = order % 2
    if odd_order:
        # First-order section
        coeff = coefficients[0]
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
            coefficients[2 * n + offset1],
            signal_out,
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        # Signal(prev_adaptor., adaptor1.input(0), name="Previous-stage to next")
        delay1 = Delay(adaptor1.output(1))
        delay2 = Delay()
        adaptor2 = SymmetricTwoportAdaptor(
            coefficients[2 * n + offset2],
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
