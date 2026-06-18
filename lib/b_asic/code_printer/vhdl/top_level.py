"""
Module for VHDL code generation of top level designs.
"""

from typing import TYPE_CHECKING, TextIO

from b_asic.code_printer.util import selector_bits, time_bin_str
from b_asic.code_printer.vhdl import common
from b_asic.data_type import _VhdlDataType
from b_asic.process import MemoryOutputPort
from b_asic.special_operations import Input, Output
from b_asic.utility_operations import DontCare

if TYPE_CHECKING:
    from b_asic.architecture import Architecture


def entity(
    f: TextIO, arch: "Architecture", dt: _VhdlDataType, enable_pin: bool = True
) -> None:
    ports = [
        "clk : in std_logic",
        "rst : in std_logic",
    ]
    if enable_pin:
        ports.append("en : in std_logic")

    ports += [
        port
        for pe in arch.processing_elements
        if pe.operation_type == Input
        for port in dt.get_input_port_declaration(pe.entity_name)
    ]
    ports += [
        port
        for pe in arch.processing_elements
        if pe.operation_type == Output
        for port in dt.get_output_port_declaration(pe.entity_name)
    ]
    common.entity_declaration(f, arch.entity_name, ports=ports)


def architecture(
    f: TextIO,
    arch: "Architecture",
    dt: _VhdlDataType,
    input_register: bool = False,
    output_register: bool = False,
    multiplexer_control_registered: bool = True,
    enable_pin: bool = True,
) -> None:
    if not enable_pin:
        en_sig = "'1'"
    elif input_register:
        en_sig = "en_internal"
    else:
        en_sig = "en"
    common.write(f, 0, f"architecture rtl of {arch.entity_name} is")

    common.write(f, 1, "-- Component declaration")
    for pe in arch.processing_elements:
        pe.write_component_declaration(f, dt)
    for mem in arch.memories:
        mem.write_component_declaration(f, dt)
    arch.write_signal_declarations(f, dt)

    if input_register or output_register:
        _write_io_register_signal_declarations(
            f, arch, dt, input_register, output_register, enable_pin
        )

    # Fetch information about multiplexers needed and declare control signals for them
    pe_mux_info, mem_mux_info = _collect_mux_info(arch)
    _write_mux_control_signal_declarations(
        f, pe_mux_info, mem_mux_info, multiplexer_control_registered
    )

    common.write(f, 0, "begin")

    if input_register or output_register:
        _write_io_registers(f, arch, dt, input_register, output_register, enable_pin)

    common.write(f, 1, "-- Component instantiation")
    for pe in arch.processing_elements:
        pe.write_component_instantiation(
            f,
            dt,
            en_sig=en_sig,
            input_register=input_register,
            output_register=output_register,
        )
    for mem in arch.memories:
        mem.write_component_instantiation(f, en_sig=en_sig)

    _write_schedule_counter(f, arch, en_sig, enable_pin)

    # Generate control signals for multiplexers and then connect the top-level
    _write_mux_control_signals(
        f,
        arch.schedule_time,
        pe_mux_info,
        mem_mux_info,
        multiplexer_control_registered,
        en_sig,
        enable_pin,
    )
    _write_interconnect(f, dt, pe_mux_info, mem_mux_info)

    common.write(f, 0, "end architecture rtl;", start="", end="\n\n")


def _collect_mux_info(arch: "Architecture") -> tuple[list[tuple], list[tuple]]:
    # Collect PE input multiplexer info
    pe_mux_info = []  # List of (pe, port_number, assignments)
    for pe in arch.processing_elements:
        for port_number in range(pe.input_count):
            assignments = []
            for process in sorted(pe.collection):
                op = process.operation
                if isinstance(op, Input):
                    continue
                op_input_port = op.inputs[port_number]
                source_port = op_input_port.signals[0].source
                source_port_index = source_port.index
                source_op = source_port.operation
                if isinstance(source_op, DontCare):
                    continue
                is_found = False

                input_latency = op_input_port.latency_offset or 0
                for mem in arch.memories:
                    for var in mem.collection:
                        read_times = [
                            time % arch.schedule_time for time in var.read_times
                        ]
                        if (
                            process.start_time + input_latency
                        ) % arch.schedule_time not in read_times:
                            continue
                        if isinstance(var.write_port, MemoryOutputPort):
                            continue  # Source is another memory variable, handled in mem mux section
                        var_op_id = var.write_port.operation.graph_id
                        var_port_index = var.write_port.index
                        if (
                            var_op_id == source_op.graph_id
                            and var_port_index == source_port.index
                        ):
                            source_resource = mem
                            is_found = True
                            source_port_index = 0
                            break
                    if is_found:
                        break

                if not is_found:
                    for other_pe in arch.processing_elements:
                        for pro in other_pe.collection:
                            if pro.operation == source_op:
                                source_resource = other_pe
                                is_found = True
                                break
                        if is_found:
                            break

                if not is_found:
                    raise ValueError("Source resource not found.")

                time = (process.start_time + input_latency) % arch.schedule_time
                source_signal = f"{source_resource.entity_name}_{source_port_index}_out"
                assignments.append((time, source_signal))

            if assignments:
                pe_mux_info.append((pe, port_number, assignments))

    # Collect memory input multiplexer info
    mem_mux_info = []  # List of (mem, assignments)
    for mem in arch.memories:
        assignments = []
        for var in mem.collection:
            is_found = False
            time = var.start_time % arch.schedule_time

            if isinstance(var.write_port, MemoryOutputPort):
                # Source is another memory variable (chained lifetime split)
                source_var = var.write_port.source_variable
                for other_mem in arch.memories:
                    if any(ov is source_var for ov in other_mem.collection):
                        source_signal = f"{other_mem.entity_name}_0_out"
                        assignments.append((time, source_signal))
                        is_found = True
                        break
                if not is_found:
                    raise ValueError(
                        f"Source memory not found for chained variable {var.name!r}"
                    )
            else:
                # Source is a PE output port
                source_op_graph_id = var.write_port.operation.graph_id
                source_port_index = var.write_port.index
                for other_pe in arch.processing_elements:
                    for pro in other_pe.collection:
                        if pro.operation.graph_id == source_op_graph_id:
                            source_pe = other_pe
                            is_found = True
                            break
                    if is_found:
                        break
                if not is_found:
                    raise ValueError("Source resource not found.")
                source_signal = f"{source_pe.entity_name}_{source_port_index}_out"
                assignments.append((time, source_signal))

        if assignments:
            mem_mux_info.append((mem, assignments))

    return pe_mux_info, mem_mux_info


def _write_mux_control_signal_declarations(
    f: TextIO,
    pe_mux_info: list,
    mem_mux_info: list,
    multiplexer_control_registered: bool = False,
) -> None:
    if not pe_mux_info and not mem_mux_info:
        return

    common.write(f, 1, "-- Multiplexer control signals")

    # PE input mux control signals
    for pe, port_number, assignments in pe_mux_info:
        unique_sources = {signal for _, signal in assignments}
        if len(unique_sources) > 1:
            # Calculate number of bits needed for selector
            sel_bits = selector_bits(len(unique_sources))
            common.signal_declaration(
                f,
                f"{pe.entity_name}_{port_number}_sel",
                f"std_logic_vector({sel_bits - 1} downto 0)",
            )
            if multiplexer_control_registered:
                common.signal_declaration(
                    f,
                    f"{pe.entity_name}_{port_number}_sel_next",
                    f"std_logic_vector({sel_bits - 1} downto 0)",
                )

    # Memory input mux control signals
    for mem, assignments in mem_mux_info:
        unique_sources = {signal for _, signal in assignments}
        if len(unique_sources) > 1:
            sel_bits = selector_bits(len(unique_sources))
            # TODO: Handle multi-input memories here
            common.signal_declaration(
                f,
                f"{mem.entity_name}_0_sel",
                f"std_logic_vector({sel_bits - 1} downto 0)",
            )
            if multiplexer_control_registered:
                common.signal_declaration(
                    f,
                    f"{mem.entity_name}_0_sel_next",
                    f"std_logic_vector({sel_bits - 1} downto 0)",
                )

    common.blank(f)


def _write_mux_control_signals(
    f: TextIO,
    schedule_time: int,
    pe_mux_info: list,
    mem_mux_info: list,
    multiplexer_control_registered: bool = False,
    en_sig: str = "en",
    enable_pin: bool = True,
) -> None:
    if not pe_mux_info and not mem_mux_info:
        return

    common.write(f, 1, "-- Multiplexer control signal generation")

    # PE input mux control signals
    for pe, port_number, assignments in pe_mux_info:
        unique_sources = {signal for _, signal in assignments}
        if len(unique_sources) > 1:
            # Build source to index mapping
            source_to_idx = {src: idx for idx, src in enumerate(list(unique_sources))}

            common.write(f, 1, "with schedule_cnt select")
            if multiplexer_control_registered:
                common.write(f, 2, f"{pe.entity_name}_{port_number}_sel_next <=")
            else:
                common.write(f, 2, f"{pe.entity_name}_{port_number}_sel <=")
            sel_bits = selector_bits(len(unique_sources))
            for time, source_signal in assignments:
                idx = source_to_idx[source_signal]
                sel_value = format(idx, f"0{sel_bits}b")
                schedule_time_val = (
                    (time - 1) % schedule_time
                    if multiplexer_control_registered
                    else time
                )
                common.write(
                    f,
                    3,
                    f'"{sel_value}" when "{time_bin_str(schedule_time_val, schedule_time)}",',
                )
            common.write(
                f, 3, f'"{"{}".format("-" * sel_bits)}" when others;', end="\n"
            )

            if multiplexer_control_registered:
                common.write(f, 1, "process(clk)")
                common.write(f, 1, "begin")
                common.write(f, 2, "if rising_edge(clk) then")
                if enable_pin:
                    common.write(f, 3, f"if {en_sig} = '1' then")
                    common.write(
                        f,
                        4,
                        f"{pe.entity_name}_{port_number}_sel <= {pe.entity_name}_{port_number}_sel_next;",
                    )
                    common.write(f, 3, "end if;")
                else:
                    common.write(
                        f,
                        3,
                        f"{pe.entity_name}_{port_number}_sel <= {pe.entity_name}_{port_number}_sel_next;",
                    )
                common.write(f, 2, "end if;")
                common.write(f, 1, "end process;", end="\n\n")
            else:
                common.blank(f)

    # Memory input mux control signals
    for mem, assignments in mem_mux_info:
        unique_sources = {signal for _, signal in assignments}
        if len(unique_sources) > 1:
            # Build source to index mapping
            source_to_idx = {src: idx for idx, src in enumerate(list(unique_sources))}

            common.write(f, 1, "with schedule_cnt select")
            if multiplexer_control_registered:
                common.write(f, 2, f"{mem.entity_name}_0_sel_next <=")
            else:
                common.write(f, 2, f"{mem.entity_name}_0_sel <=")
            sel_bits = selector_bits(len(unique_sources))
            for time, source_signal in assignments:
                idx = source_to_idx[source_signal]
                sel_value = format(idx, f"0{sel_bits}b")
                schedule_time_val = (
                    (time - 1) % schedule_time
                    if multiplexer_control_registered
                    else time
                )
                common.write(
                    f,
                    3,
                    f'"{sel_value}" when "{time_bin_str(schedule_time_val, schedule_time)}",',
                )
            common.write(
                f, 3, f'"{"{}".format("-" * sel_bits)}" when others;', end="\n"
            )

            if multiplexer_control_registered:
                common.write(f, 1, "process(clk)")
                common.write(f, 1, "begin")
                common.write(f, 2, "if rising_edge(clk) then")
                if enable_pin:
                    common.write(f, 3, f"if {en_sig} = '1' then")
                    common.write(
                        f,
                        4,
                        f"{mem.entity_name}_0_sel <= {mem.entity_name}_0_sel_next;",
                    )
                    common.write(f, 3, "end if;")
                else:
                    common.write(
                        f,
                        3,
                        f"{mem.entity_name}_0_sel <= {mem.entity_name}_0_sel_next;",
                    )
                common.write(f, 2, "end if;")
                common.write(f, 1, "end process;", end="\n\n")
            else:
                common.blank(f)


def _write_interconnect(
    f: TextIO, dt: _VhdlDataType, pe_mux_info: list, mem_mux_info: list
) -> None:
    common.write(f, 1, "-- Interconnect")

    # Define PE input interconnect
    for pe, port_number, assignments in pe_mux_info:
        unique_sources = {signal for _, signal in assignments}

        if len(unique_sources) == 1:
            # Direct assignment
            common.write(
                f,
                1,
                f"{pe.entity_name}_{port_number}_in <= {assignments[0][1]};",
                end="\n\n",
            )
        else:
            # Multiplexer needed - use control signal
            common.write(f, 1, f"with {pe.entity_name}_{port_number}_sel select")
            common.write(f, 2, f"{pe.entity_name}_{port_number}_in <=")
            sel_bits = selector_bits(len(unique_sources))
            for idx, source_signal in enumerate(list(unique_sources)):
                sel_value = format(idx, f"0{sel_bits}b")
                common.write(
                    f,
                    3,
                    f'{source_signal} when "{sel_value}",',
                )
            common.write(f, 3, f"{dt.dontcare_str} when others;", end="\n\n")

    # Define memory input interconnect
    # TODO: Handle multi-input memories here
    for mem, assignments in mem_mux_info:
        unique_sources = {signal for _, signal in assignments}

        if len(unique_sources) == 1:
            # Direct assignment
            common.write(
                f, 1, f"{mem.entity_name}_0_in <= {assignments[0][1]};", end="\n\n"
            )
        else:
            # Multiplexer needed - use control signal
            common.write(f, 1, f"with {mem.entity_name}_0_sel select")
            common.write(f, 2, f"{mem.entity_name}_0_in <=")
            sel_bits = selector_bits(len(unique_sources))
            for idx, source_signal in enumerate(list(unique_sources)):
                sel_value = format(idx, f"0{sel_bits}b")
                common.write(
                    f,
                    3,
                    f'{source_signal} when "{sel_value}",',
                )
            common.write(f, 3, f"{dt.dontcare_str} when others;", end="\n\n")


def _write_schedule_counter(
    f: TextIO,
    arch: "Architecture",
    en_sig: str = "en",
    enable_pin: bool = True,
) -> None:
    common.write(f, 1, "-- Schedule counter")
    common.synchronous_process_prologue(f, name="schedule_cnt_proc")
    if enable_pin:
        common.write_lines(
            f,
            [
                (3, "if rst = '1' then"),
                (4, "schedule_cnt <= (others => '0');"),
                (3, f"elsif {en_sig} = '1' then"),
                (4, f"if schedule_cnt = {arch.schedule_time - 1} then"),
                (5, "schedule_cnt <= (others => '0');"),
                (4, "else"),
                (5, "schedule_cnt <= schedule_cnt + 1;"),
                (4, "end if;"),
                (3, "end if;"),
            ],
        )
    else:
        common.write_lines(
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
    common.blank(f)


def _write_io_register_signal_declarations(
    f: TextIO,
    arch: "Architecture",
    dt: _VhdlDataType,
    input_register: bool = False,
    output_register: bool = False,
    enable_pin: bool = True,
) -> None:
    common.write(f, 1, "-- Internal signals for pipelined I/O")
    if enable_pin and input_register:
        common.signal_declaration(f, "en_internal", "std_logic")

    # Pipelined inputs
    if input_register:
        for pe in arch.processing_elements:
            if pe.operation_type == Input:
                for port in dt.get_input_port_declaration(pe.entity_name, "_internal"):
                    port_parts = port.split(":")
                    signal_name = port_parts[0].strip()
                    signal_type = ":".join(port_parts[1:]).strip()
                    signal_type = signal_type.replace("in ", "").replace("out ", "")
                    common.signal_declaration(f, signal_name, signal_type)

    # Pipelined outputs
    if output_register:
        for pe in arch.processing_elements:
            if pe.operation_type == Output:
                for port in dt.get_output_port_declaration(pe.entity_name, "_internal"):
                    port_parts = port.split(":")
                    signal_name = port_parts[0].strip()
                    signal_type = ":".join(port_parts[1:]).strip()
                    signal_type = signal_type.replace("in ", "").replace("out ", "")
                    common.signal_declaration(f, signal_name, signal_type)
    common.blank(f)


def _write_io_registers(
    f: TextIO,
    arch: "Architecture",
    dt: _VhdlDataType,
    input_register: bool = False,
    output_register: bool = False,
    enable_pin: bool = True,
) -> None:
    common.write(f, 1, "-- Pipelining of I/O")

    if enable_pin and input_register:
        # Pipeline the enable signal by one cycle to align with input data
        common.synchronous_process_prologue(f, name="en_reg_proc")
        common.write(f, 3, "en_internal <= en;")
        common.synchronous_process_epilogue(f, name="en_reg_proc", clk="clk")
        common.blank(f)

    # Pipelining of inputs
    input_pes = [pe for pe in arch.processing_elements if pe.operation_type == Input]
    if input_register and input_pes:
        common.synchronous_process_prologue(f, name="input_reg_proc")
        if enable_pin:
            common.write(f, 3, "if en = '1' then")
        for pe in input_pes:
            indent = 4 if enable_pin else 3
            if dt.is_complex:
                common.write(
                    f,
                    indent,
                    f"{pe.entity_name}_0_in_re_internal <= {pe.entity_name}_0_in_re;",
                )
                common.write(
                    f,
                    indent,
                    f"{pe.entity_name}_0_in_im_internal <= {pe.entity_name}_0_in_im;",
                )
            else:
                common.write(
                    f,
                    indent,
                    f"{pe.entity_name}_0_in_internal <= {pe.entity_name}_0_in;",
                )
        if enable_pin:
            common.write(f, 3, "end if;")
        common.synchronous_process_epilogue(f, name="input_reg_proc", clk="clk")
        common.blank(f)

    # Pipelining of outputs
    output_pes = [pe for pe in arch.processing_elements if pe.operation_type == Output]
    if output_register and output_pes:
        output_en_sig = "en_internal" if input_register else "en"
        common.synchronous_process_prologue(f, name="output_reg_proc")
        if enable_pin:
            common.write(f, 3, f"if {output_en_sig} = '1' then")
        for pe in output_pes:
            indent = 4 if enable_pin else 3
            if dt.is_complex:
                common.write(
                    f,
                    indent,
                    f"{pe.entity_name}_0_out_re <= {pe.entity_name}_0_out_re_internal;",
                )
                common.write(
                    f,
                    indent,
                    f"{pe.entity_name}_0_out_im <= {pe.entity_name}_0_out_im_internal;",
                )
            else:
                common.write(
                    f,
                    indent,
                    f"{pe.entity_name}_0_out <= {pe.entity_name}_0_out_internal;",
                )
        if enable_pin:
            common.write(f, 3, "end if;")
        common.synchronous_process_epilogue(f, name="output_reg_proc", clk="clk")
        common.blank(f)
