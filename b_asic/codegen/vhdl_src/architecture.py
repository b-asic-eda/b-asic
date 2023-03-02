"""
Module for code generation of VHDL architectures.
"""
from io import TextIOWrapper
from typing import Dict, Optional, Set, cast

# from b_asic.codegen.vhdl_src import common
from b_asic.codegen import vhdl
from b_asic.codegen.vhdl import VHDL_TAB
from b_asic.process import MemoryVariable, PlainMemoryVariable
from b_asic.resources import ProcessCollection


def write_memory_based_architecture(
    f: TextIOWrapper,
    assignment: Set[ProcessCollection],
    word_length: int,
    read_ports: int,
    write_ports: int,
    total_ports: int,
):
    """
    Generate the VHDL architecture for a memory based architecture from a process collection of memory variables.

    Parameters
    ----------
    assignment: dictionary
        A possible cell assignment to use when generating the memory based storage.
        The cell assignment is a dictionary int to ProcessCollection where the integer
        corresponds to the cell to assign all MemoryVariables in corresponding process
        collection.
        If unset, each MemoryVariable will be assigned to a unique cell.
    f : TextIOWrapper
        File object (or other TextIOWrapper object) to write the architecture onto.
    word_length: int
        Word length of the memory variable objects.
    read_ports:
        Number of read ports.
    write_ports:
        Number of write ports.
    total_ports:
        Total concurrent memory accesses possible.
    """

    # Code settings
    mem_depth = len(assignment)
    entity_name = "some_name"
    architecture_name = "rtl"
    schedule_time = next(iter(assignment))._schedule_time

    # Write architecture header
    f.write(f'architecture {architecture_name} of {entity_name} is\n\n')

    #
    # Architecture declerative region begin
    #
    f.write(f'{VHDL_TAB}-- HDL memory description\n')
    vhdl.common.write_constant_decl(
        f, name='MEM_WL', type='integer', value=word_length, name_pad=12
    )
    vhdl.common.write_constant_decl(
        f, name='MEM_DEPTH', type='integer', value=mem_depth, name_pad=12
    )
    vhdl.common.write_type_decl(
        f, 'mem_type', 'array(0 to MEM_DEPTH-1) of std_logic_vector(MEM_WL-1 downto 0)'
    )
    vhdl.common.write_signal_decl(f, 'memory', 'mem_type', name_pad=14)
    for i in range(read_ports):
        vhdl.common.write_signal_decl(
            f, f'read_port_{i}', 'std_logic_vector(MEM_WL-1 downto 0)', name_pad=14
        )
        vhdl.common.write_signal_decl(
            f, f'read_adr_{i}', f'integer range 0 to {schedule_time}-1', name_pad=14
        )
        vhdl.common.write_signal_decl(f, f'read_en_{i}', 'std_logic', name_pad=14)
    for i in range(write_ports):
        vhdl.common.write_signal_decl(
            f, f'write_port_{i}', 'std_logic_vector(MEM_WL-1 downto 0)', name_pad=14
        )
        vhdl.common.write_signal_decl(
            f, f'write_adr_{i}', f'integer range 0 to {schedule_time}-1', name_pad=14
        )
        vhdl.common.write_signal_decl(f, f'write_en_{i}', 'std_logic', name_pad=14)

    # Schedule time counter
    f.write('\n')
    f.write(f'{VHDL_TAB}-- Schedule counter\n')
    vhdl.common.write_signal_decl(
        f,
        name='schedule_cnt',
        type=f'integer range 0 to {schedule_time}-1',
        name_pad=14,
    )
    f.write('\n')

    #
    # Architecture body begin
    #
    f.write(f'begin\n\n')
    f.write(f'{VHDL_TAB}-- Schedule counter\n')
    vhdl.common.write_synchronous_process(
        f=f,
        name='schedule_cnt_proc',
        clk='clk',
        indent=len(1 * VHDL_TAB),
        body=(
            f'{0*VHDL_TAB}if en = \'1\' then\n'
            f'{1*VHDL_TAB}if schedule_cnt = {schedule_time}-1 then\n'
            f'{2*VHDL_TAB}schedule_cnt <= 0;\n'
            f'{1*VHDL_TAB}else\n'
            f'{2*VHDL_TAB}schedule_cnt <= schedule_cnt + 1;\n'
            f'{1*VHDL_TAB}end if;\n'
            f'{0*VHDL_TAB}end if;\n'
        ),
    )

    # Infer memory
    f.write('\n')
    f.write(f'{VHDL_TAB}-- Memory\n')
    vhdl.common.write_synchronous_memory(
        f=f,
        clk='clk',
        name=f'mem_{0}_proc',
        read_ports={
            (f'read_port_{i}', f'read_adr_{i}', f'read_en_{i}')
            for i in range(read_ports)
        },
        write_ports={
            (f'write_port_{i}', f'write_adr_{i}', f'write_en_{i}')
            for i in range(write_ports)
        },
    )

    f.write(f'\n{VHDL_TAB}-- Memory writes\n')
    f.write(f'{VHDL_TAB}process(schedule_cnt)\n')
    f.write(f'{VHDL_TAB}begin\n')

    f.write(f'{2*VHDL_TAB}case schedule_cnt is\n')
    for i, collection in enumerate(assignment):
        for mv in collection:
            mv = cast(MemoryVariable, mv)
            f.write(f'{3*VHDL_TAB}-- {mv!r}\n')
            f.write(f'{3*VHDL_TAB}when {mv.start_time} =>\n')
            f.write(f'{4*VHDL_TAB}write_adr_0 <= {i};\n')
            f.write(f'{4*VHDL_TAB}write_en_0 <= \'1\';\n')
    f.write(f'{3*VHDL_TAB}when others =>\n')
    f.write(f'{4*VHDL_TAB}write_adr_0 <= 0;\n')
    f.write(f'{4*VHDL_TAB}write_en_0 <= \'0\';\n')
    f.write(f'{2*VHDL_TAB}end case;\n')

    f.write(f'{1*VHDL_TAB}end process;\n')

    f.write(f'\n{VHDL_TAB}-- Memory reads\n')
    f.write(f'{VHDL_TAB}process(schedule_cnt)\n')
    f.write(f'{VHDL_TAB}begin\n')

    f.write(f'{2*VHDL_TAB}case schedule_cnt is\n')
    for i, collection in enumerate(assignment):
        for mv in collection:
            mv = cast(PlainMemoryVariable, mv)
            f.write(f'{3*VHDL_TAB}-- {mv!r}\n')
            for read_time in mv.reads.values():
                f.write(
                    f'{3*VHDL_TAB}when'
                    f' {(mv.start_time + read_time) % schedule_time} =>\n'
                )
                f.write(f'{4*VHDL_TAB}read_adr_0 <= {i};\n')
                f.write(f'{4*VHDL_TAB}read_en_0 <= \'1\';\n')
    f.write(f'{3*VHDL_TAB}when others =>\n')
    f.write(f'{4*VHDL_TAB}read_adr_0 <= 0;\n')
    f.write(f'{4*VHDL_TAB}read_en_0 <= \'0\';\n')
    f.write(f'{2*VHDL_TAB}end case;\n')

    f.write(f'{1*VHDL_TAB}end process;\n')

    f.write('\n')
    f.write(f'end architecture {architecture_name};')
