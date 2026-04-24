"""
B-ASIC signal flow graph generators.

This module contains a number of functions generating digital filters.
"""

from collections.abc import Sequence

import numpy as np

from b_asic.core_operations import (
    Addition,
    ConstantMultiplication,
    Name,
)
from b_asic.sfg import SFG
from b_asic.special_operations import Delay, Input, Output


def fir(
    coefficients: Sequence[complex],
    name: str | None = None,
    symmetric: bool = False,
    transposed: bool = False,
    mult_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
    add_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
) -> SFG:
    r"""
    Generate a signal flow graph of an FIR filter.

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
    symmetric : bool, optional
        Whether to generate a symmetric FIR structure.
    transposed : bool, optional
        Whether to generate a transposed FIR structure.
    mult_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.ConstantMultiplication`.
    add_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.Addition`.

    Returns
    -------
    Signal flow graph
    """
    np_coefficients = np.atleast_1d(np.squeeze(np.asarray(coefficients)))
    taps = len(np_coefficients)
    if name is None:
        name = "Direct-form FIR filter"
    if mult_properties is None:
        mult_properties = {}
    if add_properties is None:
        add_properties = {}
    input_op = Input()
    output = Output()

    if symmetric and not transposed:
        # Symmetric Direct Form FIR
        delays = [input_op]
        for _ in range(taps - 1):
            delays.append(Delay(delays[-1]))

        add_layer_1 = [
            Addition(delays[i], delays[-i - 1], **add_properties)
            for i in range(taps // 2)
        ]

        if taps == 1:
            muls = [
                ConstantMultiplication(coefficients[0], input_op, **mult_properties)
            ]
        else:
            muls = [
                ConstantMultiplication(
                    coefficients[i], add_layer_1[i], **mult_properties
                )
                for i in range(taps // 2)
            ]

        previous_op = muls[0]
        add_layer_2 = []
        for i in range(taps // 2 - 1):
            add_layer_2.append(Addition(previous_op, muls[i + 1], **add_properties))
            previous_op = add_layer_2[-1]

        output <<= add_layer_2[-1] if add_layer_2 else muls[0]
    elif transposed and not symmetric:
        # Transposed Direct Form FIR
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
    elif transposed and symmetric:
        # Transposed Symmetric Direct Form FIR
        prev_delay = None
        cmuls = [
            ConstantMultiplication(coef, input_op, **mult_properties)
            for coef in np_coefficients[: (taps + 1) // 2]
        ]
        for i in range(taps):
            tmp_mul = cmuls[i] if i < (taps + 1) // 2 else cmuls[taps - i - 1]
            tmp_add = (
                tmp_mul
                if prev_delay is None
                else Addition(tmp_mul, prev_delay, **add_properties)
            )
            if i < taps - 1:
                prev_delay = Delay(tmp_add)
        output <<= tmp_add
    else:
        # Direct Form FIR
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


def direct_form_1_iir(
    b: Sequence[complex],
    a: Sequence[complex],
    name: str | None = None,
    mult_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
    add_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
) -> SFG:
    """Generate a direct-form IIR filter of type I with coefficients a and b."""
    if len(a) < 2 or len(b) < 2:
        raise ValueError(
            "Size of coefficient lists a and b needs to contain at least 2 element."
        )
    if len(a) != len(b):
        raise ValueError("Size of coefficient lists a and b are not the same.")
    if a[0] != 1:
        raise ValueError("The value of a[0] must be 1.")
    if name is None:
        name = "Direct-form I IIR filter"
    if mult_properties is None:
        mult_properties = {}
    if add_properties is None:
        add_properties = {}

    # construct the feed-forward part
    input_op = Input()
    if b[0] != 1:
        muls = [ConstantMultiplication(b[0], input_op, **mult_properties)]
    else:
        muls = [input_op]
    delays = []
    prev_delay = input_op
    for i, coeff in enumerate(b[1:]):
        prev_delay = Delay(prev_delay)
        delays.append(prev_delay)
        if i < len(b) - 1:
            if coeff != 1:
                muls.append(
                    ConstantMultiplication(coeff, prev_delay, **mult_properties)
                )
            else:
                muls.append(prev_delay)

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
            if -coeff != 1:
                muls.append(
                    ConstantMultiplication(-coeff, prev_delay, **mult_properties)
                )
            else:
                muls.append(prev_delay)

    op_a = muls[-1]
    for i in range(len(muls) - 1):
        op_a = Addition(op_a, muls[-i - 2], **add_properties)

    tmp_add.input(1).connect(op_a)

    return SFG([input_op], [output], name=Name(name))


def direct_form_2_iir(
    b: Sequence[complex],
    a: Sequence[complex],
    name: str | None = None,
    mult_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
    add_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
) -> SFG:
    """Generate a direct-form IIR filter of type II with coefficients a and b."""
    if len(a) < 2 or len(b) < 2:
        raise ValueError(
            "Size of coefficient lists a and b needs to contain at least 2 element."
        )
    if len(a) != len(b):
        raise ValueError("Size of coefficient lists a and b are not the same.")
    if a[0] != 1:
        raise ValueError("The value of a[0] must be 1.")
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

        if -a_coeff != 1:
            left_muls.append(
                ConstantMultiplication(-a_coeff, delays[-1], **mult_properties)
            )
        else:
            left_muls.append(delays[-1])

        if b_coeff != 1:
            right_muls.append(
                ConstantMultiplication(b_coeff, delays[-1], **mult_properties)
            )
        else:
            right_muls.append(delays[-1])

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

    if b[0] == 1:
        mul = left_adds[-1]
    else:
        mul = ConstantMultiplication(b[0], left_adds[-1], **mult_properties)

    if right_adds:
        add = Addition(mul, right_adds[-1], **add_properties)
    else:
        add = Addition(mul, right_muls[-1], **add_properties)
    output = Output()
    output <<= add
    return SFG([input_op], [output], name=Name(name))
