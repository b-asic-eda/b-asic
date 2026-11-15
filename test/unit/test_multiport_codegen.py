"""Regression coverage for physical memory ports in VHDL generation."""

import shutil
import subprocess

import pytest

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.code_printer.vhdl import control, top_level
from b_asic.code_printer.vhdl.vhdl_printer import VhdlPrinter
from b_asic.data_type import DataType
from b_asic.process import MemoryVariable, OperatorProcess, PlainMemoryVariable
from b_asic.resources import ProcessCollection
from b_asic.special_operations import Input, Output


@pytest.mark.parametrize("registered", [False, True])
def test_multiport_control_tables(registered):
    variables = [
        PlainMemoryVariable(0, 0, {0: 1, 1: 3}, "first"),
        PlainMemoryVariable(0, 1, {0: 1, 1: 3}, "second"),
    ]
    memory = Memory(
        ProcessCollection(variables, 5, cyclic=True),
        memory_type="RAM",
        entity_name="storage",
        read_ports=2,
        write_ports=2,
    )
    # Keep the selected ports even when they differ from the default allocation.
    ports = {
        (variable, delay): 1 - index
        for index, variable in enumerate(variables)
        for delay in (None, 1, 3)
    }
    memory.collection._memory_port_assignment = ports
    controls = {
        item.port: item
        for item in control.memory_controls(
            memory, {"pipeline_mem_control": registered}
        )
    }
    for variable in variables:
        write_port = ports[variable, None]
        address = next(
            index for index, cell in enumerate(memory.assignment) if variable in cell
        )
        time = -int(registered) % 5
        assert controls[f"ctrl_write_adr_{write_port}"].values[time] == format(
            address, "02b"
        )
        assert controls[f"ctrl_write_en_{write_port}"].values[time] == "1"
        for delay in (1, 3):
            read_port = ports[variable, delay]
            time = (delay - 1 - int(registered)) % 5
            assert controls[f"ctrl_read_adr_{read_port}"].values[time] == format(
                address, "02b"
            )
            assert controls[f"ctrl_forward_{read_port}"].values[time] == format(
                write_port + 1 if delay == 1 else 0, "02b"
            )


def make_architecture(write_ports=2, read_ports=2, storage="RAM"):
    pes, variables = [], []
    for index in range(4):
        start = 2 * index if write_ports == 1 else 4 * (index // 2)
        source = Input()
        source.graph_id = f"in{index}"
        pes.append(
            ProcessingElement(
                ProcessCollection([OperatorProcess(start, source)], 8),
                entity_name=f"source{index}",
            )
        )
        reads = {}
        delays = (1, 3) if read_ports > 1 else (1 + index % 2, 3 + index % 2)
        for delay in delays:
            sink = Output(source)
            sink.graph_id = f"out{index}_{delay}"
            pes.append(
                ProcessingElement(
                    ProcessCollection([OperatorProcess((start + delay) % 8, sink)], 8),
                    entity_name=f"sink{index}_{delay}",
                )
            )
            reads[sink.input(0)] = delay
        variables.append(MemoryVariable(start, source.output(0), reads, f"var{index}"))
    collection = ProcessCollection(variables, 8, cyclic=True)
    # Read ports vary per access. Each input port multiplexes different PEs.
    collection._memory_port_assignment = {
        (variable, delay): index % write_ports
        if delay is None
        else (index + int(delay == 1 and write_ports > 1)) % min(read_ports, 2)
        for index, variable in enumerate(variables)
        for delay in (None, *sorted(set(variable.reads.values())))
    }
    if storage == "register":
        # Swap all reads in alternating slots so a variable's intermediate
        # and final reads can use different physical ports without conflicts.
        for (variable, delay), port in collection._memory_port_assignment.items():
            if delay is not None:
                collection._memory_port_assignment[variable, delay] = (
                    port + int((variable.start_time + delay) % 4 == 1)
                ) % read_ports
    memory = Memory(
        collection,
        memory_type=storage,
        entity_name="storage",
        read_ports=read_ports,
        write_ports=write_ports,
    )
    if storage == "register":
        memory.assign()
    return Architecture(pes, [memory], "multiport")


def test_multiport_interconnect():
    arch = make_architecture()
    pe_muxes, memory_muxes = top_level._collect_mux_info(arch)
    assert [(port, assignments) for _, port, assignments in memory_muxes] == [
        (0, [(0, "source0_0_out"), (4, "source2_0_out")]),
        (1, [(0, "source1_0_out"), (4, "source3_0_out")]),
    ]
    for pe, port, assignments in pe_muxes:
        index, delay = map(int, pe.entity_name.removeprefix("sink").split("_"))
        assert port == 0
        assert assignments == [
            (4 * (index // 2) + delay, f"storage_{(index + int(delay == 1)) % 2}_out")
        ]


def simulate(tmp_path, sources, tb):
    if not shutil.which("ghdl"):
        pytest.skip("GHDL is required for memory simulation")
    (tmp_path / "tb.vhdl").write_text(tb)
    for arguments in (
        ["-a", "--std=08", *sources, "tb.vhdl"],
        ["-e", "--std=08", "tb"],
        ["-r", "--std=08", "tb", "--assert-level=error"],
    ):
        result = subprocess.run(
            ["ghdl", *arguments],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout + result.stderr


@pytest.mark.parametrize("centralized", [False, True])
@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("output_sync", [False, True])
@pytest.mark.parametrize(
    ("write_ports", "read_ports", "storage"),
    [(2, 2, "RAM"), (1, 2, "RAM"), (2, 1, "RAM"), (3, 4, "RAM"), (1, 2, "register")],
)
def test_multiport_roundtrip(
    tmp_path, centralized, registered, output_sync, write_ports, read_ports, storage
):
    arch = make_architecture(write_ports, read_ports, storage)
    printer = VhdlPrinter(DataType(8))
    printer.print(
        arch,
        path=tmp_path,
        centralize_control=centralized,
        pipeline_mem_control=registered,
        multiplexer_control_registered=registered,
        output_sync=output_sync,
        pipeline_output_mux=registered,
        pipeline_back_edge_mux=registered,
    )
    declarations, mapping, checks, drive = (
        [],
        ["clk => clk", "rst => rst", "en => en"],
        [],
        [],
    )
    for index, variable in enumerate(arch.memories[0].collection):
        declarations.append(
            f"signal input{index} : std_logic_vector(7 downto 0) := (others => '0');"
        )
        mapping.append(f"source{index}_0_in => input{index}")
        drive.append(
            f"input{index} <= std_logic_vector(to_signed({11 + index} + 16 * frame, 8));"
        )
        for delay in sorted(set(variable.reads.values())):
            name = f"sink{index}_{delay}_0_out"
            declarations.append(f"signal {name} : std_logic_vector(7 downto 0);")
            mapping.append(f"{name} => {name}")
            time = (variable.start_time + delay) % 8
            frame = "(frame - 1)" if variable.start_time + delay >= 8 else "frame"
            checks.append(
                f"if cycle = {time} then assert signed({name}) = to_signed({11 + index} + 16 * {frame}, 8) "
                f'report "{name} incorrect" severity failure; end if;'
            )
    tb = """
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity tb is end;
architecture sim of tb is
signal clk : std_logic := '0';
signal rst : std_logic := '1';
signal en : std_logic := '0';
DECLARATIONS
begin
dut: entity work.multiport port map (MAPPING);
process begin
    wait for 5 ns; clk <= '1'; wait for 5 ns; clk <= '0';
    rst <= '0'; en <= '1';
    for frame in 0 to 2 loop
        DRIVE
        for cycle in 0 to 7 loop
            wait for 5 ns;
            -- Allow one frame to fill local control pipeline registers.
            if frame > 0 then
                CHECKS
            end if;
            -- Pause the schedule and memory together, then resume.
            if cycle = 3 then
                en <= '0'; clk <= '1'; wait for 5 ns; clk <= '0';
                wait for 5 ns; en <= '1'; wait for 5 ns;
                if frame > 0 then
                    CHECKS
                end if;
            end if;
            clk <= '1'; wait for 5 ns; clk <= '0';
        end loop;
    end loop;
    report "PASS"; std.env.stop; wait;
end process;
end;
"""
    simulate(
        tmp_path,
        printer.get_compile_order(arch),
        tb.replace("DECLARATIONS", "\n".join(declarations))
        .replace("MAPPING", ", ".join(mapping))
        .replace("DRIVE", "\n".join(drive))
        .replace("CHECKS", "\n".join(checks)),
    )


def test_register_memory_rejects_multiple_write_ports():
    memory = Memory(
        ProcessCollection(
            [
                PlainMemoryVariable(0, 0, {0: 2}, "first"),
                PlainMemoryVariable(0, 1, {0: 2}, "second"),
            ],
            4,
        ),
        memory_type="register",
        read_ports=2,
        write_ports=2,
    )
    with pytest.raises(ValueError, match="only one write port"):
        memory.assign()


@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("stored_delay", [0, 3])
def test_register_memory_bypass_and_broadcast(tmp_path, registered, stored_delay):
    stored = PlainMemoryVariable(0, 0, {0: stored_delay, 1: stored_delay}, "stored")
    bypass = PlainMemoryVariable(3, 0, {0: 0}, "bypass")
    variables = ProcessCollection([stored, bypass], 5, cyclic=True)
    variables._memory_port_assignment = {
        (stored, None): 0,
        (stored, stored_delay): 1,
        (bypass, None): 0,
        (bypass, 0): 0,
    }
    memory = Memory(
        variables,
        memory_type="register",
        entity_name="storage",
        read_ports=3,
        write_ports=1,
        assign=True,
    )
    sources = control.register_output_sources(memory)
    assert sources == [{3: -1}, {stored_delay: -1 if stored_delay == 0 else 0}, {}]
    code = VhdlPrinter(DataType(8)).print_Memory(
        memory, pipeline_output_mux=registered, pipeline_back_edge_mux=registered
    )
    (tmp_path / "storage.vhdl").write_text(code)
    simulate(
        tmp_path,
        ["storage.vhdl"],
        """
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity tb is end;
architecture sim of tb is
signal clk : std_logic := '0';
signal cnt : unsigned(2 downto 0) := (others => '0');
signal data_in, stored, bypass : signed(7 downto 0) := (others => '0');
begin
dut: entity work.storage port map (
    clk => clk, en => '1', schedule_cnt => cnt, p_0_in => data_in,
    p_0_out => bypass, p_1_out => stored, p_2_out => open
);
process begin
    for frame in 0 to 2 loop
        for cycle in 0 to 4 loop
            cnt <= to_unsigned(cycle, 3);
            if cycle = 3 then data_in <= to_signed(27, 8);
            else data_in <= to_signed(11, 8); end if;
            wait for 5 ns;
            if cycle = STORED_DELAY and frame > 0 then
                assert stored = to_signed(11, 8) report "Stored read failed" severity failure;
            end if;
            if cycle = 3 and frame > 0 then
                assert bypass = to_signed(27, 8) report "Bypass failed" severity failure;
            end if;
            clk <= '1'; wait for 5 ns; clk <= '0';
        end loop;
    end loop;
    report "PASS"; std.env.stop; wait;
end process;
end;
""".replace("STORED_DELAY", str(stored_delay)),
    )
