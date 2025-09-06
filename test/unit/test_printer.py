from b_asic.code_printer.util import bin_str


def test_bin_str():
    assert bin_str(3, 4) == "0011"

    assert bin_str(-3, 4) == "1101"
