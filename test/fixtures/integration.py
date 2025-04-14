import pytest

from b_asic.architecture import ProcessingElement
from b_asic.core_operations import Butterfly, ConstantMultiplication
from b_asic.list_schedulers import HybridScheduler
from b_asic.schedule import Schedule
from b_asic.sfg_generators import radix_2_dif_fft
from b_asic.special_operations import Input, Output


@pytest.fixture
def mem_variables_fft16():
    POINTS = 16
    sfg = radix_2_dif_fft(POINTS)
    sfg.set_latency_of_type(Butterfly, 1)
    sfg.set_latency_of_type(ConstantMultiplication, 3)
    sfg.set_execution_time_of_type(Butterfly, 1)
    sfg.set_execution_time_of_type(ConstantMultiplication, 1)

    resources = {
        Butterfly.type_name(): 2,
        ConstantMultiplication.type_name(): 2,
        Input.type_name(): 1,
        Output.type_name(): 1,
    }
    schedule = Schedule(
        sfg,
        scheduler=HybridScheduler(
            resources, max_concurrent_reads=4, max_concurrent_writes=4
        ),
    )

    operations = schedule.get_operations()
    bfs = operations.get_by_type_name(Butterfly.type_name())
    bfs = bfs.split_on_execution_time()
    const_muls = operations.get_by_type_name(ConstantMultiplication.type_name())
    inputs = operations.get_by_type_name(Input.type_name())
    outputs = operations.get_by_type_name(Output.type_name())

    bf_pe_1 = ProcessingElement(bfs[0], entity_name="bf1")
    bf_pe_2 = ProcessingElement(bfs[1], entity_name="bf2")

    mul_pe_1 = ProcessingElement(const_muls, entity_name="mul1")

    pe_in = ProcessingElement(inputs, entity_name="input")
    pe_out = ProcessingElement(outputs, entity_name="output")

    processing_elements = [bf_pe_1, bf_pe_2, mul_pe_1, pe_in, pe_out]

    mem_vars = schedule.get_memory_variables()
    direct, mem_vars = mem_vars.split_on_length()
    return direct, mem_vars, processing_elements


@pytest.fixture
def mem_variables_fft32():
    POINTS = 32
    sfg = radix_2_dif_fft(POINTS)
    sfg.set_latency_of_type(Butterfly, 1)
    sfg.set_latency_of_type(ConstantMultiplication, 3)
    sfg.set_execution_time_of_type(Butterfly, 1)
    sfg.set_execution_time_of_type(ConstantMultiplication, 1)

    resources = {
        Butterfly.type_name(): 2,
        ConstantMultiplication.type_name(): 2,
        Input.type_name(): 1,
        Output.type_name(): 1,
    }
    schedule = Schedule(
        sfg,
        scheduler=HybridScheduler(
            resources, max_concurrent_reads=4, max_concurrent_writes=4
        ),
    )

    operations = schedule.get_operations()
    bfs = operations.get_by_type_name(Butterfly.type_name())
    bfs = bfs.split_on_execution_time()
    const_muls = operations.get_by_type_name(ConstantMultiplication.type_name())
    const_muls = const_muls.split_on_execution_time()
    inputs = operations.get_by_type_name(Input.type_name())
    outputs = operations.get_by_type_name(Output.type_name())

    bf_pe_1 = ProcessingElement(bfs[0], entity_name="bf1")
    bf_pe_2 = ProcessingElement(bfs[1], entity_name="bf2")

    mul_pe_1 = ProcessingElement(const_muls[0], entity_name="mul1")
    mul_pe_2 = ProcessingElement(const_muls[1], entity_name="mul2")

    pe_in = ProcessingElement(inputs, entity_name="input")
    pe_out = ProcessingElement(outputs, entity_name="output")

    processing_elements = [bf_pe_1, bf_pe_2, mul_pe_1, mul_pe_2, pe_in, pe_out]

    mem_vars = schedule.get_memory_variables()
    direct, mem_vars = mem_vars.split_on_length()
    return direct, mem_vars, processing_elements
