"""
B-ASIC signal flow graph generators.

This module contains a number of functions generating SFGs for specific functions.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

from b_asic.core_operations import (
    MAD,
    MADS,
    Addition,
    Butterfly,
    ConstantMultiplication,
    DontCare,
    Name,
    Reciprocal,
    SymmetricTwoportAdaptor,
)
from b_asic.signal import Signal
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Delay, Input, Output

if TYPE_CHECKING:
    from b_asic.port import OutputPort


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


def direct_form_fir(
    coefficients: Sequence[complex],
    name: str | None = None,
    mult_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
    add_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
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
    transposed_direct_form_fir, symmetric_fir
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
    name: str | None = None,
    mult_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
    add_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
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
    direct_form_fir, symmetric_fir
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


def symmetric_fir(
    coefficients: Sequence[complex],
    name: str | None = None,
    mult_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
    add_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
) -> SFG:
    r"""
    Generate a signal flow graph of a symmetric FIR filter.

    The *coefficients* parameter is a sequence of impulse response values of even length::

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
    direct_form_fir, transposed_direct_form_fir
    """
    np_coefficients = np.atleast_1d(np.squeeze(np.asarray(coefficients)))
    taps = len(np_coefficients)
    if not taps:
        raise ValueError("Coefficients cannot be empty")
    if taps > 1 and taps % 2 != 0:
        raise ValueError("Coefficients must be of even length")
    if np_coefficients.ndim != 1:
        raise TypeError("coefficients must be a 1D-array")
    if name is None:
        name = "Symmetric FIR filter"
    if mult_properties is None:
        mult_properties = {}
    if add_properties is None:
        add_properties = {}
    input_op = Input()
    output = Output()

    delays = [input_op]
    for _ in range(taps - 1):
        delays.append(Delay(delays[-1]))

    add_layer_1 = [
        Addition(delays[i], delays[-i - 1], **add_properties) for i in range(taps // 2)
    ]

    if taps == 1:
        muls = [ConstantMultiplication(coefficients[0], input_op, **mult_properties)]
    else:
        muls = [
            ConstantMultiplication(coefficients[i], add_layer_1[i], **mult_properties)
            for i in range(taps // 2)
        ]

    previous_op = muls[0]
    add_layer_2 = []
    for i in range(taps // 2 - 1):
        add_layer_2.append(Addition(previous_op, muls[i + 1], **add_properties))
        previous_op = add_layer_2[-1]

    output <<= add_layer_2[-1] if add_layer_2 else muls[0]

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


def radix_2_dif_fft(points: int) -> SFG:
    """
    Generate a radix-2 decimation-in-frequency FFT structure.

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

    inputs = [Input() for _ in range(points)]

    ports = inputs
    number_of_stages = int(np.log2(points))

    twiddles = _generate_twiddles(points, number_of_stages)

    for stage in range(number_of_stages):
        ports = _construct_dif_fft_stage(ports, stage, twiddles[stage])

    ports = _get_bit_reversed_ports(ports)
    outputs = [Output(port) for port in ports]

    return SFG(inputs=inputs, outputs=outputs)


def ldlt_matrix_inverse(
    N: int,
    name: str | None = None,
    mads_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
    reciprocal_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
) -> SFG:
    """
    Generate an SFG for the LDLT matrix inverse algorithm.

    Parameters
    ----------
    N : int
        Dimension of the square input matrix.
    name : Name, optional
        The name of the SFG. If None, "LDLT matrix-inversion".
    mads_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.MADS`.
    reciprocal_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.Reciprocal`.

    Returns
    -------
    SFG
        Signal Flow Graph
    """
    if name is None:
        name = "LDLT matrix-inversion"
    if mads_properties is None:
        mads_properties = {}
    if reciprocal_properties is None:
        reciprocal_properties = {}

    inputs = []
    A = [[None for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(i, N):
            in_op = Input()
            A[i][j] = in_op
            inputs.append(in_op)

    D = [None for _ in range(N)]
    for i in range(N):
        D[i] = A[i][i]

    D_inv = [None for _ in range(N)]

    R = [[None for _ in range(N)] for _ in range(N)]
    M = [[None for _ in range(N)] for _ in range(N)]

    # R*di*R^T factorization
    for i in range(N):
        for k in range(i):
            D[i] = MADS(
                is_add=False,
                src0=D[i],
                src1=M[k][i],
                src2=R[k][i],
                do_addsub=True,
                **mads_properties,
            )

        D_inv[i] = Reciprocal(D[i], **reciprocal_properties)

        for j in range(i + 1, N):
            R[i][j] = A[i][j]

            for k in range(i):
                R[i][j] = MADS(
                    is_add=False,
                    src0=R[i][j],
                    src1=M[k][i],
                    src2=R[k][j],
                    do_addsub=True,
                    **mads_properties,
                )

            # if is_complex:
            #     M[i][j] = ComplexConjugate(R[i][j])
            # else:
            M[i][j] = R[i][j]

            R[i][j] = MADS(
                is_add=True,
                src0=DontCare(),
                src1=R[i][j],
                src2=D_inv[i],
                do_addsub=False,
                **mads_properties,
            )

    # back substitution
    A_inv = [[None for _ in range(N)] for _ in range(N)]
    for i in reversed(range(N)):
        A_inv[i][i] = D_inv[i]
        for j in reversed(range(i + 1)):
            for k in reversed(range(j + 1, N)):
                if k == N - 1 and i != j:
                    A_inv[j][i] = MADS(
                        is_add=False,
                        src0=DontCare(),
                        src1=R[j][k],
                        src2=A_inv[i][k],
                        do_addsub=True,
                        **mads_properties,
                    )
                else:
                    if A_inv[i][k]:
                        A_inv[j][i] = MADS(
                            is_add=False,
                            src0=A_inv[j][i],
                            src1=R[j][k],
                            src2=A_inv[i][k],
                            do_addsub=True,
                            **mads_properties,
                        )
                    else:
                        A_inv[j][i] = MADS(
                            is_add=False,
                            src0=A_inv[j][i],
                            src1=R[j][k],
                            src2=A_inv[k][i],
                            do_addsub=True,
                            **mads_properties,
                        )

    outputs = []
    for i in range(N):
        for j in range(i, N):
            outputs.append(Output(A_inv[i][j]))

    return SFG(inputs, outputs)


def matrix_multiplication(
    m: int,
    n: int,
    p: int,
    name: str | None = None,
    mad_properties: dict[str, int] | dict[str, dict[str, int]] | None = None,
) -> SFG:
    r"""
    Generate a structure for the multiplication of matrices A and B.
    Where A is of size :math:`m \times n` and B :math:`n \times p`.

    Parameters
    ----------
    m : int
        Number of rows in A.
    n : int
        Number of columns in A (and rows in B).
    p : int
        Number of columns in B.
    name : Name, optional
        The name of the SFG. If None, "Matrix-multiplication".
    mad_properties : dictionary, optional
        Properties passed to :class:`~b_asic.core_operations.MAD`.

    Returns
    -------
    SFG
        Signal Flow Graph
    """
    if name is None:
        name = "Matrix-multiplication"
    if mad_properties is None:
        mad_properties = {}

    A = [[Input(f"A[{i},{j}]") for i in range(n)] for j in range(m)]
    B = [[Input(f"B[{i},{j}]") for i in range(p)] for j in range(n)]

    C = []
    for i in range(m):
        for j in range(p):
            tmp = DontCare()
            for k in range(n):
                tmp = MAD(A[i][k], B[k][j], tmp, do_add=(k != 0), **mad_properties)
            C.append(Output(tmp, f"C[{i},{j}]"))

    inputs = [elem for row in A for elem in row] + [elem for row in B for elem in row]
    outputs = C

    return SFG(inputs, outputs, name=name)


def _construct_dif_fft_stage(
    ports_from_previous_stage: list["OutputPort"],
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
                twiddle_mul = ConstantMultiplication(twiddles[bf_index], output2)
                output2 = twiddle_mul.output(0)

            ports[input1_index] = output1
            ports[input2_index] = output2

    return ports


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
