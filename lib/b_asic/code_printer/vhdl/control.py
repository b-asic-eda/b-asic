"""Schedule-indexed control words for generated architectures."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO

import apytypes as apy
import numpy as np

from b_asic.code_printer.util import bin_str, selector_bits
from b_asic.code_printer.vhdl import common

if TYPE_CHECKING:
    from b_asic.architecture import Memory, ProcessingElement


@dataclass
class Control:
    name: str
    port: str
    vhdl_type: str
    bits: int
    values: list[str]
    registered: bool = False


def _encode(value, bits: int, frac_bits: int) -> str:
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, apy.APyFixed):
        return bin_str(value.to_bits(), bits)
    if isinstance(value, (int, np.integer, float, np.floating)):
        return bin_str(int(value * 2**frac_bits), bits)
    raise NotImplementedError


def unique_sources(assignments: list[tuple[int, str]]) -> list[str]:
    return list(dict.fromkeys(signal for _, signal in assignments))


def pe_controls(
    pe: "ProcessingElement",
    input_registers: int,
    cycles: dict[str, int],
    registered: bool,
) -> list[Control]:
    controls = []
    for name, entry in pe.control_table.items():
        value = next(iter(entry.values.values()))
        is_boolean = isinstance(value, bool)
        bits = 1 if is_boolean else entry.bits
        vhdl_type = (
            "std_logic"
            if is_boolean
            else f"{'signed' if entry.is_signed else 'unsigned'}({bits - 1} downto 0)"
        )

        if entry.is_static:
            values = [
                _encode(entry.get_static_value(), bits, entry.frac_bits)
            ] * pe.schedule_time
        else:
            values = ["-" * bits for _ in range(pe.schedule_time)]
            offset = cycles.get(name, input_registers) - int(registered)
            for time, value in entry.values.items():
                values[(time + offset) % pe.schedule_time] = _encode(
                    value, bits, entry.frac_bits
                )
        controls.append(
            Control(
                f"{pe.entity_name}_{name}", name, vhdl_type, bits, values, registered
            )
        )
    return controls


def memory_controls(memory: "Memory", options: dict) -> list[Control]:
    schedule_time = memory.schedule_time
    if memory._memory_type == "RAM":
        bits = len(memory.assignment).bit_length()
        registered = bool(options.get("pipeline_mem_control", False))
        write_addresses = ["-" * bits for _ in range(schedule_time)]
        write_enables = ["0" for _ in range(schedule_time)]
        read_addresses = ["0" * bits for _ in range(schedule_time)]
        forward = ["-" for _ in range(schedule_time)]
        output_sync = bool(options.get("output_sync", True))
        for address, collection in enumerate(memory.assignment):
            for variable in collection:
                write_time = (variable.start_time - int(registered)) % schedule_time
                if variable.execution_time:
                    write_addresses[write_time] = bin_str(address, bits)
                    write_enables[write_time] = "1"
                forward[write_time] = str(int(1 in variable.reads.values()))
                for read_time in variable.reads.values():
                    time = (
                        variable.start_time
                        + read_time
                        - int(output_sync)
                        - int(registered)
                    ) % schedule_time
                    read_addresses[time] = bin_str(address, bits)
        entries = [
            ("ctrl_write_adr_0", bits, write_addresses),
            ("ctrl_write_en_0", 1, write_enables),
            ("ctrl_read_adr_0", bits, read_addresses),
        ]
        if output_sync:
            entries.append(("ctrl_forward", 1, forward))
        return [
            Control(
                f"{memory.entity_name}_{name}",
                name,
                "std_logic"
                if name in ("ctrl_write_en_0", "ctrl_forward")
                else f"unsigned({width - 1} downto 0)",
                width,
                values,
                registered,
            )
            for name, width, values in entries
        ]

    table = memory._forward_backward_table
    if table is None:
        raise ValueError(
            "Memory assignment must be performed before generating register-based code."
        )
    output_regs = {
        entry.outputs_from for entry in table.table if entry.outputs_from is not None
    }
    output_table = {reg: index for index, reg in enumerate(output_regs)}
    back_edges = {
        (source, target)
        for entry in table
        for source, target in entry.back_edge_to.items()
    }
    back_table = {edge: index + 1 for index, edge in enumerate(back_edges)}
    back_bits = selector_bits(len(back_edges) + 1)
    output_bits = selector_bits(len(output_regs))
    back_registered = bool(options.get("pipeline_back_edge_mux", False))
    output_registered = bool(options.get("pipeline_output_mux", False))
    back_values = ["0" * back_bits for _ in range(schedule_time)]
    output_values = ["0" * output_bits for _ in range(schedule_time)]
    for time, entry in enumerate(table):
        if entry.back_edge_to:
            if len(entry.back_edge_to) != 1:
                raise ValueError("Only one back edge per cycle is supported")
            edge = next(iter(entry.back_edge_to.items()))
            back_values[(time - int(back_registered)) % schedule_time] = bin_str(
                back_table[edge], back_bits
            )
        if entry.outputs_from is not None:
            output_values[(time - int(output_registered)) % schedule_time] = bin_str(
                output_table[entry.outputs_from], output_bits
            )
    return [
        Control(
            f"{memory.entity_name}_ctrl_back_edge",
            "ctrl_back_edge",
            f"unsigned({back_bits - 1} downto 0)",
            back_bits,
            back_values,
            back_registered,
        ),
        Control(
            f"{memory.entity_name}_ctrl_output",
            "ctrl_output",
            f"unsigned({output_bits - 1} downto 0)",
            output_bits,
            output_values,
            output_registered,
        ),
    ]


def mux_controls(
    schedule_time: int, pe_mux_info: list, mem_mux_info: list, registered: bool
) -> list[Control]:
    result = []
    muxes = [
        (pe.entity_name, port, assignments) for pe, port, assignments in pe_mux_info
    ]
    muxes += [
        (memory.entity_name, 0, assignments) for memory, assignments in mem_mux_info
    ]
    for name, port, assignments in muxes:
        sources = unique_sources(assignments)
        if len(sources) < 2:
            continue
        bits = selector_bits(len(sources))
        values = ["-" * bits for _ in range(schedule_time)]
        for time, source in assignments:
            values[(time - int(registered)) % schedule_time] = bin_str(
                sources.index(source), bits
            )
        result.append(
            Control(
                f"{name}_{port}_sel",
                "",
                f"std_logic_vector({bits - 1} downto 0)",
                bits,
                values,
                registered,
            )
        )
    return result


def declarations(f: TextIO, controls: list[Control], schedule_time: int) -> None:
    if not controls:
        return
    width = sum(item.bits for item in controls)
    depth = 2 ** max(1, (schedule_time - 1).bit_length())
    common.write(f, 1, "-- Control signals")
    common.write(
        f,
        1,
        f"type control_rom_type is array (0 to {depth - 1}) of std_logic_vector({width - 1} downto 0);",
    )
    common.write(f, 1, "constant control_rom : control_rom_type := (")
    for time in range(schedule_time):
        word = "".join(item.values[time] for item in controls)
        common.write(f, 2, f'{time} => "{word}",')
    common.write(f, 2, "others => (others => '-')")
    common.write(f, 1, ");")
    if any(not item.registered for item in controls):
        common.signal_declaration(
            f, "control_word", f"std_logic_vector({width - 1} downto 0)"
        )
    if any(item.registered for item in controls):
        common.signal_declaration(
            f,
            "control_word_reg",
            f"std_logic_vector({width - 1} downto 0)",
            default_value=f"control_rom({schedule_time - 1})",
        )
    high = width - 1
    for item in controls:
        word = "control_word_reg" if item.registered else "control_word"
        low = high - item.bits + 1
        if item.vhdl_type == "std_logic":
            alias_type = "std_logic"
            target = f"{word}({high})"
        else:
            alias_type = f"std_logic_vector({item.bits - 1} downto 0)"
            target = f"{word}({high} downto {low})"
        common.write(f, 1, f"alias {item.name} : {alias_type} is {target};")
        high = low - 1
    common.blank(f)


def port_signal(item: Control) -> str:
    if item.vhdl_type.startswith("unsigned"):
        return f"unsigned({item.name})"
    if item.vhdl_type.startswith("signed"):
        return f"signed({item.name})"
    return item.name


def statements(
    f: TextIO, controls: list[Control], en_sig: str, schedule_time: int
) -> None:
    if not controls:
        return
    if any(not item.registered for item in controls):
        common.write(f, 1, "control_word <= control_rom(to_integer(schedule_cnt));")
    if any(item.registered for item in controls):
        common.synchronous_process_prologue(f, name="control_rom_proc")
        common.write(f, 3, "if rst = '1' then")
        common.write(f, 4, f"control_word_reg <= control_rom({schedule_time - 1});")
        common.write(f, 3, f"elsif {en_sig} = '1' then")
        common.write(f, 4, "control_word_reg <= control_rom(to_integer(schedule_cnt));")
        common.write(f, 3, "end if;")
        common.synchronous_process_epilogue(f, name="control_rom_proc")
