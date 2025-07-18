"""
Module for code generation of VHDL entity declarations.
"""

from typing import TYPE_CHECKING, TextIO

from b_asic.codegen.vhdl import write, write_lines
from b_asic.process import OperatorProcess
from b_asic.special_operations import Input, Output

if TYPE_CHECKING:
    from b_asic.architecture import Architecture, Memory, ProcessingElement


def architecture(
    f: TextIO,
    arch: "Architecture",
    word_length: int,
) -> None:
    # Write the entity header
    write_lines(
        f,
        [
            (0, f"entity {arch.entity_name} is"),
            (1, "generic("),
            (2, "-- Data word length"),
            (2, f"WL : integer := {word_length};"),
            (2, f"SCHEDULE_CNT_LEN : integer := {arch.schedule_time.bit_length()}"),
            (1, ");"),
            (1, "port("),
        ],
    )

    # Write the clock and reset signal
    write_lines(
        f,
        [
            (2, "-- Clock and synchronous reset signals"),
            (2, "clk : in std_logic;"),
            (2, "rst : in std_logic;"),
            (0, ""),
        ],
    )

    # Write the input port specification
    write(f, 2, "-- PE port I/O", end="\n")
    inputs = [pe for pe in arch.processing_elements if pe.operation_type == Input]
    for pe in inputs:
        write(f, 2, f"{pe.entity_name}_0_in : in std_logic_vector(WL-1 downto 0);\n")

    outputs = [pe for pe in arch.processing_elements if pe.operation_type == Output]
    for i, pe in enumerate(outputs):
        write(
            f,
            2,
            f"{pe.entity_name}_0_out : out std_logic_vector(WL-1 downto 0){'' if i == len(outputs) - 1 else ';'}",
        )

    # Write ending of the port header
    write(f, 1, ");", end="\n")
    write(f, 0, f"end entity {arch.entity_name};", end="\n\n")


def architecture_test_bench(f: TextIO, arch: "Architecture") -> None:
    write(f, 0, f"entity {arch.entity_name}_tb is")
    write(f, 0, f"end entity {arch.entity_name}_tb;", end="\n")


def process_element(
    f: TextIO,
    pe: "ProcessingElement",
    word_length: int,
) -> None:
    # Check that this is a ProcessCollection of OperatorProcesses
    if not all(isinstance(process, OperatorProcess) for process in pe.collection):
        raise ValueError(
            "HDL can only be generated for ProcessCollection of OperatorProcesses"
        )

    # Write the entity header
    write_lines(
        f,
        [
            (0, f"entity {pe.entity_name} is"),
            (1, "generic("),
            (2, "-- Data word length"),
            (2, f"WL : integer := {word_length};"),
            (2, "-- Schedule counter length"),
            (2, f"SCHEDULE_CNT_LEN : integer := {pe.schedule_time.bit_length()}"),
            (1, ");"),
            (1, "port("),
        ],
    )

    # Write the clock and reset signal
    write_lines(
        f,
        [
            (2, "-- Clock and synchronous reset signals"),
            (2, "clk : in std_logic;"),
            (2, "rst : in std_logic;"),
            (0, ""),
        ],
    )

    # Write the schedule counter signal
    write_lines(
        f,
        [
            (2, "-- State counter"),
            (2, "schedule_cnt : in unsigned(SCHEDULE_CNT_LEN-1 downto 0);"),
            (0, ""),
        ],
    )

    # Write the input port specification
    write(f, 2, "-- PE port I/O", end="\n")
    for input_port in range(pe.input_count):
        write(f, 2, f"p_{input_port}_in : in std_logic_vector(WL-1 downto 0);\n")
    if pe.operation_type == Input:
        write(f, 2, "p_0_in : in std_logic_vector(WL-1 downto 0);\n")

    # Write the output port specification
    for output_port in range(pe.output_count):
        port_name = "p_" + str(output_port) + "_out"
        write(
            f,
            2,
            f"{port_name} : out std_logic_vector(WL-1 downto 0){'' if output_port == pe.output_count - 1 else ';'}",
            end="\n",
        )
    if pe.operation_type == Output:
        write(f, 2, "p_0_out : out std_logic_vector(WL-1 downto 0)\n")

    # Write ending of the port header
    write(f, 1, ");", end="\n")
    write(f, 0, f"end entity {pe.entity_name};", end="\n\n")


def memory_based_storage(f: TextIO, memory: "Memory", word_length: int) -> None:
    from b_asic.process import MemoryVariable, PlainMemoryVariable  # noqa: PLC0415

    # Check that this is a ProcessCollection of (Plain)MemoryVariables
    is_memory_variable = all(
        isinstance(process, MemoryVariable) for process in memory.collection
    )
    is_plain_memory_variable = all(
        isinstance(process, PlainMemoryVariable) for process in memory.collection
    )
    if not (is_memory_variable or is_plain_memory_variable):
        raise ValueError(
            "HDL can only be generated for ProcessCollection of (Plain)MemoryVariables"
        )

    # Write the entity header
    write_lines(
        f,
        [
            (0, f"entity {memory.entity_name} is"),
            (1, "generic("),
            (2, "-- Data word length"),
            (2, f"WL               : integer := {word_length};"),
            (2, "-- Schedule counter length"),
            (2, f"SCHEDULE_CNT_LEN : integer := {memory.schedule_time.bit_length()}"),
            (1, ");"),
            (1, "port("),
        ],
    )

    # Write the clock and reset signal
    write_lines(
        f,
        [
            (2, "-- Clock, synchronous reset and enable signals"),
            (2, "clk : in std_logic;"),
            (2, "rst : in std_logic;"),
            (0, ""),
        ],
    )

    # Write the schedule counter signal
    write_lines(
        f,
        [
            (2, "-- State counter"),
            (2, "schedule_cnt : in unsigned(SCHEDULE_CNT_LEN-1 downto 0);"),
            (0, ""),
        ],
    )

    # Write the input port specification
    write(f, 2, "-- Memory port I/O", end="\n")
    for read_port in range(memory.input_count):
        write(f, 2, f"p_{read_port}_in : in std_logic_vector(WL-1 downto 0);", end="\n")

    # Write the output port specification
    for write_port in range(memory.output_count):
        write(
            f,
            2,
            f"p_{write_port}_out : out std_logic_vector(WL-1 downto 0){'' if write_port == memory.output_count - 1 else ';'}",
            end="\n",
        )

    # Write ending of the port header
    write(f, 1, ");", end="\n")
    write(f, 0, f"end entity {memory.entity_name};", end="\n\n")


def register_based_storage(f: TextIO, memory: "Memory", word_length: int) -> None:
    memory_based_storage(f, memory, word_length)
