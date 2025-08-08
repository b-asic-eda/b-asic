"""
Module for code generation of VHDL architectures.
"""

import math
from typing import TYPE_CHECKING, Literal, TextIO, cast

from b_asic.codegen.vhdl import common, write, write_lines
from b_asic.special_operations import Input, Output

if TYPE_CHECKING:
    from b_asic.architecture import Architecture, Memory, ProcessingElement, WordLengths
    from b_asic.process import MemoryVariable
    from b_asic.resources import _ForwardBackwardTable


def architecture(f: TextIO, arch: "Architecture", wl: "WordLengths") -> None:
    write(f, 0, f"architecture rtl of {arch.entity_name} is", end="\n")

    write(f, 1, "-- Component declaration")
    for pe in arch.processing_elements:
        pe.write_component_declaration(f, wl)
    for mem in arch.memories:
        mem.write_component_declaration(f, wl)
    arch.write_signal_declarations(f)

    write(f, 0, "begin", start="\n", end="\n")

    write(f, 1, "-- Component instantiation")
    for pe in arch.processing_elements:
        pe.write_component_instantiation(f, wl)
    for mem in arch.memories:
        mem.write_component_instantiation(f, wl)

    _write_schedule_counter(f, arch)
    _write_architecture_interconnect(f, arch)
    write(f, 0, "end architecture rtl;", start="", end="\n\n")


def _write_architecture_interconnect(f: TextIO, arch: "Architecture") -> None:
    # Define PE input interconnect
    for pe in arch.processing_elements:
        for port_number in range(pe.input_count):
            write(f, 1, "with to_integer(schedule_cnt) select")
            write(f, 2, f"{pe.entity_name}_{port_number}_in <=")
            for process in sorted(pe.collection):
                op = process.operation
                if isinstance(op, Input):
                    continue
                op_input_port = op.inputs[port_number]
                # Find the source resource
                source_port = op_input_port.signals[0].source
                source_op = source_port.operation
                is_found = False
                # Check in memories
                for mem in arch.memories:
                    for var in mem.collection:
                        # Skip all variables written at the same clock cycle
                        read_times = [
                            time % arch.schedule_time for time in var.read_times
                        ]
                        if process.start_time % arch.schedule_time not in read_times:
                            continue
                        var_op_id = var.name.split(".")[0]
                        var_port_index = int(var.name.split(".")[1])
                        if (
                            var_op_id == source_op.graph_id
                            and var_port_index == source_port.index
                        ):
                            source_resource = mem
                            is_found = True
                if not is_found:
                    for other_pe in arch.processing_elements:
                        for pro in other_pe.collection:
                            if pro.operation == source_op:
                                source_resource = other_pe
                                is_found = True
                if not is_found:
                    raise ValueError("Source resource not found.")
                time = process.start_time % arch.schedule_time
                write(
                    f,
                    3,
                    f"{source_resource.entity_name}_{source_port.index}_out when {time},",
                )
            write(f, 3, "(others => '-') when others;", end="\n\n")

    # Define memory input interconnect
    for mem in arch.memories:
        write(f, 1, "with to_integer(schedule_cnt) select")
        write(f, 2, f"{mem.entity_name}_0_in <=")
        for var in mem.collection:
            # an execution found -> write rows
            # TODO: Support multi-port memories here
            source_op_graph_id = var.name.split(".")[0]
            source_port_index = var.name.split(".")[1]
            is_found = False
            for other_pe in arch.processing_elements:
                for pro in other_pe.collection:
                    if pro.operation.graph_id == source_op_graph_id:
                        source_pe = other_pe
                        is_found = True
            if not is_found:
                raise ValueError("Source resource not found.")
            time = var.start_time % arch.schedule_time
            write(f, 3, f"{source_pe.entity_name}_{source_port_index}_out when {time},")
        write(f, 3, "(others => '-') when others;", end="\n\n")


def _write_schedule_counter(f: TextIO, arch: "Architecture") -> None:
    write(f, 1, "-- Schedule counter")
    common.synchronous_process_prologue(f, name="schedule_cnt_proc")
    write_lines(
        f,
        [
            (3, "if rst = '1' then"),
            (4, "schedule_cnt <= (others => '0');"),
            (3, "else"),
            (4, f"if schedule_cnt = {arch.schedule_time - 1} then"),
            (5, "schedule_cnt <= (others => '0');"),
            (4, "else"),
            (5, "schedule_cnt <= schedule_cnt + 1;"),
            (4, "end if;"),
            (3, "end if;"),
        ],
    )
    common.synchronous_process_epilogue(f, name="schedule_cnt_proc", clk="clk")
    write(f, 1, "")


def architecture_test_bench(f: TextIO, arch: "Architecture", wl: "WordLengths") -> None:
    write(f, 0, f"architecture tb of {arch.entity_name}_tb is", end="\n")

    arch.write_component_declaration(f, wl)
    _write_tb_constant_generation(f, arch, wl)
    _write_tb_signal_generation(f, arch)
    write(f, 0, "begin", end="\n")

    arch.write_component_instantiation(f)
    _write_tb_clock_generation(f)
    _write_tb_stimulus_generation(f)
    write(f, 0, "end architecture tb;", start="", end="\n\n")


def _write_tb_constant_generation(
    f: TextIO, arch: "Architecture", wl: "WordLengths"
) -> None:
    write(f, 1, "-- Constant declaration", start="\n")
    common.constant_declaration(f, "CLK_PERIOD", "time", "2 ns")
    common.constant_declaration(f, "WL_INPUT", "integer", f"{wl.input}")
    common.constant_declaration(f, "WL_INTERNAL", "integer", f"{wl.internal}")
    common.constant_declaration(f, "WL_OUTPUT", "integer", f"{wl.output}")
    common.constant_declaration(
        f, "WL_STATE", "integer", f"{arch.schedule_time.bit_length()}"
    )


def _write_tb_signal_generation(f: TextIO, arch: "Architecture") -> None:
    write(f, 1, "-- Signal declaration", start="\n")
    common.signal_declaration(f, "tb_clk", "std_logic", "'0'")
    common.signal_declaration(f, "tb_rst", "std_logic", "'0'")
    inputs = [pe for pe in arch.processing_elements if pe.operation_type == Input]
    for pe in inputs:
        common.signal_declaration(
            f,
            f"tb_{pe.entity_name}_0_in",
            "signed(WL_INPUT_INT+WL_INPUT_FRAC-1 downto 0)",
            "(others => '0')",
        )
    outputs = [pe for pe in arch.processing_elements if pe.operation_type == Output]
    for pe in outputs:
        common.signal_declaration(
            f,
            f"tb_{pe.entity_name}_0_out",
            "std_logic_vector(WL_OUTPUT_INT+WL_OUTPUT_FRAC-1 downto 0)",
            "(others => '0')",
        )


def _write_tb_clock_generation(f: TextIO) -> None:
    write(f, 1, "-- Clock generation", start="\n")
    write_lines(
        f,
        [
            (1, "CLK_GEN : process"),
            (1, "begin"),
            (2, "tb_clk <= '0';"),
            (2, "wait for CLK_PERIOD / 2;"),
            (2, "tb_clk <= '1';"),
            (2, "wait for CLK_PERIOD / 2;"),
            (1, "end process CLK_GEN;"),
        ],
    )


def _write_tb_stimulus_generation(f: TextIO) -> None:
    write(f, 1, "-- Stimulus generation", start="\n")
    write_lines(
        f,
        [
            (1, "process"),
            (1, "begin"),
            (2, "-- WRITE CODE HERE"),
            (1, "end process;"),
        ],
    )


def processing_element(
    f: TextIO, pe: "ProcessingElement", write_pe_archs: bool
) -> None:
    write(f, 0, f"architecture rtl of {pe.entity_name} is", end="\n")

    if write_pe_archs or pe.operation_type in (Input, Output):
        vhdl_code = pe.operation_type._vhdl(pe)
        write(f, 0, vhdl_code[0])

    write(f, 0, "begin", end="\n")

    if write_pe_archs or pe.operation_type in (Input, Output):
        write(f, 0, vhdl_code[1])

    write(f, 0, "end architecture rtl;", end="\n")


def memory_based_storage(
    f: TextIO,
    memory: "Memory",
    wl: "WordLengths",
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
    memory: Memory
        Memory object to generate code for.
    wl: WordLengths
        Word length of all signals.
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
    schedule_time = next(iter(memory.assignment)).schedule_time

    # Address generation "ROMs"
    total_roms = adr_mux_size**adr_pipe_depth
    bits_per_mux = int(math.log2(adr_mux_size))
    elements_per_rom = int(
        2 ** math.ceil(math.log2(schedule_time / total_roms))
    )  # Next power-of-two

    # Write architecture header
    write(f, 0, f"architecture rtl of {memory.entity_name} is", end="\n\n")

    #
    # Architecture declarative region begin
    #
    write(f, 1, "-- HDL memory description")
    common.constant_declaration(
        f, "MEM_WL", "integer", wl.internal[0] + wl.internal[1], name_pad=16
    )
    common.constant_declaration(f, "MEM_DEPTH", "integer", mem_depth, name_pad=16)
    common.type_declaration(
        f, "mem_type", "array(0 to MEM_DEPTH-1) of signed(MEM_WL-1 downto 0)"
    )
    if vivado_ram_style is not None:
        common.signal_declaration(
            f,
            name="memory",
            signal_type="mem_type",
            name_pad=18,
            vivado_ram_style=vivado_ram_style,
        )
    elif quartus_ram_style is not None:
        common.signal_declaration(
            f,
            name="memory",
            signal_type="mem_type",
            name_pad=18,
            quartus_ram_style=quartus_ram_style,
        )
    else:
        common.signal_declaration(f, name="memory", signal_type="mem_type", name_pad=18)

    # Schedule time counter pipelined signals
    for i in range(adr_pipe_depth):
        common.signal_declaration(
            f,
            name=f"schedule_cnt{i + 1}",
            signal_type="unsigned(WL_STATE-1 downto 0)",
            name_pad=18,
        )
    common.constant_declaration(
        f,
        name="ADR_LEN",
        signal_type="integer",
        value=f"WL_STATE-({int(math.log2(adr_mux_size))}*{adr_pipe_depth})",
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
    for i in range(memory.input_count):
        common.signal_declaration(
            f, f"read_port_{i}", "signed(MEM_WL-1 downto 0)", name_pad=18
        )
        common.signal_declaration(
            f, f"read_adr_{i}", "integer range 0 to MEM_DEPTH-1", name_pad=18
        )
        common.signal_declaration(f, f"read_en_{i}", "std_logic", name_pad=18)
    for i in range(memory.output_count):
        common.signal_declaration(
            f, f"write_port_{i}", "signed(MEM_WL-1 downto 0)", name_pad=18
        )
        common.signal_declaration(
            f, f"write_adr_{i}", "integer range 0 to MEM_DEPTH-1", name_pad=18
        )
        common.signal_declaration(f, f"write_en_{i}", "std_logic", name_pad=18)

    # Address generation mutltiplexing signals
    write(f, 1, "-- Address generation multiplexing signals", start="\n")
    for write_port_idx in range(memory.output_count):
        for depth in range(adr_pipe_depth + 1):
            for rom in range(total_roms // adr_mux_size**depth):
                common.signal_declaration(
                    f,
                    f"write_adr_{write_port_idx}_{depth}_{rom}",
                    signal_type="integer range 0 to MEM_DEPTH-1",
                    name_pad=18,
                )
    for write_port_idx in range(memory.output_count):
        for depth in range(adr_pipe_depth + 1):
            for rom in range(total_roms // adr_mux_size**depth):
                common.signal_declaration(
                    f,
                    f"write_en_{write_port_idx}_{depth}_{rom}",
                    signal_type="std_logic",
                    name_pad=18,
                )
    for read_port_idx in range(memory.input_count):
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
        for i in range(memory.input_count):
            common.signal_declaration(
                f,
                f"p_{i}_in_sync",
                "signed(WL_INTERNAL_INT+WL_INTERNAL_FRAC-1 downto 0)",
                name_pad=18,
            )

    #
    # Architecture body begin
    #
    # write(f, 1, "begin")
    write(f, 0, "begin", start="\n", end="\n\n")

    # Schedule counter pipelining
    if adr_pipe_depth > 0:
        write(f, 1, "-- Schedule counter")
        common.synchronous_process_prologue(f, name="schedule_cnt_proc")
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
        common.synchronous_process_prologue(f, name="input_sync_proc")
        for i in range(memory.input_count):
            write(f, 3, f"p_{i}_in_sync <= p_{i}_in;")
        common.synchronous_process_epilogue(f, name="input_sync_proc")

    # Infer the memory
    write(f, 1, "-- Memory", start="\n")
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
    write(f, 1, f"read_adr_0 <= read_adr_0_{adr_pipe_depth}_0;")
    write(f, 1, f"write_adr_0 <= write_adr_0_{adr_pipe_depth}_0;")
    write(f, 1, f"write_en_0 <= write_en_0_{adr_pipe_depth}_0;")
    if input_sync:
        write(f, 1, "write_port_0 <= p_0_in_sync;")
    else:
        write(f, 1, "write_port_0 <= p_0_in;")

    # Input and output assignments
    if output_sync:
        write(f, 1, "-- Input and output assignments", start="\n")
        p_zero_exec = filter(
            lambda p: p.execution_time == 0, (p for pc in memory.assignment for p in pc)
        )
        common.synchronous_process_prologue(f, name="output_reg_proc")
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
    else:
        write(f, 1, "p_0_out <= read_port_0;")

    #
    # ROM Write address generation
    #
    write(f, 1, "--", start="\n")
    write(f, 1, "-- Memory write address generation", start="")
    write(f, 1, "--", end="\n")

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
                f, sensitivity_list="clk", name="mem_write_address_proc"
            )
            write(f, 1, "")

    # Write address multiplexing layers
    for layer in range(adr_pipe_depth):
        for mux_idx in range(total_roms // adr_mux_size ** (layer + 1)):
            common.synchronous_process_prologue(
                f, name=f"mem_write_address_proc{layer + 1}_{mux_idx}"
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
                f, sensitivity_list="clk", name="mem_read_address_proc"
            )
            write(f, 1, "")

    # Read address multiplexing layers
    for layer in range(adr_pipe_depth):
        for mux_idx in range(total_roms // adr_mux_size ** (layer + 1)):
            common.synchronous_process_prologue(
                f, name=f"mem_read_address_proc{layer + 1}_{mux_idx}"
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

    write(f, 0, "end architecture rtl;", start="\n")


def register_based_storage(
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
    write(f, 0, f"architecture rtl of {memory.entity_name} is", end="\n\n")

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
        alias=f"array(0 to {reg_cnt}-1) of signed(WL_INTERNAL_INT+WL_INTERNAL_FRAC-1 downto 0)",
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
    common.synchronous_process_prologue(f, name="schedule_cnt_proc")
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
    common.synchronous_process_prologue(f, name="shift_reg_back_edge_decode_proc")
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
    common.synchronous_process_prologue(f, name="shift_reg_proc")
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
    common.synchronous_process_prologue(f, name="out_mux_decode_proc")
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
    common.synchronous_process_prologue(f, name="out_mux_proc")
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

    write(f, 0, "end architecture rtl;", start="\n")
