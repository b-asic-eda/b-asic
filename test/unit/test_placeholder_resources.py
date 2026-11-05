"""Utility placeholders survive graph transforms without requiring hardware."""

import pytest

from b_asic.architecture import Architecture
from b_asic.core_operations import Addition
from b_asic.fft_operations import R2Butterfly
from b_asic.resource_assigner import assign_processing_elements_and_memories
from b_asic.schedule import Schedule
from b_asic.scheduler import ILPRecursiveScheduler
from b_asic.sfg import SFG
from b_asic.sfg_generators import lattice_wdf, richards
from b_asic.special_operations import Input, Output
from b_asic.utility_operations import DontCare, Sink
from b_asic.wdf_operations import SymmetricTwoportAdaptor


def test_connected_sink_survives_flattening():
    source = Input()
    inner_source = Input()
    inner = SFG([inner_source], [Output(inner_source)])
    inner <<= source
    butterfly = R2Butterfly(inner, DontCare())
    Sink(butterfly.output(0), name="unused")
    graph = SFG([source], [Output(butterfly.output(1))]).flatten()

    (sink,) = graph.find_by_type(Sink)
    assert sink.name == "unused"
    assert sink.input(0).connected_source.operation in graph.find_by_type(R2Butterfly)
    assert len(graph.find_by_type(DontCare)) == 1
    assert "sink0" in graph.display().source


def test_sink_positional_name_remains_supported():
    assert Sink("unused").name == "unused"


def _placeholder_schedule():
    source = Input()
    operation = Addition(source, DontCare(), latency=1, execution_time=1)
    butterfly = R2Butterfly(operation, source, latency=1, execution_time=1)
    # Include a sink-only output and a sink sharing a live output.
    Sink().input(0).connect(butterfly.output(0))
    Sink().input(0).connect(butterfly.output(1))
    graph = SFG([source], [Output(butterfly.output(1))])
    return Schedule(
        graph,
        schedule_time=8,
        start_times={
            "in0": 0,
            "dontcare0": 0,
            "add0": 2,
            "r2bfly0": 4,
            "sink0": 6,
            "sink1": 7,
            "out0": 7,
        },
        laps={},
    )


def test_memory_variables_exclude_placeholders():
    schedule = _placeholder_schedule()
    variables = schedule.get_memory_variables()
    assert variables
    for variable in variables:
        assert not isinstance(variable.write_port.operation, DontCare)
        assert all(not isinstance(port.operation, Sink) for port in variable.read_ports)
    assert all(
        not isinstance(process.operation, Sink | DontCare)
        for process in schedule.get_operations()
    )


@pytest.mark.parametrize(
    "strategy", ["greedy_graph_color", "greedy_min_mux", "cp_min_mux"]
)
def test_assign_resources_with_placeholders(strategy):
    if strategy == "cp_min_mux":
        pytest.importorskip("cpmpy", exc_type=ImportError)
        pytest.importorskip("ortools.sat.python.cp_model", exc_type=ImportError)
    pes, memories, direct = assign_processing_elements_and_memories(
        _placeholder_schedule(),
        strategy=strategy,
        memory_read_ports=1,
        memory_write_ports=1,
    )
    architecture = Architecture(pes, memories, direct_interconnects=direct)
    architecture.validate_ports()


@pytest.mark.parametrize(
    ("graph_name", "period"), [("third", 8), ("third", 4), ("ref", 8)]
)
def test_wdf_placeholder_resources(graph_name, period):
    pytest.importorskip("cpmpy", exc_type=ImportError)
    pytest.importorskip("ortools.sat.python.cp_model", exc_type=ImportError)
    if graph_name == "ref":
        graph = lattice_wdf([0.1, 0.2, 0.3, 0.4, 0.5], only_adaptors=True)
    else:
        source = Input("x")
        first = richards([0.1, 0, 0.2], latency=4, execution_time=1)
        first <<= source
        second = richards([0.1, 0, -0.2], latency=4, execution_time=1)
        second <<= source
        for _ in range(2):
            second = richards(0.1, latency=4, execution_time=1)(second)
        first = richards(0.1, latency=4, execution_time=1)(first)
        adaptor = SymmetricTwoportAdaptor(0.5, first, second)
        Sink(adaptor.output(0))
        graph = SFG([source], [Output(adaptor.output(1), name="y")]).flatten()
    assert len(graph.find_by_type(Sink)) == 1
    graph.set_execution_time_of_type(SymmetricTwoportAdaptor, 1)
    graph.set_latency_of_type(SymmetricTwoportAdaptor, 4)
    schedule = Schedule(
        graph,
        schedule_time=period,
        cyclic=True,
        scheduler=ILPRecursiveScheduler(max_time=24),
    )
    if period == 4:
        schedule.move_operation("in0", 5)
        schedule.rotate_backward()
    pes, memories, direct = assign_processing_elements_and_memories(
        schedule,
        strategy="cp_min_mux",
        memory_read_ports=1,
        memory_write_ports=1,
    )
    Architecture(pes, memories, direct_interconnects=direct)
