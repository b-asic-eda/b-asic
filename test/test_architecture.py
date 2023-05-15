from itertools import chain
from typing import List, cast

import pytest

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.process import MemoryVariable, OperatorProcess, PlainMemoryVariable
from b_asic.resources import ProcessCollection
from b_asic.schedule import Schedule
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
        ValueError, match="Do not create Resource with empty ProcessCollection"
    ):
        ProcessingElement(empty_collection)


def test_add_remove_process_from_resource(schedule_direct_form_iir_lp_filter: Schedule):
    mvs = schedule_direct_form_iir_lp_filter.get_memory_variables()
    operations = schedule_direct_form_iir_lp_filter.get_operations()
    memory = Memory(mvs)
    pe = ProcessingElement(
        operations.get_by_type_name(ConstantMultiplication.type_name())
    )
    for process in operations:
        with pytest.raises(KeyError, match=f"{process} not of type"):
            memory.add_process(process)
    for process in mvs:
        with pytest.raises(KeyError, match=f"{process} not of type"):
            pe.add_process(process)

    with pytest.raises(KeyError, match="PlainMV not of type"):
        memory.add_process(PlainMemoryVariable(0, 0, {0: 2}, "PlainMV"))


def test_extract_processing_elements(schedule_direct_form_iir_lp_filter: Schedule):
    # Extract operations from schedule
    operations = schedule_direct_form_iir_lp_filter.get_operations()

    # Split into new process collections on overlapping execution time
    adders = operations.get_by_type_name(Addition.type_name()).split_on_execution_time()
    const_mults = operations.get_by_type_name(
        ConstantMultiplication.type_name()
    ).split_on_execution_time()

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
        ValueError, match="Do not create Resource with empty ProcessCollection"
    ):
        Memory(empty_collection)
    with pytest.raises(TypeError, match="Can only have MemoryProcess"):
        Memory(operations)
    # No exception
    Memory(mvs)


def test_architecture(schedule_direct_form_iir_lp_filter: Schedule):
    # Extract memory variables and operations
    mvs = schedule_direct_form_iir_lp_filter.get_memory_variables()
    operations = schedule_direct_form_iir_lp_filter.get_operations()

    # Split operations further into chunks
    adders = operations.get_by_type_name(Addition.type_name()).split_on_execution_time()
    assert len(adders) == 1
    const_mults = operations.get_by_type_name(
        ConstantMultiplication.type_name()
    ).split_on_execution_time()
    assert len(const_mults) == 1
    inputs = operations.get_by_type_name(Input.type_name()).split_on_execution_time()
    assert len(inputs) == 1
    outputs = operations.get_by_type_name(Output.type_name()).split_on_execution_time()
    assert len(outputs) == 1

    # Create necessary processing elements
    processing_elements: List[ProcessingElement] = [
        ProcessingElement(operation)
        for operation in chain(adders, const_mults, inputs, outputs)
    ]
    for i, pe in enumerate(processing_elements):
        pe.set_entity_name(f"{pe._type_name.upper()}{i}")
        if pe._type_name == 'add':
            s = (
                'digraph {\n\tnode [shape=record]\n\t'
                + pe._entity_name
                + ' [label="{{<in0> in0|<in1> in1}|'
                + pe._entity_name
                + '|{<out0> out0}}"]\n}'
            )
            assert pe._digraph().source in (s, s + '\n')

    # Extract zero-length memory variables
    direct_conn, mvs = mvs.split_on_length()

    # Create Memories from the memory variables
    memories: List[Memory] = [
        Memory(pc) for pc in mvs.split_on_ports(read_ports=1, write_ports=1)
    ]
    assert len(memories) == 1

    for i, memory in enumerate(memories):
        memory.set_entity_name(f"MEM{i}")
        s = (
            'digraph {\n\tnode [shape=record]\n\tMEM0 [label="{{<in0> in0}|MEM0|{<out0>'
            ' out0}}"]\n}'
        )
        assert memory.schedule_time == 18
        assert memory._digraph().source in (s, s + '\n')

    # Create architecture from
    architecture = Architecture(
        processing_elements, memories, direct_interconnects=direct_conn
    )

    assert architecture.schedule_time == 18

    # assert architecture._digraph().source == "foo"
    for pe in processing_elements:
        print(pe)
        assert pe.schedule_time == 18
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


def test_move_process(schedule_direct_form_iir_lp_filter: Schedule):
    # Resources
    mvs = schedule_direct_form_iir_lp_filter.get_memory_variables()
    operations = schedule_direct_form_iir_lp_filter.get_operations()
    adders1, adders2 = operations.get_by_type_name(Addition.type_name()).split_on_ports(
        total_ports=1
    )
    adders1 = [adders1]  # Fake two PEs needed for the adders
    adders2 = [adders2]  # Fake two PEs needed for the adders
    const_mults = operations.get_by_type_name(
        ConstantMultiplication.type_name()
    ).split_on_execution_time()
    inputs = operations.get_by_type_name(Input.type_name()).split_on_execution_time()
    outputs = operations.get_by_type_name(Output.type_name()).split_on_execution_time()

    # Create necessary processing elements
    processing_elements: List[ProcessingElement] = [
        ProcessingElement(operation, entity_name=f'pe{i}')
        for i, operation in enumerate(chain(adders1, adders2, const_mults))
    ]
    for i, pc in enumerate(inputs):
        processing_elements.append(ProcessingElement(pc, entity_name=f'input{i}'))
    for i, pc in enumerate(outputs):
        processing_elements.append(ProcessingElement(pc, entity_name=f'output{i}'))

    # Extract zero-length memory variables
    direct_conn, mvs = mvs.split_on_length()

    # Create Memories from the memory variables (split on length to get two memories)
    memories: List[Memory] = [Memory(pc) for pc in mvs.split_on_length(6)]

    # Create architecture
    architecture = Architecture(
        processing_elements, memories, direct_interconnects=direct_conn
    )

    # Some movement that must work
    assert memories[1].collection.from_name('cmul4.0')
    architecture.move_process('cmul4.0', memories[1], memories[0])
    assert memories[0].collection.from_name('cmul4.0')

    assert memories[1].collection.from_name('in1.0')
    architecture.move_process('in1.0', memories[1], memories[0])
    assert memories[0].collection.from_name('in1.0')

    assert processing_elements[1].collection.from_name('add1')
    architecture.move_process('add1', processing_elements[1], processing_elements[0])
    assert processing_elements[0].collection.from_name('add1')

    # Processes leave the resources they have moved from
    with pytest.raises(KeyError):
        memories[1].collection.from_name('cmul4.0')
    with pytest.raises(KeyError):
        memories[1].collection.from_name('in1.0')
    with pytest.raises(KeyError):
        processing_elements[1].collection.from_name('add1')

    # Processes can only be moved when the source and destination process-types match
    with pytest.raises(KeyError, match="cmul4.0 not of type"):
        architecture.move_process('cmul4.0', memories[0], processing_elements[0])
    with pytest.raises(KeyError, match="invalid_name not in"):
        architecture.move_process('invalid_name', memories[0], processing_elements[1])
