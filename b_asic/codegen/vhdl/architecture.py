"""
Module for code generation of VHDL architectures.
"""

from math import ceil, log2
from typing import TYPE_CHECKING, Dict, List, Optional, Set, TextIO, Tuple, cast

from b_asic.codegen.vhdl import common, write, write_lines
from b_asic.process import MemoryVariable

if TYPE_CHECKING:
    from b_asic.resources import ProcessCollection, _ForwardBackwardTable


def memory_based_storage(
    f: TextIO,
    assignment: List["ProcessCollection"],
    entity_name: str,
    word_length: int,
    read_ports: int,
    write_ports: int,
    total_ports: int,
    *,
    input_sync: bool = True,
    adr_mux_size: int = 1,
    adr_pipe_depth: int = 0,
):
    """
    Generate the VHDL architecture for a memory-based storage architecture.

    Settings should be sanitized when calling this function, e.g. from calling
    generate_memory_based_storage_vhdl from one of the memory classes.

    Parameters
    ----------
    f : TextIO
        File object (or other TextIO object) to write the architecture onto.
    assignment : list
        A possible cell assignment to use when generating the memory based storage.
        The cell assignment is a dictionary int to ProcessCollection where the integer
        corresponds to the cell to assign all MemoryVariables in corresponding process
        collection.
        If unset, each MemoryVariable will be assigned to a unique cell.
    entity_name : str
        The entity name for the resulting HDL.
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
        Adding registers to the inputs allow pipelining of address generation (which
        is added automatically). For large interleavers, this can improve timing
        significantly.
    adr_mux_size : int, default: 1
        Size of multiplexer if using address generation pipelining. Set to 1 for no
        multiplexer pipelining. If any other value than 1, `input_sync` must be set.
    adr_pipe_depth : int, default: 0
        Depth of address generation pipelining. Set to 0 for no multiplexer pipelining.
        If any other value than 0, `input_sync` must be set.
    """

    # Code settings
    mem_depth = len(assignment)
    architecture_name = "rtl"
    schedule_time = next(iter(assignment)).schedule_time

    # Address generation "ROMs"
    total_roms = adr_mux_size**adr_pipe_depth
    bits_per_mux = int(log2(adr_mux_size))
    elements_per_rom = int(
        2 ** ceil(log2(schedule_time / total_roms))
    )  # Next power-of-two

    # Write architecture header
    write(f, 0, f"architecture {architecture_name} of {entity_name} is", end="\n\n")

    #
    # Architecture declarative region begin
    #
    write(f, 1, "-- HDL memory description")
    common.constant_declaration(
        f, name="MEM_WL", signal_type="integer", value=word_length, name_pad=16
    )
    common.constant_declaration(
        f, name="MEM_DEPTH", signal_type="integer", value=mem_depth, name_pad=16
    )
    common.type_declaration(
        f, "mem_type", "array(0 to MEM_DEPTH-1) of std_logic_vector(MEM_WL-1 downto 0)"
    )
    common.signal_declaration(
        f,
        name="memory",
        signal_type="mem_type",
        name_pad=18,
        vivado_ram_style="distributed",  # Xilinx Vivado distributed RAM
    )

    # Schedule time counter
    write(f, 1, "-- Schedule counter", start="\n")
    common.constant_declaration(
        f,
        name="SCHEDULE_CNT_LEN",
        signal_type="integer",
        value=ceil(log2(schedule_time)),
        name_pad=16,
    )
    common.signal_declaration(
        f,
        name="schedule_cnt",
        signal_type="unsigned(SCHEDULE_CNT_LEN-1 downto 0)",
        name_pad=18,
    )
    for i in range(adr_pipe_depth):
        common.signal_declaration(
            f,
            name=f"schedule_cnt{i + 1}",
            signal_type="unsigned(SCHEDULE_CNT_LEN-1 downto 0)",
            name_pad=18,
        )
    common.constant_declaration(
        f,
        name="ADR_LEN",
        signal_type="integer",
        value=f"SCHEDULE_CNT_LEN-({int(log2(adr_mux_size))}*{adr_pipe_depth})",
        name_pad=16,
    )
    common.alias_declaration(
        f,
        name="schedule_cnt_adr",
        signal_type="unsigned(ADR_LEN-1 downto 0)",
        value="schedule_cnt(ADR_LEN-1 downto 0)",
        name_pad=19,
    )

    # Address generation signals
    write(f, 1, "-- Memory address generation", start="\n")
    for i in range(read_ports):
        common.signal_declaration(
            f, f"read_port_{i}", "std_logic_vector(MEM_WL-1 downto 0)", name_pad=18
        )
        common.signal_declaration(
            f, f"read_adr_{i}", "integer range 0 to MEM_DEPTH-1", name_pad=18
        )
        common.signal_declaration(f, f"read_en_{i}", "std_logic", name_pad=18)
    for i in range(write_ports):
        common.signal_declaration(
            f, f"write_port_{i}", "std_logic_vector(MEM_WL-1 downto 0)", name_pad=18
        )
        common.signal_declaration(
            f, f"write_adr_{i}", "integer range 0 to MEM_DEPTH-1", name_pad=18
        )
        common.signal_declaration(f, f"write_en_{i}", "std_logic", name_pad=18)

    # Address generation mutltiplexing signals
    write(f, 1, "-- Address generation multiplexing signals", start="\n")
    for write_port_idx in range(write_ports):
        for depth in range(adr_pipe_depth + 1):
            for rom in range(total_roms // adr_mux_size**depth):
                common.signal_declaration(
                    f,
                    f"write_adr_{write_port_idx}_{depth}_{rom}",
                    signal_type="integer range 0 to MEM_DEPTH-1",
                    name_pad=18,
                )
    for write_port_idx in range(write_ports):
        for depth in range(adr_pipe_depth + 1):
            for rom in range(total_roms // adr_mux_size**depth):
                common.signal_declaration(
                    f,
                    f"write_en_{write_port_idx}_{depth}_{rom}",
                    signal_type="std_logic",
                    name_pad=18,
                )
    for read_port_idx in range(read_ports):
        for depth in range(adr_pipe_depth + 1):
            for rom in range(total_roms // adr_mux_size**depth):
                common.signal_declaration(
                    f,
                    f"read_adr_{read_port_idx}_{depth}_{rom}",
                    signal_type="integer range 0 to MEM_DEPTH-1",
                    name_pad=18,
                )

    # Input sync signals
    if input_sync:
        write(f, 1, "-- Input synchronization", start="\n")
        for i in range(read_ports):
            common.signal_declaration(
                f, f"p_{i}_in_sync", "std_logic_vector(WL-1 downto 0)", name_pad=18
            )

    #
    # Architecture body begin
    #

    # Schedule counter
    write(f, 0, "begin", start="\n", end="\n\n")
    write(f, 1, "-- Schedule counter")
    common.synchronous_process_prologue(f=f, name="schedule_cnt_proc", clk="clk")
    write_lines(
        f,
        [
            (3, "if rst = '1' then"),
            (4, "schedule_cnt <= (others => '0');"),
            (3, "else"),
            (4, "if en = '1' then"),
            (5, f"if schedule_cnt = {schedule_time - 1} then"),
            (6, "schedule_cnt <= (others => '0');"),
            (5, "else"),
            (6, "schedule_cnt <= schedule_cnt + 1;"),
            (5, "end if;"),
            (4, "end if;"),
        ],
    )
    for i in range(adr_pipe_depth):
        if i == 0:
            write(f, 4, "schedule_cnt1 <= schedule_cnt;")
        else:
            write(f, 4, f"schedule_cnt{i + 1} <= schedule_cnt{i};")
    write(f, 3, "end if;")
    common.synchronous_process_epilogue(
        f=f,
        name="schedule_cnt_proc",
        clk="clk",
    )

    # Input synchronization
    if input_sync:
        write(f, 1, "-- Input synchronization", start="\n")
        common.synchronous_process_prologue(
            f=f,
            name="input_sync_proc",
            clk="clk",
        )
        for i in range(read_ports):
            write(f, 3, f"p_{i}_in_sync <= p_{i}_in;")
        common.synchronous_process_epilogue(
            f=f,
            name="input_sync_proc",
            clk="clk",
        )

    # Infer the memory
    write(f, 1, "-- Memory", start="\n")
    common.asynchronous_read_memory(
        f=f,
        clk="clk",
        name=f"mem_{0}_proc",
        read_ports={
            (f"read_port_{i}", f"read_adr_{i}", f"read_en_{i}")
            for i in range(read_ports)
        },
        write_ports={
            (f"write_port_{i}", f"write_adr_{i}", f"write_en_{i}")
            for i in range(write_ports)
        },
    )
    write(f, 1, f"read_adr_0 <= read_adr_0_{adr_pipe_depth}_0;")
    write(f, 1, f"write_adr_0 <= write_adr_0_{adr_pipe_depth}_0;")
    write(f, 1, f"write_en_0 <= write_en_0_{adr_pipe_depth}_0;")
    if input_sync:
        write(f, 1, "write_port_0 <= p_0_in_sync;")
    else:
        write(f, 1, "write_port_0 <= p_0_in;")

    # Input and output assignments
    write(f, 1, "-- Input and output assignments", start="\n")
    p_zero_exec = filter(
        lambda p: p.execution_time == 0, (p for pc in assignment for p in pc)
    )
    common.synchronous_process_prologue(
        f,
        clk="clk",
        name="output_reg_proc",
    )
    write(f, 3, "case to_integer(schedule_cnt) is")
    for p in p_zero_exec:
        if input_sync:
            write_time = (p.start_time + 1) % schedule_time
            if adr_pipe_depth:
                write(
                    f,
                    4,
                    f"when {write_time}+{adr_pipe_depth} => p_0_out <= p_0_in_sync;",
                )
            else:
                write(f, 4, f"when {write_time} => p_0_out <= p_0_in_sync;")
        else:
            write_time = (p.start_time) % schedule_time
            write(f, 4, f"when {write_time} => p_0_out <= p_0_in;")
    write_lines(
        f,
        [
            (4, "when others => p_0_out <= read_port_0;"),
            (3, "end case;"),
        ],
    )
    common.synchronous_process_epilogue(
        f,
        clk="clk",
        name="output_reg_proc",
    )

    #
    # ROM Write address generation
    #
    write(f, 1, "--", start="\n")
    write(f, 1, "-- Memory write address generation", start="")
    write(f, 1, "--", end="\n")

    # Extract all the write addresses
    write_list: List[Optional[Tuple[int, MemoryVariable]]] = [
        None for _ in range(schedule_time)
    ]
    for i, collection in enumerate(assignment):
        for mv in collection:
            mv = cast(MemoryVariable, mv)
            if mv.start_time >= schedule_time:
                raise ValueError("start_time greater than schedule_time")
            if mv.execution_time:
                write_list[mv.start_time] = (i, mv)

    for rom in range(total_roms):
        if input_sync:
            common.synchronous_process_prologue(
                f, clk="clk", name=f"mem_write_address_proc_{0}_{rom}"
            )
        else:
            common.process_prologue(
                f, sensitivity_list="schedule_cnt_adr", name="mem_write_address_proc"
            )
        write(f, 3, "case to_integer(schedule_cnt_adr) is")
        list_start_idx = rom * elements_per_rom
        list_stop_idx = list_start_idx + elements_per_rom
        for i, mv in filter(None, write_list[list_start_idx:list_stop_idx]):
            write_lines(
                f,
                [
                    (4, f"-- {mv!r}"),
                    (
                        4,
                        (
                            f"when {mv.start_time % schedule_time} mod"
                            f" {elements_per_rom} =>"
                        ),
                    ),
                    (5, f"write_adr_0_{0}_{rom} <= {i};"),
                    (5, f"write_en_0_{0}_{rom} <= '1';"),
                ],
            )
        write_lines(
            f,
            [
                (4, "when others =>"),
                (5, f"write_adr_0_{0}_{rom} <= 0;"),
                (5, f"write_en_0_{0}_{rom} <= '0';"),
                (3, "end case;"),
            ],
        )
        if input_sync:
            common.synchronous_process_epilogue(
                f, clk="clk", name=f"mem_write_address_proc_{0}_{rom}"
            )
            write(f, 1, "")
        else:
            common.process_epilogue(
                f, sensitivity_list="clk", name=f"mem_write_address_proc_{0}_{rom}"
            )
            write(f, 1, "")

    # Write address multiplexing layers
    for layer in range(adr_pipe_depth):
        for mux_idx in range(total_roms // adr_mux_size ** (layer + 1)):
            common.synchronous_process_prologue(
                f, clk="clk", name=f"mem_write_address_proc{layer + 1}_{mux_idx}"
            )
            write(
                f,
                3,
                (
                    f"case to_integer(schedule_cnt{layer + 1}("
                    f"ADR_LEN+{layer * bits_per_mux + bits_per_mux - 1} downto "
                    f"ADR_LEN+{layer * bits_per_mux}"
                    ")) is"
                ),
            )
            for in_idx in range(adr_mux_size):
                out_idx = in_idx + mux_idx * adr_mux_size
                write(
                    f,
                    4,
                    (
                        f"-- {adr_mux_size}-to-1 MUX layer: "
                        f"layer={layer}, MUX={mux_idx}, input={in_idx}"
                    ),
                )
                write_lines(
                    f,
                    [
                        (4, f"when {in_idx} =>"),
                        (
                            5,
                            (
                                f"write_adr_0_{layer + 1}_{mux_idx} <="
                                f" write_adr_0_{layer}_{out_idx};"
                            ),
                        ),
                        (
                            5,
                            (
                                f"write_en_0_{layer + 1}_{mux_idx} <="
                                f" write_en_0_{layer}_{out_idx};"
                            ),
                        ),
                    ],
                )
            write_lines(
                f,
                [
                    (4, "when others =>"),
                    (5, f"write_adr_0_{layer + 1}_{mux_idx} <= 0;"),
                    (5, f"write_en_0_{layer + 1}_{mux_idx} <= '0';"),
                    (3, "end case;"),
                ],
            )
            common.synchronous_process_epilogue(
                f, clk="clk", name=f"mem_write_address_proc{layer + 1}_{mux_idx}"
            )
            write(f, 1, "")

    #
    # ROM read address generation
    #
    write(f, 1, "--", start="\n")
    write(f, 1, "-- Memory read address generation", start="")
    write(f, 1, "--", end="\n")

    # Extract all the read addresses
    read_list: List[Optional[Tuple[int, MemoryVariable]]] = [
        None for _ in range(schedule_time)
    ]
    for i, collection in enumerate(assignment):
        for mv in collection:
            mv = cast(MemoryVariable, mv)
            for read_time in mv.reads.values():
                read_list[
                    (mv.start_time + read_time - int(not (input_sync))) % schedule_time
                ] = (i, mv)

    for rom in range(total_roms):
        if input_sync:
            common.synchronous_process_prologue(
                f, clk="clk", name=f"mem_read_address_proc_{0}_{rom}"
            )
        else:
            common.process_prologue(
                f, sensitivity_list="schedule_cnt_adr", name="mem_read_address_proc"
            )
        write(f, 3, "case to_integer(schedule_cnt_adr) is")
        list_start_idx = rom * elements_per_rom
        list_stop_idx = list_start_idx + elements_per_rom
        for idx in range(list_start_idx, list_stop_idx):
            if idx < schedule_time:
                tp = read_list[idx]
                if tp is None:
                    continue
                i = tp[0]
                mv = tp[1]
                write_lines(
                    f,
                    [
                        (4, f"-- {mv!r}"),
                        (4, f"when {idx} mod {elements_per_rom} =>"),
                        (5, f"read_adr_0_{0}_{rom} <= {i};"),
                    ],
                )
        write_lines(
            f,
            [
                (4, "when others =>"),
                (5, f"read_adr_0_{0}_{rom} <= 0;"),
                (3, "end case;"),
            ],
        )
        if input_sync:
            common.synchronous_process_epilogue(
                f, clk="clk", name=f"mem_read_address_proc_{0}_{rom}"
            )
            write(f, 1, "")
        else:
            common.process_epilogue(
                f, sensitivity_list="clk", name=f"mem_read_address_proc_{0}_{rom}"
            )
            write(f, 1, "")

    # Read address multiplexing layers
    for layer in range(adr_pipe_depth):
        for mux_idx in range(total_roms // adr_mux_size ** (layer + 1)):
            common.synchronous_process_prologue(
                f, clk="clk", name=f"mem_read_address_proc{layer + 1}_{mux_idx}"
            )
            write(
                f,
                3,
                (
                    f"case to_integer(schedule_cnt{layer + 1}("
                    f"ADR_LEN+{layer * bits_per_mux + bits_per_mux - 1} downto "
                    f"ADR_LEN+{layer * bits_per_mux}"
                    ")) is"
                ),
            )
            for in_idx in range(adr_mux_size):
                out_idx = in_idx + mux_idx * adr_mux_size
                write(
                    f,
                    4,
                    (
                        f"-- {adr_mux_size}-to-1 MUX layer: "
                        f"layer={layer}, MUX={mux_idx}, input={in_idx}"
                    ),
                )
                write_lines(
                    f,
                    [
                        (4, f"when {in_idx} =>"),
                        (
                            5,
                            (
                                f"read_adr_0_{layer + 1}_{mux_idx} <="
                                f" read_adr_0_{layer}_{out_idx};"
                            ),
                        ),
                    ],
                )
            write_lines(
                f,
                [
                    (4, "when others =>"),
                    (5, f"read_adr_0_{layer + 1}_{mux_idx} <= 0;"),
                    (3, "end case;"),
                ],
            )
            common.synchronous_process_epilogue(
                f, clk="clk", name=f"mem_read_address_proc{layer + 1}_{mux_idx}"
            )
            write(f, 1, "")

    write(f, 0, f"end architecture {architecture_name};", start="\n")


def register_based_storage(
    f: TextIO,
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
    output_regs = {
        entry.outputs_from
        for entry in forward_backward_table.table
        if entry.outputs_from is not None
    }

    # Table with mapping: register to output multiplexer index
    output_mux_table: Dict[int, int] = {reg: i for i, reg in enumerate(output_regs)}

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
    # Architecture declarative region begin
    #
    # Write architecture header
    write(f, 0, f"architecture {architecture_name} of {entity_name} is", end="\n\n")

    # Schedule time counter
    write(f, 1, "-- Schedule counter")
    common.signal_declaration(
        f,
        name="schedule_cnt",
        signal_type=f"integer range 0 to {schedule_time}-1",
        name_pad=18,
        default_value="0",
    )

    # Shift register
    write(f, 1, "-- Shift register", start="\n")
    common.type_declaration(
        f,
        name="shift_reg_type",
        alias=f"array(0 to {reg_cnt}-1) of std_logic_vector(WL-1 downto 0)",
    )
    common.signal_declaration(
        f,
        name="shift_reg",
        signal_type="shift_reg_type",
        name_pad=18,
    )

    # Back edge mux decoder
    write(f, 1, "-- Back-edge mux select signal", start="\n")
    common.signal_declaration(
        f,
        name="back_edge_mux_sel",
        signal_type=f"integer range 0 to {len(back_edges)}",
        name_pad=18,
    )

    # Output mux selector
    write(f, 1, "-- Output mux select signal", start="\n")
    common.signal_declaration(
        f,
        name="out_mux_sel",
        signal_type=f"integer range 0 to {len(output_regs) - 1}",
        name_pad=18,
    )

    #
    # Architecture body begin
    #
    write(f, 0, "begin", start="\n", end="\n\n")
    write(f, 1, "-- Schedule counter")
    common.synchronous_process_prologue(
        f=f,
        name="schedule_cnt_proc",
        clk="clk",
    )
    write_lines(
        f,
        [
            (4, "if en = '1' then"),
            (5, f"if schedule_cnt = {schedule_time}-1 then"),
            (6, "schedule_cnt <= 0;"),
            (5, "else"),
            (6, "schedule_cnt <= schedule_cnt + 1;"),
            (5, "end if;"),
            (4, "end if;"),
        ],
    )
    common.synchronous_process_epilogue(
        f=f,
        name="schedule_cnt_proc",
        clk="clk",
    )

    # Shift register back-edge decoding
    write(f, 1, "-- Shift register back-edge decoding", start="\n")
    common.synchronous_process_prologue(
        f,
        clk="clk",
        name="shift_reg_back_edge_decode_proc",
    )
    write(f, 3, "case schedule_cnt is")
    for time, entry in enumerate(forward_backward_table):
        if entry.back_edge_to:
            assert len(entry.back_edge_to) == 1
            for src, dst in entry.back_edge_to.items():
                mux_idx = back_edge_table[(src, dst)]
                write_lines(
                    f,
                    [
                        (4, f"when {(time - 1) % schedule_time} =>"),
                        (5, f"-- ({src} -> {dst})"),
                        (5, f"back_edge_mux_sel <= {mux_idx};"),
                    ],
                )
    write_lines(
        f,
        [
            (4, "when others =>"),
            (5, "back_edge_mux_sel <= 0;"),
            (3, "end case;"),
        ],
    )
    common.synchronous_process_epilogue(
        f,
        clk="clk",
        name="shift_reg_back_edge_decode_proc",
    )

    # Shift register multiplexer logic
    write(f, 1, "-- Multiplexers for shift register", start="\n")
    common.synchronous_process_prologue(
        f,
        clk="clk",
        name="shift_reg_proc",
    )
    if sync_rst:
        write(f, 3, "if rst = '1' then")
        for reg_idx in range(reg_cnt):
            write(f, 4, f"shift_reg({reg_idx}) <= (others => '0');")
        write(f, 3, "else")

    write_lines(
        f,
        [
            (3, "-- Default case"),
            (3, "shift_reg(0) <= p_0_in;"),
        ],
    )
    for reg_idx in range(1, reg_cnt):
        write(f, 3, f"shift_reg({reg_idx}) <= shift_reg({reg_idx - 1});")
    write(f, 3, "case back_edge_mux_sel is")
    for edge, mux_sel in back_edge_table.items():
        write_lines(
            f,
            [
                (4, f"when {mux_sel} =>"),
                (5, f"shift_reg({edge[1]}) <= shift_reg({edge[0]});"),
            ],
        )
    write_lines(
        f,
        [
            (4, "when others => null;"),
            (3, "end case;"),
        ],
    )

    if sync_rst:
        write(f, 3, "end if;")

    common.synchronous_process_epilogue(
        f,
        clk="clk",
        name="shift_reg_proc",
    )

    # Output multiplexer decoding logic
    write(f, 1, "-- Output multiplexer decoding logic", start="\n")
    common.synchronous_process_prologue(f, clk="clk", name="out_mux_decode_proc")
    write(f, 3, "case schedule_cnt is")
    for i, entry in enumerate(forward_backward_table):
        if entry.outputs_from is not None:
            sel = output_mux_table[entry.outputs_from]
            write(f, 4, f"when {(i - 1) % schedule_time} =>")
            write(f, 5, f"out_mux_sel <= {sel};")
    write(f, 3, "end case;")
    common.synchronous_process_epilogue(f, clk="clk", name="out_mux_decode_proc")

    # Output multiplexer logic
    write(f, 1, "-- Output multiplexer", start="\n")
    common.synchronous_process_prologue(
        f,
        clk="clk",
        name="out_mux_proc",
    )
    write(f, 3, "case out_mux_sel is")
    for reg_i, mux_i in output_mux_table.items():
        write(f, 4, f"when {mux_i} =>")
        if reg_i < 0:
            write(f, 5, f"p_0_out <= p_{-1 - reg_i}_in;")
        else:
            write(f, 5, f"p_0_out <= shift_reg({reg_i});")
    write(f, 3, "end case;")
    common.synchronous_process_epilogue(
        f,
        clk="clk",
        name="out_mux_proc",
    )

    write(f, 0, f"end architecture {architecture_name};", start="\n")
