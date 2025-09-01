"""
Module for VHDL code generation of test benches.
"""

from typing import TYPE_CHECKING, TextIO

from b_asic.code_printer.vhdl import common
from b_asic.data_type import VhdlDataType
from b_asic.special_operations import Input, Output

if TYPE_CHECKING:
    from b_asic.architecture import Architecture


def entity(f: TextIO, arch: "Architecture") -> None:
    common.entity_declaration(f, f"{arch.entity_name}_tb")


def architecture(f: TextIO, arch: "Architecture", dt: VhdlDataType) -> None:
    common.write(f, 0, f"architecture tb of {arch.entity_name}_tb is")

    arch.write_component_declaration(f, dt)
    common.constant_declaration(f, "CLK_PERIOD", "time", "2 ns")
    _write_signal_generation(f, arch, dt)
    common.write(f, 0, "begin")

    arch.write_component_instantiation(f, dt)
    _write_clock_generation(f)
    _write_stimulus_generation(f)
    common.write(f, 0, "end architecture tb;", start="", end="\n\n")


def _write_signal_generation(f: TextIO, arch: "Architecture", dt: VhdlDataType) -> None:
    common.signal_declaration(f, "tb_clk", "std_logic", "'0'")
    common.signal_declaration(f, "tb_rst", "std_logic", "'0'")
    inputs = [pe for pe in arch.processing_elements if pe.operation_type == Input]
    for pe in inputs:
        if dt.is_complex:
            common.signal_declaration(
                f,
                f"tb_{pe.entity_name}_0_in_re",
                dt.get_input_type_str(),
                "(others => '0')",
            )
            common.signal_declaration(
                f,
                f"tb_{pe.entity_name}_0_in_im",
                dt.get_input_type_str(),
                "(others => '0')",
            )
        else:
            common.signal_declaration(
                f,
                f"tb_{pe.entity_name}_0_in",
                dt.get_input_type_str(),
                "(others => '0')",
            )
    outputs = [pe for pe in arch.processing_elements if pe.operation_type == Output]
    for pe in outputs:
        if dt.is_complex:
            common.signal_declaration(
                f,
                f"tb_{pe.entity_name}_0_out_re",
                dt.get_input_type_str(),
                "(others => '0')",
            )
            common.signal_declaration(
                f,
                f"tb_{pe.entity_name}_0_out_im",
                dt.get_input_type_str(),
                "(others => '0')",
            )
        else:
            common.signal_declaration(
                f,
                f"tb_{pe.entity_name}_0_out",
                dt.get_input_type_str(),
                "(others => '0')",
            )


def _write_clock_generation(f: TextIO) -> None:
    common.write(f, 1, "-- Clock generation", start="\n")
    common.write_lines(
        f,
        [
            (1, "CLK_GEN : process"),
            (1, "begin"),
            (2, "tb_clk <= '0';"),
            (2, "wait for CLK_PERIOD / 2;"),
            (2, "tb_clk <= '1';"),
            (2, "wait for CLK_PERIOD / 2;"),
            (1, "end process CLK_GEN;"),
        ],
    )


def _write_stimulus_generation(f: TextIO) -> None:
    common.write(f, 1, "-- Stimulus generation", start="\n")
    common.write_lines(
        f,
        [
            (1, "process"),
            (1, "begin"),
            (2, "-- WRITE CODE HERE"),
            (1, "end process;"),
        ],
    )
