"""External memory interfaces for scheduled MemoryRead and MemoryWrite PEs."""

from operator import index
from typing import TYPE_CHECKING, TextIO

from b_asic.code_printer.util import bin_str, time_bin_str
from b_asic.code_printer.vhdl import common
from b_asic.data_type import _VhdlDataType
from b_asic.special_operations import MemoryRead, MemoryWrite

if TYPE_CHECKING:
    from b_asic.architecture import ProcessingElement
    from b_asic.process import OperatorProcess


def is_memory_io(pe: "ProcessingElement") -> bool:
    return issubclass(pe.operation_type, (MemoryRead, MemoryWrite))


def interfaces(pe: "ProcessingElement") -> list[tuple[str, list["OperatorProcess"]]]:
    """Group a PE's accesses by memory name, in sorted name order."""
    if not is_memory_io(pe):
        return []
    banks = {}
    for process in pe.processes:
        banks.setdefault(process.operation.memory_name, []).append(process)
    return sorted(banks.items())


def _address_bits(processes: list["OperatorProcess"]) -> int:
    addresses = []
    for process in processes:
        try:
            address = index(process.operation.address)
        except TypeError as error:
            raise ValueError(
                "Memory addresses must be non-negative integers"
            ) from error
        if address < 0:
            raise ValueError("Memory addresses must be non-negative integers")
        addresses.append(address)
    return max(1, max(addresses).bit_length())


def ports(pe: "ProcessingElement", dt: _VhdlDataType, prefix: str) -> list[str]:
    """Declare one data/address/enable interface for each memory used by a PE."""
    result = []
    for bank, (_, processes) in enumerate(interfaces(pe)):
        name = f"{prefix}_memory_{bank}"
        bits = _address_bits(processes)
        if issubclass(pe.operation_type, MemoryRead):
            result.extend(dt.get_input_port_declaration(name))
        else:
            result.extend(dt.get_output_port_declaration(name))
        result += [
            f"{name}_address : out std_logic_vector({bits - 1} downto 0)",
            f"{name}_enable : out std_logic",
        ]
    return result


def port_mappings(pe: "ProcessingElement", dt: _VhdlDataType) -> list[str]:
    local = ports(pe, dt, "p")
    external = ports(pe, dt, pe.entity_name)
    return [
        f"{left.split(':')[0].strip()} => {right.split(':')[0].strip()}"
        for left, right in zip(local, external, strict=True)
    ]


def declarations(f: TextIO, pe: "ProcessingElement", dt: _VhdlDataType) -> None:
    if not is_memory_io(pe):
        return
    data_ports = (
        dt.get_input_port_declaration("p")
        if issubclass(pe.operation_type, MemoryRead)
        else dt.get_output_port_declaration("p")
    )
    for port in data_ports:
        name, direction_type = port.split(":", maxsplit=1)
        signal_type = direction_type.strip().split(maxsplit=1)[1]
        common.signal_declaration(f, name.strip(), signal_type)
    for bank, (memory_name, _) in enumerate(interfaces(pe)):
        common.write(f, 1, f"-- memory_{bank}: memory name {memory_name!r}")


def statements(f: TextIO, pe: "ProcessingElement", dt: _VhdlDataType) -> None:
    if not is_memory_io(pe):
        return
    banks = interfaces(pe)
    read = issubclass(pe.operation_type, MemoryRead)
    parts = ("_re", "_im") if dt.is_complex else ("",)
    for bank, (_, processes) in enumerate(banks):
        prefix = f"p_memory_{bank}"
        bits = _address_bits(processes)
        requests = {}
        for process in processes:
            offset = 0 if read else (process.operation.input(0).latency_offset or 0)
            time = (process.start_time + offset) % pe.schedule_time
            if time in requests:
                raise ValueError(
                    f"Multiple memory accesses at cycle {time} in {pe.entity_name}"
                )
            requests[time] = process.operation.address
        common.write(f, 1, "with schedule_cnt select")
        common.write(f, 2, f"{prefix}_address <=")
        for time, address in sorted(requests.items()):
            common.write(
                f,
                3,
                f'"{bin_str(address, bits)}" when "{time_bin_str(time, pe.schedule_time)}",',
            )
        common.write(f, 3, "(others => '0') when others;")
        active = " or ".join(
            f'schedule_cnt = "{time_bin_str(time, pe.schedule_time)}"'
            for time in sorted(requests)
        )
        common.write(f, 1, f"{prefix}_enable <= en when {active} else '0';")
        if not read:
            for part in parts:
                common.write(f, 1, f"{prefix}_0_out{part} <= p_0_out{part};")

    if read:
        for part in parts:
            if len(banks) == 1:
                common.write(f, 1, f"p_0_in{part} <= p_memory_0_0_in{part};")
                continue
            common.write(f, 1, "with schedule_cnt select")
            common.write(f, 2, f"p_0_in{part} <=")
            for bank, (_, processes) in enumerate(banks):
                for process in processes:
                    time = (
                        process.start_time + process.operation.latency
                    ) % pe.schedule_time
                    common.write(
                        f,
                        3,
                        f'p_memory_{bank}_0_in{part} when "{time_bin_str(time, pe.schedule_time)}",',
                    )
            common.write(f, 3, "(others => '-') when others;")
    common.blank(f)
