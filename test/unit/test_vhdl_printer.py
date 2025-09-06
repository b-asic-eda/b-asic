from b_asic.code_printer.vhdl.util import signed_type


def test_signed_type():
    assert signed_type(4) == "signed(3 downto 0)"
