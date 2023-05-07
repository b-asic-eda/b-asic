from itertools import chain
from typing import List, Set, cast

import matplotlib.pyplot as plt
import pytest

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.process import MemoryVariable, OperatorProcess
from b_asic.resources import ProcessCollection
from b_asic.schedule import Schedule
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Input, Output


def test_processing_element_exceptions(schedule_direct_form_iir_lp_filter: Schedule):
    mvs = schedule_direct_form_iir_lp_filter.get_memory_variables()
    with pytest.raises(
        TypeError,
        match="Can only have OperatorProcesses in ProcessCollection when creating",
    ):
        ProcessingElement(mvs)
    empty_collection = ProcessCollection(collection=set(), schedule_time=5)
    with pytest.raises(
        ValueError, match="Do not create ProcessingElement with empty ProcessCollection"
    ):
        ProcessingElement(empty_collection)


def test_extract_processing_elements(schedule_direct_form_iir_lp_filter: Schedule):
    # Extract operations from schedule
    operations = schedule_direct_form_iir_lp_filter.get_operations()

    # Split into new process collections on overlapping execution time
    adders = operations.get_by_type_name(Addition.type_name()).split_execution_time()
    const_mults = operations.get_by_type_name(
        ConstantMultiplication.type_name()
    ).split_execution_time()

    # List of ProcessingElements
    processing_elements: List[ProcessingElement] = []
    for adder_collection in adders:
        processing_elements.append(ProcessingElement(adder_collection))
    for const_mult_collection in const_mults:
        processing_elements.append(ProcessingElement(const_mult_collection))

    assert len(processing_elements) == len(adders) + len(const_mults)


def test_memory_exceptions(schedule_direct_form_iir_lp_filter: Schedule):
    mvs = schedule_direct_form_iir_lp_filter.get_memory_variables()
    operations = schedule_direct_form_iir_lp_filter.get_operations()
    empty_collection = ProcessCollection(collection=set(), schedule_time=5)
    with pytest.raises(
        ValueError, match="Do not create Memory with empty ProcessCollection"
    ):
        Memory(empty_collection)
    with pytest.raises(
        TypeError, match="Can only have MemoryVariable or PlainMemoryVariable"
    ):
        Memory(operations)
    # No exception
    Memory(mvs)


def test_architecture(schedule_direct_form_iir_lp_filter: Schedule):
    # Extract memory variables and operations
    mvs = schedule_direct_form_iir_lp_filter.get_memory_variables()
    operations = schedule_direct_form_iir_lp_filter.get_operations()

    # Split operations further into chunks
    adders = operations.get_by_type_name(Addition.type_name()).split_execution_time()
    assert len(adders) == 1
    const_mults = operations.get_by_type_name(
        ConstantMultiplication.type_name()
    ).split_execution_time()
    assert len(const_mults) == 1
    inputs = operations.get_by_type_name(Input.type_name()).split_execution_time()
    assert len(inputs) == 1
    outputs = operations.get_by_type_name(Output.type_name()).split_execution_time()
    assert len(outputs) == 1

    # Create necessary processing elements
    processing_elements: List[ProcessingElement] = [
        ProcessingElement(operation)
        for operation in chain(adders, const_mults, inputs, outputs)
    ]
    for i, pe in enumerate(processing_elements):
        pe.set_entity_name(f"{pe._type_name.upper()}-{i}")

    # Extract zero-length memory variables
    direct_conn, mvs = mvs.split_on_length()

    # Create Memories from the memory variables
    memories: List[Memory] = [
        Memory(pc) for pc in mvs.split_ports(read_ports=1, write_ports=1)
    ]
    assert len(memories) == 1
    for i, memory in enumerate(memories):
        memory.set_entity_name(f"mem-{i}")

    # Create architecture from
    architecture = Architecture(
        set(processing_elements), set(memories), direct_interconnects=direct_conn
    )

    for pe in processing_elements:
        print(pe)
        for operation in pe._collection:
            operation = cast(OperatorProcess, operation)
            print(f'  {operation}')
        print(architecture.get_interconnects_for_pe(pe))

    print("")
    print("")
    for memory in memories:
        print(memory)
        for mv in memory._collection:
            mv = cast(MemoryVariable, mv)
            print(f'  {mv.start_time} -> {mv.execution_time}: {mv.write_port.name}')
        print(architecture.get_interconnects_for_memory(memory))
