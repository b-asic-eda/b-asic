"""
Module for VHDL code generation of processing elements.
"""

from typing import TYPE_CHECKING, TextIO

import numpy as np

from b_asic.code_printer.util import bin_str, time_bin_str
from b_asic.code_printer.vhdl import common
from b_asic.code_printer.vhdl.util import schedule_time_type
from b_asic.data_type import VhdlDataType
from b_asic.process import OperatorProcess
from b_asic.special_operations import Input, Output

if TYPE_CHECKING:
    from b_asic.architecture import ProcessingElement


def entity(f: TextIO, pe: "ProcessingElement", dt: VhdlDataType) -> None:
    if not all(isinstance(process, OperatorProcess) for process in pe.collection):
        raise ValueError(
            "HDL can only be generated for ProcessCollection of OperatorProcesses"
        )

    ports = [
        "clk : in std_logic",
        f"schedule_cnt : in {schedule_time_type(pe.schedule_time)}",
    ]
    ports += [f"p_{count}_in : in {dt.type_str}" for count in range(pe.input_count)]
    if pe.operation_type == Input:
        ports.extend(dt.get_input_port_declaration("p"))

    ports += [f"p_{count}_out : out {dt.type_str}" for count in range(pe.output_count)]
    if pe.operation_type == Output:
        ports.extend(dt.get_output_port_declaration("p"))

    common.entity_declaration(f, pe.entity_name, ports=ports)


def architecture(
    f: TextIO, pe: "ProcessingElement", dt: VhdlDataType, core_code: tuple[str, str]
) -> None:
    common.write(f, 0, f"architecture rtl of {pe.entity_name} is")

    _declarative_region_common(f, pe, dt)
    common.write(f, 0, core_code[0])
    common.write(f, 0, "begin")
    _statement_region_common(f, pe, dt)
    common.write(f, 0, core_code[1])

    common.write(f, 0, "end architecture rtl;")


def _declarative_region_common(
    f: TextIO, pe: "ProcessingElement", dt: VhdlDataType
) -> None:
    # Define pipeline stages
    for stage in range(pe._latency):
        if stage == 0:
            for output_port in range(pe.output_count):
                common.signal_declaration(
                    f, f"res_{output_port}_reg_{stage}", dt.type_str
                )
        else:
            for input_port in range(pe.input_count):
                common.signal_declaration(
                    f,
                    f"p_{input_port}_in_reg_{stage - 1}",
                    dt.type_str,
                    dt.init_val,
                )

    for input_port in range(pe.input_count):
        common.signal_declaration(f, f"op_{input_port}", dt.type_str)

    # Define results
    for count in range(pe.output_count):
        common.signal_declaration(f, f"res_{count}", dt.type_str)

    # Define control signals
    for name, entry in pe.control_table.items():
        if entry.int_bits == 1 and entry.frac_bits == 0:
            vhdl_type = "std_logic"
        else:
            vhdl_type = f"signed({entry.bits - 1} downto 0)"
        common.signal_declaration(f, name, vhdl_type)

    # Define integer bits for control signals
    for name, entry in pe.control_table.items():
        common.constant_declaration(
            f, f"WL_{name.upper()}_INT", "integer", entry.int_bits
        )


def _statement_region_common(
    f: TextIO, pe: "ProcessingElement", dt: VhdlDataType
) -> None:
    # Generate pipeline stages
    if pe._latency > 0:
        common.synchronous_process_prologue(f)

        for stage in range(pe._latency):
            if stage == 0:
                for count in range(pe.output_count):
                    common.write(f, 3, f"res_{count}_reg_0 <= res_{count};")
            elif stage == 1:
                for count in range(pe.input_count):
                    common.write(f, 3, f"p_{count}_in_reg_{stage - 1} <= p_{count}_in;")
            elif stage >= 2:
                for count in range(pe.input_count):
                    common.write(
                        f,
                        3,
                        f"p_{count}_in_reg_{stage - 1} <= p_{count}_in_reg_{stage - 2};",
                    )

        common.synchronous_process_epilogue(f)

    for input_port in range(pe.input_count):
        if pe._latency > 1:
            common.write(
                f,
                1,
                f"op_{input_port} <= p_{input_port}_in_reg_{pe._latency - 2};",
            )
        else:
            common.write(f, 1, f"op_{input_port} <= p_{input_port}_in;")

    # Generate control signals
    for name, entry in pe.control_table.items():
        common.write(f, 1, "with schedule_cnt select")
        common.write(f, 2, f"{name} <=")
        for time, val in entry.values.items():
            if isinstance(val, bool):
                val_str = f"'{int(val)}'"
            elif isinstance(val, (int, np.integer, float, np.floating)):
                int_val = int(val * 2**entry.frac_bits)
                val_str = f'b"{bin_str(int_val, entry.bits)}"'
            else:
                raise NotImplementedError
            offset = pe._latency - 1 if pe._latency >= 2 else 0
            avail_time = (time + offset) % pe.schedule_time if pe._latency > 0 else time
            common.write(f, 3, f'{val_str} when "{time_bin_str(avail_time, pe)}",')
        if isinstance(val, bool):
            common.write(f, 3, "'-' when others;", end="\n\n")
        else:
            common.write(f, 3, "(others => '-') when others;", end="\n\n")

    # Connect results to outputs
    if pe._latency == 0:
        for count in range(pe.output_count):
            common.write(f, 1, f"p_{count}_out <= res_{count};")
    else:
        for count in range(pe.output_count):
            common.write(f, 1, f"p_{count}_out <= res_{count}_reg_0;")
