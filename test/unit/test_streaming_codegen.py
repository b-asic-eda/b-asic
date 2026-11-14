"""Simulate generated streaming interfaces, including independently clocked FIFOs."""

import shutil
import subprocess

import pytest

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.code_printer.vhdl.streaming import StreamInterface
from b_asic.code_printer.vhdl.vhdl_printer import VhdlPrinter
from b_asic.data_type import DataType
from b_asic.process import MemoryVariable, OperatorProcess
from b_asic.resources import ProcessCollection
from b_asic.special_operations import Input, Output


def make_arch(shared=False, storage=None):
    pes, wires = [], []
    period = 4 if storage else 2
    for i in range(2 if shared else 1):
        source = Input()
        sink = Output(source)
        for op, name in ((source, f"source{i}"), (sink, f"sink{i}")):
            time = i + (3 if storage and op is sink else 0)
            pes.append(
                ProcessingElement(
                    ProcessCollection([OperatorProcess(time, op)], period),
                    entity_name=name,
                )
            )
        wires.append(
            MemoryVariable(i, source.output(0), {sink.input(0): 3 if storage else 0})
        )
    memories = []
    if storage:
        memory = Memory(
            ProcessCollection(wires, period, cyclic=True),
            memory_type=storage,
            entity_name="storage",
        )
        memory.assign()
        memories.append(memory)
        wires = []
    if shared == "resource":
        pes = [
            ProcessingElement(
                ProcessCollection(
                    [p for pe in pes if pe.operation_type == op for p in pe.collection],
                    period,
                ),
                entity_name=name,
            )
            for op, name in ((Input, "source0"), (Output, "sink0"))
        ]
    return Architecture(pes, memories, "stream_core", ProcessCollection(wires, period))


def run_vhdl(tmp_path, printer, arch, tb, **options):
    if not shutil.which("ghdl"):
        pytest.skip("GHDL is required for streaming simulation")
    printer.print(arch, path=tmp_path, **options)
    (tmp_path / "tb.vhdl").write_text(tb)
    for args in (
        ["-a", "--std=08", *printer.get_compile_order(arch), "tb.vhdl"],
        ["-e", "--std=08", "tb"],
        ["-r", "--std=08", "tb", "--assert-level=error", "--stop-time=30us"],
    ):
        result = subprocess.run(
            ["ghdl", *args],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout + result.stderr


@pytest.mark.parametrize("protocol", ["axi4_stream", "avalon_st"])
@pytest.mark.parametrize("dual", [False, True])
@pytest.mark.parametrize(
    ("shared", "storage"),
    [
        (False, None),
        (True, None),
        ("resource", None),
        (False, "RAM"),
        (False, "register"),
    ],
)
def test_stream_roundtrip(tmp_path, protocol, dual, shared, storage):
    arch = make_arch(shared, storage)
    config = StreamInterface(
        protocol,
        clock_mode="asynchronous" if dual else "synchronous",
        fifo_depth=4,
        startup_threshold=3,
        frame_length=5,
    )
    inputs = {
        "rx": [
            pe.entity_name
            for pe in arch.processing_elements
            if pe.operation_type == Input
        ]
    }
    outputs = {
        "tx": [
            pe.entity_name
            for pe in arch.processing_elements
            if pe.operation_type == Output
        ]
    }
    names = (
        ("tdata", "tvalid", "tready", "tlast")
        if protocol == "axi4_stream"
        else ("data", "valid", "ready", "endofpacket")
    )
    mapping = ", ".join(
        f"{prefix}_{pin} => {prefix}_{signal}"
        for prefix in ("rx", "tx")
        for pin, signal in zip(names, ("data", "valid", "ready", "last"), strict=True)
    )
    clocks = ", rx_clk => bus_clk, tx_clk => bus_clk" if dual else ""
    tb = _TB.replace("MAPPING", mapping + clocks).replace(
        "BUS_HALF", "7" if dual else "5"
    )
    run_vhdl(
        tmp_path,
        VhdlPrinter(DataType(8)),
        arch,
        tb,
        interface=config,
        stream_inputs=inputs,
        stream_outputs=outputs,
    )


def test_fixed_interval_default():
    printer, arch = VhdlPrinter(DataType(8)), make_arch()
    code = printer.print_Architecture(arch)
    explicit = printer.print_Architecture(arch, interface=StreamInterface())
    # The generated banner contains a timestamp.
    assert (
        code[code.index("library ieee;") :]
        == explicit[explicit.index("library ieee;") :]
    )
    assert "tvalid" not in code


@pytest.mark.parametrize("complex_data", [False, True])
@pytest.mark.parametrize("vhdl_2008", [False, True])
def test_stream_top_level_port_shapes(tmp_path, complex_data, vhdl_2008):
    if not shutil.which("ghdl"):
        pytest.skip("GHDL is required")
    arch = make_arch()
    printer = VhdlPrinter(
        DataType((3, 4), is_complex=complex_data), vhdl_2008=vhdl_2008
    )
    printer.print(
        arch,
        path=tmp_path,
        interface=StreamInterface("axi4_stream", clock_mode="asynchronous"),
    )
    result = subprocess.run(
        [
            "ghdl",
            "-a",
            "--std=08" if vhdl_2008 else "--std=93",
            # Compile the streaming interface independently of arithmetic backends.
            *(["types.vhdl"] if complex_data else []),
            "stream_core.vhdl",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("overflow", [False, True])
def test_rigid_core_fault(tmp_path, overflow):
    arch = make_arch()
    config = StreamInterface("axi4_stream", fifo_depth=2, stallable=False)
    tb = _FAULT_TB.replace("INPUT_VALID", "'1'" if overflow else "input_valid")
    run_vhdl(
        tmp_path,
        VhdlPrinter(DataType(8)),
        arch,
        tb,
        interface=config,
        stream_inputs={"rx": ["source0"]},
        stream_outputs={"tx": ["sink0"]},
    )


def test_streaming_without_external_enable(tmp_path):
    tb = (
        _TB.replace(
            "MAPPING",
            "rx_tdata => rx_data, rx_tvalid => rx_valid, rx_tready => rx_ready, rx_tlast => rx_last, tx_tdata => tx_data, tx_tvalid => tx_valid, tx_tready => tx_ready, tx_tlast => tx_last",
        )
        .replace("BUS_HALF", "5")
        .replace("en => en,", "")
    )
    run_vhdl(
        tmp_path,
        VhdlPrinter(DataType(8)),
        make_arch(),
        tb,
        interface=StreamInterface("axi4_stream", fifo_depth=3, frame_length=5),
        stream_inputs={"rx": ["source0"]},
        stream_outputs={"tx": ["sink0"]},
        enable_pin=False,
    )


@pytest.mark.parametrize(
    "options",
    [
        {"fifo_depth": 0},
        {"startup_threshold": 17},
        {"clock_mode": "asynchronous", "fifo_depth": 3},
        {"frame_length": 0},
        {"protocol": "invalid"},
    ],
)
def test_invalid_configuration(options):
    with pytest.raises(ValueError, match=r"must|Unknown"):
        StreamInterface(**options)


def test_group_collision():
    arch = make_arch(True)
    # Put the two input samples at the same time: a serial stream cannot serve both.
    arch.processing_elements[2].collection.collection[0]._start_time = 0
    with pytest.raises(ValueError, match="same cycle"):
        VhdlPrinter(DataType(8)).print_Architecture(
            arch,
            interface=StreamInterface("axi4_stream"),
            stream_inputs={"rx": ["source0", "source1"]},
        )


_TB = """
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity tb is end;
architecture sim of tb is
    signal clk, bus_clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal en : std_logic := '1';
    signal active, fault, core_last, core_valid : std_logic;
    signal rx_data, tx_data : std_logic_vector(7 downto 0) := (others => '0');
    signal rx_valid, rx_ready, rx_last, tx_valid, tx_ready, tx_last : std_logic := '0';
begin
    clk <= not clk after 5 ns;
    bus_clk <= not bus_clk after BUS_HALF ns;
    dut: entity work.stream_core port map (
        clk => clk, rst => rst, en => en, core_active => active, stream_error => fault,
        rx_core_last => core_last, rx_core_valid => core_valid, MAPPING);
    process begin
        wait for 42 ns; rst <= '0';
        -- External enable must stop counting without stopping FIFO drainage.
        wait for 900 ns; en <= '0'; wait for 170 ns; en <= '1'; wait;
    end process;
    process
    begin
        wait until rst = '0';
        for sample in 0 to 79 loop
            wait until falling_edge(bus_clk);
            rx_valid <= '1';
            rx_data <= std_logic_vector(to_unsigned(sample, 8));
            if sample mod 5 = 4 then rx_last <= '1'; else rx_last <= '0'; end if;
            loop
                wait until rising_edge(bus_clk);
                exit when rx_ready = '1';
            end loop;
            if sample mod 13 = 12 then
                wait until falling_edge(bus_clk); rx_valid <= '0';
                wait for 240 ns;
            end if;
        end loop;
        wait until falling_edge(bus_clk); rx_valid <= '0'; wait;
    end process;
    process
        variable ticks : natural := 0;
    begin
        wait until falling_edge(bus_clk);
        ticks := ticks + 1;
        -- Force FIFO fill and prolonged stalls, then alternating backpressure.
        if ticks mod 41 > 26 then tx_ready <= '1'; else tx_ready <= '0'; end if;
    end process;
    process
        variable expected : natural := 0;
        variable stalled : boolean := false;
        variable held : std_logic_vector(8 downto 0);
    begin
        wait until rising_edge(bus_clk);
        if rst = '0' then
            assert fault = '0' report "unexpected stream fault" severity failure;
            if stalled then
                assert tx_valid = '1' and (tx_last & tx_data) = held report "unstable stalled output" severity failure;
            end if;
            stalled := tx_valid = '1' and tx_ready = '0';
            held := tx_last & tx_data;
            if tx_valid = '1' and tx_ready = '1' then
                assert to_integer(unsigned(tx_data)) = expected report "sample order/data mismatch: expected " & integer'image(expected) & " got " & integer'image(to_integer(unsigned(tx_data))) severity failure;
                if expected mod 5 = 4 then assert tx_last = '1' severity failure;
                else assert tx_last = '0' severity failure; end if;
                expected := expected + 1;
                if expected = 80 then report "PASS"; std.env.stop; end if;
            end if;
        end if;
    end process;
    process
        variable consumed : natural := 0;
    begin
        wait until rising_edge(clk);
        if rst = '0' and core_valid = '1' then
            if consumed mod 5 = 4 then assert core_last = '1' severity failure;
            else assert core_last = '0' severity failure; end if;
            consumed := consumed + 1;
        end if;
    end process;
    process begin wait for 25 us; assert false report "timeout" severity failure; end process;
end architecture;
"""


_FAULT_TB = """
library ieee;
use ieee.std_logic_1164.all;
entity tb is end;
architecture sim of tb is
    signal clk, rst, fault, active, input_valid, ready : std_logic := '0';
begin
    clk <= not clk after 5 ns;
    dut: entity work.stream_core port map (
        clk => clk, rst => rst, en => '1', stream_error => fault, core_active => active,
        rx_tdata => x"12", rx_tvalid => INPUT_VALID, rx_tready => ready, rx_tlast => '0',
        rx_core_valid => open, rx_core_last => open,
        tx_tdata => open, tx_tvalid => open, tx_tready => '0', tx_tlast => open);
    process begin
        rst <= '1'; wait for 40 ns; rst <= '0';
        input_valid <= '1'; wait until rising_edge(clk) and ready = '1';
        wait until falling_edge(clk); input_valid <= '0';
        wait for 400 ns;
        assert fault = '1' and active = '0' report "missing fatal stream fault" severity failure;
        wait for 50 ns;
        assert fault = '1' report "fault not sticky" severity failure;
        rst <= '1'; wait for 20 ns;
        assert fault = '0' report "reset did not clear fault" severity failure;
        report "PASS"; std.env.stop;
    end process;
end architecture;
"""
