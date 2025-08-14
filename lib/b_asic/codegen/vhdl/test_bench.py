"""
Module for VHDL code generation of test benches.
"""

from typing import TYPE_CHECKING, TextIO

from b_asic.codegen.vhdl import common
from b_asic.special_operations import Input, Output

if TYPE_CHECKING:
    from b_asic.architecture import Architecture, WordLengths


def entity(f: TextIO, arch: "Architecture") -> None:
    common.entity_declaration(f, f"{arch.entity_name}_tb")


def architecture(f: TextIO, arch: "Architecture", wl: "WordLengths") -> None:
    common.write(f, 0, f"architecture tb of {arch.entity_name}_tb is", end="\n")

    arch.write_component_declaration(f, wl)
    _write_constant_generation(f, arch, wl)
    _write_signal_generation(f, arch)
    common.write(f, 0, "begin", end="\n")

    arch.write_component_instantiation(f)
    _write_clock_generation(f)
    _write_stimulus_generation(f)
    common.write(f, 0, "end architecture tb;", start="", end="\n\n")


def _write_constant_generation(
    f: TextIO, arch: "Architecture", wl: "WordLengths"
) -> None:
    common.write(f, 1, "-- Constant declaration", start="\n")
    common.constant_declaration(f, "CLK_PERIOD", "time", "2 ns")
    common.constant_declaration(f, "WL_INPUT", "integer", f"{wl.input}")
    common.constant_declaration(f, "WL_INTERNAL", "integer", f"{wl.internal}")
    common.constant_declaration(f, "WL_OUTPUT", "integer", f"{wl.output}")
    common.constant_declaration(
        f, "WL_STATE", "integer", f"{arch.schedule_time.bit_length()}"
    )


def _write_signal_generation(f: TextIO, arch: "Architecture") -> None:
    common.write(f, 1, "-- Signal declaration", start="\n")
    common.signal_declaration(f, "tb_clk", "std_logic", "'0'")
    common.signal_declaration(f, "tb_rst", "std_logic", "'0'")
    inputs = [pe for pe in arch.processing_elements if pe.operation_type == Input]
    for pe in inputs:
        common.signal_declaration(
            f,
            f"tb_{pe.entity_name}_0_in",
            "signed(WL_INPUT_INT+WL_INPUT_FRAC-1 downto 0)",
            "(others => '0')",
        )
    outputs = [pe for pe in arch.processing_elements if pe.operation_type == Output]
    for pe in outputs:
        common.signal_declaration(
            f,
            f"tb_{pe.entity_name}_0_out",
            "std_logic_vector(WL_OUTPUT_INT+WL_OUTPUT_FRAC-1 downto 0)",
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
