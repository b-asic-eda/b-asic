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
from b_asic.utility_operations import Sink
from b_asic.wdf_operations import SymmetricTwoportAdaptor


def richards(
    coefficients: float | Sequence[float],
    name: str | None = None,
    latency: int | None = None,
    latency_offsets: dict[str, int] | None = None,
    execution_time: int | None = None,
    adaptor_names: Sequence[str | None] | str | None = None,
) -> SFG:
    """
    Generate a Richards structure using symmetric two-port adaptors.

    Zero-valued adaptors are simplified using constant propagation.

    Parameters
    ----------
    coefficients : float or 1D-array
        Adaptor coefficients, from the outermost to the innermost adaptor.
        A scalar generates a first-order section.
        For two coefficients ``[a, b]``, the denominator in powers of
        ``z**-1`` is ``[1, b * (a - 1), -a]`` and the numerator is its
        reverse. For one coefficient ``a``, the denominator is ``[1, -a]``.
        Each additional coefficient nests another adaptor behind the previous
        adaptor's delay, increasing the order by one.
    name : :data:`~b_asic.types.Name`, optional
        The name of the SFG. If None, "Richards structure".
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
    :class:`~b_asic.sfg.SFG`
        Signal Flow Graph
    """
    np_coefficients = np.atleast_1d(np.squeeze(np.asarray(coefficients)))
    order = len(np_coefficients)
    if not order:
        raise ValueError("Coefficients cannot be empty")
    if np_coefficients.ndim != 1:
        raise TypeError("coefficients must be a 1D-array")
    if name is None:
        name = "Richards structure"

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
    adaptors = []
    source = input_op
    for idx, coefficient in enumerate(np_coefficients):
        adaptor = SymmetricTwoportAdaptor(
            coefficient,
            source,
            name=_aname(idx),
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
        )
        if adaptors:
            Signal(adaptor.output(0), adaptors[-1].input(1))
        source = Delay(adaptor.output(1), name=_tname(idx))
        adaptors.append(adaptor)
    Signal(source, adaptors[-1].input(1))
    output = Output(adaptors[0].output(0), name=Name("y"))
    return SFG([input_op], [output], name=Name(name)).constant_propagation()


def wdf_allpass(
    coefficients: float | Sequence[float],
    name: str | None = None,
    latency: int | None = None,
    latency_offsets: dict[str, int] | None = None,
    execution_time: int | None = None,
    adaptor_names: Sequence[str | None] | str | None = None,
) -> SFG:
    """
    Generate a WDF allpass filter as a cascade of Richards structures.

    An odd-order filter starts with a first-order section, followed by
    second-order sections. Adaptors with zero coefficients are simplified.

    Parameters
    ----------
    coefficients : float or 1D-array
        Adaptor coefficients, grouped into consecutive sections.
    name : str, optional
        Name of the SFG. Defaults to ``"WDF allpass section"``.
    latency : int, optional
        Latency of the symmetric two-port adaptors.
    latency_offsets : dict, optional
        Latency offsets of the symmetric two-port adaptors.
    execution_time : int, optional
        Execution time of the symmetric two-port adaptors.
    adaptor_names : sequence of str or None, or str, optional
        Names parallel to ``coefficients``, or a prefix used to generate names
        based on coefficient position. Defaults to ``"a0"``, ``"a1"``, ...

    Returns
    -------
    :class:`~b_asic.sfg.SFG`
        Flat signal flow graph of the allpass filter.

    See Also
    --------
    richards : Generate a single Richards structure of arbitrary order.
    """
    np_coefficients = np.atleast_1d(np.squeeze(np.asarray(coefficients)))
    if not len(np_coefficients):
        raise ValueError("Coefficients cannot be empty")
    if np_coefficients.ndim != 1:
        raise TypeError("coefficients must be a 1D-array")

    if isinstance(adaptor_names, str):
        names = [f"{adaptor_names}{i}" for i in range(len(np_coefficients))]
    elif adaptor_names is not None:
        names = list(adaptor_names)
    else:
        names = [f"a{i}" for i in range(len(np_coefficients))]

    input_op = Input(name=Name("x"))
    signal_out = input_op
    start = 0
    while start < len(np_coefficients):
        stop = start + (1 if start == 0 and len(np_coefficients) % 2 else 2)
        section = richards(
            np_coefficients[start:stop],
            latency=latency,
            latency_offsets=latency_offsets,
            execution_time=execution_time,
            adaptor_names=names[start:stop],
        )
        unnamed_delays = {
            f"T{i}": Name(f"T{start + i}")
            for i, adaptor_name in enumerate(names[start:stop])
            if not adaptor_name
        }
        for delay in section.find_by_type(Delay):
            if delay.name in unnamed_delays:
                delay.name = unnamed_delays[delay.name]
        section <<= signal_out
        signal_out = section
        start = stop

    output = Output(signal_out, name=Name("y"))
    return SFG(
        [input_op],
        [output],
        name=Name("WDF allpass section" if name is None else name),
    ).flatten()


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
    :class:`~b_asic.sfg.SFG`
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
        Sink().input(0).connect(adaptor.output(1))
    else:
        output = Output((sig_a + sig_b) * 0.5, name=Name("y"))

    sfg = SFG([input_op], [output], name=Name(name or "Lattice WDF"))
    return sfg.flatten()
