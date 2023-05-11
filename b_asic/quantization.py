"""B-ASIC quantization module."""

import math
from enum import Enum

from b_asic.types import Num


class Quantization(Enum):
    """Quantization types."""

    ROUNDING = 1
    "Standard two's complement rounding, i.e, tie rounds towards infinity."

    TRUNCATION = 2
    "Two's complement truncation, i.e., round towards negative infinity."

    MAGNITUDE_TRUNCATION = 3
    "Magnitude truncation, i.e., round towards zero."

    JAMMING = 4
    "Jamming/von Neumann rounding, i.e., set the LSB to one"

    UNBIASED_ROUNDING = 5
    "Unbiased rounding, i.e., tie rounds towards even."


class Overflow(Enum):
    """Overflow types."""

    TWOS_COMPLEMENT = 1
    "Two's complement overflow, i.e., remove the more significant bits."

    SATURATION = 2
    """
    Two's complement saturation, i.e., overflow return the most positive/negative
    number.
    """


def quantize(
    value: Num,
    fractional_bits: int,
    integer_bits: int = 1,
    quantization: Quantization = Quantization.TRUNCATION,
    overflow: Overflow = Overflow.TWOS_COMPLEMENT,
):
    r"""
    Quantize *value* assuming two's complement representation.

    Quantization happens before overflow, so, e.g., rounding may lead to an overflow.

    The total number of bits is *fractional_bits* + *integer_bits*. However, there is
    no check that this will be a positive number. Note that the sign bit is included in
    these bits. If *integer_bits* is not given, then use 1, i.e., the result is between

    .. math::   -1 \leq \text{value} \leq 1-2^{-\text{fractional_bits}}

    If *value* is a complex number, the real and imaginary parts are quantized
    separately.

    Parameters
    ----------
    value : int, float, complex
        The value to be quantized.
    fractional_bits : int
        Number of fractional bits, can be negative.
    integer_bits : int, default: 1
        Number of integer bits, can be negative.
    quantization : :class:`Quantization`, default: :class:`Quantization.TRUNCATION`
        Type of quantization.
    overflow : :class:`Overflow`, default: :class:`Overflow.TWOS_COMPLEMENT`
        Type of overflow.

    Returns
    -------
    int, float, complex
        The quantized value.

    Examples
    --------
    >>> from b_asic.quantization import quantize, Quantization, Overflow
    ...
    ... quantize(0.3, 4)  # Truncate 0.3 using four fractional bits and one integer bit
    0.25
    >>> quantize(0.3, 4, quantization=Quantization.ROUNDING)  # As above, but round
    0.3125
    >>> quantize(1.3, 4)  # Will overflow
    -0.75
    >>> quantize(1.3, 4, 2)  # Use two integer bits
    1.25
    >>> quantize(1.3, 4, overflow=Overflow.SATURATION)  # use saturation
    0.9375
    >>> quantize(0.3, 4, -1)  # Three bits in total, will overflow
    -0.25

    """
    if isinstance(value, complex):
        return complex(
            quantize(
                value.real,
                fractional_bits=fractional_bits,
                integer_bits=integer_bits,
                quantization=quantization,
                overflow=overflow,
            ),
            quantize(
                value.imag,
                fractional_bits=fractional_bits,
                integer_bits=integer_bits,
                quantization=quantization,
                overflow=overflow,
            ),
        )
    b = 2**fractional_bits
    v = b * value
    if quantization is Quantization.TRUNCATION:
        v = math.floor(v)
    elif quantization is Quantization.ROUNDING:
        v = math.floor(v + 0.5)
    elif quantization is Quantization.MAGNITUDE_TRUNCATION:
        if v >= 0:
            v = math.floor(v)
        else:
            v = math.ceil(v)
    elif quantization is Quantization.JAMMING:
        v = math.floor(v) | 1
    else:  # Quantization.UNBIASED_ROUNDING
        v = round(v)

    v = v / b
    i = 2 ** (integer_bits - 1)
    if overflow is Overflow.SATURATION:
        pos_val = i - 1 / b
        neg_val = -i
        v = max(neg_val, min(v, pos_val))
    else:  # Overflow.TWOS_COMPLEMENT
        v = (v + i) % (2 * i) - i

    return v
