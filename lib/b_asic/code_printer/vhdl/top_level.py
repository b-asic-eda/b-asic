"""
Module for VHDL code generation of top level designs.
"""

from typing import TYPE_CHECKING, TextIO

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


def architecture(f: TextIO, arch: "Architecture", dt: VhdlDataType) -> None:
    common.write(f, 0, f"architecture rtl of {arch.entity_name} is")

    common.write(f, 1, "-- Component declaration")
    for pe in arch.processing_elements:
        pe.write_component_declaration(f, dt)
    for mem in arch.memories:
        mem.write_component_declaration(f, dt)
    arch.write_signal_declarations(f, dt)

    common.write(f, 0, "begin", start="\n")

    common.write(f, 1, "-- Component instantiation")
    for pe in arch.processing_elements:
        pe.write_component_instantiation(f, dt)
    for mem in arch.memories:
        mem.write_component_instantiation(f)

    _write_schedule_counter(f, arch)
    _write_interconnect(f, arch, dt)
    common.write(f, 0, "end architecture rtl;", start="", end="\n\n")


def _write_interconnect(f: TextIO, arch: "Architecture", dt: VhdlDataType) -> None:
    # Define PE input interconnect
    for pe in arch.processing_elements:
        for port_number in range(pe.input_count):
            common.write(f, 1, "with schedule_cnt select")
            common.write(f, 2, f"{pe.entity_name}_{port_number}_in <=")
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
                time_bit_str = bin(time)[2:].zfill(pe.schedule_time.bit_length())
                common.write(
                    f,
                    3,
                    f'{source_resource.entity_name}_{source_port.index}_out when "{time_bit_str}",',
                )
            common.write(f, 3, f"{dt.get_dontcare_str()} when others;", end="\n\n")

    # Define memory input interconnect
    for mem in arch.memories:
        common.write(f, 1, "with schedule_cnt select")
        common.write(f, 2, f"{mem.entity_name}_0_in <=")
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
            time_bit_str = bin(time)[2:].zfill(pe.schedule_time.bit_length())
            common.write(
                f,
                3,
                f'{source_pe.entity_name}_{source_port_index}_out when "{time_bit_str}",',
            )
        common.write(f, 3, f"{dt.get_dontcare_str()} when others;", end="\n\n")


def _write_schedule_counter(f: TextIO, arch: "Architecture") -> None:
    common.write(f, 1, "-- Schedule counter")
    common.synchronous_process_prologue(f, name="schedule_cnt_proc")
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
    common.write(f, 1, "")
