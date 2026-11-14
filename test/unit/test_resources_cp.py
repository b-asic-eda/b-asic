"""Constraint programming strategies for splitting process collections."""

import itertools

import pytest

from b_asic.architecture import ProcessingElement
from b_asic.process import MemoryVariable, OperatorProcess, PlainMemoryVariable
from b_asic.resources import ProcessCollection
from b_asic.special_operations import Input, Output

MUX_STRATEGIES = ("cp_min_input_mux", "cp_min_output_mux", "cp_min_mux")
PORT_STRATEGIES = ("cp_graph_color", *MUX_STRATEGIES)


@pytest.fixture
def cp():
    module = pytest.importorskip("cpmpy", exc_type=ImportError)
    pytest.importorskip("ortools.sat.python.cp_model", exc_type=ImportError)
    return module


def _validate_split(collection, groups, graph):
    coloring = {process: idx for idx, group in enumerate(groups) for process in group}
    assert set(coloring) == set(collection)
    assert sum(map(len, groups)) == len(collection)
    assert all(
        group and group.schedule_time == collection.schedule_time for group in groups
    )
    assert all(group._cyclic == collection._cyclic for group in groups)
    assert all(coloring[u] != coloring[v] for u, v in graph.edges())
    return coloring


@pytest.mark.parametrize("cyclic", [False, True])
def test_execution_time_coloring(cp, simple_collection, cyclic):
    collection = ProcessCollection(simple_collection, 8, cyclic=cyclic)
    groups = collection.split_on_execution_time("cp_graph_color")
    _validate_split(
        collection, groups, collection.exclusion_graph_from_execution_time()
    )
    assert len(groups) == len(collection.split_on_execution_time("ilp_graph_color"))


def test_execution_time_wrap_and_zero_duration(cp):
    first = PlainMemoryVariable(6, 0, {0: 3}, "first")
    second = PlainMemoryVariable(0, 0, {0: 1}, "second")
    zero = PlainMemoryVariable(0, 0, {0: 0}, "zero")
    collection = ProcessCollection([first, second, zero], 8, cyclic=True)
    groups = collection.split_on_execution_time("cp_graph_color")
    coloring = _validate_split(
        collection, groups, collection.exclusion_graph_from_execution_time()
    )
    assert len(groups) == 2
    assert coloring[first] != coloring[second]


def test_excessive_execution_time(cp):
    collection = ProcessCollection([PlainMemoryVariable(0, 0, {0: 9})], 8)
    with pytest.raises(ValueError, match="split_into_chains"):
        collection.split_on_execution_time("cp_graph_color")


@pytest.mark.parametrize("total_ports", [1, 2])
def test_port_coloring(cp, simple_collection, total_ports):
    groups = simple_collection.split_on_ports(
        "cp_graph_color", read_ports=1, write_ports=1, total_ports=total_ports
    )
    _validate_split(
        simple_collection,
        groups,
        simple_collection.exclusion_graph_from_ports(
            read_ports=1, write_ports=1, total_ports=total_ports
        ),
    )
    assert len(groups) == len(
        simple_collection.split_on_ports(
            "ilp_graph_color", read_ports=1, write_ports=1, total_ports=total_ports
        )
    )


@pytest.mark.parametrize("method", ["split_on_execution_time", "split_on_ports"])
def test_empty_and_isolated(cp, method):
    options = (
        {"read_ports": 1, "write_ports": 1, "total_ports": 2}
        if method == "split_on_ports"
        else {}
    )
    collection = ProcessCollection([], 8, cyclic=False)
    assert getattr(collection, method)("cp_graph_color", **options) == []
    process = PlainMemoryVariable(1, 0, {0: 0})
    collection.add_process(process)
    groups = getattr(collection, method)("cp_graph_color", **options)
    assert len(groups) == 1
    assert list(groups[0]) == [process]
    assert not groups[0]._cyclic


@pytest.mark.parametrize("method", ["split_on_execution_time", "split_on_ports"])
def test_insufficient_colors(cp, simple_collection, method):
    options = (
        {"read_ports": 1, "write_ports": 1, "total_ports": 2}
        if method == "split_on_ports"
        else {}
    )
    with pytest.raises(ValueError, match="Solution could not be found via CP"):
        getattr(simple_collection, method)(
            "cp_graph_color", alg_params={"max_colors": 1}, **options
        )


@pytest.mark.parametrize("bound", [0, -1, 1.5])
def test_invalid_bound(cp, simple_collection, bound):
    with pytest.raises(ValueError, match="max_colors must be a positive integer"):
        simple_collection.split_on_execution_time(
            "cp_graph_color", alg_params={"max_colors": bound}
        )


def _mux_problem(fanout=False):
    sources = [Input() for _ in range(4)]
    outputs = [Output(source) for source in sources]
    read_times = (4, 4, 5, 5)
    for idx, (source, output) in enumerate(zip(sources, outputs, strict=True)):
        source.graph_id = f"in{idx}"
        output.graph_id = f"out{idx}"
    variables = [
        MemoryVariable(
            idx, source.output(0), {output.input(0): time - idx}, name=f"v{idx}"
        )
        for idx, (source, output, time) in enumerate(
            zip(sources, outputs, read_times, strict=True)
        )
    ]
    source_groups = [[0, 2], [1, 3]]
    destination_groups = [[0, 3], [1, 2]]
    pes = [
        ProcessingElement(
            ProcessCollection(
                [OperatorProcess(idx, sources[idx]) for idx in indices], 8
            ),
            entity_name=f"source{pe}",
        )
        for pe, indices in enumerate(source_groups)
    ]
    for pe, indices in enumerate(destination_groups):
        processes = [OperatorProcess(read_times[idx], outputs[idx]) for idx in indices]
        if fanout and pe == 1:
            extra = Output(sources[0])
            extra.graph_id = "out4"
            processes.append(OperatorProcess(6, extra))
            variables[0] = MemoryVariable(
                0,
                sources[0].output(0),
                {outputs[0].input(0): 4, extra.input(0): 6},
                name="fanout",
            )
        pes.append(
            ProcessingElement(
                ProcessCollection(processes, 8), entity_name=f"destination{pe}"
            )
        )
    return ProcessCollection(variables, 8), pes


def _connection_cost(coloring, pes, strategy):
    pe_for_op = {process.operation: idx for idx, pe in enumerate(pes) for process in pe}
    links = set()
    for var, memory in coloring.items():
        if strategy != "cp_min_output_mux":
            port = var.write_port
            links.add(("out", pe_for_op[port.operation], port.index, memory))
        if strategy != "cp_min_input_mux":
            for port in var.read_ports:
                links.add(("in", pe_for_op[port.operation], port.index, memory))
    return len(links)


@pytest.mark.parametrize("strategy", MUX_STRATEGIES)
@pytest.mark.parametrize("fanout", [False, True])
def test_mux_optimality(cp, strategy, fanout):
    collection, pes = _mux_problem(fanout)
    solver = cp.SolverLookup.get("ortools")
    params = {"processing_elements": pes, "max_colors": 2, "solver": solver}
    groups = collection.split_on_ports(
        strategy, read_ports=1, write_ports=1, total_ports=2, alg_params=params
    )
    graph = collection.exclusion_graph_from_ports(
        read_ports=1, write_ports=1, total_ports=2
    )
    coloring = _validate_split(collection, groups, graph)
    # Compare the physical connection cost against every feasible assignment.
    costs = []
    for colors in itertools.product(range(2), repeat=len(collection)):
        candidate = dict(zip(collection, colors, strict=True))
        if all(candidate[u] != candidate[v] for u, v in graph.edges()):
            costs.append(_connection_cost(candidate, pes, strategy))
    assert _connection_cost(coloring, pes, strategy) == min(costs)
    assert solver.objective_value() == min(costs)


@pytest.mark.parametrize("strategy", MUX_STRATEGIES)
def test_missing_processing_elements(simple_collection, strategy):
    with pytest.raises(
        ValueError,
        match=f"processing_elements must be provided if strategy = '{strategy}'",
    ):
        simple_collection.split_on_ports(
            strategy, read_ports=1, write_ports=1, total_ports=2
        )


@pytest.mark.parametrize("strategy", PORT_STRATEGIES)
def test_multiple_read_ports(cp, strategy):
    collection, pes = _mux_problem()
    groups = collection.split_on_ports(
        strategy,
        read_ports=2,
        write_ports=1,
        alg_params={"processing_elements": pes},
    )
    assert len(groups) == 1
    assert set(groups[0]) == set(collection)


@pytest.mark.parametrize("instance", [False, True])
def test_solver_options(cp, simple_collection, instance):
    solver = cp.SolverLookup.get("ortools") if instance else "ortools"
    if instance:
        solver.ort_solver.parameters.num_search_workers = 1
    params = {"solver": solver, "solver_options": {"time_limit": 10}}
    groups = simple_collection.split_on_execution_time(
        "cp_graph_color", alg_params=params
    )
    _validate_split(
        simple_collection,
        groups,
        simple_collection.exclusion_graph_from_execution_time(),
    )
    assert params["solver_options"] == {"time_limit": 10}
    if instance:
        assert solver.ort_solver.parameters.num_search_workers == 1


def test_invalid_solver(cp, simple_collection):
    with pytest.raises(TypeError, match="CPMpy solver name or instance"):
        simple_collection.split_on_execution_time(
            "cp_graph_color", alg_params={"solver": object()}
        )


def test_missing_cp_dependency(monkeypatch, simple_collection):
    import builtins

    original_import = builtins.__import__

    def without_cpmpy(name, *args, **kwargs):
        if name == "cpmpy":
            raise ImportError("CPMpy unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_cpmpy)
    with pytest.raises(ImportError, match=r"install b-asic\[cp\]"):
        simple_collection.split_on_execution_time("cp_graph_color")


@pytest.mark.parametrize("method", ["split_on_execution_time", "split_on_ports"])
def test_split_recovers_after_interruption(cp, simple_collection, monkeypatch, method):
    solver = cp.SolverLookup.get("ortools")
    solve = solver.solve

    def interrupted_solve(**options):
        assert solve(**options)
        for var in solver.user_vars:
            var.clear()
        raise KeyboardInterrupt

    monkeypatch.setattr(solver, "solve", interrupted_solve)
    options = (
        {"read_ports": 1, "write_ports": 1, "total_ports": 2}
        if method == "split_on_ports"
        else {}
    )
    groups = getattr(simple_collection, method)(
        "cp_graph_color", alg_params={"solver": solver}, **options
    )
    graph = (
        simple_collection.exclusion_graph_from_ports(**options)
        if options
        else simple_collection.exclusion_graph_from_execution_time()
    )
    _validate_split(simple_collection, groups, graph)
