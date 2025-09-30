import pytest
from pulp import PULP_CBC_CMD

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import (
    MADS,
    ConstantMultiplication,
    Reciprocal,
)
from b_asic.fft_operations import R2Butterfly
from b_asic.list_schedulers import HybridScheduler
from b_asic.resource_assigner import assign_processing_elements_and_memories
from b_asic.schedule import Schedule
from b_asic.scheduler import ASAPScheduler
from b_asic.sfg_generators import ldlt_matrix_inverse, radix_2_dif_fft
from b_asic.special_operations import Input, Output


def test_pe_constrained_schedule():
    sfg = ldlt_matrix_inverse(N=5)

    sfg.set_latency_of_type_name(MADS.type_name(), 3)
    sfg.set_latency_of_type_name(Reciprocal.type_name(), 2)
    sfg.set_execution_time_of_type_name(MADS.type_name(), 1)
    sfg.set_execution_time_of_type_name(Reciprocal.type_name(), 1)

    resources = {MADS.type_name(): 2, Reciprocal.type_name(): 1}

    # Generate a schedule to ensure that schedule can be overwritten without bugs
    schedule = Schedule(sfg, scheduler=ASAPScheduler())

    schedule = Schedule(sfg, scheduler=HybridScheduler(resources))

    _, mem_vars = schedule.get_memory_variables().split_on_length()
    assert mem_vars.read_ports_bound() <= 7
    assert mem_vars.write_ports_bound() <= 4

    operations = schedule.get_operations()

    with pytest.raises(
        TypeError, match=r"Different Operation types in ProcessCollection"
    ):
        ProcessingElement(operations)

    mads = operations.get_by_type_name(MADS.type_name())
    with pytest.raises(
        ValueError, match=r"Cannot map ProcessCollection to single ProcessingElement"
    ):
        ProcessingElement(mads, entity_name="mad")
    mads = mads.split_on_execution_time("ilp_graph_color")
    with pytest.raises(
        TypeError,
        match=r"Argument process_collection must be ProcessCollection, not <class 'list'>",
    ):
        ProcessingElement(mads, entity_name="mad")

    assert len(mads) == 2

    # TODO: Restore these checks when Architecture can handle DontCares

    # reciprocals = operations.get_by_type_name(Reciprocal.type_name())
    # inputs = operations.get_by_type_name(Input.type_name())
    # outputs = operations.get_by_type_name(Output.type_name())

    # mads0 = ProcessingElement(mads[0], entity_name="mads0")
    # mads1 = ProcessingElement(mads[1], entity_name="mads1")
    # reciprocal_pe = ProcessingElement(reciprocals, entity_name="rec")

    # pe_in = ProcessingElement(inputs, entity_name='input')
    # pe_out = ProcessingElement(outputs, entity_name='output')

    # mem_vars_set = mem_vars.split_on_ports(read_ports=1, write_ports=1, total_ports=2)
    # memories = []
    # for i, mem in enumerate(mem_vars_set):
    #     memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
    #     memories.append(memory)
    #     memory.assign("greedy_graph_color")

    # arch = Architecture(
    #     {mads0, mads1, reciprocal_pe, pe_in, pe_out},
    #     memories,
    #     direct_interconnects=direct,
    # )

    # assert len(arch.memories) == len(memories)
    # for i in range(len(memories)):
    #     assert arch.memories[i] == memories[i]

    # assert len(arch.processing_elements) == 4

    # assert arch.direct_interconnects == direct

    # assert arch.schedule_time == schedule.schedule_time


def test_pe_and_memory_constrained_schedule():
    sfg = radix_2_dif_fft(points=16)

    sfg.set_latency_of_type_name(R2Butterfly.type_name(), 3)
    sfg.set_latency_of_type_name(ConstantMultiplication.type_name(), 2)
    sfg.set_execution_time_of_type_name(R2Butterfly.type_name(), 1)
    sfg.set_execution_time_of_type_name(ConstantMultiplication.type_name(), 1)

    # generate a schedule to ensure that schedule can be overwritten without bugs
    schedule = Schedule(sfg, scheduler=ASAPScheduler())

    # generate the real constrained schedule
    resources = {R2Butterfly.type_name(): 1, ConstantMultiplication.type_name(): 1}
    schedule = Schedule(
        sfg,
        scheduler=HybridScheduler(
            resources, max_concurrent_reads=2, max_concurrent_writes=2
        ),
    )

    operations = schedule.get_operations()
    bfs = operations.get_by_type_name(R2Butterfly.type_name())
    const_muls = operations.get_by_type_name(ConstantMultiplication.type_name())
    inputs = operations.get_by_type_name(Input.type_name())
    outputs = operations.get_by_type_name(Output.type_name())

    bf_pe = ProcessingElement(bfs, entity_name="bf")
    mul_pe = ProcessingElement(const_muls, entity_name="mul")

    pe_in = ProcessingElement(inputs, entity_name="input")
    pe_out = ProcessingElement(outputs, entity_name="output")

    mem_vars = schedule.get_memory_variables()
    direct, mem_vars = mem_vars.split_on_length()
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1, write_ports=1, total_ports=2, strategy="greedy_graph_color"
    )

    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1, write_ports=1, total_ports=2, strategy="greedy_graph_color"
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("greedy_graph_color")

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


def test_left_edge(mem_variables_fft32):
    direct, mem_vars, processing_elements = mem_variables_fft32

    # LEFT-EDGE
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="left_edge",
        processing_elements=processing_elements,
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("greedy_graph_color")

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 6
    assert len(arch.memories) == 6


def test_min_pe_to_mem(mem_variables_fft32):
    direct, mem_vars, processing_elements = mem_variables_fft32

    # MIN-PE-TO-MEM
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="left_edge_min_pe_to_mem",
        processing_elements=processing_elements,
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("greedy_graph_color")

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 6
    assert len(arch.memories) == 6


def test_min_mem_to_pe(mem_variables_fft32):
    direct, mem_vars, processing_elements = mem_variables_fft32

    # MIN-MEM-TO-PE
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="left_edge_min_mem_to_pe",
        processing_elements=processing_elements,
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("greedy_graph_color")

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 6
    assert len(arch.memories) == 6


def test_greedy_graph_coloring(mem_variables_fft32):
    direct, mem_vars, processing_elements = mem_variables_fft32

    # GREEDY GRAPH COLORING
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="greedy_graph_color",
        processing_elements=processing_elements,
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("greedy_graph_color")

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 6
    assert len(arch.memories) == 4


def test_equitable_color(mem_variables_fft32):
    direct, mem_vars, processing_elements = mem_variables_fft32

    # EQUITABLE COLOR
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="equitable_graph_color",
        processing_elements=processing_elements,
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("greedy_graph_color")

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 6
    assert len(arch.memories) == 7


def test_ilp_color(mem_variables_fft16):
    direct, mem_vars, processing_elements = mem_variables_fft16
    # ILP COLOR
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="ilp_graph_color",
        processing_elements=processing_elements,
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("ilp_graph_color")

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 5
    assert len(arch.memories) == 4


def test_ilp_color_with_colors_given(mem_variables_fft16):
    direct, mem_vars, processing_elements = mem_variables_fft16
    # ILP COLOR (amount of colors given)
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="ilp_graph_color",
        processing_elements=processing_elements,
        max_colors=4,
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("ilp_graph_color")

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 5
    assert len(arch.memories) == 4


def test_ilp_color_input_mux(mem_variables_fft16):
    direct, mem_vars, processing_elements = mem_variables_fft16
    # ILP COLOR MIN INPUT MUX
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="ilp_min_input_mux",
        processing_elements=processing_elements,
        max_colors=4,
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("ilp_graph_color")

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 5
    assert len(arch.memories) == 4


def test_ilp_color_output_mux(mem_variables_fft16):
    direct, mem_vars, processing_elements = mem_variables_fft16
    # ILP COLOR MIN OUTPUT MUX
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="ilp_min_output_mux",
        processing_elements=processing_elements,
        max_colors=4,
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("ilp_graph_color")

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 5
    assert len(arch.memories) == 4


def test_ilp_color_total_mux(mem_variables_fft16):
    direct, mem_vars, processing_elements = mem_variables_fft16

    # ILP COLOR MIN TOTAL MUX
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="ilp_min_total_mux",
        processing_elements=processing_elements,
        max_colors=4,
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("ilp_graph_color")

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 5
    assert len(arch.memories) == 4


def test_ilp_resource_algorithm_custom_solver():
    POINTS = 16
    sfg = radix_2_dif_fft(POINTS)
    sfg.set_latency_of_type(R2Butterfly, 3)
    sfg.set_latency_of_type(ConstantMultiplication, 8)
    sfg.set_execution_time_of_type(R2Butterfly, 2)
    sfg.set_execution_time_of_type(ConstantMultiplication, 8)

    resources = {
        R2Butterfly.type_name(): 1,
        ConstantMultiplication.type_name(): 1,
        Input.type_name(): 1,
        Output.type_name(): 1,
    }
    schedule = Schedule(
        sfg,
        scheduler=HybridScheduler(
            resources, max_concurrent_reads=3, max_concurrent_writes=3
        ),
    )

    operations = schedule.get_operations()
    bfs = operations.get_by_type_name(R2Butterfly.type_name())
    const_muls = operations.get_by_type_name(ConstantMultiplication.type_name())
    inputs = operations.get_by_type_name(Input.type_name())
    outputs = operations.get_by_type_name(Output.type_name())

    bf_pe = ProcessingElement(bfs, entity_name="bf1")
    mul_pe = ProcessingElement(const_muls, entity_name="mul1")

    pe_in = ProcessingElement(inputs, entity_name="input")
    pe_out = ProcessingElement(outputs, entity_name="output")

    processing_elements = [bf_pe, mul_pe, pe_in, pe_out]

    mem_vars = schedule.get_memory_variables()
    direct, mem_vars = mem_vars.split_on_length()

    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="ilp_min_total_mux",
        processing_elements=processing_elements,
        max_colors=3,
        solver=PULP_CBC_CMD(),
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("ilp_graph_color")

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 4
    assert len(arch.memories) == 3


def test_joint_resource_assignment():
    POINTS = 32
    sfg = radix_2_dif_fft(POINTS)
    sfg.set_latency_of_type_name("r2bfly", 1)
    sfg.set_latency_of_type_name("cmul", 3)
    sfg.set_execution_time_of_type_name("r2bfly", 1)
    sfg.set_execution_time_of_type_name("cmul", 1)

    resources = {"r2bfly": 1, "cmul": 1, "in": 1, "out": 1}
    schedule = Schedule(
        sfg,
        scheduler=HybridScheduler(
            resources, max_concurrent_reads=3, max_concurrent_writes=3
        ),
    )

    pes, mems, direct = assign_processing_elements_and_memories(
        schedule.get_operations(),
        schedule.get_memory_variables(),
        resources=resources,
        max_memories=3,
        memory_read_ports=1,
        memory_write_ports=1,
        memory_total_ports=2,
    )

    arch = Architecture(pes, mems, direct_interconnects=direct)
    assert len(arch.processing_elements) == 4
    assert len(arch.memories) == 3

    resources = {"r2bfly": 2, "cmul": 1, "in": 1, "out": 1}
    schedule = Schedule(
        sfg,
        scheduler=HybridScheduler(
            resources, max_concurrent_reads=4, max_concurrent_writes=4
        ),
    )

    pes, mems, direct = assign_processing_elements_and_memories(
        schedule.get_operations(),
        schedule.get_memory_variables(),
        resources=resources,
        max_memories=4,
        memory_read_ports=1,
        memory_write_ports=1,
        memory_total_ports=2,
    )

    arch = Architecture(pes, mems, direct_interconnects=direct)
    assert len(arch.processing_elements) == 5
    assert len(arch.memories) == 4


def test_joint_resource_assignment_mux_reduction():
    POINTS = 32
    sfg = radix_2_dif_fft(POINTS)
    sfg.set_latency_of_type_name("r2bfly", 1)
    sfg.set_latency_of_type_name("cmul", 3)
    sfg.set_execution_time_of_type_name("r2bfly", 1)
    sfg.set_execution_time_of_type_name("cmul", 1)

    resources = {"r2bfly": 1, "cmul": 1, "in": 1, "out": 1}
    schedule = Schedule(
        sfg,
        scheduler=HybridScheduler(
            resources, max_concurrent_reads=3, max_concurrent_writes=3
        ),
    )

    pes, mems, direct = assign_processing_elements_and_memories(
        schedule.get_operations(),
        schedule.get_memory_variables(),
        strategy="ilp_min_total_mux",
        resources=resources,
        max_memories=3,
        memory_read_ports=1,
        memory_write_ports=1,
        memory_total_ports=2,
    )

    arch = Architecture(pes, mems, direct_interconnects=direct)
    assert len(arch.processing_elements) == 4
    assert len(arch.memories) == 3


def test_separate_ilp_color_no_max_colors_provided(mem_variables_fft16):
    direct, mem_vars, processing_elements = mem_variables_fft16

    # test that the separate memory assignment with mux reduction can handle no colors provided
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="ilp_min_input_mux",
        processing_elements=processing_elements,
    )

    memories = [
        Memory(mem, memory_type="RAM", entity_name=f"memory{i}", assign=True)
        for i, mem in enumerate(mem_vars_set)
    ]

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 5
    assert len(arch.memories) == 4

    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="ilp_min_output_mux",
        processing_elements=processing_elements,
    )

    memories = [
        Memory(mem, memory_type="RAM", entity_name=f"memory{i}", assign=True)
        for i, mem in enumerate(mem_vars_set)
    ]

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 5
    assert len(arch.memories) == 4

    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=2,
        strategy="ilp_min_total_mux",
        processing_elements=processing_elements,
    )

    memories = [
        Memory(mem, memory_type="RAM", entity_name=f"memory{i}", assign=True)
        for i, mem in enumerate(mem_vars_set)
    ]

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 5
    assert len(arch.memories) == 4


def test_joint_ilp_color_no_max_colors_or_resources_provided():
    # test the joint resource assigner with mux reduction can handle no colors provided
    sfg = radix_2_dif_fft(8)
    sfg.set_latency_of_type_name("r2bfly", 1)
    sfg.set_latency_of_type_name("cmul", 3)
    sfg.set_execution_time_of_type_name("r2bfly", 1)
    sfg.set_execution_time_of_type_name("cmul", 1)

    resources = {"r2bfly": 1, "cmul": 1, "in": 2, "out": 1}
    schedule = Schedule(
        sfg,
        scheduler=HybridScheduler(
            resources, max_concurrent_reads=3, max_concurrent_writes=3
        ),
    )

    pes, mems, direct = assign_processing_elements_and_memories(
        schedule.get_operations(),
        schedule.get_memory_variables(),
        strategy="ilp_min_total_mux",
        memory_read_ports=1,
        memory_write_ports=1,
        memory_total_ports=2,
    )

    arch = Architecture(pes, mems, direct_interconnects=direct)
    assert len(arch.processing_elements) == 5
    assert len(arch.memories) == 3


def test_ilp_resource_algorithm_single_port_memory(mem_variables_fft16):
    direct, mem_vars, processing_elements = mem_variables_fft16

    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1,
        write_ports=1,
        total_ports=1,
        strategy="ilp_graph_color",
        processing_elements=processing_elements,
    )

    memories = [
        Memory(mem, memory_type="RAM", entity_name=f"memory{i}", assign=True)
        for i, mem in enumerate(mem_vars_set)
    ]

    arch = Architecture(
        processing_elements,
        memories,
        direct_interconnects=direct,
    )
    assert len(arch.processing_elements) == 5
    assert len(arch.memories) <= 2 * 4  # upper bound

    sfg = radix_2_dif_fft(32)
    sfg.set_latency_of_type_name("r2bfly", 2)
    sfg.set_latency_of_type_name("cmul", 3)
    sfg.set_execution_time_of_type_name("r2bfly", 2)
    sfg.set_execution_time_of_type_name("cmul", 3)

    resources = {"r2bfly": 1, "cmul": 1, "in": 1, "out": 2}
    schedule = Schedule(
        sfg,
        scheduler=HybridScheduler(
            resources, max_concurrent_reads=3, max_concurrent_writes=3
        ),
    )

    pes, mems, direct = assign_processing_elements_and_memories(
        schedule.get_operations(),
        schedule.get_memory_variables(),
        strategy="ilp_graph_color",
        memory_read_ports=1,
        memory_write_ports=1,
        memory_total_ports=1,
    )

    arch = Architecture(pes, mems, direct_interconnects=direct)
    assert len(arch.processing_elements) == 5
    assert len(arch.memories) <= 2 * 3  # upper bound
