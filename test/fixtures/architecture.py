import math

import numpy as np
import pytest

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import (
    MADS,
    Addition,
    AddSub,
    ConstantMultiplication,
    Reciprocal,
)
from b_asic.list_schedulers import HybridScheduler
from b_asic.schedule import Schedule
from b_asic.sfg_generators import direct_form_2_iir, ldlt_matrix_inverse
from b_asic.signal_flow_graph import SFG
from b_asic.special_operations import Input, Output


@pytest.fixture
def arch_first_order_iir():
    b = np.array([0.29289322, 0.29289322])
    a = np.array([1.0, -0.41421356])
    sfg = direct_form_2_iir(b, a)
    sfg.set_latency_of_type(Addition, 1)
    sfg.set_latency_of_type(ConstantMultiplication, 2)
    sfg.set_execution_time_of_type(Addition, 1)
    sfg.set_execution_time_of_type(ConstantMultiplication, 1)

    schedule = Schedule(sfg, cyclic=True)
    schedule.move_operation("cmul2", 1)
    schedule.move_operation("out0", 1)
    schedule.move_operation("add1", 1)
    schedule.set_schedule_time(5)
    schedule.move_operation("cmul2", -1)
    schedule.move_operation("out0", 1)
    schedule.move_operation("add1", 1)
    schedule.move_operation("cmul1", 1)
    schedule.move_operation("out0", 2)
    schedule.move_operation("add1", 1)
    schedule.move_operation("cmul1", 1)
    schedule.move_operation("out0", -1)
    schedule.set_schedule_time(3)
    schedule.move_operation("cmul2", 1)
    schedule.move_operation("in0", 2)
    schedule.rotate_backward()
    schedule.rotate_backward()
    schedule.move_operation("out0", 1)
    schedule.move_operation("add1", 1)
    schedule.move_operation("cmul1", 1)
    schedule.move_operation("cmul2", 1)

    ops = schedule.get_operations()
    adds = ops.get_by_type_name("add")
    cmuls = ops.get_by_type_name("cmul")
    inputs = ops.get_by_type_name("in")
    outputs = ops.get_by_type_name("out")

    adder = ProcessingElement(adds, entity_name="adder")
    mult = ProcessingElement(cmuls, entity_name="mult")
    input_pe = ProcessingElement(inputs, entity_name="input")
    output_pe = ProcessingElement(outputs, entity_name="output")

    mem_vars = schedule.get_memory_variables()
    direct, mem_vars = mem_vars.split_on_length()
    mem_vars_set = mem_vars.split_on_ports(read_ports=1, write_ports=1, total_ports=2)

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"mem{i}")
        memories.append(memory)
        memory.assign("left_edge")

    return Architecture(
        {adder, mult, input_pe, output_pe}, memories, "first_order_iir", direct
    )


@pytest.fixture
def arch_r2bf():
    x0 = Input("x0")
    x1 = Input("x1")
    s0 = AddSub(True, x0, x1, latency=1, execution_time=1)
    s1 = AddSub(False, x0, x1, latency=1, execution_time=1)
    y0 = Output(s0)
    y1 = Output(s1)

    sfg = SFG([x0, x1], [y0, y1])

    schedule = Schedule(sfg, cyclic=True)
    schedule.set_schedule_time(2)
    schedule.move_operation("out1", 2)
    schedule.move_operation("out0", 1)
    schedule.move_operation("addsub0", 1)
    schedule.move_operation("addsub1", 2)
    schedule.move_operation("in1", 1)

    ops = schedule.get_operations()
    addsubs = ops.get_by_type_name("addsub")
    inputs = ops.get_by_type_name("in")
    outputs = ops.get_by_type_name("out")
    addsub0 = ProcessingElement(addsubs, entity_name="addsub0")
    input0 = ProcessingElement(inputs, entity_name="input0")
    output0 = ProcessingElement(outputs, entity_name="output0")

    mem_vars = schedule.get_memory_variables()
    direct, mem_vars = mem_vars.split_on_length()
    mem_vars_set = mem_vars.split_on_ports(read_ports=1, write_ports=1, total_ports=2)
    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"mem{i}")
        memories.append(memory)
        memory.assign("left_edge")

    return Architecture({addsub0, input0, output0}, memories, "r2bf", direct)


@pytest.fixture
def arch_r3bf():
    u = -2 * math.pi / 3
    c30 = math.cos(u) - 1
    c31 = 1j * math.sin(u)

    in0 = Input("x0")
    in1 = Input("x1")
    in2 = Input("x2")

    a0 = AddSub(True, in1, in2)
    a1 = AddSub(False, in1, in2)
    a2 = AddSub(True, a0, in0)

    m0 = c30 * a0
    m1 = c31 * a1

    a3 = AddSub(True, a2, m0)
    a4 = AddSub(True, a3, m1)
    a5 = AddSub(False, a3, m1)

    out0 = Output(a2, "X0")
    out1 = Output(a4, "X1")
    out2 = Output(a5, "X2")

    sfg = SFG(
        inputs=[in0, in1, in2],
        outputs=[out0, out1, out2],
        name="3-point Winograd DFT",
    )

    sfg.set_latency_of_type_name("addsub", 1)
    sfg.set_execution_time_of_type_name("addsub", 1)
    sfg.set_latency_of_type_name("cmul", 1)
    sfg.set_execution_time_of_type_name("cmul", 1)

    schedule = Schedule(sfg, cyclic=True)
    schedule.move_operation("out0", 3)
    schedule.move_operation("out0", 4)
    schedule.move_operation("out1", 2)
    schedule.move_operation("out1", 4)
    schedule.move_y_location("out0", 13, True)
    schedule.move_y_location("out1", 13, True)
    schedule.move_operation("out2", 2)
    schedule.move_operation("out2", 3)
    schedule.move_operation("out2", 2)
    schedule.move_operation("addsub4", 3)
    schedule.move_operation("addsub4", 4)
    schedule.move_operation("addsub3", 4)
    schedule.move_operation("addsub3", 2)
    schedule.set_schedule_time(3)
    schedule.move_operation("addsub2", 3)
    schedule.move_operation("addsub2", 1)
    schedule.move_operation("cmul1", 3)
    schedule.move_operation("cmul1", 2)
    schedule.move_operation("cmul0", 1)
    schedule.move_operation("cmul0", 1)
    schedule.move_operation("cmul0", 2)
    schedule.move_operation("addsub0", 2)
    schedule.move_y_location("in0", 0, True)
    schedule.move_operation("addsub1", 2)
    schedule.move_operation("addsub5", 4)
    schedule.move_operation("in1", 1)
    schedule.move_operation("in2", 2)

    operations = schedule.get_operations()
    addsubs = operations.get_by_type_name("addsub")
    cmuls = operations.get_by_type_name("cmul")
    inputs = operations.get_by_type_name("in")
    outputs = operations.get_by_type_name("out")

    addsubs = addsubs.split_on_execution_time()

    addsub0 = ProcessingElement(addsubs[0], entity_name="addsub0")
    addsub1 = ProcessingElement(addsubs[1], entity_name="addsub1")
    mult = ProcessingElement(cmuls, entity_name="mult")
    pe_in = ProcessingElement(inputs, entity_name="input")
    pe_out = ProcessingElement(outputs, entity_name="output")

    mem_vars = schedule.get_memory_variables()
    direct, mem_vars = mem_vars.split_on_length()
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1, write_ports=1, total_ports=2, strategy="greedy_graph_color"
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"memory{i}")
        memories.append(memory)
        memory.assign("greedy_graph_color")

    return Architecture(
        {addsub0, addsub1, mult, pe_in, pe_out}, memories, "r3bf", direct
    )


@pytest.fixture
def arch_r4bf():
    x0 = Input()
    x1 = Input()
    x2 = Input()
    x3 = Input()

    s0 = AddSub(True, x0, x2)
    s1 = AddSub(True, x1, x3)
    s2 = AddSub(False, x0, x2)
    s3 = AddSub(False, x3, x1)
    m0 = ConstantMultiplication(1j, s3)

    s4 = AddSub(True, s0, s1)
    s5 = AddSub(True, s2, m0)
    s6 = AddSub(False, s0, s1)
    s7 = AddSub(False, s2, m0)

    y0 = Output(s4)
    y1 = Output(s5)
    y2 = Output(s6)
    y3 = Output(s7)

    sfg = SFG([x0, x1, x2, x3], [y0, y1, y2, y3])

    sfg.set_latency_of_type(AddSub, 1)
    sfg.set_execution_time_of_type(AddSub, 1)
    sfg.set_latency_of_type(ConstantMultiplication, 1)
    sfg.set_execution_time_of_type(ConstantMultiplication, 1)

    schedule = Schedule(sfg, cyclic=True)

    schedule.set_schedule_time(4)
    schedule.move_operation("addsub4", 1)
    schedule.move_operation("out2", 1)
    schedule.move_operation("out0", 1)
    schedule.move_operation("out0", 2)
    schedule.move_y_location("out0", 17, True)
    schedule.move_operation("out1", 2)
    schedule.move_y_location("out1", 17, True)
    schedule.move_operation("out2", 2)
    schedule.move_y_location("out2", 17, True)
    schedule.move_operation("out3", 2)
    schedule.move_y_location("out3", 17, False)
    schedule.move_operation("out1", 1)
    schedule.move_operation("out2", 2)
    schedule.move_operation("out3", 3)
    schedule.move_operation("addsub5", 3)
    schedule.move_operation("addsub6", 4)
    schedule.move_operation("addsub6", 1)
    schedule.move_operation("cmul0", 3)
    schedule.move_operation("addsub1", 3)
    schedule.move_operation("addsub2", 5)
    schedule.move_operation("addsub7", 3)
    schedule.move_operation("addsub3", 3)
    schedule.move_operation("addsub4", 3)
    schedule.move_operation("addsub0", 3)
    schedule.move_operation("in1", 1)
    schedule.move_operation("in2", 2)
    schedule.move_operation("in3", 3)
    schedule.move_operation("addsub0", -1)
    schedule.move_operation("addsub6", -2)
    schedule.move_operation("addsub4", -1)
    schedule.move_operation("addsub4", -1)
    schedule.move_operation("addsub2", -1)
    schedule.move_operation("addsub2", -1)

    ops = schedule.get_operations()
    addsubs = ops.get_by_type_name("addsub")
    addsubs = addsubs.split_on_execution_time()
    cmuls = ops.get_by_type_name("cmul")
    inputs = ops.get_by_type_name("in")
    outputs = ops.get_by_type_name("out")

    addsub0 = ProcessingElement(addsubs[0], entity_name="addsub0")
    addsub1 = ProcessingElement(addsubs[1], entity_name="addsub1")
    mult = ProcessingElement(cmuls, entity_name="mult")
    input_pe = ProcessingElement(inputs, entity_name="input")
    output_pe = ProcessingElement(outputs, entity_name="output")

    mem_vars = schedule.get_memory_variables()
    direct, mem_vars = mem_vars.split_on_length()
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1, write_ports=1, total_ports=2, strategy="greedy_graph_color"
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"mem{i}")
        memories.append(memory)
        memory.assign("greedy_graph_color")

    return Architecture(
        {addsub0, addsub1, mult, input_pe, output_pe}, memories, "r4bf", direct
    )


@pytest.fixture
def arch_simple():
    in0 = Input()
    in1 = Input()
    add0 = Addition(in0, in1)
    cmul0 = ConstantMultiplication(3, add0)
    add1 = Addition(add0, cmul0)
    out0 = Output(add1)

    sfg = SFG([in0, in1], [out0])

    sfg.set_execution_time_of_type(Addition, 1)
    sfg.set_latency_of_type(Addition, 1)

    sfg.set_execution_time_of_type(ConstantMultiplication, 1)
    sfg.set_latency_of_type(ConstantMultiplication, 2)

    schedule = Schedule(sfg)
    schedule.set_schedule_time(5)
    schedule.move_operation("out0", 1)
    schedule.move_operation("add1", 1)
    schedule.move_operation("cmul0", 1)
    schedule.move_operation("add0", 1)
    schedule.move_operation("in1", 1)

    operations = schedule.get_operations()
    adders = operations.get_by_type_name("add")
    cmuls = operations.get_by_type_name("cmul")
    inputs = operations.get_by_type_name("in")
    outputs = operations.get_by_type_name("out")

    adder = ProcessingElement(adders, entity_name="adder")
    mult = ProcessingElement(cmuls, entity_name="mult")
    input_pe = ProcessingElement(inputs, entity_name="input")
    output_pe = ProcessingElement(outputs, entity_name="output")

    mem_vars = schedule.get_memory_variables()
    direct, mem_vars = mem_vars.split_on_length()
    mem_vars_set = mem_vars.split_on_ports(read_ports=1, write_ports=1, total_ports=2)

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"mem{i}")
        memories.append(memory)
        memory.assign("left_edge")

    return Architecture(
        {adder, mult, input_pe, output_pe},
        memories,
        entity_name="simple",
        direct_interconnects=direct,
    )


@pytest.fixture
def arch_mat_inv():
    N = 4
    sfg = ldlt_matrix_inverse(N)

    sfg.set_execution_time_of_type(MADS, 1)
    sfg.set_latency_of_type(MADS, 2)

    sfg.set_execution_time_of_type(Reciprocal, 1)
    sfg.set_latency_of_type(Reciprocal, 2)

    input_times = {f"in{i}": i for i in range(N * (N + 1) // 2)}
    output_delta_times = {
        f"out{(N * (N + 1) // 2) - 1 - i}": i for i in range(N * (N + 1) // 2)
    }
    scheduler = HybridScheduler(
        input_times=input_times, output_delta_times=output_delta_times
    )
    schedule = Schedule(sfg, scheduler)

    operations = schedule.get_operations()
    madss = operations.get_by_type_name("mads")
    recs = operations.get_by_type_name("rec")
    dontcares = operations.get_by_type_name("dontcare")
    ins = operations.get_by_type_name("in")
    outs = operations.get_by_type_name("out")

    mads = ProcessingElement(madss, entity_name="mads")
    rec = ProcessingElement(recs, entity_name="rec")
    dc = ProcessingElement(dontcares, entity_name="dc")
    input_pe = ProcessingElement(ins, entity_name="input")
    output_pe = ProcessingElement(outs, entity_name="output")

    mem_vars = schedule.get_memory_variables()
    direct, mem_vars = mem_vars.split_on_length()
    mem_vars_set = mem_vars.split_on_ports(
        read_ports=1, write_ports=1, total_ports=2, strategy="greedy_graph_color"
    )

    memories = []
    for i, mem in enumerate(mem_vars_set):
        memory = Memory(mem, memory_type="RAM", entity_name=f"mem{i}")
        memories.append(memory)
        memory.assign("greedy_graph_color")

    return Architecture(
        {mads, rec, dc, input_pe, output_pe},
        memories,
        entity_name="mat_inv",
        direct_interconnects=direct,
    )
