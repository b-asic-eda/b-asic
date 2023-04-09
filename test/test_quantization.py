from b_asic.quantization import Overflow, Quantization, quantize


def test_quantization():
    a = 0.3
    assert quantize(a, 4) == 0.25
    assert quantize(a, 4, quantization=Quantization.TRUNCATION) == 0.25
    assert quantize(a, 4, quantization=Quantization.ROUNDING) == 0.3125
    assert quantize(a, 4, quantization=Quantization.MAGNITUDE_TRUNCATION) == 0.25
    assert quantize(a, 4, quantization=Quantization.JAMMING) == 0.3125
    assert quantize(-a, 4, quantization=Quantization.TRUNCATION) == -0.3125
    assert quantize(-a, 4, quantization=Quantization.ROUNDING) == -0.3125
    assert quantize(-a, 4, quantization=Quantization.MAGNITUDE_TRUNCATION) == -0.25
    assert quantize(-a, 4, quantization=Quantization.JAMMING) == -0.3125
    assert quantize(complex(a, -a), 4) == complex(0.25, -0.3125)
    assert quantize(
        complex(a, -a), 4, quantization=Quantization.MAGNITUDE_TRUNCATION
    ) == complex(0.25, -0.25)

    assert quantize(1.3, 4) == -0.75
    assert quantize(1.3, 4, overflow=Overflow.SATURATION) == 0.9375
    assert quantize(0.97, 4, quantization=Quantization.ROUNDING) == -1.0
    assert (
        quantize(
            0.97, 4, quantization=Quantization.ROUNDING, overflow=Overflow.SATURATION
        )
        == 0.9375
    )
