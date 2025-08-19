from b_asic.code_printer.vhdl.common import is_valid_vhdl_identifier


def test_is_valid_vhdl_identifier():
    identifier_pass = {
        "COUNT",
        "X",
        "c_out",
        "FFT",
        "Decoder",
        "VHSIC",
        "X1",
        "PageCount",
        "STORE_NEXT_ITEM",
        "ValidIdentifier123",
        "valid_identifier",
    }
    identifier_fail = {
        "",
        "architecture",
        "Architecture",
        "ArChItEctUrE",
        "entity",
        "invalid+",
        "invalid}",
        "not-valid",
        "(invalid)",
        "invalid£",
        "1nvalid",
        "_abc",
    }

    for identifier in identifier_pass:
        assert is_valid_vhdl_identifier(identifier)

    for identifier in identifier_fail:
        assert not is_valid_vhdl_identifier(identifier)
