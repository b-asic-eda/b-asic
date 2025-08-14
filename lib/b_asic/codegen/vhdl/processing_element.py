"""
Module for VHDL code generation of processing elements.
"""

from typing import TYPE_CHECKING, TextIO

from b_asic.codegen.vhdl import common
from b_asic.process import OperatorProcess
from b_asic.special_operations import Input, Output

if TYPE_CHECKING:
    from b_asic.architecture import ProcessingElement, WordLengths


def entity(f: TextIO, pe: "ProcessingElement", wl: "WordLengths") -> None:
    if not all(isinstance(process, OperatorProcess) for process in pe.collection):
        raise ValueError(
            "HDL can only be generated for ProcessCollection of OperatorProcesses"
        )

    generics = ["WL_INTERNAL_INT : integer", "WL_INTERNAL_FRAC : integer"]
    ports = [
        "clk : in std_logic",
        f"schedule_cnt : in unsigned({wl.state - 1} downto 0)",
    ]
    ports += [
        f"p_{input_port}_in : in signed(WL_INTERNAL_INT+WL_INTERNAL_FRAC-1 downto 0)"
        for input_port in range(pe.input_count)
    ]
    if pe.operation_type == Input:
        ports += ["p_0_in : in std_logic_vector(WL_INPUT_INT+WL_INPUT_FRAC-1 downto 0)"]
        generics += ["WL_INPUT_INT : integer", "WL_INPUT_FRAC : integer"]

    ports += [
        f"p_{output_port}_out : out signed(WL_INTERNAL_INT+WL_INTERNAL_FRAC-1 downto 0)"
        for output_port in range(pe.output_count)
    ]
    if pe.operation_type == Output:
        ports += [
            "p_0_out : out std_logic_vector(WL_OUTPUT_INT+WL_OUTPUT_FRAC-1 downto 0)"
        ]
        generics += ["WL_OUTPUT_INT : integer", "WL_OUTPUT_FRAC : integer"]

    common.entity_declaration(f, pe.entity_name, generics, ports)


def architecture(f: TextIO, pe: "ProcessingElement", write_pe_archs: bool) -> None:
    common.write(f, 0, f"architecture rtl of {pe.entity_name} is", end="\n")

    if write_pe_archs or pe.operation_type in (Input, Output):
        vhdl_code = pe.operation_type._vhdl(pe)
        common.write(f, 0, vhdl_code[0])

    common.write(f, 0, "begin", end="\n")

    if write_pe_archs or pe.operation_type in (Input, Output):
        common.write(f, 0, vhdl_code[1])

    common.write(f, 0, "end architecture rtl;", end="\n")
