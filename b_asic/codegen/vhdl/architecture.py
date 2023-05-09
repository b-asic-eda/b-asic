"""
Module for code generation of VHDL architectures.
"""
from io import TextIOWrapper
from typing import TYPE_CHECKING, Dict, Set, Tuple, cast

from b_asic.codegen import vhdl
from b_asic.process import MemoryVariable, PlainMemoryVariable

if TYPE_CHECKING:
    from b_asic.resources import ProcessCollection, _ForwardBackwardTable


def memory_based_storage(
    f: TextIOWrapper,
    assignment: Set["ProcessCollection"],
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
    vhdl.write(
        f, 0, f'architecture {architecture_name} of {entity_name} is', end='\n\n'
    )

    #
    # Architecture declerative region begin
    #
    vhdl.write(f, 1, '-- HDL memory description')
    vhdl.common.constant_declaration(
        f, name='MEM_WL', signal_type='integer', value=word_length, name_pad=12
    )
    vhdl.common.constant_declaration(
        f, name='MEM_DEPTH', signal_type='integer', value=mem_depth, name_pad=12
    )
    vhdl.common.type_declaration(
        f, 'mem_type', 'array(0 to MEM_DEPTH-1) of std_logic_vector(MEM_WL-1 downto 0)'
    )
    vhdl.common.signal_decl(
        f,
        name='memory',
        signal_type='mem_type',
        name_pad=14,
        vivado_ram_style='distributed',
    )
    for i in range(read_ports):
        vhdl.common.signal_decl(
            f, f'read_port_{i}', 'std_logic_vector(MEM_WL-1 downto 0)', name_pad=14
        )
        vhdl.common.signal_decl(
            f, f'read_adr_{i}', f'integer range 0 to {schedule_time}-1', name_pad=14
        )
        vhdl.common.signal_decl(f, f'read_en_{i}', 'std_logic', name_pad=14)
    for i in range(write_ports):
        vhdl.common.signal_decl(
            f, f'write_port_{i}', 'std_logic_vector(MEM_WL-1 downto 0)', name_pad=14
        )
        vhdl.common.signal_decl(
            f, f'write_adr_{i}', f'integer range 0 to {schedule_time}-1', name_pad=14
        )
        vhdl.common.signal_decl(f, f'write_en_{i}', 'std_logic', name_pad=14)

    # Schedule time counter
    vhdl.write(f, 1, '-- Schedule counter', start='\n')
    vhdl.common.signal_decl(
        f,
        name='schedule_cnt',
        signal_type=f'integer range 0 to {schedule_time}-1',
        name_pad=14,
    )

    # Input sync signals
    if input_sync:
        vhdl.write(f, 1, '-- Input synchronization', start='\n')
        for i in range(read_ports):
            vhdl.common.signal_decl(
                f, f'p_{i}_in_sync', 'std_logic_vector(WL-1 downto 0)', name_pad=14
            )

    #
    # Architecture body begin
    #
    vhdl.write(f, 0, 'begin', start='\n', end='\n\n')
    vhdl.write(f, 1, '-- Schedule counter')
    vhdl.common.synchronous_process_prologue(
        f=f,
        name='schedule_cnt_proc',
        clk='clk',
    )
    vhdl.write_lines(
        f,
        [
            (3, 'if rst = \'1\' then'),
            (4, 'schedule_cnt <= 0;'),
            (3, 'else'),
            (4, 'if en = \'1\' then'),
            (5, f'if schedule_cnt = {schedule_time-1} then'),
            (6, 'schedule_cnt <= 0;'),
            (5, 'else'),
            (6, 'schedule_cnt <= schedule_cnt + 1;'),
            (5, 'end if;'),
            (4, 'end if;'),
            (3, 'end if;'),
        ],
    )
    vhdl.common.synchronous_process_epilogue(
        f=f,
        name='schedule_cnt_proc',
        clk='clk',
    )

    if input_sync:
        vhdl.write(f, 1, '-- Input synchronization', start='\n')
        vhdl.common.synchronous_process_prologue(
            f=f,
            name='input_sync_proc',
            clk='clk',
        )
        for i in range(read_ports):
            vhdl.write(f, 3, f'p_{i}_in_sync <= p_{i}_in;')
        vhdl.common.synchronous_process_epilogue(
            f=f,
            name='input_sync_proc',
            clk='clk',
        )

    # Infer memory
    vhdl.write(f, 1, '-- Memory', start='\n')
    vhdl.common.asynchronous_read_memory(
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
    vhdl.write(f, 1, '-- Memory write address generation', start='\n')
    if input_sync:
        vhdl.common.synchronous_process_prologue(
            f, clk="clk", name="mem_write_address_proc"
        )
    else:
        vhdl.common.process_prologue(
            f, sensitivity_list="schedule_cnt", name="mem_write_address_proc"
        )
    vhdl.write(f, 3, 'case schedule_cnt is')
    for i, collection in enumerate(assignment):
        for mv in collection:
            mv = cast(MemoryVariable, mv)
            if mv.execution_time:
                vhdl.write_lines(
                    f,
                    [
                        (4, f'-- {mv!r}'),
                        (4, f'when {(mv.start_time) % schedule_time} =>'),
                        (5, f'write_adr_0 <= {i};'),
                        (5, 'write_en_0 <= \'1\';'),
                    ],
                )
    vhdl.write_lines(
        f,
        [
            (4, 'when others =>'),
            (5, 'write_adr_0 <= 0;'),
            (5, 'write_en_0 <= \'0\';'),
            (3, 'end case;'),
        ],
    )
    if input_sync:
        vhdl.common.synchronous_process_epilogue(
            f, clk="clk", name="mem_write_address_proc"
        )
    else:
        vhdl.common.process_epilogue(
            f, sensitivity_list="clk", name="mem_write_address_proc"
        )

    # Read address generation
    vhdl.write(f, 1, '-- Memory read address generation', start='\n')
    vhdl.common.synchronous_process_prologue(f, clk="clk", name="mem_read_address_proc")
    vhdl.write(f, 3, 'case schedule_cnt is')
    for i, collection in enumerate(assignment):
        for mv in collection:
            mv = cast(PlainMemoryVariable, mv)
            vhdl.write(f, 4, f'-- {mv!r}')
            for read_time in mv.reads.values():
                vhdl.write(
                    f,
                    4,
                    'when'
                    f' {(mv.start_time+read_time-int(not(input_sync))) % schedule_time} =>',
                )
                vhdl.write_lines(
                    f,
                    [
                        (5, f'read_adr_0 <= {i};'),
                        (5, 'read_en_0 <= \'1\';'),
                    ],
                )
    vhdl.write_lines(
        f,
        [
            (4, 'when others =>'),
            (5, 'read_adr_0 <= 0;'),
            (5, 'read_en_0 <= \'0\';'),
            (3, 'end case;'),
        ],
    )
    vhdl.common.synchronous_process_epilogue(f, clk="clk", name="mem_read_address_proc")

    vhdl.write(f, 1, '-- Input and output assignmentn', start='\n')
    if input_sync:
        vhdl.write(f, 1, 'write_port_0 <= p_0_in_sync;')
    else:
        vhdl.write(f, 1, 'write_port_0 <= p_0_in;')
    p_zero_exec = filter(
        lambda p: p.execution_time == 0, (p for pc in assignment for p in pc)
    )
    vhdl.common.synchronous_process_prologue(
        f,
        clk='clk',
        name='output_reg_proc',
    )
    vhdl.write(f, 3, 'case schedule_cnt is')
    for p in p_zero_exec:
        if input_sync:
            write_time = (p.start_time + 1) % schedule_time
            vhdl.write(f, 4, f'when {write_time} => p_0_out <= p_0_in_sync;')
        else:
            write_time = (p.start_time) % schedule_time
            vhdl.write(f, 4, f'when {write_time} => p_0_out <= p_0_in;')
    vhdl.write_lines(
        f,
        [
            (4, 'when others => p_0_out <= read_port_0;'),
            (3, 'end case;'),
        ],
    )
    vhdl.common.synchronous_process_epilogue(
        f,
        clk='clk',
        name='output_reg_proc',
    )
    vhdl.write(f, 0, f'end architecture {architecture_name};', start='\n')


def register_based_storage(
    f: TextIOWrapper,
    forward_backward_table: "_ForwardBackwardTable",
    entity_name: str,
    word_length: int,
    read_ports: int,
    write_ports: int,
    total_ports: int,
    sync_rst: bool = False,
    async_rst: bool = False,
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
    vhdl.write(
        f, 0, f'architecture {architecture_name} of {entity_name} is', end='\n\n'
    )

    # Schedule time counter
    vhdl.write(f, 1, '-- Schedule counter')
    vhdl.common.signal_decl(
        f,
        name='schedule_cnt',
        signal_type=f'integer range 0 to {schedule_time}-1',
        name_pad=18,
        default_value='0',
    )

    # Shift register
    vhdl.write(f, 1, '-- Shift register', start='\n')
    vhdl.common.type_declaration(
        f,
        name='shift_reg_type',
        alias=f'array(0 to {reg_cnt}-1) of std_logic_vector(WL-1 downto 0)',
    )
    vhdl.common.signal_decl(
        f,
        name='shift_reg',
        signal_type='shift_reg_type',
        name_pad=18,
    )

    # Back edge mux decoder
    vhdl.write(f, 1, '-- Back-edge mux select signal', start='\n')
    vhdl.common.signal_decl(
        f,
        name='back_edge_mux_sel',
        signal_type=f'integer range 0 to {len(back_edges)}',
        name_pad=18,
    )

    # Output mux selector
    vhdl.write(f, 1, '-- Output mux select signal', start='\n')
    vhdl.common.signal_decl(
        f,
        name='out_mux_sel',
        signal_type=f'integer range 0 to {len(output_regs) - 1}',
        name_pad=18,
    )

    #
    # Architecture body begin
    #
    vhdl.write(f, 0, 'begin', start='\n', end='\n\n')
    vhdl.write(f, 1, '-- Schedule counter')
    vhdl.common.synchronous_process_prologue(
        f=f,
        name='schedule_cnt_proc',
        clk='clk',
    )
    vhdl.write_lines(
        f,
        [
            (4, 'if en = \'1\' then'),
            (5, f'if schedule_cnt = {schedule_time}-1 then'),
            (6, 'schedule_cnt <= 0;'),
            (5, 'else'),
            (6, 'schedule_cnt <= schedule_cnt + 1;'),
            (5, 'end if;'),
            (4, 'end if;'),
        ],
    )
    vhdl.common.synchronous_process_epilogue(
        f=f,
        name='schedule_cnt_proc',
        clk='clk',
    )

    # Shift register back-edge decoding
    vhdl.write(f, 1, '-- Shift register back-edge decoding', start='\n')
    vhdl.common.synchronous_process_prologue(
        f,
        clk='clk',
        name='shift_reg_back_edge_decode_proc',
    )
    vhdl.write(f, 3, 'case schedule_cnt is')
    for time, entry in enumerate(forward_backward_table):
        if entry.back_edge_to:
            assert len(entry.back_edge_to) == 1
            for src, dst in entry.back_edge_to.items():
                mux_idx = back_edge_table[(src, dst)]
                vhdl.write_lines(
                    f,
                    [
                        (4, f'when {(time-1)%schedule_time} =>'),
                        (5, f'-- ({src} -> {dst})'),
                        (5, f'back_edge_mux_sel <= {mux_idx};'),
                    ],
                )
    vhdl.write_lines(
        f,
        [
            (4, 'when others =>'),
            (5, 'back_edge_mux_sel <= 0;'),
            (3, 'end case;'),
        ],
    )
    vhdl.common.synchronous_process_epilogue(
        f,
        clk='clk',
        name='shift_reg_back_edge_decode_proc',
    )

    # Shift register multiplexer logic
    vhdl.write(f, 1, '-- Multiplexers for shift register', start='\n')
    vhdl.common.synchronous_process_prologue(
        f,
        clk='clk',
        name='shift_reg_proc',
    )
    if sync_rst:
        vhdl.write(f, 3, 'if rst = \'1\' then')
        for reg_idx in range(reg_cnt):
            vhdl.write(f, 4, f'shift_reg({reg_idx}) <= (others => \'0\');')
        vhdl.write(f, 3, 'else')

    vhdl.write_lines(
        f,
        [
            (3, '-- Default case'),
            (3, 'shift_reg(0) <= p_0_in;'),
        ],
    )
    for reg_idx in range(1, reg_cnt):
        vhdl.write(f, 3, f'shift_reg({reg_idx}) <= shift_reg({reg_idx-1});')
    vhdl.write(f, 3, 'case back_edge_mux_sel is')
    for edge, mux_sel in back_edge_table.items():
        vhdl.write_lines(
            f,
            [
                (4, f'when {mux_sel} =>'),
                (5, f'shift_reg({edge[1]}) <= shift_reg({edge[0]});'),
            ],
        )
    vhdl.write_lines(
        f,
        [
            (4, 'when others => null;'),
            (3, 'end case;'),
        ],
    )

    if sync_rst:
        vhdl.write(f, 3, 'end if;')

    vhdl.common.synchronous_process_epilogue(
        f,
        clk='clk',
        name='shift_reg_proc',
    )

    # Output multiplexer decoding logic
    vhdl.write(f, 1, '-- Output muliplexer decoding logic', start='\n')
    vhdl.common.synchronous_process_prologue(f, clk='clk', name='out_mux_decode_proc')
    vhdl.write(f, 3, 'case schedule_cnt is')
    for i, entry in enumerate(forward_backward_table):
        if entry.outputs_from is not None:
            sel = output_mux_table[entry.outputs_from]
            vhdl.write(f, 4, f'when {(i-1)%schedule_time} =>')
            vhdl.write(f, 5, f'out_mux_sel <= {sel};')
    vhdl.write(f, 3, 'end case;')
    vhdl.common.synchronous_process_epilogue(f, clk='clk', name='out_mux_decode_proc')

    # Output multiplexer logic
    vhdl.write(f, 1, '-- Output muliplexer', start='\n')
    vhdl.common.synchronous_process_prologue(
        f,
        clk='clk',
        name='out_mux_proc',
    )
    vhdl.write(f, 3, 'case out_mux_sel is')
    for reg_i, mux_i in output_mux_table.items():
        vhdl.write(f, 4, f'when {mux_i} =>')
        if reg_i < 0:
            vhdl.write(f, 5, f'p_0_out <= p_{-1-reg_i}_in;')
        else:
            vhdl.write(f, 5, f'p_0_out <= shift_reg({reg_i});')
    vhdl.write(f, 3, 'end case;')
    vhdl.common.synchronous_process_epilogue(
        f,
        clk='clk',
        name='out_mux_proc',
    )

    vhdl.write(f, 0, f'end architecture {architecture_name};', start='\n')
