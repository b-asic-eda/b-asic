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


def entity(
    f: TextIO,
    mem: "Memory",
    dt: VhdlDataType,
    external_schedule_counter: bool = True,
    std_logic_vector: bool = False,
) -> None:
    """
    Generate entity for memory storage.

    Parameters
    ----------
    f : TextIO
        File object to write to.
    mem : Memory
        Memory object to generate entity for.
    dt : VhdlDataType
        Data type information.
    external_schedule_counter : bool, default: True
        If True, schedule counter is an input port. If False, it's generated internally.
    std_logic_vector : bool, default: False
        If True, use std_logic_vector for data signals. If False, use dt.type_str.
    """
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

    ports = ["clk : in std_logic"]
    # Add rst port if internal schedule counter
    if not external_schedule_counter:
        ports.append("rst : in std_logic")
    ports.append("en : in std_logic")
    if external_schedule_counter:
        ports.append(f"schedule_cnt : in {schedule_time_type(mem.schedule_time)}")
    # Use dt.type_str or std_logic_vector for interface ports based on flag
    data_type = (
        f"std_logic_vector({dt.bits - 1} downto 0)" if std_logic_vector else dt.type_str
    )
    ports += [f"p_{count}_in : in {data_type}" for count in range(mem.input_count)]
    ports += [f"p_{count}_out : out {data_type}" for count in range(mem.output_count)]
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
    external_schedule_counter: bool = True,
    std_logic_vector: bool = False,
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
    memory : :class:`Memory`
        Memory object to generate code for.
    dt : :class:`DataType`
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
    external_schedule_counter : bool, default: True
        If True, schedule counter comes from external input port.
        If False, schedule counter is generated internally with synchronous reset.
    std_logic_vector : bool, default: False
        If True, use std_logic_vector for data signals. If False, use dt.type_str.
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

    # Data type selection based on flag
    data_type = (
        f"std_logic_vector({dt.high} downto 0)" if std_logic_vector else dt.type_str
    )

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
    # Schedule counter (only declare if internal)
    if not external_schedule_counter:
        common.write(f, 1, "-- Schedule counter")
        common.signal_declaration(
            f,
            name="schedule_cnt",
            signal_type=schedule_time_type(schedule_time),
            default_value="(others => '0')",
        )

    common.write(f, 1, "-- HDL memory description")
    common.type_declaration(
        f,
        "mem_type",
        f"array(0 to {mem_depth - 1}) of {data_type}",
    )
    if vivado_ram_style is not None:
        common.signal_declaration(
            f,
            name="memory",
            signal_type="mem_type",
            vivado_ram_style=vivado_ram_style,
        )
    elif quartus_ram_style is not None:
        common.signal_declaration(
            f,
            name="memory",
            signal_type="mem_type",
            quartus_ram_style=quartus_ram_style,
        )
    else:
        common.signal_declaration(
            f,
            name="memory",
            signal_type="mem_type",
        )

    # Schedule time counter pipelined signals
    for i in range(adr_pipe_depth):
        common.signal_declaration(
            f,
            name=f"schedule_cnt{i + 1}",
            signal_type=schedule_time_type(memory.schedule_time),
            default_value=dt.init_val,
        )
    ADR_LEN = (memory.schedule_time - 1).bit_length() - int(
        math.log2(adr_mux_size)
    ) * adr_pipe_depth

    common.alias_declaration(
        f,
        name="schedule_cnt_adr",
        signal_type=unsigned_type(ADR_LEN),
        value=f"schedule_cnt({ADR_LEN - 1} downto 0)",
    )

    # Address generation signals
    common.write(f, 1, "-- Memory address generation", start="\n")
    for i in range(memory.input_count):
        common.signal_declaration(f, f"read_port_{i}", data_type)
        common.signal_declaration(f, f"read_adr_{i}", unsigned_type(mem_adress_bits))
        common.signal_declaration(f, f"read_en_{i}", "std_logic")
    for i in range(memory.output_count):
        common.signal_declaration(f, f"write_port_{i}", data_type)
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
            common.signal_declaration(f, f"p_{i}_in_sync", data_type)

    # Type conversion signals for interface
    common.write(f, 1, "-- Type conversion for interface", start="\n")
    for i in range(memory.input_count):
        common.signal_declaration(f, f"p_{i}_in_internal", data_type)
    for i in range(memory.output_count):
        common.signal_declaration(f, f"p_{i}_out_internal", data_type)

    #
    # Architecture body begin
    #
    # common.write(f, 1, "begin")
    common.write(f, 0, "begin", start="\n", end="\n\n")

    # Generate internal schedule counter if needed
    if not external_schedule_counter:
        common.write(f, 1, "-- Schedule counter")
        common.synchronous_process_prologue(f, name="schedule_cnt_proc")
        common.write_lines(
            f,
            [
                (3, "if rst = '1' then"),
                (4, "schedule_cnt <= (others => '0');"),
                (3, "elsif en = '1' then"),
                (4, f"if schedule_cnt = {schedule_time - 1} then"),
                (5, "schedule_cnt <= (others => '0');"),
                (4, "else"),
                (5, "schedule_cnt <= schedule_cnt + 1;"),
                (4, "end if;"),
                (3, "end if;"),
            ],
        )
        common.synchronous_process_epilogue(
            f=f,
            name="schedule_cnt_proc",
            clk="clk",
        )

    # Schedule counter pipelining
    if adr_pipe_depth > 0:
        common.write(f, 1, "-- Schedule counter pipelining")
        common.synchronous_process_prologue(f, name="schedule_cnt_pipe_proc")
        common.write(f, 3, "if en = '1' then")
        for i in range(adr_pipe_depth):
            if i == 0:
                common.write(f, 4, "schedule_cnt1 <= schedule_cnt;")
            else:
                common.write(f, 4, f"schedule_cnt{i + 1} <= schedule_cnt{i};")
        common.write(f, 3, "end if;")
        common.synchronous_process_epilogue(
            f=f,
            name="schedule_cnt_pipe_proc",
            clk="clk",
        )

    # Input synchronization
    if input_sync:
        common.write(f, 1, "-- Input synchronization", start="\n")
        common.synchronous_process_prologue(f, name="input_sync_proc")
        common.write(f, 3, "if en = '1' then")
        for i in range(memory.input_count):
            common.write(f, 4, f"p_{i}_in_sync <= p_{i}_in_internal;")
        common.write(f, 3, "end if;")
        common.synchronous_process_epilogue(f, name="input_sync_proc")

    # Type conversions
    common.write(f, 1, "-- Type conversions", start="\n")
    for i in range(memory.input_count):
        common.write(f, 1, f"p_{i}_in_internal <= p_{i}_in;")
    for i in range(memory.output_count):
        common.write(f, 1, f"p_{i}_out <= p_{i}_out_internal;")

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
        enable="en",
    )
    common.write(f, 1, f"read_adr_0 <= read_adr_0_{adr_pipe_depth}_0;")
    common.write(f, 1, f"write_adr_0 <= write_adr_0_{adr_pipe_depth}_0;")
    common.write(f, 1, f"write_en_0 <= write_en_0_{adr_pipe_depth}_0;")
    if input_sync:
        common.write(f, 1, "write_port_0 <= p_0_in_sync;")
    else:
        common.write(f, 1, "write_port_0 <= p_0_in_internal;")

    # Input and output assignments
    if output_sync:
        common.write(f, 1, "-- Input and output assignments", start="\n")
        p_zero_exec = filter(
            lambda p: p.execution_time == 0, (p for pc in memory.assignment for p in pc)
        )
        common.synchronous_process_prologue(f, name="output_reg_proc")
        common.write(f, 3, "if en = '1' then")
        common.write(f, 4, "case to_integer(schedule_cnt) is")
        for p in p_zero_exec:
            if input_sync:
                write_time = (p.start_time + 1) % schedule_time
                if adr_pipe_depth:
                    common.write(
                        f,
                        5,
                        f"when {write_time}+{adr_pipe_depth} => p_0_out_internal <= p_0_in_sync;",
                    )
                else:
                    common.write(
                        f, 5, f"when {write_time} => p_0_out_internal <= p_0_in_sync;"
                    )
            else:
                write_time = (p.start_time) % schedule_time
                common.write(
                    f, 5, f"when {write_time} => p_0_out_internal <= p_0_in_internal;"
                )
        common.write_lines(
            f,
            [
                (5, "when others => p_0_out_internal <= read_port_0;"),
                (4, "end case;"),
                (3, "end if;"),
            ],
        )
        common.synchronous_process_epilogue(
            f,
            clk="clk",
            name="output_reg_proc",
        )
    else:
        common.write(f, 1, "p_0_out_internal <= read_port_0;")

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
            common.write(f, 3, "if en = '1' then")
            indent_offset = 1
        else:
            common.process_prologue(
                f, sensitivity_list="schedule_cnt_adr", name="mem_write_address_proc"
            )
            indent_offset = 0
        common.write(f, 3 + indent_offset, "case to_integer(schedule_cnt_adr) is")
        list_start_idx = rom * elements_per_rom
        list_stop_idx = list_start_idx + elements_per_rom
        for i, mv in filter(None, write_list[list_start_idx:list_stop_idx]):
            common.write_lines(
                f,
                [
                    (4 + indent_offset, f"-- {mv!r}"),
                    (
                        4 + indent_offset,
                        (
                            f"when {(mv.start_time % schedule_time) % elements_per_rom} =>"
                        ),
                    ),
                    (
                        5 + indent_offset,
                        f"write_adr_0_{0}_{rom} <= to_unsigned({i}, write_adr_0_{0}_{rom}'length);",
                    ),
                    (5 + indent_offset, f"write_en_0_{0}_{rom} <= '1';"),
                ],
            )
        common.write_lines(
            f,
            [
                (4 + indent_offset, "when others =>"),
                (5 + indent_offset, f"write_adr_0_{0}_{rom} <= (others => '-');"),
                (5 + indent_offset, f"write_en_0_{0}_{rom} <= '0';"),
                (3 + indent_offset, "end case;"),
            ],
        )
        if input_sync:
            common.write(f, 3, "end if;")
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
            common.write(f, 3, "if en = '1' then")
            common.write(
                f,
                4,
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
                    5,
                    (
                        f"-- {adr_mux_size}-to-1 MUX layer: "
                        f"layer={layer}, MUX={mux_idx}, input={in_idx}"
                    ),
                )
                common.write_lines(
                    f,
                    [
                        (5, f"when {in_idx} =>"),
                        (
                            6,
                            (
                                f"write_adr_0_{layer + 1}_{mux_idx} <="
                                f" write_adr_0_{layer}_{out_idx};"
                            ),
                        ),
                        (
                            6,
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
                    (5, "when others =>"),
                    (6, f"write_adr_0_{layer + 1}_{mux_idx} <= (others => '-');"),
                    (6, f"write_en_0_{layer + 1}_{mux_idx} <= '0';"),
                    (4, "end case;"),
                    (3, "end if;"),
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
            common.write(f, 3, "if en = '1' then")
            indent_offset = 1
        else:
            common.process_prologue(
                f, sensitivity_list="schedule_cnt_adr", name="mem_read_address_proc"
            )
            indent_offset = 0
        common.write(f, 3 + indent_offset, "case to_integer(schedule_cnt_adr) is")
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
                        (4 + indent_offset, f"-- {mv!r}"),
                        (4 + indent_offset, f"when {idx % elements_per_rom} =>"),
                        (
                            5 + indent_offset,
                            f"read_adr_0_{0}_{rom} <= to_unsigned({i}, read_adr_0_{0}_{rom}'length);",
                        ),
                    ],
                )
        common.write_lines(
            f,
            [
                (4 + indent_offset, "when others =>"),
                (5 + indent_offset, f"read_adr_0_{0}_{rom} <= (others => '-');"),
                (3 + indent_offset, "end case;"),
            ],
        )
        if input_sync:
            common.write(f, 3, "end if;")
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
            common.write(f, 3, "if en = '1' then")
            common.write(
                f,
                4,
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
                    5,
                    (
                        f"-- {adr_mux_size}-to-1 MUX layer: "
                        f"layer={layer}, MUX={mux_idx}, input={in_idx}"
                    ),
                )
                common.write_lines(
                    f,
                    [
                        (5, f"when {in_idx} =>"),
                        (
                            6,
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
                    (5, "when others =>"),
                    (6, f"read_adr_0_{layer + 1}_{mux_idx} <= (others => '-');"),
                    (4, "end case;"),
                    (3, "end if;"),
                ],
            )
            common.synchronous_process_epilogue(
                f, clk="clk", name=f"mem_read_address_proc{layer + 1}_{mux_idx}"
            )
            common.blank(f)

    common.write(f, 0, "end architecture rtl;")
