"""Exact memory assignment under per-cycle multiport capacity constraints."""

from collections import Counter
from itertools import product

import pytest

from b_asic.process import PlainMemoryVariable
from b_asic.resources import ProcessCollection
from test.unit.test_resources_cp import _connection_cost, _mux_problem

STRATEGIES = [
    f"{solver}_{objective}"
    for solver in ("ilp", "cp")
    for objective in ("graph_color", "min_input_mux", "min_output_mux", "min_mux")
]


@pytest.fixture(params=STRATEGIES)
def strategy(request):
    if request.param.startswith("cp_"):
        pytest.importorskip("cpmpy", exc_type=ImportError)
        pytest.importorskip("ortools.sat.python.cp_model", exc_type=ImportError)
    return request.param


def _feasible(collection, coloring, ports):
    for memory in set(coloring.values()):
        variables = [var for var in collection if coloring[var] == memory]
        reads = Counter(
            time % collection.schedule_time
            for var in variables
            for time in var.read_times
        )
        writes = Counter(var.start_time % collection.schedule_time for var in variables)
        if any(
            max(counts.values(), default=0) > capacity
            for counts, capacity in zip(
                (reads, writes, reads + writes), ports, strict=True
            )
        ):
            return False
    return True


def _coloring(collection, groups, ports):
    assigned = [var for group in groups for var in group]
    assert Counter(assigned) == Counter(collection)
    assert all(group.schedule_time == collection.schedule_time for group in groups)
    assert all(group._cyclic == collection._cyclic for group in groups)
    coloring = {var: index for index, group in enumerate(groups) for var in group}
    assert _feasible(collection, coloring, ports)
    return coloring


@pytest.mark.parametrize("ports", [(2, 1, 3), (2, 1, 2), (2, 2, 2)])
def test_multiport_objective_matches_exhaustive_search(strategy, ports, monkeypatch):
    collection, pes = _mux_problem(fanout=True)

    def no_graph(*args, **kwargs):
        pytest.fail("Multiport assignment must not use exclusion_graph_from_ports")

    monkeypatch.setattr(ProcessCollection, "exclusion_graph_from_ports", no_graph)
    bound = 3
    groups = collection.split_on_ports(
        strategy,
        read_ports=ports[0],
        write_ports=ports[1],
        total_ports=ports[2],
        strat_params={"processing_elements": pes, "max_resources": bound},
    )
    actual = _coloring(collection, groups, ports)

    def cost(coloring):
        if strategy.endswith("graph_color"):
            return len(set(coloring.values()))
        return _connection_cost(coloring, pes, strategy.replace("ilp_", "cp_"))

    costs = []
    for colors in product(range(bound), repeat=len(collection)):
        candidate = dict(zip(collection, colors, strict=True))
        if _feasible(collection, candidate, ports):
            costs.append(cost(candidate))
    assert cost(actual) == min(costs)


def test_multiport_default_bound_and_empty(strategy):
    collection, pes = _mux_problem()
    groups = collection.split_on_ports(
        strategy,
        read_ports=2,
        write_ports=1,
        strat_params={"processing_elements": pes},
    )
    assert len(groups) == 1
    _coloring(collection, groups, (2, 1, 3))
    assert (
        ProcessCollection([], 8).split_on_ports(
            strategy,
            read_ports=2,
            write_ports=1,
            strat_params={"processing_elements": pes},
        )
        == []
    )


def test_multiport_infeasible_bound(strategy):
    collection, pes = _mux_problem()
    # Make three variables compete for two read ports in cycle four.
    variables = list(collection)
    from b_asic.process import MemoryVariable

    variables[2] = MemoryVariable(
        variables[2].start_time,
        variables[2].write_port,
        dict.fromkeys(variables[2].read_ports, 4 - variables[2].start_time),
        name=variables[2].name,
    )
    collection = ProcessCollection(variables, 8)
    with pytest.raises(ValueError, match="Solution could not be found via"):
        collection.split_on_ports(
            strategy,
            read_ports=2,
            write_ports=1,
            strat_params={"processing_elements": pes, "max_resources": 1},
        )


@pytest.mark.parametrize("bound", [0, -1, 1.5])
def test_invalid_resource_bound(strategy, bound):
    collection, pes = _mux_problem()
    with pytest.raises(ValueError, match="max_resources must be a positive integer"):
        collection.split_on_ports(
            strategy,
            read_ports=2,
            write_ports=1,
            strat_params={"processing_elements": pes, "max_resources": bound},
        )


def test_individually_impossible_demand(strategy):
    collection = ProcessCollection(
        [PlainMemoryVariable(0, 0, {0: 1, 1: 9, 2: 17}, "three")], 8
    )
    with pytest.raises(ValueError, match="exceeds the port limits"):
        collection.split_on_ports(
            strategy,
            read_ports=2,
            write_ports=1,
            strat_params={"processing_elements": []},
        )


@pytest.mark.parametrize("solver", ["ilp", "cp"])
@pytest.mark.parametrize("ports", [(2, 1, 3), (2, 2, 3), (2, 2, 2)])
def test_folded_read_write_and_shared_capacity(solver, ports):
    if solver == "cp":
        pytest.importorskip("cpmpy", exc_type=ImportError)
    collection = ProcessCollection(
        [
            PlainMemoryVariable(0, 0, {0: 1, 1: 9}, "double"),
            PlainMemoryVariable(8, 0, {0: 1}, "single"),
            PlainMemoryVariable(1, 0, {0: 1}, "writer"),
        ],
        8,
        cyclic=True,
    )
    groups = collection.split_on_ports(
        f"{solver}_graph_color",
        read_ports=ports[0],
        write_ports=ports[1],
        total_ports=ports[2],
    )
    _coloring(collection, groups, ports)
    assert len(groups) == 2


@pytest.mark.parametrize("solver", ["ilp", "cp"])
def test_single_port_keeps_graph_model(solver, simple_collection, monkeypatch):
    if solver == "cp":
        pytest.importorskip("cpmpy", exc_type=ImportError)
    original = ProcessCollection.exclusion_graph_from_ports
    calls = []

    def graph(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(ProcessCollection, "exclusion_graph_from_ports", graph)
    groups = simple_collection.split_on_ports(
        f"{solver}_graph_color", read_ports=1, write_ports=1
    )
    assert calls
    assert len(groups) == 3
