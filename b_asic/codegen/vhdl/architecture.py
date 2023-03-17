"""
Module for code generation of VHDL architectures.
"""
from io import TextIOWrapper
from typing import Dict, List, Set, Tuple, cast

from b_asic.codegen import vhdl
from b_asic.codegen.vhdl import VHDL_TAB
from b_asic.process import MemoryVariable, PlainMemoryVariable
from b_asic.resources import ProcessCollection, _ForwardBackwardTable


def write_memory_based_storage(
    f: TextIOWrapper,
    assignment: Set[ProcessCollection],
    entity_name: str,
    word_length: int,
    read_ports: int,
    write_ports: int,
    total_ports: int,
    input_sync: bool = True,
):
    """
    Generate the VHDL architecture for a memory based architecture from a process collection of memory variables.

    Parameters
    ----------
    assignment : dict
        A possible cell assignment to use when generating the memory based storage.
        The cell assignment is a dictionary int to ProcessCollection where the integer
        corresponds to the cell to assign all MemoryVariables in corresponding process
        collection.
        If unset, each MemoryVariable will be assigned to a unique cell.
    f : TextIOWrapper
        File object (or other TextIOWrapper object) to write the architecture onto.
    word_length : int
        Word length of the memory variable objects.
    read_ports : int
        Number of read ports.
    write_ports : int
        Number of write ports.
    total_ports : int
        Total concurrent memory accesses possible.
    input_sync : bool, default: True
        Add registers to the input signals (enable signal and data input signals).
        Adding registers to the inputs allow pipelining of address generation (which is added automatically).
        For large interleavers, this can improve timing significantly.
    """

    # Code settings
    mem_depth = len(assignment)
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
    vhdl.common.write_signal_decl(
        f, name='memory', type='mem_type', name_pad=14, vivado_ram_style='distributed'
    )
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
    f.write(f'\n{VHDL_TAB}-- Schedule counter\n')
    vhdl.common.write_signal_decl(
        f,
        name='schedule_cnt',
        type=f'integer range 0 to {schedule_time}-1',
        name_pad=14,
    )

    # Input sync signals
    if input_sync:
        f.write(f'\n{VHDL_TAB}-- Input synchronization\n')
        for i in range(read_ports):
            vhdl.common.write_signal_decl(
                f, f'p_{i}_in_sync', 'std_logic_vector(WL-1 downto 0)', name_pad=14
            )

    #
    # Architecture body begin
    #
    f.write(f'\nbegin\n\n')
    f.write(f'{VHDL_TAB}-- Schedule counter\n')
    vhdl.common.write_synchronous_process(
        f=f,
        name='schedule_cnt_proc',
        clk='clk',
        body=(
            f'{0*VHDL_TAB}if rst = \'1\' then\n'
            f'{1*VHDL_TAB}schedule_cnt <= 0;\n'
            f'{0*VHDL_TAB}else\n'
            f'{1*VHDL_TAB}if en = \'1\' then\n'
            f'{2*VHDL_TAB}if schedule_cnt = {schedule_time-1} then\n'
            f'{3*VHDL_TAB}schedule_cnt <= 0;\n'
            f'{2*VHDL_TAB}else\n'
            f'{3*VHDL_TAB}schedule_cnt <= schedule_cnt + 1;\n'
            f'{2*VHDL_TAB}end if;\n'
            f'{1*VHDL_TAB}end if;\n'
            f'{0*VHDL_TAB}end if;\n'
        ),
    )

    if input_sync:
        f.write(f'\n{VHDL_TAB}-- Input synchronization\n')
        vhdl.common.write_synchronous_process_prologue(
            f=f,
            name='input_sync_proc',
            clk='clk',
        )
        for i in range(read_ports):
            f.write(f'{3*VHDL_TAB}p_{i}_in_sync <= p_{i}_in;\n')
        vhdl.common.write_synchronous_process_epilogue(
            f=f,
            name='input_sync_proc',
            clk='clk',
        )

    # Infer memory
    f.write(f'\n{VHDL_TAB}-- Memory\n')
    vhdl.common.write_asynchronous_read_memory(
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

    # Write address generation
    f.write(f'\n{VHDL_TAB}-- Memory write address generation\n')
    if input_sync:
        vhdl.common.write_synchronous_process_prologue(
            f, clk="clk", name="mem_write_address_proc"
        )
    else:
        vhdl.common.write_process_prologue(
            f, sensitivity_list="schedule_cnt", name="mem_write_address_proc"
        )
    f.write(f'{3*VHDL_TAB}case schedule_cnt is\n')
    for i, collection in enumerate(assignment):
        for mv in collection:
            mv = cast(MemoryVariable, mv)
            if mv.execution_time:
                f.write(f'{4*VHDL_TAB}-- {mv!r}\n')
                f.write(f'{4*VHDL_TAB}when {(mv.start_time) % schedule_time} =>\n')
                f.write(f'{5*VHDL_TAB}write_adr_0 <= {i};\n')
                f.write(f'{5*VHDL_TAB}write_en_0 <= \'1\';\n')
    f.write(f'{4*VHDL_TAB}when others =>\n')
    f.write(f'{5*VHDL_TAB}write_adr_0 <= 0;\n')
    f.write(f'{5*VHDL_TAB}write_en_0 <= \'0\';\n')
    f.write(f'{3*VHDL_TAB}end case;\n')
    if input_sync:
        vhdl.common.write_synchronous_process_epilogue(
            f, clk="clk", name="mem_write_address_proc"
        )
    else:
        vhdl.common.write_process_epilogue(
            f, sensitivity_list="clk", name="mem_write_address_proc"
        )

    # Read address generation
    f.write(f'\n{VHDL_TAB}-- Memory read address generation\n')
    vhdl.common.write_synchronous_process_prologue(
        f, clk="clk", name="mem_read_address_proc"
    )
    f.write(f'{3*VHDL_TAB}case schedule_cnt is\n')
    for i, collection in enumerate(assignment):
        for mv in collection:
            mv = cast(PlainMemoryVariable, mv)
            f.write(f'{4*VHDL_TAB}-- {mv!r}\n')
            for read_time in mv.reads.values():
                f.write(
                    f'{4*VHDL_TAB}when'
                    f' {(mv.start_time+read_time-int(not(input_sync))) % schedule_time} =>\n'
                )
                f.write(f'{5*VHDL_TAB}read_adr_0 <= {i};\n')
                f.write(f'{5*VHDL_TAB}read_en_0 <= \'1\';\n')
    f.write(f'{4*VHDL_TAB}when others =>\n')
    f.write(f'{5*VHDL_TAB}read_adr_0 <= 0;\n')
    f.write(f'{5*VHDL_TAB}read_en_0 <= \'0\';\n')
    f.write(f'{3*VHDL_TAB}end case;\n')
    vhdl.common.write_synchronous_process_epilogue(
        f, clk="clk", name="mem_read_address_proc"
    )

    f.write(f'\n{1*VHDL_TAB}-- Input and output assignment\n')
    if input_sync:
        f.write(f'{1*VHDL_TAB}write_port_0 <= p_0_in_sync;\n')
    else:
        f.write(f'{1*VHDL_TAB}write_port_0 <= p_0_in;\n')
    p_zero_exec = filter(
        lambda p: p.execution_time == 0, (p for pc in assignment for p in pc)
    )
    vhdl.common.write_synchronous_process_prologue(
        f,
        clk='clk',
        name='output_reg_proc',
    )
    f.write(f'{3*VHDL_TAB}case schedule_cnt is\n')
    for p in p_zero_exec:
        if input_sync:
            f.write(
                f'{4*VHDL_TAB}when {(p.start_time+1)%schedule_time} => p_0_out <='
                ' p_0_in_sync;\n'
            )
        else:
            f.write(
                f'{4*VHDL_TAB}when {(p.start_time)%schedule_time} => p_0_out <='
                ' p_0_in;\n'
            )
    f.write(f'{4*VHDL_TAB}when others => p_0_out <= read_port_0;\n')
    f.write(f'{3*VHDL_TAB}end case;\n')
    vhdl.common.write_synchronous_process_epilogue(
        f,
        clk='clk',
        name='output_reg_proc',
    )
    f.write(f'\nend architecture {architecture_name};')


def write_register_based_storage(
    f: TextIOWrapper,
    forward_backward_table: _ForwardBackwardTable,
    entity_name: str,
    word_length: int,
    read_ports: int,
    write_ports: int,
    total_ports: int,
):
    architecture_name = "rtl"
    schedule_time = len(forward_backward_table)

    # Number of registers in this design
    reg_cnt = len(forward_backward_table[0].regs)

    # Set of the register indices to output from
    output_regs = {entry.outputs_from for entry in forward_backward_table.table}
    if None in output_regs:
        output_regs.remove(None)
    output_regs = cast(Set[int], output_regs)

    # Table with mapping: register to output multiplexer index
    output_mux_table = {reg: i for i, reg in enumerate(output_regs)}

    # Back-edge register indices
    back_edges: Set[Tuple[int, int]] = {
        (frm, to)
        for entry in forward_backward_table
        for frm, to in entry.back_edge_to.items()
    }
    back_edge_table: Dict[Tuple[int, int], int] = {
        edge: i + 1 for i, edge in enumerate(back_edges)
    }

    #
    # Architecture declerative region begin
    #
    # Write architecture header
    f.write(f'architecture {architecture_name} of {entity_name} is\n\n')

    # Schedule time counter
    f.write(f'{VHDL_TAB}-- Schedule counter\n')
    vhdl.common.write_signal_decl(
        f,
        name='schedule_cnt',
        type=f'integer range 0 to {schedule_time}-1',
        name_pad=18,
        default_value='0',
    )

    # Shift register
    f.write(f'\n{VHDL_TAB}-- Shift register\n')
    vhdl.common.write_type_decl(
        f,
        name='shift_reg_type',
        alias=f'array(0 to {reg_cnt}-1) of std_logic_vector(WL-1 downto 0)',
    )
    vhdl.common.write_signal_decl(
        f,
        name='shift_reg',
        type='shift_reg_type',
        name_pad=18,
    )

    # Back edge mux decoder
    f.write(f'\n{VHDL_TAB}-- Back-edge mux select signal\n')
    vhdl.common.write_signal_decl(
        f,
        name='back_edge_mux_sel',
        type=f'integer range 0 to {len(back_edges)}',
        name_pad=18,
    )

    # Output mux selector
    f.write(f'\n{VHDL_TAB}-- Output mux select signal\n')
    vhdl.common.write_signal_decl(
        f,
        name='out_mux_sel',
        type=f'integer range 0 to {len(output_regs)-1}',
        name_pad=18,
    )

    #
    # Architecture body begin
    #
    f.write(f'begin\n\n')

    f.write(f'{VHDL_TAB}-- Schedule counter\n')
    vhdl.common.write_synchronous_process(
        f=f,
        name='schedule_cnt_proc',
        clk='clk',
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

    # Shift register back-edge decoding
    f.write(f'\n{VHDL_TAB}-- Shift register back-edge decoding\n')
    vhdl.common.write_synchronous_process_prologue(
        f,
        clk='clk',
        name='shift_reg_back_edge_decode_proc',
    )
    vhdl.write(f, 3, f'case schedule_cnt is')
    for time, entry in enumerate(forward_backward_table):
        if entry.back_edge_to:
            assert len(entry.back_edge_to) == 1
            for src, dst in entry.back_edge_to.items():
                mux_idx = back_edge_table[(src, dst)]
                vhdl.write(f, 4, f'when {(time-1)%schedule_time} =>')
                vhdl.write(f, 5, f'-- ({src} -> {dst})')
                vhdl.write(f, 5, f'back_edge_mux_sel <= {mux_idx};')
    vhdl.write(f, 4, f'when others =>')
    vhdl.write(f, 5, f'back_edge_mux_sel <= 0;')
    vhdl.write(f, 3, f'end case;')
    vhdl.common.write_synchronous_process_epilogue(
        f,
        clk='clk',
        name='shift_reg_back_edge_decode_proc',
    )

    # Shift register multiplexer logic
    f.write(f'\n{VHDL_TAB}-- Multiplexers for shift register\n')
    vhdl.common.write_synchronous_process_prologue(
        f,
        clk='clk',
        name='shift_reg_proc',
    )
    f.write(f'{3*VHDL_TAB}-- Default case\n')
    f.write(f'{3*VHDL_TAB}shift_reg(0) <= p_0_in;\n')
    for reg_idx in range(1, reg_cnt):
        f.write(f'{3*VHDL_TAB}shift_reg({reg_idx}) <= shift_reg({reg_idx-1});\n')
    vhdl.write(f, 3, f'case back_edge_mux_sel is')
    for edge, mux_sel in back_edge_table.items():
        vhdl.write(f, 4, f'when {mux_sel} =>')
        vhdl.write(f, 5, f'shift_reg({edge[1]}) <= shift_reg({edge[0]});')
    # f.write(f'{3*VHDL_TAB}case schedule_cnt is\n')
    # for i, entry in enumerate(forward_backward_table):
    #    if entry.back_edge_from:
    #        f.write(f'{4*VHDL_TAB} when {schedule_time-1 if (i-1)<0 else (i-1)} =>\n')
    #        for dst, src in entry.back_edge_from.items():
    #            f.write(f'{5*VHDL_TAB} shift_reg({dst}) <= shift_reg({src});\n')
    f.write(f'{4*VHDL_TAB}when others => null;\n')
    f.write(f'{3*VHDL_TAB}end case;\n')

    vhdl.common.write_synchronous_process_epilogue(
        f,
        clk='clk',
        name='shift_reg_proc',
    )

    # Output multiplexer decoding logic
    f.write(f'\n{VHDL_TAB}-- Output muliplexer decoding logic\n')
    vhdl.common.write_synchronous_process_prologue(
        f, clk='clk', name='out_mux_decode_proc'
    )
    f.write(f'{3*VHDL_TAB}case schedule_cnt is\n')
    for i, entry in enumerate(forward_backward_table):
        if entry.outputs_from is not None:
            f.write(f'{4*VHDL_TAB}when {(i-1)%schedule_time} =>\n')
            f.write(
                f'{5*VHDL_TAB}out_mux_sel <= {output_mux_table[entry.outputs_from]};\n'
            )
    f.write(f'{3*VHDL_TAB}end case;\n')
    vhdl.common.write_synchronous_process_epilogue(
        f, clk='clk', name='out_mux_decode_proc'
    )

    # Output multiplexer logic
    f.write(f'\n{VHDL_TAB}-- Output muliplexer\n')
    vhdl.common.write_synchronous_process_prologue(
        f,
        clk='clk',
        name='out_mux_proc',
    )
    f.write(f'{3*VHDL_TAB}case out_mux_sel is\n')
    for reg_i, mux_i in output_mux_table.items():
        f.write(f'{4*VHDL_TAB}when {mux_i} =>\n')
        if reg_i < 0:
            f.write(f'{5*VHDL_TAB}p_0_out <= p_{-1-reg_i}_in;\n')
        else:
            f.write(f'{5*VHDL_TAB}p_0_out <= shift_reg({reg_i});\n')
    f.write(f'{3*VHDL_TAB}end case;\n')
    vhdl.common.write_synchronous_process_epilogue(
        f,
        clk='clk',
        name='out_mux_proc',
    )

    f.write(f'end architecture {architecture_name};')
