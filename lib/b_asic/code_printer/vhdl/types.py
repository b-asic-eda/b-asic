"""
Module for VHDL code generation of a package defining custom types.
"""

from typing import TYPE_CHECKING, TextIO

from b_asic.code_printer.vhdl import common

if TYPE_CHECKING:
    from b_asic.architecture import WordLengths


def package(f: TextIO, wl: "WordLengths") -> None:
    common.b_asic_preamble(f)
    common.ieee_header(f)

    # TODO: Define the correct complex type based on DataType
    common.write(f, 0, "package types is")
    common.write(f, 1, "type complex is record")
    common.write(f, 2, f"re : signed({sum(wl.internal) - 1} downto 0);")
    common.write(f, 2, f"im : signed({sum(wl.internal) - 1} downto 0);")
    common.write(f, 1, "end record;")
    common.write(f, 0, "end types;")
