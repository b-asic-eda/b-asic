"""Computation of lattice wave digital filter (LWDF) coefficients."""

from collections.abc import Sequence

import numpy as np


def lattice_coeffs_from_tf(a: Sequence[float]) -> list[float]:
    """
    Compute the coefficients for the symmetric two-port adaptors of a LWDF.

    Parameters
    ----------
    a : Sequence[float]
        Denominator coefficients of the transfer function.

    Returns
    -------
    list[float]
        Coefficients for the symmetric two-port adaptors of a LWDF.

    See Also
    --------
    :func:`~b_asic.sfg_generators.wave_digital_filters.lattice_wdf`
        --Constructs an SFG of a LWDF given the adaptor coefficients.
    """
    np_a = np.atleast_1d(np.asarray(a, dtype=float))
    np_a = np_a / np_a[0]
    poles = np.roots(np_a)
    real_poles = [p for p in poles if abs(p.imag) < 1e-10]
    complex_pairs = [p for p in poles if p.imag > 1e-10]

    def _sec(pole):
        if abs(pole.imag) < 1e-10:
            return [float(pole.real)]
        return [-(abs(pole) ** 2), 2.0 * pole.real / (1.0 + abs(pole) ** 2)]

    a_sections: list = []
    b_sections: list = []
    if real_poles:
        a_sections.append(_sec(real_poles[0]))
        for i, p in enumerate(complex_pairs):
            (b_sections if i % 2 == 0 else a_sections).append(_sec(p))
    else:
        for i, p in enumerate(complex_pairs):
            (a_sections if i % 2 == 0 else b_sections).append(_sec(p))

    coeffs: list = []
    if real_poles:
        coeffs.extend(a_sections[0])
        a_rest = a_sections[1:]
        for i in range(max(len(a_rest), len(b_sections))):
            if i < len(b_sections):
                coeffs.extend(b_sections[i])
            if i < len(a_rest):
                coeffs.extend(a_rest[i])
    else:
        for i in range(max(len(a_sections), len(b_sections))):
            if i < len(a_sections):
                coeffs.extend(a_sections[i])
            if i < len(b_sections):
                coeffs.extend(b_sections[i])
    return coeffs
