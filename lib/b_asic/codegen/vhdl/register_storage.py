"""
Module for VHDL code generation of register based storage.
"""

from typing import TYPE_CHECKING, TextIO

from b_asic.codegen.vhdl import common, memory_storage
from b_asic.resources import _ForwardBackwardTable

if TYPE_CHECKING:
    from b_asic.architecture import Memory, WordLengths


def entity(f: TextIO, memory: "Memory", wl: "WordLengths") -> None:
    memory_storage.entity(f, memory, wl)


def architecture(
    f: TextIO,
    forward_backward_table: "_ForwardBackwardTable",
    memory: "Memory",
    sync_rst: bool = False,
    async_rst: bool = False,
) -> None:
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
    output_mux_table: dict[int, int] = {reg: i for i, reg in enumerate(output_regs)}

    # Back-edge register indices
    back_edges: set[tuple[int, int]] = {
        (frm, to)
        for entry in forward_backward_table
        for frm, to in entry.back_edge_to.items()
    }
    back_edge_table: dict[tuple[int, int], int] = {
        edge: i + 1 for i, edge in enumerate(back_edges)
    }

    #
    # Architecture declarative region begin
    #
    # Write architecture header
    common.write(f, 0, f"architecture rtl of {memory.entity_name} is", end="\n\n")

    # Schedule time counter
    common.write(f, 1, "-- Schedule counter")
    common.signal_declaration(
        f,
        name="schedule_cnt",
        signal_type=f"integer range 0 to {schedule_time}-1",
        name_pad=18,
        default_value="0",
    )

    # Shift register
    common.write(f, 1, "-- Shift register", start="\n")
    common.type_declaration(
        f,
        name="shift_reg_type",
        alias=f"array(0 to {reg_cnt}-1) of signed(WL_INTERNAL_INT+WL_INTERNAL_FRAC-1 downto 0)",
    )
    common.signal_declaration(
        f,
        name="shift_reg",
        signal_type="shift_reg_type",
        name_pad=18,
    )

    # Back edge mux decoder
    common.write(f, 1, "-- Back-edge mux select signal", start="\n")
    common.signal_declaration(
        f,
        name="back_edge_mux_sel",
        signal_type=f"integer range 0 to {len(back_edges)}",
        name_pad=18,
    )

    # Output mux selector
    common.write(f, 1, "-- Output mux select signal", start="\n")
    common.signal_declaration(
        f,
        name="out_mux_sel",
        signal_type=f"integer range 0 to {len(output_regs) - 1}",
        name_pad=18,
    )

    #
    # Architecture body begin
    #
    common.write(f, 0, "begin", start="\n", end="\n\n")
    common.write(f, 1, "-- Schedule counter")
    common.synchronous_process_prologue(f, name="schedule_cnt_proc")
    common.write_lines(
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
    common.write(f, 1, "-- Shift register back-edge decoding", start="\n")
    common.synchronous_process_prologue(f, name="shift_reg_back_edge_decode_proc")
    common.write(f, 3, "case schedule_cnt is")
    for time, entry in enumerate(forward_backward_table):
        if entry.back_edge_to:
            assert len(entry.back_edge_to) == 1
            for src, dst in entry.back_edge_to.items():
                mux_idx = back_edge_table[(src, dst)]
                common.write_lines(
                    f,
                    [
                        (4, f"when {(time - 1) % schedule_time} =>"),
                        (5, f"-- ({src} -> {dst})"),
                        (5, f"back_edge_mux_sel <= {mux_idx};"),
                    ],
                )
    common.write_lines(
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
    common.write(f, 1, "-- Multiplexers for shift register", start="\n")
    common.synchronous_process_prologue(f, name="shift_reg_proc")
    if sync_rst:
        common.write(f, 3, "if rst = '1' then")
        for reg_idx in range(reg_cnt):
            common.write(f, 4, f"shift_reg({reg_idx}) <= (others => '0');")
        common.write(f, 3, "else")

    common.write_lines(
        f,
        [
            (3, "-- Default case"),
            (3, "shift_reg(0) <= p_0_in;"),
        ],
    )
    for reg_idx in range(1, reg_cnt):
        common.write(f, 3, f"shift_reg({reg_idx}) <= shift_reg({reg_idx - 1});")
    common.write(f, 3, "case back_edge_mux_sel is")
    for edge, mux_sel in back_edge_table.items():
        common.write_lines(
            f,
            [
                (4, f"when {mux_sel} =>"),
                (5, f"shift_reg({edge[1]}) <= shift_reg({edge[0]});"),
            ],
        )
    common.write_lines(
        f,
        [
            (4, "when others => null;"),
            (3, "end case;"),
        ],
    )

    if sync_rst:
        common.write(f, 3, "end if;")

    common.synchronous_process_epilogue(
        f,
        clk="clk",
        name="shift_reg_proc",
    )

    # Output multiplexer decoding logic
    common.write(f, 1, "-- Output multiplexer decoding logic", start="\n")
    common.synchronous_process_prologue(f, name="out_mux_decode_proc")
    common.write(f, 3, "case schedule_cnt is")
    for i, entry in enumerate(forward_backward_table):
        if entry.outputs_from is not None:
            sel = output_mux_table[entry.outputs_from]
            common.write(f, 4, f"when {(i - 1) % schedule_time} =>")
            common.write(f, 5, f"out_mux_sel <= {sel};")
    common.write(f, 3, "end case;")
    common.synchronous_process_epilogue(f, clk="clk", name="out_mux_decode_proc")

    # Output multiplexer logic
    common.write(f, 1, "-- Output multiplexer", start="\n")
    common.synchronous_process_prologue(f, name="out_mux_proc")
    common.write(f, 3, "case out_mux_sel is")
    for reg_i, mux_i in output_mux_table.items():
        common.write(f, 4, f"when {mux_i} =>")
        if reg_i < 0:
            common.write(f, 5, f"p_0_out <= p_{-1 - reg_i}_in;")
        else:
            common.write(f, 5, f"p_0_out <= shift_reg({reg_i});")
    common.write(f, 3, "end case;")
    common.synchronous_process_epilogue(
        f,
        clk="clk",
        name="out_mux_proc",
    )

    common.write(f, 0, "end architecture rtl;", start="\n")
