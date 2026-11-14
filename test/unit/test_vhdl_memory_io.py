"""VHDL generation for scheduled external memory interfaces."""

import io
import shutil
import subprocess

import pytest

from b_asic.architecture import Architecture, ProcessingElement
from b_asic.code_printer import VhdlPrinter
from b_asic.data_type import DataType, NumRepresentation
from b_asic.list_schedulers import HybridScheduler
from b_asic.process import MemoryVariable, OperatorProcess
from b_asic.resource_assigner import assign_processing_elements_and_memories
from b_asic.resources import ProcessCollection
from b_asic.schedule import Schedule
from b_asic.sfg_generators import ldlt_matrix_inverse
from b_asic.special_operations import MemoryRead, MemoryWrite


def _architecture(latency=2):
    reads = [
        MemoryRead(0, memory_name="A", latency=latency),
        MemoryRead(17, memory_name="B", latency=latency),
    ]
    writes = [
        MemoryWrite(7, reads[0], memory_name="C"),
        MemoryWrite(8, reads[1], memory_name="C"),
    ]
    schedule_time = 8
    read_pe = ProcessingElement(
        ProcessCollection(
            [OperatorProcess(0, reads[0]), OperatorProcess(2, reads[1])], schedule_time
        ),
        entity_name="reader",
    )
    write_pe = ProcessingElement(
        ProcessCollection(
            [
                OperatorProcess(latency, writes[0]),
                OperatorProcess(2 + latency, writes[1]),
            ],
            schedule_time,
        ),
        entity_name="writer",
    )
    direct = ProcessCollection(
        [
            MemoryVariable(latency, reads[0].output(0), {writes[0].input(0): 0}),
            MemoryVariable(2 + latency, reads[1].output(0), {writes[1].input(0): 0}),
        ],
        schedule_time,
    )
    return Architecture([read_pe, write_pe], [], "memory_design", direct)


@pytest.mark.parametrize(
    ("maximum", "bits"), [(0, 1), (1, 1), (7, 3), (8, 4), (17, 5), (255, 8), (256, 9)]
)
@pytest.mark.parametrize("operation_type", [MemoryRead, MemoryWrite])
def test_address_width_uses_values(maximum, bits, operation_type):
    pe = ProcessingElement(
        ProcessCollection(
            [
                OperatorProcess(0, operation_type(0)),
                OperatorProcess(1, operation_type(maximum)),
            ],
            4,
        ),
        entity_name="memory_access",
    )
    printer = VhdlPrinter(DataType(8))
    code = printer.print_ProcessingElement(pe)
    assert f"p_memory_0_address : out std_logic_vector({bits - 1} downto 0)" in code
    assert pe.control_table == {}


@pytest.mark.parametrize("address", [-1, 1.5, "3"])
def test_invalid_address(address):
    pe = ProcessingElement(
        ProcessCollection([OperatorProcess(0, MemoryRead(address))], 2),
        entity_name="memory_access",
    )
    with pytest.raises(ValueError, match="non-negative integers"):
        VhdlPrinter(DataType(8)).print_ProcessingElement(pe)


def test_requests_and_read_return_timing():
    arch = _architecture()
    reader, writer = arch.processing_elements
    printer = VhdlPrinter(DataType(8))
    read_code = printer.print_ProcessingElement(reader)
    write_code = printer.print_ProcessingElement(writer)
    assert "-- memory_0: memory name 'A'" in read_code
    assert "-- memory_1: memory name 'B'" in read_code
    assert "p_memory_0_enable <= en when schedule_cnt = \"000\" else '0';" in read_code
    assert "p_memory_1_enable <= en when schedule_cnt = \"010\" else '0';" in read_code
    assert 'p_memory_0_0_in when "010"' in read_code
    assert 'p_memory_1_0_in when "100"' in read_code
    assert '"0111" when "010"' in write_code
    assert '"1000" when "100"' in write_code
    assert "res_overflow_0_reg" not in read_code


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"centralize_control": False},
        {"pipeline_control": True},
        {"io_registers": True},
        {"enable_pin": False},
    ],
)
def test_architecture_wiring_and_enable(options):
    arch = _architecture()
    printer = VhdlPrinter(DataType(8))
    code = printer.print_Architecture(arch, **options)
    assert "reader_memory_0_address : out std_logic_vector(0 downto 0)" in code
    assert "reader_memory_1_address : out std_logic_vector(4 downto 0)" in code
    assert "writer_memory_0_address : out std_logic_vector(3 downto 0)" in code
    assert "p_memory_1_address => reader_memory_1_address" in code
    assert "p_memory_0_enable => writer_memory_0_enable" in code
    enable = (
        "'1'"
        if options.get("enable_pin") is False
        else ("en_internal" if options.get("io_registers") else "en")
    )
    assert f"memory_io_en <= {enable} and not rst;" in code
    assert "en => memory_io_en" in code
    assert "reader_memory_0_0_in_internal" not in code
    declaration = io.StringIO()
    arch.write_component_declaration(declaration, printer._dt)
    assert "reader_memory_1_address" in declaration.getvalue()


@pytest.mark.parametrize(
    "data_type",
    [
        DataType(8),
        DataType(8, is_complex=True),
        DataType((5, 10), num_repr=NumRepresentation.FLOATING_POINT),
    ],
)
@pytest.mark.parametrize(
    "options",
    [
        {},
        {"centralize_control": False},
        {"pipeline_control": True, "io_registers": True},
    ],
)
def test_generate_and_compile(tmp_path, data_type, options):
    ghdl = shutil.which("ghdl")
    if ghdl is None:
        pytest.skip("GHDL is not installed")
    arch = _architecture()
    printer = VhdlPrinter(data_type)
    printer.print(arch, path=tmp_path, **options)
    for filename in printer.get_compile_order(arch):
        result = subprocess.run(
            [ghdl, "-a", "--std=08", filename],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run(
        [ghdl, "-e", "--std=08", arch.entity_name],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_matrix_inverse_memory_codegen(tmp_path):
    ghdl = shutil.which("ghdl")
    if ghdl is None:
        pytest.skip("GHDL is not installed")
    graph = ldlt_matrix_inverse(2, pe="mads", mem=True)
    for operation_type in ("mads", "rec"):
        graph.set_latency_of_type_name(operation_type, 2)
        graph.set_execution_time_of_type_name(operation_type, 1)
    graph.set_latency_of_type_name("read", 2)
    schedule = Schedule(
        graph,
        HybridScheduler(
            input_times={f"read{i}": i for i in range(3)},
            output_delta_times={f"write{2 - i}": i for i in range(3)},
        ),
    )
    pes, memories, direct = assign_processing_elements_and_memories(
        schedule,
        strategy="left_edge",
        memory_read_ports=1,
        memory_write_ports=1,
        memory_total_ports=2,
    )
    arch = Architecture(pes, memories, "inverse_memory", direct)
    printer = VhdlPrinter(DataType((4, 4)))
    printer.print(arch, path=tmp_path)
    for filename in printer.get_compile_order(arch):
        result = subprocess.run(
            [ghdl, "-a", "--std=08", filename],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run(
        [ghdl, "-e", "--std=08", arch.entity_name],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_memory_timing_enable_and_reset_simulation(tmp_path):
    ghdl = shutil.which("ghdl")
    if ghdl is None:
        pytest.skip("GHDL is not installed")
    arch = _architecture()
    printer = VhdlPrinter(DataType(8))
    printer.print(arch, path=tmp_path)
    testbench = """
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity memory_test is end entity;
architecture test of memory_test is
    signal clk : std_logic := '0';
    signal rst, en : std_logic := '1';
    signal a_data, b_data, c_data : std_logic_vector(7 downto 0);
    signal a_address : std_logic_vector(0 downto 0);
    signal b_address : std_logic_vector(4 downto 0);
    signal c_address : std_logic_vector(3 downto 0);
    signal a_enable, b_enable, c_enable : std_logic;
    signal a_pending, b_pending : std_logic_vector(7 downto 0) := (others => '0');
    signal writes : natural := 0;
begin
    clk <= not clk after 5 ns;
    dut : entity work.memory_design port map (
        clk => clk, rst => rst, en => en,
        reader_memory_0_0_in => a_data,
        reader_memory_0_address => a_address,
        reader_memory_0_enable => a_enable,
        reader_memory_1_0_in => b_data,
        reader_memory_1_address => b_address,
        reader_memory_1_enable => b_enable,
        writer_memory_0_0_out => c_data,
        writer_memory_0_address => c_address,
        writer_memory_0_enable => c_enable
    );
    memory_model : process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                a_pending <= (others => '0'); b_pending <= (others => '0');
                a_data <= (others => '0'); b_data <= (others => '0');
                writes <= 0;
            elsif en = '1' then
                -- Two-cycle external read latency, with stalls shared by the design.
                a_data <= a_pending; b_data <= b_pending;
                if a_enable = '1' then
                    assert unsigned(a_address) = 0 report "wrong A address" severity failure;
                    a_pending <= x"25";
                end if;
                if b_enable = '1' then
                    assert unsigned(b_address) = 17 report "wrong B address" severity failure;
                    b_pending <= x"5A";
                end if;
                if c_enable = '1' then
                    if writes mod 2 = 0 then
                        assert unsigned(c_address) = 7 and c_data = x"25"
                            report "wrong first write address/data/latency" severity failure;
                    else
                        assert unsigned(c_address) = 8 and c_data = x"5A"
                            report "wrong second write address/data/latency" severity failure;
                    end if;
                    writes <= writes + 1;
                end if;
            end if;
        end if;
    end process;
    stimulus : process
    begin
        wait for 12 ns;
        assert a_enable = '0' and b_enable = '0' and c_enable = '0'
            report "access during reset" severity failure;
        rst <= '0';
        wait until falling_edge(clk);
        wait until rising_edge(clk);
        wait for 1 ns;
        assert c_enable = '1' report "missing first write" severity failure;
        en <= '0';
        wait for 1 ns;
        assert a_enable = '0' and b_enable = '0' and c_enable = '0'
            report "access while disabled" severity failure;
        wait for 20 ns;
        en <= '1';
        wait for 100 ns;
        assert writes >= 2 report "missing writes after resume" severity failure;
        std.env.stop;
        wait;
    end process;
end architecture;
"""
    (tmp_path / "memory_test.vhdl").write_text(testbench)
    sources = [*printer.get_compile_order(arch), "memory_test.vhdl"]
    for arguments in (
        ["-a", "--std=08", *sources],
        ["-e", "--std=08", "memory_test"],
        ["-r", "--std=08", "memory_test", "--assert-level=error", "--stop-time=200ns"],
    ):
        result = subprocess.run(
            [ghdl, *arguments],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
