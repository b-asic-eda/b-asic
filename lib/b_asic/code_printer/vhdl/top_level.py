"""
Module for VHDL code generation of top level designs.
"""

from typing import TYPE_CHECKING, TextIO

from b_asic.code_printer.util import selector_bits, time_bin_str
from b_asic.code_printer.vhdl import common
from b_asic.data_type import VhdlDataType
from b_asic.special_operations import Input, Output

if TYPE_CHECKING:
    from b_asic.architecture import Architecture


def entity(f: TextIO, arch: "Architecture", dt: VhdlDataType) -> None:
    ports = ["clk : in std_logic", "rst : in std_logic"]
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
    f: TextIO, arch: "Architecture", dt: VhdlDataType, io_registers: bool = False
) -> None:
    common.write(f, 0, f"architecture rtl of {arch.entity_name} is")

    common.write(f, 1, "-- Component declaration")
    for pe in arch.processing_elements:
        pe.write_component_declaration(f, dt)
    for mem in arch.memories:
        mem.write_component_declaration(f, dt)
    arch.write_signal_declarations(f, dt)

    if io_registers:
        _write_io_register_signal_declarations(f, arch, dt)

    # Fetch information about multiplexers needed and declare control signals for them
    pe_mux_info, mem_mux_info = _collect_mux_info(arch)
    _write_mux_control_signal_declarations(f, pe_mux_info, mem_mux_info)

    common.write(f, 0, "begin")

    if io_registers:
        _write_io_registers(f, arch, dt)

    common.write(f, 1, "-- Component instantiation")
    for pe in arch.processing_elements:
        pe.write_component_instantiation(f, dt, io_registers=io_registers)
    for mem in arch.memories:
        mem.write_component_instantiation(f)

    _write_schedule_counter(f, arch, io_registers)

    # Generate control signals for multiplexers and then connect the top-level
    _write_mux_control_signals(f, arch.schedule_time, pe_mux_info, mem_mux_info)
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
                is_found = False

                for mem in arch.memories:
                    for var in mem.collection:
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

                time = process.start_time % arch.schedule_time
                source_signal = f"{source_resource.entity_name}_{source_port_index}_out"
                assignments.append((time, source_signal))

            if assignments:
                pe_mux_info.append((pe, port_number, assignments))

    # Collect memory input multiplexer info
    mem_mux_info = []  # List of (mem, assignments)
    for mem in arch.memories:
        assignments = []
        for var in mem.collection:
            source_op_graph_id = var.name.split(".")[0]
            source_port_index = var.name.split(".")[1]
            is_found = False
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
            time = var.start_time % arch.schedule_time
            source_signal = f"{source_pe.entity_name}_{source_port_index}_out"
            assignments.append((time, source_signal))

        if assignments:
            mem_mux_info.append((mem, assignments))

    return pe_mux_info, mem_mux_info


def _write_mux_control_signal_declarations(
    f: TextIO, pe_mux_info: list, mem_mux_info: list
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

    common.blank(f)


def _write_mux_control_signals(
    f: TextIO, schedule_time: int, pe_mux_info: list, mem_mux_info: list
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
            common.write(f, 2, f"{pe.entity_name}_{port_number}_sel <=")
            sel_bits = selector_bits(len(unique_sources))
            for time, source_signal in assignments:
                idx = source_to_idx[source_signal]
                sel_value = format(idx, f"0{sel_bits}b")
                common.write(
                    f,
                    3,
                    f'"{sel_value}" when "{time_bin_str(time, schedule_time)}",',
                )
            common.write(
                f, 3, f'"{"{}".format("-" * sel_bits)}" when others;', end="\n\n"
            )

    # Memory input mux control signals
    for mem, assignments in mem_mux_info:
        unique_sources = {signal for _, signal in assignments}
        if len(unique_sources) > 1:
            # Build source to index mapping
            source_to_idx = {src: idx for idx, src in enumerate(list(unique_sources))}

            common.write(f, 1, "with schedule_cnt select")
            common.write(f, 2, f"{mem.entity_name}_0_sel <=")
            sel_bits = selector_bits(len(unique_sources))
            for time, source_signal in assignments:
                idx = source_to_idx[source_signal]
                sel_value = format(idx, f"0{sel_bits}b")
                common.write(
                    f,
                    3,
                    f'"{sel_value}" when "{time_bin_str(time, schedule_time)}",',
                )
            common.write(
                f, 3, f'"{"{}".format("-" * sel_bits)}" when others;', end="\n\n"
            )


def _write_interconnect(
    f: TextIO, dt: VhdlDataType, pe_mux_info: list, mem_mux_info: list
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
    f: TextIO, arch: "Architecture", io_registers: bool = False
) -> None:
    rst_signal = "rst_int" if io_registers else "rst"
    common.write(f, 1, "-- Schedule counter")
    common.synchronous_process_prologue(f, name="schedule_cnt_proc")
    common.write_lines(
        f,
        [
            (3, f"if {rst_signal} = '1' then"),
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
    f: TextIO, arch: "Architecture", dt: VhdlDataType
) -> None:
    common.write(f, 1, "-- Internal signals for pipelined I/O")

    # Pipelined reset
    common.signal_declaration(f, "rst_int", "std_logic")

    # Pipelined inputs
    for pe in arch.processing_elements:
        if pe.operation_type == Input:
            for port in dt.get_input_port_declaration(f"{pe.entity_name}_int"):
                port_parts = port.split(":")
                signal_name = port_parts[0].strip()
                signal_type = ":".join(port_parts[1:]).strip()
                signal_type = signal_type.replace("in ", "").replace("out ", "")
                common.signal_declaration(f, signal_name, signal_type)

    # Pipelined outputs
    for pe in arch.processing_elements:
        if pe.operation_type == Output:
            for port in dt.get_output_port_declaration(f"{pe.entity_name}_int"):
                port_parts = port.split(":")
                signal_name = port_parts[0].strip()
                signal_type = ":".join(port_parts[1:]).strip()
                signal_type = signal_type.replace("in ", "").replace("out ", "")
                common.signal_declaration(f, signal_name, signal_type)
    common.blank(f)


def _write_io_registers(f: TextIO, arch: "Architecture", dt: VhdlDataType) -> None:
    common.write(f, 1, "-- Pipelining of I/O")

    # Pipelining of reset
    common.synchronous_process_prologue(f, name="rst_pipeline_proc")
    common.write(f, 3, "rst_int <= rst;")
    common.synchronous_process_epilogue(f, name="rst_pipeline_proc", clk="clk")
    common.blank(f)

    # Pipelining of inputs
    input_pes = [pe for pe in arch.processing_elements if pe.operation_type == Input]
    if input_pes:
        common.synchronous_process_prologue(f, name="input_reg_proc")
        for pe in input_pes:
            if dt.is_complex:
                common.write(
                    f, 3, f"{pe.entity_name}_int_0_in_re <= {pe.entity_name}_0_in_re;"
                )
                common.write(
                    f, 3, f"{pe.entity_name}_int_0_in_im <= {pe.entity_name}_0_in_im;"
                )
            else:
                common.write(
                    f, 3, f"{pe.entity_name}_int_0_in <= {pe.entity_name}_0_in;"
                )
        common.synchronous_process_epilogue(f, name="input_reg_proc", clk="clk")
        common.blank(f)

    # Pipelining of outputs
    output_pes = [pe for pe in arch.processing_elements if pe.operation_type == Output]
    if output_pes:
        common.synchronous_process_prologue(f, name="output_reg_proc")
        for pe in output_pes:
            if dt.is_complex:
                common.write(
                    f, 3, f"{pe.entity_name}_0_out_re <= {pe.entity_name}_int_0_out_re;"
                )
                common.write(
                    f, 3, f"{pe.entity_name}_0_out_im <= {pe.entity_name}_int_0_out_im;"
                )
            else:
                common.write(
                    f, 3, f"{pe.entity_name}_0_out <= {pe.entity_name}_int_0_out;"
                )
        common.synchronous_process_epilogue(f, name="output_reg_proc", clk="clk")
        common.blank(f)
