from b_asic.quantization import OverflowMode, QuantizationMode, quantize


def test_quantization():
    a = 0.3
    assert quantize(a, 4) == 0.25
    assert quantize(a, 4, quantization_mode=QuantizationMode.TRUNCATION) == 0.25
    assert quantize(a, 4, quantization_mode=QuantizationMode.ROUNDING) == 0.3125
    assert (
        quantize(a, 4, quantization_mode=QuantizationMode.MAGNITUDE_TRUNCATION) == 0.25
    )
    assert quantize(a, 4, quantization_mode=QuantizationMode.JAMMING) == 0.3125
    assert (
        quantize(a, 4, quantization_mode=QuantizationMode.UNBIASED_ROUNDING) == 0.3125
    )
    assert quantize(a, 4, quantization_mode=QuantizationMode.UNBIASED_JAMMING) == 0.3125
    assert quantize(-a, 4, quantization_mode=QuantizationMode.TRUNCATION) == -0.3125
    assert quantize(-a, 4, quantization_mode=QuantizationMode.ROUNDING) == -0.3125
    assert (
        quantize(-a, 4, quantization_mode=QuantizationMode.MAGNITUDE_TRUNCATION)
        == -0.25
    )
    assert quantize(-a, 4, quantization_mode=QuantizationMode.JAMMING) == -0.3125
    assert (
        quantize(-a, 4, quantization_mode=QuantizationMode.UNBIASED_ROUNDING) == -0.3125
    )
    assert (
        quantize(-a, 4, quantization_mode=QuantizationMode.UNBIASED_JAMMING) == -0.3125
    )
    assert quantize(complex(a, -a), 4) == complex(0.25, -0.3125)
    assert quantize(
        complex(a, -a), 4, quantization_mode=QuantizationMode.MAGNITUDE_TRUNCATION
    ) == complex(0.25, -0.25)

    assert quantize(1.3, 4) == -0.75
    assert quantize(1.3, 4, overflow_mode=OverflowMode.SATURATION) == 0.9375
    assert quantize(0.97, 4, quantization_mode=QuantizationMode.ROUNDING) == -1.0
    assert (
        quantize(
            0.97,
            4,
            quantization_mode=QuantizationMode.ROUNDING,
            overflow_mode=OverflowMode.SATURATION,
        )
        == 0.9375
    )

    assert quantize(0.3125, 3, quantization_mode=QuantizationMode.ROUNDING) == 0.375
    assert (
        quantize(0.3125, 3, quantization_mode=QuantizationMode.UNBIASED_ROUNDING)
        == 0.25
    )
    assert quantize(0.25, 3, quantization_mode=QuantizationMode.JAMMING) == 0.375
    assert (
        quantize(0.25, 3, quantization_mode=QuantizationMode.UNBIASED_JAMMING) == 0.25
    )
