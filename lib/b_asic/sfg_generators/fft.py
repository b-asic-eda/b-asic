"""
B-ASIC signal flow graph generators.

This module contains a number of functions generating FFTs.
"""

from typing import TYPE_CHECKING

import numpy as np

from b_asic.core_operations import (
    ConstantMultiplication,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output

if TYPE_CHECKING:
    from b_asic.port import OutputPort


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

            butterfly = R2Butterfly(input1, input2)
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
