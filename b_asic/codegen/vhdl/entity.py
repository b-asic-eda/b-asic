"""
Module for code generation of VHDL entity declarations
"""
from io import TextIOWrapper
from typing import Set

from b_asic.codegen import vhdl
from b_asic.codegen.vhdl import VHDL_TAB
from b_asic.port import Port
from b_asic.process import MemoryVariable, PlainMemoryVariable
from b_asic.resources import ProcessCollection


def write_memory_based_storage(
    f: TextIOWrapper, entity_name: str, collection: ProcessCollection, word_length: int
):
    # Check that this is a ProcessCollection of (Plain)MemoryVariables
    is_memory_variable = all(
        isinstance(process, MemoryVariable) for process in collection
    )
    is_plain_memory_variable = all(
        isinstance(process, PlainMemoryVariable) for process in collection
    )
    if not (is_memory_variable or is_plain_memory_variable):
        raise ValueError(
            "HDL can only be generated for ProcessCollection of (Plain)MemoryVariables"
        )

    entity_name = entity_name

    # Write the entity header
    vhdl.write_lines(
        f,
        [
            (0, f'entity {entity_name} is'),
            (1, f'generic('),
            (2, f'-- Data word length'),
            (2, f'WL : integer := {word_length}'),
            (1, f');'),
            (1, f'port('),
        ],
    )

    # Write the clock and reset signal
    vhdl.write_lines(
        f,
        [
            (0, f'-- Clock, synchronous reset and enable signals'),
            (2, f'clk : in std_logic;'),
            (2, f'rst : in std_logic;'),
            (2, f'en  : in std_logic;'),
            (0, f''),
        ],
    )

    # Write the input port specification
    f.write(f'{2*VHDL_TAB}-- Memory port I/O\n')
    read_ports: set[Port] = set(sum((mv.read_ports for mv in collection), ()))  # type: ignore
    for idx, read_port in enumerate(read_ports):
        port_name = read_port if isinstance(read_port, int) else read_port.name
        port_name = 'p_' + str(port_name) + '_in'
        f.write(f'{2*VHDL_TAB}{port_name} : in std_logic_vector(WL-1 downto 0);\n')

    # Write the output port specification
    write_ports: Set[Port] = {mv.write_port for mv in collection}  # type: ignore
    for idx, write_port in enumerate(write_ports):
        port_name = write_port if isinstance(write_port, int) else write_port.name
        port_name = 'p_' + str(port_name) + '_out'
        f.write(f'{2*VHDL_TAB}{port_name} : out std_logic_vector(WL-1 downto 0)')
        if idx == len(write_ports) - 1:
            f.write('\n')
        else:
            f.write(';\n')

    # Write ending of the port header
    f.write(f'{VHDL_TAB});\n')
    f.write(f'end entity {entity_name};\n\n')


def write_register_based_storage(
    f: TextIOWrapper, entity_name: str, collection: ProcessCollection, word_length: int
):
    write_memory_based_storage(f, entity_name, collection, word_length)
