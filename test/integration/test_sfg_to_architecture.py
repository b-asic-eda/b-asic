import pytest

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import (
    MADS,
    Butterfly,
    ConstantMultiplication,
    DontCare,
    Reciprocal,
)
from b_asic.core_schedulers import ASAPScheduler, HybridScheduler
from b_asic.schedule import Schedule
from b_asic.sfg_generators import ldlt_matrix_inverse, radix_2_dif_fft
from b_asic.special_operations import Input, Output


def test_pe_constrained_schedule():
    sfg = ldlt_matrix_inverse(N=5)

    sfg.set_latency_of_type(MADS.type_name(), 3)
    sfg.set_latency_of_type(Reciprocal.type_name(), 2)
    sfg.set_execution_time_of_type(MADS.type_name(), 1)
    sfg.set_execution_time_of_type(Reciprocal.type_name(), 1)

    resources = {MADS.type_name(): 2, Reciprocal.type_name(): 1}

    # Generate a schedule to ensure that schedule can be overwritten without bugs
    schedule = Schedule(sfg, scheduler=ASAPScheduler())

    schedule = Schedule(sfg, scheduler=HybridScheduler(resources))

    direct, mem_vars = schedule.get_memory_variables().split_on_length()
    assert mem_vars.read_ports_bound() <= 7
    assert mem_vars.write_ports_bound() <= 4

    operations = schedule.get_operations()

    with pytest.raises(
        TypeError, match="Different Operation types in ProcessCollection"
    ):
        ProcessingElement(operations)

    mads = operations.get_by_type_name(MADS.type_name())
    with pytest.raises(
        ValueError, match="Cannot map ProcessCollection to single ProcessingElement"
    ):
        ProcessingElement(mads, entity_name="mad")
    mads = mads.split_on_execution_time()
    with pytest.raises(
        TypeError,
        match="Argument process_collection must be ProcessCollection, not <class 'list'>",
    ):
        ProcessingElement(mads, entity_name="mad")

    assert len(mads) == 2

    reciprocals = operations.get_by_type_name(Reciprocal.type_name())
    dont_cares = operations.get_by_type_name(DontCare.type_name())
    inputs = operations.get_by_type_name(Input.type_name())
    outputs = operations.get_by_type_name(Output.type_name())

    mads0 = ProcessingElement(mads[0], entity_name="mads0")
    mads1 = ProcessingElement(mads[1], entity_name="mads1")
    reciprocal_pe = ProcessingElement(reciprocals, entity_name="rec")

    dont_care_pe = ProcessingElement(dont_cares, entity_name="dc")

    pe_in = ProcessingElement(inputs, entity_name='input')
    pe_out = ProcessingElement(outputs, entity_name='output')

    mem_vars_set = mem_vars.split_on_ports(read_ports=1, write_ports=1, total_ports=2)
    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("graph_color")

    arch = Architecture(
        {mads0, mads1, reciprocal_pe, dont_care_pe, pe_in, pe_out},
        memories,
        direct_interconnects=direct,
    )

    assert len(arch.memories) == len(memories)
    for i in range(len(memories)):
        assert arch.memories[i] == memories[i]

    assert len(arch.processing_elements) == 6

    assert arch.direct_interconnects == direct

    assert arch.schedule_time == schedule.schedule_time


def test_pe_and_memory_constrained_chedule():
    sfg = radix_2_dif_fft(points=16)

    sfg.set_latency_of_type(Butterfly.type_name(), 3)
    sfg.set_latency_of_type(ConstantMultiplication.type_name(), 2)
    sfg.set_execution_time_of_type(Butterfly.type_name(), 1)
    sfg.set_execution_time_of_type(ConstantMultiplication.type_name(), 1)

    # generate a schedule to ensure that schedule can be overwritten without bugs
    schedule = Schedule(sfg, scheduler=ASAPScheduler())

    # generate the real constrained schedule
    resources = {Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}
    schedule = Schedule(
        sfg,
        scheduler=HybridScheduler(
            resources, max_concurrent_reads=2, max_concurrent_writes=2
        ),
    )

    operations = schedule.get_operations()
    bfs = operations.get_by_type_name(Butterfly.type_name())
    const_muls = operations.get_by_type_name(ConstantMultiplication.type_name())
    inputs = operations.get_by_type_name(Input.type_name())
    outputs = operations.get_by_type_name(Output.type_name())

    bf_pe = ProcessingElement(bfs, entity_name="bf")
    mul_pe = ProcessingElement(const_muls, entity_name="mul")

    pe_in = ProcessingElement(inputs, entity_name='input')
    pe_out = ProcessingElement(outputs, entity_name='output')

    mem_vars = schedule.get_memory_variables()
    direct, mem_vars = mem_vars.split_on_length()
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1, write_ports=1, total_ports=2, heuristic="graph_color"
    )

    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1, write_ports=1, total_ports=2, heuristic="graph_color"
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("graph_color")

    arch = Architecture(
        {bf_pe, mul_pe, pe_in, pe_out},
        memories,
        direct_interconnects=direct,
    )

    assert len(arch.memories) == 2
    assert arch.memories[0] == memories[0]
    assert arch.memories[1] == memories[1]

    assert len(arch.processing_elements) == 4

    assert arch.direct_interconnects == direct

    assert arch.schedule_time == schedule.schedule_time
