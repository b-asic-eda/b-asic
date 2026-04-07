"""
Module for VHDL code generation of memory based storage.
"""

import math
from typing import TYPE_CHECKING, TextIO, cast

from b_asic.code_printer.util import bin_str, time_bin_str
from b_asic.code_printer.vhdl import common
from b_asic.code_printer.vhdl.util import schedule_time_type, unsigned_type
from b_asic.data_type import _VhdlDataType
from b_asic.process import MemoryVariable, PlainMemoryVariable

if TYPE_CHECKING:
    from b_asic.architecture import Memory


def entity(
    f: TextIO,
    mem: "Memory",
    dt: _VhdlDataType,
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
    dt : _VhdlDataType
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
    dt: _VhdlDataType,
    *,
    output_sync: bool = True,
    external_schedule_counter: bool = True,
    std_logic_vector: bool = False,
    pipeline_control_signals: bool = False,
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
    output_sync : bool, default: True
        Add registers to the output signal.
    external_schedule_counter : bool, default: True
        If True, schedule counter comes from external input port.
        If False, schedule counter is generated internally with synchronous reset.
    std_logic_vector : bool, default: False
        If True, use std_logic_vector for data signals. If False, use dt.type_str.
    pipeline_control_signals : bool, default: False
        If True, register the control signals.
    """
    # Code settings
    mem_depth = len(memory.assignment)
    mem_adress_bits = mem_depth.bit_length()
    schedule_time = next(iter(memory.assignment)).schedule_time

    # Data type selection based on flag
    data_type = (
        f"std_logic_vector({dt.high} downto 0)" if std_logic_vector else dt.type_str
    )

    # Address generation "ROM" (single non-pipelined table)
    elements_per_rom = int(
        2 ** math.ceil(math.log2(schedule_time))
    )  # Next power-of-two

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
    common.signal_declaration(
        f,
        name="memory",
        signal_type="mem_type",
    )

    ADR_LEN = (memory.schedule_time - 1).bit_length()

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

    # Address generation signals (single ROM instance)
    common.write(f, 1, "-- Address generation multiplexing signals", start="\n")
    for write_port_idx in range(memory.output_count):
        common.signal_declaration(
            f,
            f"write_adr_{write_port_idx}_0_0",
            unsigned_type(mem_adress_bits),
        )
    for write_port_idx in range(memory.output_count):
        common.signal_declaration(
            f,
            f"write_en_{write_port_idx}_0_0",
            signal_type="std_logic",
        )
    for read_port_idx in range(memory.input_count):
        common.signal_declaration(
            f,
            f"read_adr_{read_port_idx}_0_0",
            unsigned_type(mem_adress_bits),
        )
    for read_port_idx in range(memory.input_count):
        common.signal_declaration(
            f,
            f"read_en_{read_port_idx}_0_0",
            signal_type="std_logic",
        )

    # Type conversion signals for interface
    common.write(f, 1, "-- Type conversion for interface", start="\n")
    for i in range(memory.input_count):
        common.signal_declaration(
            f, f"p_{i}_in_internal", data_type, default_value=dt.init_val
        )
    for i in range(memory.output_count):
        common.signal_declaration(
            f, f"p_{i}_out_internal", data_type, default_value=dt.init_val
        )

    # forward_ctrl signal
    if output_sync:
        common.signal_declaration(
            f,
            "forward_ctrl",
            signal_type="std_logic",
        )

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

    # Type conversions
    common.write(f, 1, "-- Type conversions", start="\n")
    for i in range(memory.input_count):
        common.write(f, 1, f"p_{i}_in_internal <= p_{i}_in;")
    for i in range(memory.output_count):
        common.write(f, 1, f"p_{i}_out <= p_{i}_out_internal;")

    # Register control signals generated by address ROMs.
    if pipeline_control_signals:
        common.write(f, 1, "-- Control signal registers", start="\n")
        common.synchronous_process_prologue(f, name="control_regs_proc")
        common.write(f, 3, "if en = '1' then")
        for i in range(memory.input_count):
            common.write(f, 4, f"read_adr_{i} <= read_adr_{i}_0_0;")
            common.write(f, 4, f"read_en_{i} <= read_en_{i}_0_0;")
        for i in range(memory.output_count):
            common.write(f, 4, f"write_adr_{i} <= write_adr_{i}_0_0;")
            common.write(f, 4, f"write_en_{i} <= write_en_{i}_0_0;")
        common.write(f, 3, "end if;")
        common.synchronous_process_epilogue(f, clk="clk", name="control_regs_proc")

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
    if not pipeline_control_signals:
        common.write(f, 1, "read_adr_0 <= read_adr_0_0_0;")
        common.write(f, 1, "read_en_0 <= read_en_0_0_0;")
        common.write(f, 1, "write_adr_0 <= write_adr_0_0_0;")
        common.write(f, 1, "write_en_0 <= write_en_0_0_0;")
    common.write(f, 1, "write_port_0 <= p_0_in_internal;")

    # Input and output assignments
    if output_sync:
        common.write(f, 1, "-- Input and output assignments", start="\n")
        all_procs = [p for pc in memory.assignment for p in pc]
        output_cases: dict[int, str] = {}
        # forward_ctrl ROM
        for p in all_procs:
            if pipeline_control_signals:
                write_time = (p.start_time - 1) % schedule_time
            else:
                write_time = p.start_time % schedule_time
            output_cases[write_time] = f"'{int(1 in p.reads.values())}'"
        common.synchronous_process_prologue(f, name="output_reg_proc")
        common.write(f, 3, "if forward_ctrl = '1' then")
        common.write(f, 4, "p_0_out_internal <= p_0_in_internal;")
        common.write(f, 3, "else")
        common.write(f, 4, "p_0_out_internal <= read_port_0;")
        common.write(f, 3, "end if;")
        common.synchronous_process_epilogue(
            f,
            clk="clk",
            name="output_reg_proc",
        )
        if pipeline_control_signals:
            common.synchronous_process_prologue(f, name="forward_ctrl_rom_proc")
            common.write(f, 3, "if en = '1' then")
            common.write(f, 4, "case schedule_cnt is")
            for write_time, stmt in sorted(output_cases.items()):
                bin_time = time_bin_str(write_time, schedule_time)
                common.write(f, 5, f"when {bin_time} => forward_ctrl <= {stmt};")
            # Normal operation, output the read port
            common.write_lines(
                f,
                [
                    (5, "when others => forward_ctrl <= '-';"),
                    (4, "end case;"),
                ],
            )
            common.write(f, 3, "end if;")
            common.synchronous_process_epilogue(
                f,
                clk="clk",
                name="forward_ctrl_rom_proc",
            )
        else:
            common.write(f, 1, "with schedule_cnt select", start="\n")
            common.write(f, 2, "forward_ctrl <=", end="\n")
            for write_time, stmt in sorted(output_cases.items()):
                bin_time = time_bin_str(write_time, schedule_time)
                common.write(f, 2, f'{stmt} when "{bin_time}",')
            common.write(f, 2, "'-' when others;")

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

    common.process_prologue(
        f, sensitivity_list="schedule_cnt", name="mem_write_address_proc"
    )
    indent_offset = 0
    common.write(f, 3 + indent_offset, "case schedule_cnt is")
    for i, mv in filter(None, write_list[:elements_per_rom]):
        write_time = mv.start_time % schedule_time
        if pipeline_control_signals:
            write_time = (write_time - 1) % schedule_time
        bin_time = bin_str(write_time % elements_per_rom, ADR_LEN)
        common.write_lines(
            f,
            [
                (4 + indent_offset, f"-- {mv!r}"),
                (4 + indent_offset, (f'when "{bin_time}" =>')),
                (
                    5 + indent_offset,
                    f"write_adr_0_0_0 <= to_unsigned({i}, write_adr_0_0_0'length);",
                ),
                (5 + indent_offset, "write_en_0_0_0 <= '1';"),
            ],
        )
    common.write_lines(
        f,
        [
            (4 + indent_offset, "when others =>"),
            (5 + indent_offset, "write_adr_0_0_0 <= (others => '-');"),
            (5 + indent_offset, "write_en_0_0_0 <= '0';"),
            (3 + indent_offset, "end case;"),
        ],
    )
    common.process_epilogue(f, sensitivity_list="clk", name="mem_write_address_proc")
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

    common.process_prologue(
        f, sensitivity_list="schedule_cnt", name="mem_read_address_proc"
    )
    indent_offset = 0
    common.write(f, 3 + indent_offset, "case schedule_cnt is")
    for idx in range(elements_per_rom):
        if idx < schedule_time:
            tp = read_list[idx]
            if tp is None:
                continue
            i = tp[0]
            mv = tp[1]
            time = idx % elements_per_rom
            if output_sync:
                time -= 1  # Account for output register
            if pipeline_control_signals:
                time -= 1  # Account for control-signal register stage
            time = time % elements_per_rom
            common.write_lines(
                f,
                [
                    (4 + indent_offset, f"-- {mv!r}"),
                    (
                        4 + indent_offset,
                        f'when "{bin_str(time, ADR_LEN)}" =>',
                    ),
                    (
                        5 + indent_offset,
                        f"read_adr_0_0_0 <= to_unsigned({i}, read_adr_0_0_0'length);",
                    ),
                    (5 + indent_offset, "read_en_0_0_0 <= '1';"),
                ],
            )
    common.write_lines(
        f,
        [
            (4 + indent_offset, "when others =>"),
            (5 + indent_offset, "read_adr_0_0_0 <= (others => '-');"),
            (5 + indent_offset, "read_en_0_0_0 <= '0';"),
            (3 + indent_offset, "end case;"),
        ],
    )
    common.process_epilogue(f, sensitivity_list="clk", name="mem_read_address_proc")
    common.blank(f)

    common.write(f, 0, "end architecture rtl;")
