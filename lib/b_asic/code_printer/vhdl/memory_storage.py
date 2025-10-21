"""
Module for VHDL code generation of memory based storage.
"""

import math
from typing import TYPE_CHECKING, Literal, TextIO, cast

from b_asic.code_printer.vhdl import common
from b_asic.code_printer.vhdl.util import schedule_time_type, unsigned_type
from b_asic.data_type import VhdlDataType
from b_asic.process import MemoryVariable, PlainMemoryVariable

if TYPE_CHECKING:
    from b_asic.architecture import Memory


def entity(f: TextIO, mem: "Memory", dt: VhdlDataType) -> None:
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

    ports = [
        "clk : in std_logic",
        f"schedule_cnt : in {schedule_time_type(mem.schedule_time)}",
    ]
    ports += [f"p_{count}_in : in {dt.type_str}" for count in range(mem.input_count)]
    ports += [f"p_{count}_out : out {dt.type_str}" for count in range(mem.output_count)]
    common.entity_declaration(f, mem.entity_name, ports=ports)


def architecture(
    f: TextIO,
    memory: "Memory",
    dt: VhdlDataType,
    *,
    input_sync: bool = True,
    output_sync: bool = True,
    adr_mux_size: int = 1,
    adr_pipe_depth: int = 0,
    vivado_ram_style: (
        Literal["block", "distributed", "registers", "ultra", "mixed", "auto"] | None
    ) = None,
    quartus_ram_style: (
        Literal["M4K", "M9K", "M10K", "M20K", "M144K", "MLAB", "logic"] | None
    ) = None,
) -> None:
    """
    Generate the VHDL architecture for a memory-based storage architecture.

    Settings should be sanitized when calling this function, e.g. from calling
    generate_memory_based_storage_vhdl from one of the memory classes.

    Parameters
    ----------
    f : TextIO
        File object (or other TextIO object) to write the architecture onto.
    memory : Memory
        Memory object to generate code for.
    dt : DataType
        Meta information of data signals.
    input_sync : bool, default: True
        Add registers to the input signals (enable signal and data input signals).
        Adding registers to the inputs allow pipelining of address generation (which
        is added automatically). For large interleavers, this can improve timing
        significantly.
    output_sync : bool, default: True
        Add registers to the output signal.
    adr_mux_size : int, default: 1
        Size of multiplexer if using address generation pipelining. Set to 1 for no
        multiplexer pipelining. If any other value than 1, `input_sync` must be set.
    adr_pipe_depth : int, default: 0
        Depth of address generation pipelining. Set to 0 for no multiplexer pipelining.
        If any other value than 0, `input_sync` must be set.
    vivado_ram_style : str, optional
        An optional Xilinx Vivado RAM style attribute to apply to this memory.
        If set, exactly one of: "block", "distributed", "registers", "ultra", "mixed" or "auto".
    quartus_ram_style : str, optional
        An optional Quartus Prime RAM style attribute to apply to this memory.
        If set, exactly one of: "M4K", "M9K", "M10K", "M20K", "M144K", "MLAB" or "logic".
    """
    # Code settings
    mem_depth = len(memory.assignment)
    mem_adress_bits = mem_depth.bit_length()
    schedule_time = next(iter(memory.assignment)).schedule_time

    # Address generation "ROMs"
    total_roms = adr_mux_size**adr_pipe_depth
    bits_per_mux = int(math.log2(adr_mux_size))
    elements_per_rom = int(
        2 ** math.ceil(math.log2(schedule_time / total_roms))
    )  # Next power-of-two

    # Write architecture header
    common.write(f, 0, f"architecture rtl of {memory.entity_name} is", end="\n\n")

    #
    # Architecture declarative region begin
    #
    common.write(f, 1, "-- HDL memory description")
    common.type_declaration(
        f, "mem_type", f"array(0 to {mem_depth - 1}) of {dt.type_str}"
    )
    if vivado_ram_style is not None:
        common.signal_declaration(
            f,
            name="memory",
            signal_type="mem_type",
            default_value=f"(others => {dt.init_val})",
            vivado_ram_style=vivado_ram_style,
        )
    elif quartus_ram_style is not None:
        common.signal_declaration(
            f,
            name="memory",
            signal_type="mem_type",
            default_value=f"(others => {dt.init_val})",
            quartus_ram_style=quartus_ram_style,
        )
    else:
        common.signal_declaration(
            f,
            name="memory",
            signal_type="mem_type",
            default_value=f"(others => {dt.init_val})",
        )

    # Schedule time counter pipelined signals
    for i in range(adr_pipe_depth):
        common.signal_declaration(
            f,
            name=f"schedule_cnt{i + 1}",
            signal_type=schedule_time_type(memory.schedule_time),
            default_value=f"(others => {dt.init_val})",
        )
    ADR_LEN = (
        memory.schedule_time.bit_length()
        - int(math.log2(adr_mux_size)) * adr_pipe_depth
    )

    common.alias_declaration(
        f,
        name="schedule_cnt_adr",
        signal_type=unsigned_type(ADR_LEN),
        value=f"schedule_cnt({ADR_LEN - 1} downto 0)",
    )

    # Address generation signals
    common.write(f, 1, "-- Memory address generation", start="\n")
    for i in range(memory.input_count):
        common.signal_declaration(f, f"read_port_{i}", dt.type_str)
        common.signal_declaration(f, f"read_adr_{i}", unsigned_type(mem_adress_bits))
        common.signal_declaration(f, f"read_en_{i}", "std_logic")
    for i in range(memory.output_count):
        common.signal_declaration(f, f"write_port_{i}", dt.type_str)
        common.signal_declaration(f, f"write_adr_{i}", unsigned_type(mem_adress_bits))
        common.signal_declaration(f, f"write_en_{i}", "std_logic")

    # Address generation mutltiplexing signals
    common.write(f, 1, "-- Address generation multiplexing signals", start="\n")
    for write_port_idx in range(memory.output_count):
        for depth in range(adr_pipe_depth + 1):
            for rom in range(total_roms // adr_mux_size**depth):
                common.signal_declaration(
                    f,
                    f"write_adr_{write_port_idx}_{depth}_{rom}",
                    unsigned_type(mem_adress_bits),
                )
    for write_port_idx in range(memory.output_count):
        for depth in range(adr_pipe_depth + 1):
            for rom in range(total_roms // adr_mux_size**depth):
                common.signal_declaration(
                    f,
                    f"write_en_{write_port_idx}_{depth}_{rom}",
                    signal_type="std_logic",
                )
    for read_port_idx in range(memory.input_count):
        for depth in range(adr_pipe_depth + 1):
            for rom in range(total_roms // adr_mux_size**depth):
                common.signal_declaration(
                    f,
                    f"read_adr_{read_port_idx}_{depth}_{rom}",
                    unsigned_type(mem_adress_bits),
                )

    # Input sync signals
    if input_sync:
        common.write(f, 1, "-- Input synchronization", start="\n")
        for i in range(memory.input_count):
            common.signal_declaration(f, f"p_{i}_in_sync", dt.type_str)

    #
    # Architecture body begin
    #
    # common.write(f, 1, "begin")
    common.write(f, 0, "begin", start="\n", end="\n\n")

    # Schedule counter pipelining
    if adr_pipe_depth > 0:
        common.write(f, 1, "-- Schedule counter")
        common.synchronous_process_prologue(f, name="schedule_cnt_proc")
        for i in range(adr_pipe_depth):
            if i == 0:
                common.write(f, 4, "schedule_cnt1 <= schedule_cnt;")
            else:
                common.write(f, 4, f"schedule_cnt{i + 1} <= schedule_cnt{i};")
        common.write(f, 3, "end if;")
        common.synchronous_process_epilogue(
            f=f,
            name="schedule_cnt_proc",
            clk="clk",
        )

    # Input synchronization
    if input_sync:
        common.write(f, 1, "-- Input synchronization", start="\n")
        common.synchronous_process_prologue(f, name="input_sync_proc")
        for i in range(memory.input_count):
            common.write(f, 3, f"p_{i}_in_sync <= p_{i}_in;")
        common.synchronous_process_epilogue(f, name="input_sync_proc")

    # Infer the memory
    common.write(f, 1, "-- Memory", start="\n")
    common.asynchronous_read_memory(
        f=f,
        clk="clk",
        name=f"mem_{0}_proc",
        read_ports={
            (f"read_port_{i}", f"read_adr_{i}", f"read_en_{i}")
            for i in range(memory.input_count)
        },
        write_ports={
            (f"write_port_{i}", f"write_adr_{i}", f"write_en_{i}")
            for i in range(memory.output_count)
        },
    )
    common.write(f, 1, f"read_adr_0 <= read_adr_0_{adr_pipe_depth}_0;")
    common.write(f, 1, f"write_adr_0 <= write_adr_0_{adr_pipe_depth}_0;")
    common.write(f, 1, f"write_en_0 <= write_en_0_{adr_pipe_depth}_0;")
    if input_sync:
        common.write(f, 1, "write_port_0 <= p_0_in_sync;")
    else:
        common.write(f, 1, "write_port_0 <= p_0_in;")

    # Input and output assignments
    if output_sync:
        common.write(f, 1, "-- Input and output assignments", start="\n")
        p_zero_exec = filter(
            lambda p: p.execution_time == 0, (p for pc in memory.assignment for p in pc)
        )
        common.synchronous_process_prologue(f, name="output_reg_proc")
        common.write(f, 3, "case to_integer(schedule_cnt) is")
        for p in p_zero_exec:
            if input_sync:
                write_time = (p.start_time + 1) % schedule_time
                if adr_pipe_depth:
                    common.write(
                        f,
                        4,
                        f"when {write_time}+{adr_pipe_depth} => p_0_out <= p_0_in_sync;",
                    )
                else:
                    common.write(f, 4, f"when {write_time} => p_0_out <= p_0_in_sync;")
            else:
                write_time = (p.start_time) % schedule_time
                common.write(f, 4, f"when {write_time} => p_0_out <= p_0_in;")
        common.write_lines(
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
    else:
        common.write(f, 1, "p_0_out <= read_port_0;")

    #
    # ROM Write address generation
    #
    common.write(f, 1, "--", start="\n")
    common.write(f, 1, "-- Memory write address generation", start="")
    common.write(f, 1, "--")

    # Extract all the write addresses
    write_list: list[tuple[int, MemoryVariable] | None] = [
        None for _ in range(schedule_time)
    ]
    for i, collection in enumerate(memory.assignment):
        for mv in collection:
            mv = cast("MemoryVariable", mv)
            if mv.start_time >= schedule_time:
                raise ValueError("start_time greater than schedule_time")
            if mv.execution_time:
                write_list[mv.start_time] = (i, mv)

    for rom in range(total_roms):
        if input_sync:
            common.synchronous_process_prologue(
                f, name=f"mem_write_address_proc_{0}_{rom}"
            )
        else:
            common.process_prologue(
                f, sensitivity_list="schedule_cnt_adr", name="mem_write_address_proc"
            )
        common.write(f, 3, "case to_integer(schedule_cnt_adr) is")
        list_start_idx = rom * elements_per_rom
        list_stop_idx = list_start_idx + elements_per_rom
        for i, mv in filter(None, write_list[list_start_idx:list_stop_idx]):
            common.write_lines(
                f,
                [
                    (4, f"-- {mv!r}"),
                    (
                        4,
                        (
                            f"when {(mv.start_time % schedule_time) % elements_per_rom} =>"
                        ),
                    ),
                    (
                        5,
                        f"write_adr_0_{0}_{rom} <= to_unsigned({i}, write_adr_0_{0}_{rom}'length);",
                    ),
                    (5, f"write_en_0_{0}_{rom} <= '1';"),
                ],
            )
        common.write_lines(
            f,
            [
                (4, "when others =>"),
                (5, f"write_adr_0_{0}_{rom} <= (others => '-');"),
                (5, f"write_en_0_{0}_{rom} <= '0';"),
                (3, "end case;"),
            ],
        )
        if input_sync:
            common.synchronous_process_epilogue(
                f, clk="clk", name=f"mem_write_address_proc_{0}_{rom}"
            )
            common.blank(f)
        else:
            common.process_epilogue(
                f, sensitivity_list="clk", name="mem_write_address_proc"
            )
            common.blank(f)

    # Write address multiplexing layers
    for layer in range(adr_pipe_depth):
        for mux_idx in range(total_roms // adr_mux_size ** (layer + 1)):
            common.synchronous_process_prologue(
                f, name=f"mem_write_address_proc{layer + 1}_{mux_idx}"
            )
            common.write(
                f,
                3,
                (
                    f"case to_integer(schedule_cnt{layer + 1}("
                    f"{ADR_LEN + layer * bits_per_mux + bits_per_mux - 1} downto "
                    f"{ADR_LEN + layer * bits_per_mux}"
                    ")) is"
                ),
            )
            for in_idx in range(adr_mux_size):
                out_idx = in_idx + mux_idx * adr_mux_size
                common.write(
                    f,
                    4,
                    (
                        f"-- {adr_mux_size}-to-1 MUX layer: "
                        f"layer={layer}, MUX={mux_idx}, input={in_idx}"
                    ),
                )
                common.write_lines(
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
            common.write_lines(
                f,
                [
                    (4, "when others =>"),
                    (5, f"write_adr_0_{layer + 1}_{mux_idx} <= (others => '-');"),
                    (5, f"write_en_0_{layer + 1}_{mux_idx} <= '0';"),
                    (3, "end case;"),
                ],
            )
            common.synchronous_process_epilogue(
                f, clk="clk", name=f"mem_write_address_proc{layer + 1}_{mux_idx}"
            )
            common.blank(f)

    #
    # ROM read address generation
    #
    common.write(f, 1, "--", start="\n")
    common.write(f, 1, "-- Memory read address generation", start="")
    common.write(f, 1, "--")

    # Extract all the read addresses
    read_list: list[tuple[int, MemoryVariable] | None] = [
        None for _ in range(schedule_time)
    ]
    for i, collection in enumerate(memory.assignment):
        for mv in collection:
            mv = cast("MemoryVariable", mv)
            for read_time in mv.reads.values():
                read_list[(mv.start_time + read_time) % schedule_time] = (i, mv)

    for rom in range(total_roms):
        if input_sync:
            common.synchronous_process_prologue(
                f, name=f"mem_read_address_proc_{0}_{rom}"
            )
        else:
            common.process_prologue(
                f, sensitivity_list="schedule_cnt_adr", name="mem_read_address_proc"
            )
        common.write(f, 3, "case to_integer(schedule_cnt_adr) is")
        list_start_idx = rom * elements_per_rom
        list_stop_idx = list_start_idx + elements_per_rom
        for idx in range(list_start_idx, list_stop_idx):
            if idx < schedule_time:
                tp = read_list[idx]
                if tp is None:
                    continue
                i = tp[0]
                mv = tp[1]
                common.write_lines(
                    f,
                    [
                        (4, f"-- {mv!r}"),
                        (4, f"when {idx % elements_per_rom} =>"),
                        (
                            5,
                            f"read_adr_0_{0}_{rom} <= to_unsigned({i}, write_adr_0_{0}_{rom}'length);",
                        ),
                    ],
                )
        common.write_lines(
            f,
            [
                (4, "when others =>"),
                (5, f"read_adr_0_{0}_{rom} <= (others => '-');"),
                (3, "end case;"),
            ],
        )
        if input_sync:
            common.synchronous_process_epilogue(
                f, clk="clk", name=f"mem_read_address_proc_{0}_{rom}"
            )
            common.blank(f)
        else:
            common.process_epilogue(
                f, sensitivity_list="clk", name="mem_read_address_proc"
            )
            common.blank(f)

    # Read address multiplexing layers
    for layer in range(adr_pipe_depth):
        for mux_idx in range(total_roms // adr_mux_size ** (layer + 1)):
            common.synchronous_process_prologue(
                f, name=f"mem_read_address_proc{layer + 1}_{mux_idx}"
            )
            common.write(
                f,
                3,
                (
                    f"case to_integer(schedule_cnt{layer + 1}("
                    f"{ADR_LEN + layer * bits_per_mux + bits_per_mux - 1} downto "
                    f"{ADR_LEN + layer * bits_per_mux}"
                    ")) is"
                ),
            )
            for in_idx in range(adr_mux_size):
                out_idx = in_idx + mux_idx * adr_mux_size
                common.write(
                    f,
                    4,
                    (
                        f"-- {adr_mux_size}-to-1 MUX layer: "
                        f"layer={layer}, MUX={mux_idx}, input={in_idx}"
                    ),
                )
                common.write_lines(
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
            common.write_lines(
                f,
                [
                    (4, "when others =>"),
                    (5, f"read_adr_0_{layer + 1}_{mux_idx} <= (others => '-');"),
                    (3, "end case;"),
                ],
            )
            common.synchronous_process_epilogue(
                f, clk="clk", name=f"mem_read_address_proc{layer + 1}_{mux_idx}"
            )
            common.blank(f)

    common.write(f, 0, "end architecture rtl;")
