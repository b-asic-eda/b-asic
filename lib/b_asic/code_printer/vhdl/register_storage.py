"""
Module for VHDL code generation of register based storage.
"""

from typing import TYPE_CHECKING, TextIO

from b_asic.code_printer.vhdl import common, memory_storage
from b_asic.data_type import _VhdlDataType
from b_asic.resources import _ForwardBackwardTable

if TYPE_CHECKING:
    from b_asic.architecture import Memory


def entity(
    f: TextIO,
    memory: "Memory",
    dt: _VhdlDataType,
    std_logic_vector: bool = True,
) -> None:
    """
    Generate entity for register-based storage.

    Parameters
    ----------
    f : TextIO
        File object to write to.
    memory : Memory
        Memory object to generate entity for.
    dt : _VhdlDataType
        Data type information.
    std_logic_vector : bool, default: True
        If True, use std_logic_vector for data signals. If False, use dt.type_str.
    """
    memory_storage.entity(
        f,
        memory,
        dt,
        external_schedule_counter=True,
        std_logic_vector=std_logic_vector,
    )


def architecture(
    f: TextIO,
    forward_backward_table: "_ForwardBackwardTable",
    memory: "Memory",
    dt: _VhdlDataType,
    sync_rst: bool = False,
    async_rst: bool = False,
    std_logic_vector: bool = True,
    pipeline_control_signals: bool = False,
) -> None:
    """
    Generate architecture for register-based storage.

    Parameters
    ----------
    f : TextIO
        File object to write to.
    forward_backward_table : _ForwardBackwardTable
        Forward-backward allocation table.
    memory : Memory
        Memory object.
    dt : _VhdlDataType
        Data type information.
    sync_rst : bool, default: False
        Enable synchronous reset.
    async_rst : bool, default: False
        Enable asynchronous reset.
    std_logic_vector : bool, default: True
        If True, use std_logic_vector for data signals. If False, use dt.type_str.
    pipeline_control_signals : bool, default: False
        If True, register the control signals.
    """
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
        name="schedule_cnt_int",
        signal_type=f"integer range 0 to {schedule_time - 1}",
        name_pad=18,
    )

    # Shift register
    common.write(f, 1, "-- Shift register", start="\n")
    data_type = (
        f"std_logic_vector({dt.high} downto 0)" if std_logic_vector else dt.type_str
    )
    common.type_declaration(
        f,
        name="shift_reg_type",
        alias=f"array(0 to {reg_cnt}-1) of {data_type}",
    )
    common.signal_declaration(
        f,
        name="shift_reg",
        signal_type="shift_reg_type",
        name_pad=18,
        default_value=f"(others => {dt.init_val})",
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

    # Schedule counter logic
    # Convert external unsigned schedule_cnt to integer
    common.write(f, 1, "-- Convert unsigned schedule counter to integer", start="\n")
    common.write(f, 1, "schedule_cnt_int <= to_integer(schedule_cnt);")

    # Shift register back-edge decoding
    common.write(f, 1, "-- Shift register back-edge decoding", start="\n")
    if pipeline_control_signals:
        common.synchronous_process_prologue(
            f, clk="clk", name="shift_reg_back_edge_decode_proc"
        )
        common.write(f, 3, "if en = '1' then")
        common.write(f, 4, "case schedule_cnt_int is")
        for time, entry in enumerate(forward_backward_table):
            if entry.back_edge_to:
                assert len(entry.back_edge_to) == 1
                for src, dst in entry.back_edge_to.items():
                    mux_idx = back_edge_table[(src, dst)]
                    time_val = (time - 1) % schedule_time
                    common.write_lines(
                        f,
                        [
                            (5, f"when {time_val} =>"),
                            (6, f"-- ({src} -> {dst})"),
                            (6, f"back_edge_mux_sel <= {mux_idx};"),
                        ],
                    )
        common.write_lines(
            f,
            [
                (5, "when others =>"),
                (6, "back_edge_mux_sel <= 0;"),
                (4, "end case;"),
                (3, "end if;"),
            ],
        )
        common.synchronous_process_epilogue(
            f,
            clk="clk",
            name="shift_reg_back_edge_decode_proc",
        )
    else:
        common.write(f, 1, "with schedule_cnt_int select")
        common.write(f, 2, "back_edge_mux_sel <=")
        for time, entry in enumerate(forward_backward_table):
            if entry.back_edge_to:
                assert len(entry.back_edge_to) == 1
                for src, dst in entry.back_edge_to.items():
                    mux_idx = back_edge_table[(src, dst)]
                    time_val = time % schedule_time
                    common.write(
                        f, 3, f"{mux_idx} when {time_val}, -- ({src} -> {dst})"
                    )
        common.write(f, 3, "0 when others;")

    # Shift register multiplexer logic
    common.write(f, 1, "-- Multiplexers for shift register", start="\n")
    common.synchronous_process_prologue(f, clk="clk", name="shift_reg_proc")
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
    decode_entries = [
        (i % schedule_time, output_mux_table[entry.outputs_from])
        for i, entry in enumerate(forward_backward_table)
        if entry.outputs_from is not None
    ]
    common.write(f, 1, "with schedule_cnt_int select")
    common.write(f, 2, "out_mux_sel <=")
    for time_val, sel in decode_entries:
        common.write(f, 3, f"{sel} when {time_val},")
    common.write(f, 3, "0 when others;")

    # Output multiplexer logic
    common.write(f, 1, "-- Output multiplexer", start="\n")
    mux_items = list(output_mux_table.items())
    common.write(f, 1, "with out_mux_sel select")
    common.write(f, 2, "p_0_out <=")
    for reg_i, mux_i in mux_items:
        rhs = f"p_{-1 - reg_i}_in" if reg_i < 0 else f"shift_reg({reg_i})"
        common.write(f, 3, f"{rhs} when {mux_i},")
    common.write(f, 3, "(others => '0') when others;")

    common.write(f, 0, "end architecture rtl;", start="\n")
