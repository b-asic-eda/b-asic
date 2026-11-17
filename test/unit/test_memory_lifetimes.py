"""Long-lived storage without unnecessary memory-to-memory transfers."""

from unittest.mock import Mock

import pytest

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.code_printer.vhdl import control, top_level
from b_asic.code_printer.vhdl.vhdl_printer import VhdlPrinter
from b_asic.core_operations import ConstantMultiplication
from b_asic.data_type import DataType
from b_asic.process import (
    MemoryInputPort,
    MemoryOutputPort,
    MemoryVariable,
    OperatorProcess,
    PlainMemoryVariable,
    Process,
)
from b_asic.resource_assigner import assign_processing_elements_and_memories
from b_asic.resources import ProcessCollection
from b_asic.special_operations import Input, Output


def long_schedule():
    source = Input()
    source.graph_id = "in0"
    sink = Output(source)
    sink.graph_id = "out0"
    schedule = Mock()
    schedule.get_operations.return_value = ProcessCollection(
        [OperatorProcess(0, source), OperatorProcess(1, sink)], 4, cyclic=True
    )
    schedule.get_memory_variables.return_value = ProcessCollection(
        [MemoryVariable(0, source.output(0), {sink.input(0): 9}, "long")],
        4,
        cyclic=True,
    )
    return schedule


@pytest.mark.parametrize(
    "strategy",
    [
        "left_edge",
        "greedy_graph_color",
        "greedy_min_mux",
        "ilp_graph_color",
        "ilp_min_mux",
        "cp_min_mux",
    ],
)
@pytest.mark.parametrize("options", [{}, {"chain_split_strategy": None}])
def test_default_preserves_long_lifetimes(strategy, options):
    if strategy == "cp_min_mux":
        pytest.importorskip("cpmpy")
    schedule = long_schedule()
    pes, memories, direct = assign_processing_elements_and_memories(
        schedule, strategy=strategy, **options
    )
    arch = Architecture(pes, memories, direct_interconnects=direct)
    assert arch.schedule_time == 4
    assert arch.memory_schedule_time == 12
    assert all(pe.schedule_time == 4 for pe in pes)
    variables = [v for memory in memories for v in memory]
    assert len(variables) == 3
    assert all(v.execution_time == 9 for v in variables)
    assert all(not isinstance(v.write_port, MemoryOutputPort) for v in variables)
    assert sum(len(memory.assignment) for memory in memories) == 3
    original = next(iter(schedule.get_memory_variables.return_value))
    assert original.name == "long"
    assert original.execution_time == 9


@pytest.mark.parametrize("storage", ["RAM", "register"])
def test_long_lifetimes_work_with_both_storage_types(storage):
    pes, memories, direct = assign_processing_elements_and_memories(
        long_schedule(), strategy="left_edge", memory_type=storage
    )
    arch = Architecture(pes, memories, direct_interconnects=direct)
    printer = VhdlPrinter(DataType(8))
    assert "memory_schedule_cnt" in printer.print_Architecture(arch)
    assert all(printer.print_Memory(memory) for memory in memories)


@pytest.mark.parametrize("strategy", ["greedy_min_mux", "ilp_min_mux", "cp_min_mux"])
def test_unfolding_preserves_pe_conflicts_at_period_boundary(strategy):
    if strategy == "cp_min_mux":
        pytest.importorskip("cpmpy")
    sources = [Input(), Input()]
    sources[1].execution_time = 2
    sinks = [Output(source) for source in sources]
    for index, (source, sink) in enumerate(zip(sources, sinks, strict=True)):
        source.graph_id = f"in{index}"
        sink.graph_id = f"out{index}"
    schedule = Mock()
    schedule.get_operations.return_value = ProcessCollection(
        [
            OperatorProcess(time, op)
            for time, op in zip((0, 3, 1, 0), [*sources, *sinks], strict=True)
        ],
        4,
    )
    schedule.get_memory_variables.return_value = ProcessCollection(
        [
            MemoryVariable(time, source.output(0), {sink.input(0): 9}, f"long{index}")
            for index, (time, source, sink) in enumerate(
                zip((0, 3), sources, sinks, strict=True)
            )
        ],
        4,
    )
    pes, _, _ = assign_processing_elements_and_memories(schedule, strategy=strategy)
    assert sum(pe.operation_type == Input for pe in pes) == 2


@pytest.mark.parametrize("factor", [1, 2, 3, 4])
@pytest.mark.parametrize("strategy", ["fixed", "min_ports"])
def test_explicit_splitting_and_partial_unfolding(factor, strategy):
    pes, memories, direct = assign_processing_elements_and_memories(
        long_schedule(),
        strategy="left_edge",
        chain_split_strategy=strategy,
        memory_unfolding_factor=factor,
    )
    arch = Architecture(pes, memories, direct_interconnects=direct)
    assert arch.schedule_time == 4
    assert arch.memory_schedule_time == 4 * factor
    variables = [v for memory in memories for v in memory]
    segments = (9 + 4 * factor - 1) // (4 * factor)
    assert len(variables) == factor * segments
    assert sum(isinstance(v.write_port, MemoryOutputPort) for v in variables) == (
        factor * (segments - 1)
    )
    assert all(v.execution_time <= 4 * factor for v in variables)


@pytest.mark.parametrize("chain_strategy", ["fixed", "min_ports"])
def test_chain_strategy_enables_splitting_on_one_period(chain_strategy):
    _, memories, _ = assign_processing_elements_and_memories(
        long_schedule(), strategy="left_edge", chain_split_strategy=chain_strategy
    )
    assert all(memory.schedule_time == 4 for memory in memories)
    assert sum(len(memory.collection) for memory in memories) == 3


def test_partial_unfolding_requires_explicit_splitting():
    with pytest.raises(ValueError, match="chain_split_strategy"):
        assign_processing_elements_and_memories(
            long_schedule(), strategy="left_edge", memory_unfolding_factor=2
        )


@pytest.mark.parametrize("factor", [0, -1, 1.5, True])
def test_invalid_memory_unfolding_factor(factor):
    with pytest.raises(ValueError, match="positive integer"):
        assign_processing_elements_and_memories(
            long_schedule(), strategy="left_edge", memory_unfolding_factor=factor
        )


@pytest.mark.parametrize("length", [0, -1, 1.5, True])
def test_invalid_chain_length(length):
    with pytest.raises(ValueError, match="positive integer"):
        ProcessCollection([], 4).split_into_chains(length)


def test_invalid_chain_strategy():
    with pytest.raises(ValueError, match="Invalid chain split strategy"):
        assign_processing_elements_and_memories(
            long_schedule(), chain_split_strategy="unknown"
        )


def consumer_delays(collection):
    """Follow relays and recover each original consumer's absolute lifetime."""
    result = {}

    def visit(variable, elapsed):
        for port, delay in variable.reads.items():
            if isinstance(port, MemoryInputPort):
                assert port.destination_variable.write_port.source_variable is variable
                visit(port.destination_variable, elapsed + delay)
            else:
                result[port] = elapsed + delay

    root = next(v for v in collection if not isinstance(v.write_port, MemoryOutputPort))
    visit(root, 0)
    return result


def test_load_aware_splitting_reduces_peak_accesses():
    source = Input()
    sinks = [Output(source) for _ in range(4)]
    variable = MemoryVariable(
        0,
        source.output(0),
        {sink.input(0): delay for sink, delay in zip(sinks, (0, 7, 7, 9), strict=True)},
        "long",
    )
    original = ProcessCollection([variable], 8, cyclic=True)
    fixed = original.split_into_chains()
    balanced = original.split_into_chains(strategy="min_ports")
    assert len(fixed) == len(balanced) == 2
    assert balanced.total_ports_bound() < fixed.total_ports_bound()
    assert consumer_delays(fixed) == consumer_delays(balanced) == variable.reads
    assert original.collection == [variable]
    assert all(v.execution_time <= 8 for v in balanced)


@pytest.mark.parametrize("factor", [2, 3])
def test_unfold_chains_reconnects_wrapping_relays(factor):
    source = Input()
    sink = Output(source)
    original = ProcessCollection(
        [MemoryVariable(3, source.output(0), {sink.input(0): 9}, "long")], 4, True
    ).split_into_chains()
    unfolded = original.unfold(factor)
    assert unfolded.schedule_time == 4 * factor
    assert unfolded._cyclic
    assert len(unfolded) == 3 * factor
    assert all(v not in original for v in unfolded)
    for variable in unfolded:
        for port, delay in variable.reads.items():
            if isinstance(port, MemoryInputPort):
                target = port.destination_variable
                assert target in unfolded
                assert target.write_port.source_variable is variable
                assert (variable.start_time + delay) % unfolded.schedule_time == (
                    target.start_time
                )
    assert consumer_delays(original) == {sink.input(0): 9}


def test_unfold_requires_complete_relay_chains():
    source = Input()
    sink = Output(source)
    chain = ProcessCollection(
        [MemoryVariable(0, source.output(0), {sink.input(0): 9})], 4
    ).split_into_chains()
    root = next(v for v in chain if not isinstance(v.write_port, MemoryOutputPort))
    with pytest.raises(ValueError, match="all connected chain variables"):
        ProcessCollection([root], 4).unfold(2)


def test_unfold_plain_variables_preserves_lifetimes_and_ports():
    variable = PlainMemoryVariable(1, 2, {3: 9}, "plain")
    unfolded = ProcessCollection([variable], 4, True).unfold(3)
    assert [v.start_time for v in unfolded] == [1, 5, 9]
    assert all(v.write_port == 2 and v.reads == {3: 9} for v in unfolded)
    assert all(v.reads is not variable.reads for v in unfolded)


def test_unfold_rejects_operations():
    with pytest.raises(TypeError, match="Only memory variables"):
        ProcessCollection([Process(0, 1)], 4).unfold(2)


def unfolded_architecture():
    """Use different memory banks on successive iterations of the PE schedule."""
    inputs = [Input(), Input()]
    multipliers = [
        ConstantMultiplication(value, source, latency=0, execution_time=1)
        for source, value in zip(inputs, (2, 3), strict=True)
    ]
    outputs = [Output(multiplier) for multiplier in multipliers]
    pes = [
        ProcessingElement(
            ProcessCollection(
                [
                    OperatorProcess(time, op)
                    for time, op in zip(times, ops, strict=True)
                ],
                4,
            ),
            name,
        )
        for name, ops, times in (
            ("inputs", inputs, (0, 2)),
            ("multipliers", multipliers, (0, 2)),
            ("outputs", outputs, (1, 3)),
        )
    ]
    variables = ProcessCollection(
        [
            MemoryVariable(time, mul.output(0), {out.input(0): 9}, f"long{index}")
            for index, (time, mul, out) in enumerate(
                zip((0, 2), multipliers, outputs, strict=True)
            )
        ],
        4,
        True,
    ).unfold(3)
    memories = [
        Memory(
            ProcessCollection([v for v in variables if v.start_time // 4 == phase], 12),
            entity_name=f"storage{phase}",
        )
        for phase in range(3)
    ]
    direct = ProcessCollection(
        [
            MemoryVariable(time, source.output(0), {mul.input(0): 0})
            for time, source, mul in zip((0, 2), inputs, multipliers, strict=True)
        ],
        4,
    )
    return Architecture(pes, memories, "unfolded", direct)


@pytest.mark.parametrize("centralized", [False, True])
@pytest.mark.parametrize("registered", [False, True])
def test_unfolded_control_periods(centralized, registered):
    arch = unfolded_architecture()
    code = VhdlPrinter(DataType(8)).print_Architecture(
        arch,
        centralize_control=centralized,
        pipeline_pe_control=registered,
        pipeline_mem_control=registered,
        multiplexer_control_registered=registered,
    )
    assert "if schedule_cnt = 3 then" in code
    assert "if memory_schedule_cnt = 11 then" in code
    if centralized:
        assert "constant pe_control_rom" in code
        assert "constant memory_control_rom" in code
        assert "pe_control_rom(to_integer(schedule_cnt))" in code
        assert "memory_control_rom(to_integer(memory_schedule_cnt))" in code
    else:
        assert "schedule_cnt => memory_schedule_cnt" in code
        assert "with memory_schedule_cnt select" in code


def test_unfolded_muxes_select_the_correct_iteration():
    arch = unfolded_architecture()
    pe_muxes, _ = top_level._collect_mux_info(arch)
    output_mux = next(
        assignments for pe, _, assignments in pe_muxes if pe.entity_name == "outputs"
    )
    assert dict(output_mux) == {
        1: "storage1_0_out",
        3: "storage1_0_out",
        5: "storage2_0_out",
        7: "storage2_0_out",
        9: "storage0_0_out",
        11: "storage0_0_out",
    }
    # Execute the generated address tables over several memory periods. Reads
    # must see the value from nine cycles ago, across every counter wrap.
    tables = {
        memory: {
            item.port: item.values
            for item in control.memory_controls(memory, {"output_sync": False})
        }
        for memory in arch.memories
    }
    contents = {memory.entity_name: {} for memory in arch.memories}
    for time in range(60):
        cycle = time % 12
        for memory, table in tables.items():
            if time >= 9 and cycle in output_mux_times(output_mux, memory):
                address = int(table["ctrl_read_adr_0"][cycle], 2)
                assert contents[memory.entity_name][address] == time - 9
            if table["ctrl_write_en_0"][cycle] == "1":
                address = int(table["ctrl_write_adr_0"][cycle], 2)
                contents[memory.entity_name][address] = time


def output_mux_times(assignments, memory):
    return {
        time for time, signal in assignments if signal == f"{memory.entity_name}_0_out"
    }


def test_architecture_rejects_fractional_memory_period():
    arch = unfolded_architecture()
    arch.memories[0].collection._schedule_time = 6
    with pytest.raises(ValueError, match="integer multiple"):
        Architecture(
            arch.processing_elements,
            arch.memories,
            direct_interconnects=arch.direct_interconnects,
        )


@pytest.mark.parametrize("centralized", [False, True])
@pytest.mark.parametrize("registered", [False, True])
def test_unfolded_vhdl_roundtrip(tmp_path, centralized, registered):
    from test.unit.test_multiport_codegen import simulate

    arch = unfolded_architecture()
    printer = VhdlPrinter(DataType(8))
    printer.print(
        arch,
        path=tmp_path,
        centralize_control=centralized,
        pipeline_pe_control=registered,
        pipeline_mem_control=registered,
        multiplexer_control_registered=registered,
    )
    simulate(
        tmp_path,
        printer.get_compile_order(arch),
        """
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity tb is end;
architecture sim of tb is
signal clk : std_logic := '0';
signal rst : std_logic := '1';
signal en : std_logic := '0';
signal data_in, data_out : std_logic_vector(7 downto 0) := (others => '0');
begin
dut: entity work.unfolded port map (
    clk => clk, rst => rst, en => en,
    inputs_0_in => data_in, outputs_0_out => data_out
);
process begin
    wait for 5 ns; clk <= '1'; wait for 5 ns; clk <= '0';
    rst <= '0'; en <= '1';
    for cycle in 0 to 59 loop
        data_in <= std_logic_vector(to_signed(cycle + 1, 8));
        wait for 5 ns;
        if cycle >= 13 and cycle mod 2 = 1 then
            if cycle mod 4 = 1 then
                assert signed(data_out) = to_signed(2 * (cycle - 8), 8)
                    report "Wrong value after unfolded read (coefficient 2)" severity failure;
            else
                assert signed(data_out) = to_signed(3 * (cycle - 8), 8)
                    report "Wrong value after unfolded read (coefficient 3)" severity failure;
            end if;
        end if;
        if cycle = 22 then
            en <= '0'; clk <= '1'; wait for 5 ns; clk <= '0';
            wait for 5 ns; en <= '1'; wait for 5 ns;
        end if;
        clk <= '1'; wait for 5 ns; clk <= '0';
    end loop;
    report "PASS"; std.env.stop; wait;
end process;
end;
""",
    )
