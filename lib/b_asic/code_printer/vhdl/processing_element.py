"""
Module for VHDL code generation of processing elements.
"""

from typing import TYPE_CHECKING, TextIO

import numpy as np

from b_asic.code_printer.vhdl import common
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
        f"schedule_cnt : in unsigned({pe.schedule_time.bit_length() - 1} downto 0)",
    ]
    ports += [
        f"p_{count}_in : in {dt.get_type_str()}" for count in range(pe.input_count)
    ]
    if pe.operation_type == Input:
        ports.extend(dt.get_input_port_declaration("p"))

    ports += [
        f"p_{count}_out : out {dt.get_type_str()}" for count in range(pe.output_count)
    ]
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
            for input_port in range(pe.input_count):
                common.write(
                    f,
                    1,
                    f"signal p_{input_port}_in_reg_{stage} : {dt.get_type_str()} := {dt.get_init_val()};",
                )
        else:
            for output_port in range(pe.output_count):
                common.write(
                    f,
                    1,
                    f"signal res_{output_port}_reg_{stage - 1} : {dt.get_type_str()};",
                )

    # Define results
    for count in range(pe.output_count):
        common.write(f, 1, f"signal res_{count} : {dt.get_type_str()};")

    # Define control signals
    for entry in pe.control_table:
        if entry.int_bits == 1 and entry.frac_bits == 0:
            vhdl_type = "std_logic"
        else:
            vhdl_type = f"signed({entry.int_bits + entry.frac_bits - 1} downto 0)"
        common.write(f, 1, f"signal {entry.name} : {vhdl_type};")

    # Define integer bits for control signals
    for entry in pe.control_table:
        common.write(
            f, 1, f"constant WL_{entry.name.upper()}_INT : integer := {entry.int_bits};"
        )


def _statement_region_common(
    f: TextIO, pe: "ProcessingElement", dt: VhdlDataType
) -> None:
    # Generate pipeline stages
    if pe._latency > 0:
        common.write(f, 1, "process(clk)")
        common.write(f, 1, "begin")
        common.write(f, 2, "if rising_edge(clk) then")

        for stage in range(pe._latency):
            if stage == 0:
                for count in range(pe.input_count):
                    common.write(f, 3, f"p_{count}_in_reg_{stage} <= p_{count}_in;")
            elif stage == 1:
                for count in range(pe.output_count):
                    common.write(f, 3, f"res_{count}_reg_0 <= res_{count};")
            elif stage >= 2:
                for count in range(pe.output_count):
                    common.write(
                        f,
                        3,
                        f"res_{count}_reg_{stage - 1} <= res_{count}_reg_{stage - 2};",
                    )

        common.write(f, 2, "end if;")
        common.write(f, 1, "end process;", end="\n\n")

    # Generate control signals
    for entry in pe.control_table:
        common.write(f, 1, "with schedule_cnt select")
        common.write(f, 2, f"{entry.name} <=")
        for time, val in entry.values.items():
            if isinstance(val, bool):
                val_str = f"'{int(val)}'"
            elif isinstance(val, (int, np.integer, float, np.floating)):
                int_val = int(val * 2**entry.frac_bits)
                val_str = f'b"{common._get_bin_str(int_val, entry.int_bits + entry.frac_bits)}"'
            else:
                raise NotImplementedError
            avail_time = (time + 1) % pe.schedule_time if pe._latency > 0 else time
            avail_time_bit_str = bin(avail_time)[2:].zfill(
                pe.schedule_time.bit_length()
            )
            common.write(f, 3, f'{val_str} when "{avail_time_bit_str}",')
        if isinstance(val, bool):
            common.write(f, 3, "'-' when others;", end="\n\n")
        else:
            common.write(f, 3, "(others => '-') when others;", end="\n\n")

    # Connect results to outputs
    if pe._latency < 2:
        for count in range(pe.output_count):
            common.write(f, 1, f"p_{count}_out <= res_{count};")
    else:
        for count in range(pe.output_count):
            common.write(f, 1, f"p_{count}_out <= res_{count}_reg_{pe._latency - 2};")
