"""B-ASIC quantization module."""

import math
from enum import Enum, auto

from apytypes import OverflowMode as ApyOverflowMode
from apytypes import QuantizationMode as ApyQuantizationMode

from b_asic.types import Num


class QuantizationMode(Enum):
    """Quantization types."""

    ROUNDING = auto()
    """Standard two's complement rounding, i.e, tie rounds towards infinity."""

    TRUNCATION = auto()
    """Two's complement truncation, i.e., round towards negative infinity."""

    MAGNITUDE_TRUNCATION = auto()
    """Magnitude truncation, i.e., round towards zero."""

    JAMMING = auto()
    """Jamming/von Neumann rounding, i.e., set the LSB to one."""

    UNBIASED_ROUNDING = auto()
    """Unbiased rounding, i.e., tie rounds towards even."""

    UNBIASED_JAMMING = auto()
    """Unbiased jamming/von Neumann rounding."""

    def to_apytypes(self) -> ApyQuantizationMode:
        """
        Convert to APyTypes QuantizationMode.

        Returns
        -------
        ApyQuantizationMode
            The corresponding APyTypes quantization mode.

        Raises
        ------
        ValueError
            If the mode has no APyTypes equivalent.
        """
        mapping = {
            QuantizationMode.ROUNDING: ApyQuantizationMode.RND,
            QuantizationMode.TRUNCATION: ApyQuantizationMode.TRN,
            QuantizationMode.MAGNITUDE_TRUNCATION: ApyQuantizationMode.TRN_ZERO,
            QuantizationMode.JAMMING: ApyQuantizationMode.JAM,
            QuantizationMode.UNBIASED_ROUNDING: ApyQuantizationMode.RND_CONV,
            QuantizationMode.UNBIASED_JAMMING: ApyQuantizationMode.JAM_UNBIASED,
        }

        if self not in mapping:
            raise ValueError(f"No APyTypes equivalent for {self}")

        return mapping[self]


class OverflowMode(Enum):
    """Overflow types."""

    WRAPPING = auto()
    """
    Two's complement overflow, i.e., remove the more significant bits.
    """

    SATURATION = auto()
    """
    Two's complement saturation.

    Overflow return the most positive/negative number.
    """

    def to_apytypes(self) -> ApyOverflowMode:
        """
        Convert to APyTypes OverflowMode.

        Returns
        -------
        ApyOverflowMode
            The corresponding APyTypes overflow mode.
        """
        mapping = {
            OverflowMode.WRAPPING: ApyOverflowMode.WRAP,
            OverflowMode.SATURATION: ApyOverflowMode.SAT,
        }
        return mapping[self]


def quantize(
    value: Num,
    fractional_bits: int,
    integer_bits: int = 1,
    quantization_mode: QuantizationMode = QuantizationMode.TRUNCATION,
    overflow_mode: OverflowMode = OverflowMode.WRAPPING,
) -> Num:
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
    quantization_mode : :class:`QuantizationMode`, default: :class:`QuantizationMode.TRUNCATION`
        Type of quantization to use.
    overflow_mode : :class:`OverflowMode`, default: :class:`OverflowMode.WRAPPING`
        Type of overflow to use.

    Returns
    -------
    int, float, complex
        The quantized value.

    Examples
    --------
    >>> from b_asic.quantization import quantize, QuantizationMode, OverflowMode
    ...
    ... quantize(0.3, 4)  # Truncate 0.3 using four fractional bits and one integer bit
    0.25
    >>> quantize(0.3, 4, quantization_mode=QuantizationMode.ROUNDING)  # As above, but round
    0.3125
    >>> quantize(1.3, 4)  # Will overflow
    -0.75
    >>> quantize(1.3, 4, 2)  # Use two integer bits
    1.25
    >>> quantize(1.3, 4, overflow_mode=OverflowMode.SATURATION)  # use saturation
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
                quantization_mode=quantization_mode,
                overflow_mode=overflow_mode,
            ),
            quantize(
                value.imag,
                fractional_bits=fractional_bits,
                integer_bits=integer_bits,
                quantization_mode=quantization_mode,
                overflow_mode=overflow_mode,
            ),
        )
    b = 2**fractional_bits
    v = b * value
    if quantization_mode is QuantizationMode.TRUNCATION:
        v = math.floor(v)
    elif quantization_mode is QuantizationMode.ROUNDING:
        v = math.floor(v + 0.5)
    elif quantization_mode is QuantizationMode.MAGNITUDE_TRUNCATION:
        v = math.floor(v) if v >= 0 else math.ceil(v)
    elif quantization_mode is QuantizationMode.JAMMING:
        v = math.floor(v) | 1
    elif quantization_mode is QuantizationMode.UNBIASED_ROUNDING:
        v = round(v)
    elif quantization_mode is QuantizationMode.UNBIASED_JAMMING:
        f = math.floor(v)
        v = f if v - f == 0 else f | 1
    else:
        raise TypeError("Unknown quantization method: {quantization!r}")

    v = v / b
    i = 2 ** (integer_bits - 1)
    if overflow_mode is OverflowMode.SATURATION:
        pos_val = i - 1 / b
        neg_val = -i
        v = max(neg_val, min(v, pos_val))
    else:  # OverflowMode.WRAPPING
        v = (v + i) % (2 * i) - i

    return v
