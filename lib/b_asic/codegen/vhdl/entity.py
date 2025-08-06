"""
Module for code generation of VHDL entity declarations.
"""

from typing import TYPE_CHECKING, TextIO

from b_asic.codegen.vhdl import common as vhdl_common
from b_asic.process import MemoryVariable, OperatorProcess, PlainMemoryVariable
from b_asic.special_operations import Input, Output

if TYPE_CHECKING:
    from b_asic.architecture import Architecture, Memory, ProcessingElement, WordLengths


def architecture(f: TextIO, arch: "Architecture", wl: "WordLengths") -> None:
    generics = wl.generics_with_default()
    ports = [
        "clk : in std_logic",
        "rst : in std_logic",
    ]
    ports += [
        f"{pe.entity_name}_0_in : in std_logic_vector(WL_INPUT_INT+WL_INPUT_FRAC-1 downto 0)"
        for pe in arch.processing_elements
        if pe.operation_type == Input
    ]
    ports += [
        f"{pe.entity_name}_0_out : out std_logic_vector(WL_OUTPUT_INT+WL_OUTPUT_FRAC-1 downto 0)"
        for pe in arch.processing_elements
        if pe.operation_type == Output
    ]
    vhdl_common.entity_declaration(f, arch.entity_name, generics, ports)


def architecture_test_bench(f: TextIO, arch: "Architecture") -> None:
    vhdl_common.entity_declaration(f, f"{arch.entity_name}_tb")


def processing_element(f: TextIO, pe: "ProcessingElement", wl: "WordLengths") -> None:
    if not all(isinstance(process, OperatorProcess) for process in pe.collection):
        raise ValueError(
            "HDL can only be generated for ProcessCollection of OperatorProcesses"
        )

    generics = wl.generics()
    ports = [
        "clk : in std_logic",
        "rst : in std_logic",
        "schedule_cnt : in unsigned(WL_STATE-1 downto 0)",
    ]
    ports += [
        f"p_{input_port}_in : in std_logic_vector(WL_INTERNAL_INT+WL_INTERNAL_FRAC-1 downto 0)"
        for input_port in range(pe.input_count)
    ]
    if pe.operation_type == Input:
        ports += ["p_0_in : in std_logic_vector(WL_INPUT_INT+WL_INPUT_FRAC-1 downto 0)"]
    ports += [
        f"p_{output_port}_out : out std_logic_vector(WL_INTERNAL_INT+WL_INTERNAL_FRAC-1 downto 0)"
        for output_port in range(pe.output_count)
    ]
    if pe.operation_type == Output:
        ports += [
            "p_0_out : out std_logic_vector(WL_OUTPUT_INT+WL_OUTPUT_FRAC-1 downto 0)"
        ]
    vhdl_common.entity_declaration(f, pe.entity_name, generics, ports)


def memory_based_storage(f: TextIO, mem: "Memory", wl: "WordLengths") -> None:
    is_memory_variable = all(
        isinstance(process, MemoryVariable) for process in mem.collection
    )
    is_plain_memory_variable = all(
        isinstance(process, PlainMemoryVariable) for process in mem.collection
    )
    if not (is_memory_variable or is_plain_memory_variable):
        raise ValueError(
            "HDL can only be generated for ProcessCollection of (Plain)MemoryVariables"
        )

    generics = wl.generics()
    ports = [
        "clk : in std_logic",
        "rst : in std_logic",
        "schedule_cnt : in unsigned(WL_STATE-1 downto 0)",
    ]
    ports += [
        f"p_{input_port}_in : in std_logic_vector(WL_INTERNAL_INT+WL_INTERNAL_FRAC-1 downto 0)"
        for input_port in range(mem.input_count)
    ]
    ports += [
        f"p_{output_port}_out : out std_logic_vector(WL_INTERNAL_INT+WL_INTERNAL_FRAC-1 downto 0)"
        for output_port in range(mem.output_count)
    ]
    vhdl_common.entity_declaration(f, mem.entity_name, generics, ports)


def register_based_storage(f: TextIO, memory: "Memory", wl: "WordLengths") -> None:
    memory_based_storage(f, memory, wl)
