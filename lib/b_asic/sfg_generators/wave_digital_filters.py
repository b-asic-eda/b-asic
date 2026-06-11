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
    adaptor_names: Sequence[str | None] | str | None = None,
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
    adaptor_names : sequence of str or None, or str, optional
        Names for each adaptor, parallel to ``coefficients``, or a string prefix
        used to generate names as ``f"{adaptor_names}{idx}"`` based on
        coefficient position. Defaults to ``"a0"``, ``"a1"``, ... based on
        coefficient position.

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

    def _aname(idx: int) -> Name:
        if isinstance(adaptor_names, str):
            return Name(f"{adaptor_names}{idx}")
        if adaptor_names is not None:
            n = adaptor_names[idx]
            return Name(n) if n else Name("")
        return Name(f"a{idx}")

    def _tname(idx: int) -> Name:
        aname = str(_aname(idx))
        if not aname:
            return Name(f"T{idx}")
        return Name(f"T{aname[1:]}" if aname.startswith("a") else f"{aname}_T")

    input_op = Input(name=Name("x"))
    output = Output(name=Name("y"))
    odd_order = order % 2
    if odd_order:
        if np_coefficients[0]:
            # First-order section
            adaptor0 = SymmetricTwoportAdaptor(
                np_coefficients[0],
                input_op,
                name=_aname(0),
                latency=latency,
                latency_offsets=latency_offsets,
                execution_time=execution_time,
            )
            signal_out = Signal(adaptor0.output(0))
            delay = Delay(adaptor0.output(1), name=_tname(0))
            Signal(delay, adaptor0.input(1))
        else:
            signal_out = Delay(input_op, name=_tname(0))
    else:
        signal_out = Signal(input_op)

    # Second-order sections
    sos_count = (order - 1) // 2 if odd_order else order // 2
    offset1, offset2 = (1, 2) if odd_order else (0, 1)
    for n in range(sos_count):
        idx1 = 2 * n + offset1
        idx2 = 2 * n + offset2
        if np_coefficients[idx1]:
            adaptor1 = SymmetricTwoportAdaptor(
                np_coefficients[idx1],
                signal_out,
                name=_aname(idx1),
                latency=latency,
                latency_offsets=latency_offsets,
                execution_time=execution_time,
            )
            delay1 = Delay(adaptor1.output(1), name=_tname(idx1))
        else:
            delay1 = Delay(signal_out, name=_tname(idx1))
        if np_coefficients[idx2]:
            delay2 = Delay(name=_tname(idx2))
            adaptor2 = SymmetricTwoportAdaptor(
                np_coefficients[idx2],
                delay1,
                delay2,
                name=_aname(idx2),
                latency=latency,
                latency_offsets=latency_offsets,
                execution_time=execution_time,
            )
            Signal(adaptor2.output(0), adaptor1.input(1))
            Signal(adaptor2.output(1), delay2)
            signal_out = Signal(adaptor1.output(0))
        else:
            delay2 = Delay(delay1, name=_tname(idx2))
            if np_coefficients[idx1]:
                Signal(delay2, adaptor1.input(1))
                signal_out = Signal(adaptor1.output(0))
            else:
                signal_out = Signal(delay2)
    output <<= signal_out
    return SFG([input_op], [output], name=Name(name))


def lattice_wdf(
    coefficients: Sequence[float],
    name: str | None = None,
    only_adaptors: bool = False,
    adaptor_names: Sequence[str | None] | str | None = None,
) -> SFG:
    """
    Generate a signal flow graph of a lattice wave digital filter.

    Parameters
    ----------
    coefficients : 1D-array
        Adaptor coefficients, interleaved between the two allpass branches.
    name : str, optional
        Name of the SFG. Defaults to ``"Lattice WDF"``.
    only_adaptors : bool, optional
        If True, use an adaptor for the final addition and scaling.
    adaptor_names : sequence of str or None, or str, optional
        Names for each adaptor, parallel to ``coefficients``, or a string prefix
        used to generate names as ``f"{adaptor_names}{idx}"`` based on
        coefficient position. Defaults to ``"a0"``, ``"a1"``, ... based on
        coefficient position.

    Returns
    -------
    SFG
        Signal flow graph of the lattice WDF.
    """
    if not len(coefficients):
        raise ValueError("coefficients cannot be empty")

    odd = len(coefficients) % 2
    if odd:
        a_coeffs = [coefficients[0]]
        a_indices = [0]
        rest = coefficients[1:]
        b_coeffs: list[float] = []
        b_indices: list[int] = []
        for i in range(0, len(rest), 2):
            pair = rest[i : i + 2]
            orig = [i + 1, i + 2]
            if (i // 2) % 2 == 0:
                b_coeffs.extend(pair)
                b_indices.extend(orig)
            else:
                a_coeffs.extend(pair)
                a_indices.extend(orig)
    else:
        a_coeffs = []
        a_indices = []
        b_coeffs = []
        b_indices = []
        for i in range(0, len(coefficients), 2):
            pair = coefficients[i : i + 2]
            orig = [i, i + 1]
            if (i // 2) % 2 == 0:
                a_coeffs.extend(pair)
                a_indices.extend(orig)
            else:
                b_coeffs.extend(pair)
                b_indices.extend(orig)

    input_op = Input(name=Name("x"))

    if isinstance(adaptor_names, str):
        names = [f"{adaptor_names}{i}" for i in range(len(coefficients))]
    elif adaptor_names is not None:
        names = list(adaptor_names)
    else:
        names = [f"a{i}" for i in range(len(coefficients))]

    a_names = [names[i] for i in a_indices]
    sec_a = wdf_allpass(a_coeffs, adaptor_names=a_names)
    sec_a <<= input_op
    sig_a = sec_a

    if b_coeffs:
        b_names = [names[i] for i in b_indices]
        sec_b = wdf_allpass(b_coeffs, adaptor_names=b_names)
        sec_b <<= input_op
        sig_b = sec_b
    else:
        sig_b = input_op

    if only_adaptors:
        adaptor = SymmetricTwoportAdaptor(-0.5, sig_a, sig_b)
        output = Output(adaptor.output(0), name=Name("y"))
    else:
        output = Output((sig_a + sig_b) * 0.5, name=Name("y"))

    sfg = SFG([input_op], [output], name=Name(name or "Lattice WDF"))
    return sfg.flatten()
