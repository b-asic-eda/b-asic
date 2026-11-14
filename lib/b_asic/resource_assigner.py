"""
B-ASIC Resource Assigner Module.

Contains functions for joint resource assignment of processing elements and memories.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from random import Random
from typing import TYPE_CHECKING, Literal, cast

import networkx as nx
from pulp import (
    LpBinary,
    LpProblem,
    LpSolver,
    LpVariable,
    lpSum,
    value,
)

import b_asic.logger
from b_asic._cp_utils import _solve_cp_problem
from b_asic._ilp_utils import _solve_ilp_problem
from b_asic._memory_ports import _memory_access_groups, _MemoryAssignment
from b_asic.architecture import Memory, ProcessingElement
from b_asic.operation import Operation
from b_asic.port import InputPort
from b_asic.process import MemoryOutputPort, MemoryVariable, Process
from b_asic.resources import ProcessCollection, _sanitize_port_option
from b_asic.schedule import Schedule
from b_asic.types import TypeName
from b_asic.utility_operations import DontCare

if TYPE_CHECKING:
    from cpmpy.solvers.solver_interface import SolverInterface

log = b_asic.logger.getLogger()


def assign_processing_elements_and_memories(
    schedule: Schedule,
    *,
    strategy: Literal[
        "ilp_graph_color",
        "ilp_min_mux",
        "cp_min_mux",
        "greedy_min_mux",
        "greedy_graph_color",
        "left_edge",
    ] = "ilp_graph_color",
    max_mux_size: int | None = None,
    resources: dict[TypeName, int] | None = None,
    max_mems: int | None = None,
    memory_read_ports: int = 1,
    memory_write_ports: int = 1,
    memory_total_ports: int | None = None,
    memory_type: Literal["RAM", "register"] = "RAM",
    solver: LpSolver | str | SolverInterface | None = None,
    strat_params: dict | None = None,
) -> tuple[list[ProcessingElement], list[Memory], ProcessCollection]:
    """
    Assign PEs and memories jointly using resource assignment strategies.

    Parameters
    ----------
    schedule : :class:`~b_asic.schedule.Schedule`
        The schedule containing the operations and memory variables to assign resources to.

    strategy : str, default: "ilp_graph_color"
        The strategy used when assigning resources.
        Valid options are:

        * "ilp_graph_color" - ILP-based optimal resource assignment.
        * "ilp_min_mux" - ILP-based optimal resource assignment with multiplexer minimization.
        * "cp_min_mux" - CPMpy-based multiplexer minimization (requires the ``cp`` extra).
        * "greedy_min_mux" - Connection-aware coloring and local search.
        * "greedy_graph_color" - Greedy graph coloring-based resource assignment.
        * "left_edge" - Left-edge coloring-based resource assignment.

    max_mux_size : int, optional
        The maximum fan-in size for any enabled multiplexer target in
        strategies 'ilp_min_mux', 'cp_min_mux', and 'greedy_min_mux'. Must be
        at least 1. The heuristic may fail to find a feasible assignment even
        when one exists.
        Memory read ports count as distinct sources, and each memory write
        port is a separate target. Memory access ports are optimized together
        with resource assignment and retained in the resulting memories.

    resources : dict[:data:`~b_asic.types.TypeName`, int], optional
        The maximum amount of resources to assign to, used to limit the solution
        space for performance gains.

    max_mems : int, optional
        The maximum amount of memories to assign to, used to limit the solution
        space for performance gains.

    memory_read_ports : int, default 1
        The number of read ports used when splitting process collection based on
        memory variable access. ``left_edge`` supports multiple read ports and
        uses capacity-aware greedy packing for multiport memories.
        ``ilp_min_mux``, ``cp_min_mux``, and ``greedy_min_mux`` also support multiple read ports;
        their models enforce per-cycle port capacities. Other strategies
        require one read and one write port.

    memory_write_ports : int, default 1
        The number of write ports used when splitting process collection based on
        memory variable access. Multiple write ports are supported by
        ``left_edge``, ``ilp_min_mux``, ``cp_min_mux``, and ``greedy_min_mux``.

    memory_total_ports : int, optional
        The total number of ports used when splitting process collection based on
        memory variable access. Defaults to the sum of the read and write ports.
        Strategies other than ``left_edge``, ``ilp_min_mux``, ``cp_min_mux``, and ``greedy_min_mux``
        require one or two total ports.

    memory_type : {'RAM', 'register'}, default: 'RAM'
        The type of memory to assign to.

    solver : :class:`~pulp.LpSolver` or str or :class:`~cpmpy.solvers.solver_interface.SolverInterface`, optional
        For ``cp_min_mux``, a CPMpy solver name (default: ``"ortools"``) or
        a CPMpy solver instance. Use a fresh instance: the generated constraints
        and objective are added to it in place. Native solver settings are
        preserved. For example:

        .. code-block:: python

           import cpmpy as cp

           cp_solver = cp.SolverLookup.get("ortools")
           cp_solver.ort_solver.parameters.num_search_workers = 4
           pes, memories, direct = assign_processing_elements_and_memories(
               schedule, strategy="cp_min_mux", solver=cp_solver
           )

        For ILP strategies, a PuLP solver instance. To see which PuLP
        solvers are available:

        .. code-block:: python

           import pulp

           print(pulp.listSolvers(onlyAvailable=True))

    strat_params : dict, optional
        Options passed to the selected assignment strategy. The dictionary is
        not modified. For example, ``{"restarts": 1, "seed": 42}`` configures
        ``greedy_min_mux`` and ``{"time_limit": 60}`` configures ``cp_min_mux``.

        For ``greedy_min_mux``, the following options are supported:

        * ``restarts`` : int, default: 8
          Number of search starts. Must be positive.
        * ``max_passes`` : int, default: 20
          Maximum number of local search passes per start. Must be nonnegative;
          zero disables local search.
        * ``seed`` : int, default: 0
          Random seed. Results are reproducible for a fixed process order and seed.

        For ``greedy_graph_color``, options are forwarded to
        :func:`networkx.coloring.greedy_color` for both PEs and memories:

        * ``coloring_strategy`` : str or callable, default: "saturation_largest_first"
          Overrides NetworkX's coloring ``strategy`` for both PEs and memories.
          This is separate from the assignment ``strategy`` argument.
        * ``interchange`` : bool, default: False
          Enable color interchange. Requires a compatible ``coloring_strategy``;
          the default ``"saturation_largest_first"`` does not support it.
        * ``backend`` : str, optional
          NetworkX `backend <https://networkx.org/documentation/stable/reference/backends.html>`_
          to use. Additional backend-specific keyword arguments
          are forwarded to that backend.

        For ``cp_min_mux``, dictionary entries are passed to the CP solver's
        ``solve()`` method, e.g. ``{"time_limit": 60}`` (seconds) and, for OR-Tools,
        ``{"num_search_workers": 4, "log_search_progress": False}``. With a solver
        name, OR-Tools search logging defaults to True; supplied options override
        this default. With an instance, no logging default is imposed.

        The ``ilp_graph_color``, ``ilp_min_mux``, and ``left_edge``
        strategies have no additional algorithm options. Configure ILP solvers
        through the ``solver`` instance.

    Returns
    -------
    processing_elements : list[:class:`~b_asic.architecture.ProcessingElement`]
        The assigned processing elements.
    memories : list[:class:`~b_asic.architecture.Memory`]
        The assigned memories.
    direct : :class:`~b_asic.resources.ProcessCollection`
        Zero-time memory variables used for direct interconnects.
    """
    if max_mux_size is not None and strategy not in (
        "ilp_min_mux",
        "cp_min_mux",
        "greedy_min_mux",
    ):
        raise ValueError(
            "max_mux_size can only be specified with strategy='ilp_min_mux', "
            "'cp_min_mux', or 'greedy_min_mux', "
            f"not '{strategy}'"
        )

    if max_mux_size is not None and max_mux_size < 1:
        raise ValueError(
            f"max_mux_size must be greater than or equal to 1, got {max_mux_size}"
        )

    if strategy == "cp_min_mux":
        if solver is not None and not isinstance(solver, str):
            if isinstance(solver, LpSolver):
                raise TypeError(
                    "cp_min_mux requires a CPMpy solver name or instance, not a PuLP solver"
                )
            from cpmpy.solvers.solver_interface import SolverInterface  # noqa: PLC0415

            if not isinstance(solver, SolverInterface):
                raise TypeError("cp_min_mux requires a CPMpy solver name or instance")
    elif solver is not None and not isinstance(solver, LpSolver):
        raise TypeError(
            "ILP strategies require a PuLP solver instance, not a solver name or CP instance"
        )

    operations = schedule.get_operations()
    memory_variables = schedule.get_memory_variables()

    op_groups = operations.split_on_type_name()
    direct, mem_vars = memory_variables.split_on_length()

    operations_set, memory_variable_set = _split_operations_and_variables(
        op_groups,
        mem_vars,
        direct,
        strategy,
        max_mux_size,
        resources,
        max_mems,
        memory_read_ports,
        memory_write_ports,
        memory_total_ports,
        memory_type,
        solver,
        strat_params=strat_params,
    )

    processing_elements = [
        ProcessingElement(op_set, f"{type_name}{i}")
        for type_name, pe_operation_sets in operations_set.items()
        for i, op_set in enumerate(pe_operation_sets)
    ]

    memories = [
        Memory(
            mem,
            memory_type=memory_type,
            entity_name=f"memory{i}",
            read_ports=memory_read_ports,
            write_ports=memory_write_ports,
            total_ports=memory_total_ports,
            assign=True,
        )
        for i, mem in enumerate(memory_variable_set)
    ]

    return processing_elements, memories, direct


def _memory_upper_bound_assignment(
    mem_vars: ProcessCollection,
    read_ports: int,
    write_ports: int,
    total_ports: int | None = None,
) -> list[ProcessCollection]:
    """Return a feasible memory partition whose size bounds the minimum count."""
    read_ports, write_ports, total_ports = _sanitize_port_option(
        read_ports, write_ports, total_ports
    )
    if not mem_vars:
        return []
    strategy = (
        "greedy_graph_color"
        if read_ports == write_ports == 1 and total_ports in (1, 2)
        else "greedy_port_packing"
    )
    return mem_vars.split_on_ports(
        strategy=strategy,
        read_ports=read_ports,
        write_ports=write_ports,
        total_ports=total_ports,
    )


def _split_operations_and_variables(
    op_groups: dict[TypeName, ProcessCollection],
    mem_vars: ProcessCollection,
    direct_variables: ProcessCollection,
    strategy: Literal[
        "ilp_graph_color",
        "ilp_min_mux",
        "cp_min_mux",
        "greedy_min_mux",
        "greedy_graph_color",
        "left_edge",
    ] = "ilp_graph_color",
    max_mux_size: int | None = None,
    resources: dict[TypeName, int] | None = None,
    max_mems: int | None = None,
    memory_read_ports: int = 1,
    memory_write_ports: int = 1,
    memory_total_ports: int | None = None,
    memory_type: Literal["RAM", "register"] = "RAM",
    solver: LpSolver | str | SolverInterface | None = None,
    strat_params: dict | None = None,
) -> tuple[dict[TypeName, list[ProcessCollection]], list[ProcessCollection]]:
    strat_params = dict(strat_params or {})
    log.info("Checking that operation execution times do not exceed schedule time")
    for group in op_groups.values():
        for process in group:
            if process.execution_time > group.schedule_time:
                raise ValueError(
                    f"Operation {process} has execution time greater than the schedule time."
                )

    if any(p.execution_time > mem_vars.schedule_time for p in mem_vars):
        log.info(
            "Memory variables with execution time exceeding schedule time detected;"
            " splitting into chains automatically"
        )
        mem_vars = mem_vars.split_into_chains()

    memory_read_ports, memory_write_ports, memory_total_ports = _sanitize_port_option(
        memory_read_ports, memory_write_ports, memory_total_ports
    )
    multiport = (
        memory_read_ports != 1
        or memory_write_ports != 1
        or memory_total_ports not in (1, 2)
    )
    if multiport and strategy not in (
        "left_edge",
        "ilp_min_mux",
        "cp_min_mux",
        "greedy_min_mux",
    ):
        raise ValueError(
            f"Strategy '{strategy}' requires one read port, one write port, "
            "and one or two total memory ports; use 'left_edge', 'ilp_min_mux', "
            "'cp_min_mux', or 'greedy_min_mux' for multiport memories."
        )

    if strategy == "left_edge":
        mem_process_collections = (
            _memory_upper_bound_assignment(
                mem_vars, memory_read_ports, memory_write_ports, memory_total_ports
            )
            if multiport
            else mem_vars.split_on_ports(
                strategy="left_edge",
                read_ports=memory_read_ports,
                write_ports=memory_write_ports,
                total_ports=memory_total_ports,
                strat_params=strat_params,
            )
        )
        return {
            op_type: group.split_on_execution_time(
                "left_edge", strat_params=strat_params
            )
            for op_type, group in op_groups.items()
        }, mem_process_collections

    if strategy not in (
        "ilp_graph_color",
        "ilp_min_mux",
        "cp_min_mux",
        "greedy_min_mux",
        "greedy_graph_color",
    ):
        raise ValueError(f"Invalid strategy '{strategy}'")

    # Only ILP mux minimization consumes heuristic warm starts. Greedy graph
    # coloring uses its actual assignments to derive any missing bounds.
    warm_start = strategy == "ilp_min_mux"
    greedy_assignment = strategy == "greedy_graph_color"
    coloring_strategy = (
        strat_params.pop("coloring_strategy", "saturation_largest_first")
        if greedy_assignment
        else "saturation_largest_first"
    )
    coloring_options = strat_params if greedy_assignment else {}

    # Generate the color upper bound for PEs
    log.info("Generating color upper bounds")
    max_pes = {}
    pe_greedy_colorings: dict[TypeName, dict] = {}
    pe_operations = []
    for op_type, group in op_groups.items():
        if warm_start:
            pe_operations.append(next(iter(group)).operation)
        if (
            greedy_assignment
            or warm_start
            or resources is None
            or op_type not in resources
        ):
            coloring = nx.coloring.greedy_color(
                group.exclusion_graph_from_execution_time(),
                strategy=coloring_strategy,
                **coloring_options,
            )
            pe_greedy_colorings[op_type] = coloring
        if resources is None or op_type not in resources:
            max_pes[op_type] = len(set(pe_greedy_colorings[op_type].values()))
        else:
            max_pes[op_type] = resources[op_type]
    log.info("Upper bounds on PE colors: %s", max_pes)

    mem_exclusion_graph = None
    mem_greedy_coloring = None
    if (
        max_mems is None
        or warm_start
        or strategy == "ilp_graph_color"
        or greedy_assignment
    ):
        if multiport:
            log.info(
                "Generating multiport memory bound and warm start using port packing"
            )
            mem_greedy_coloring = {
                var: color
                for color, group in enumerate(
                    _memory_upper_bound_assignment(
                        mem_vars,
                        memory_read_ports,
                        memory_write_ports,
                        memory_total_ports,
                    )
                )
                for var in group
            }
        else:
            log.info("Generating memory variable exclusion graph")
            mem_exclusion_graph = mem_vars.exclusion_graph_from_ports(
                memory_read_ports, memory_write_ports, memory_total_ports
            )
        if not multiport and (max_mems is None or warm_start or greedy_assignment):
            mem_greedy_coloring = nx.coloring.greedy_color(
                mem_exclusion_graph, strategy=coloring_strategy, **coloring_options
            )
    if max_mems is None:
        log.info(
            "max_mems not provided, using the feasible greedy assignment as the memory upper bound"
        )
        max_mems = len(set(mem_greedy_coloring.values()))
    read_ports_bound = mem_vars.read_ports_bound()
    write_ports_bound = mem_vars.write_ports_bound()
    memory_lower_bound = max(
        (read_ports_bound + memory_read_ports - 1) // memory_read_ports,
        (write_ports_bound + memory_write_ports - 1) // memory_write_ports,
        (mem_vars.total_ports_bound() + memory_total_ports - 1) // memory_total_ports,
    )
    log.info(
        "Upper bound on memory colors: %d, lower bound on memories: %d, "
        "lower bound on read ports: %d and write ports: %d",
        max_mems,
        memory_lower_bound,
        read_ports_bound,
        write_ports_bound,
    )

    log.info("Using strategy '%s' for resource assignment", strategy)
    if strategy == "ilp_graph_color":
        # Color the graphs concurrently using ILP to minimize the total amount of resources
        problem = LpProblem()
        pe_x, mem_x = _ilp_coloring(
            problem,
            op_groups,
            mem_exclusion_graph,
            max_pes,
            max_mems,
            solver,
            **strat_params,
        )
    elif strategy == "ilp_min_mux":
        # Color the graphs concurrently using ILP to minimize the amount of multiplexers
        # given the amount of resources and memories
        problem = LpProblem()
        pe_x, mem_x = _ilp_min_mux(
            problem,
            op_groups,
            mem_vars,
            max_pes,
            max_mems,
            pe_operations,
            direct_variables,
            max_mux_size,
            solver,
            pe_greedy_colorings,
            mem_greedy_coloring,
            memory_read_ports=memory_read_ports,
            memory_write_ports=memory_write_ports,
            memory_total_ports=memory_total_ports,
            **strat_params,
        )
    elif strategy == "cp_min_mux":
        pe_x, mem_x = _cp_min_mux(
            op_groups,
            mem_vars,
            max_pes,
            max_mems,
            direct_variables,
            memory_total_ports=memory_total_ports,
            max_mux_size=max_mux_size,
            solver=cast("str | SolverInterface | None", solver),
            memory_read_ports=memory_read_ports,
            memory_write_ports=memory_write_ports,
            **strat_params,
        )
    elif strategy == "greedy_min_mux":
        pe_x, mem_x = _greedy_min_mux(
            op_groups,
            mem_vars,
            max_pes,
            max_mems,
            direct_variables,
            memory_total_ports=memory_total_ports,
            memory_read_ports=memory_read_ports,
            memory_write_ports=memory_write_ports,
            max_mux_size=max_mux_size,
            **strat_params,
        )
    elif strategy == "greedy_graph_color":
        pe_x = {}
        for op_type_name, coloring in pe_greedy_colorings.items():
            pe_x[op_type_name] = {
                node: {
                    color: 1 if color == node_color else 0
                    for color in range(max_pes[op_type_name])
                }
                for node, node_color in coloring.items()
            }
        mem_x = {
            node: {color: 1 if color == node_color else 0 for color in range(max_mems)}
            for node, node_color in mem_greedy_coloring.items()
        }

    # Assign memories based on coloring
    mem_assignment_dict = _get_assignment_from_coloring(
        mem_vars, mem_x, max_mems, mem_vars.schedule_time
    )
    mem_process_collections = [
        mem_assignment_dict[i] for i in sorted(mem_assignment_dict.keys())
    ]

    # Assign PEs based on coloring
    pe_process_collections = {}
    schedule_time = next(iter(op_groups.values())).schedule_time
    for op_type_name, group in op_groups.items():
        pe_assignment_dict = _get_assignment_from_coloring(
            group, pe_x[op_type_name], max_pes[op_type_name], schedule_time
        )
        pe_process_collections[op_type_name] = [
            pe_assignment_dict[j] for j in sorted(pe_assignment_dict.keys())
        ]

    return pe_process_collections, mem_process_collections


def _ilp_coloring(
    problem: LpProblem,
    op_groups: dict[TypeName, ProcessCollection],
    mem_exclusion_graph: nx.Graph | None,
    max_pes: dict[TypeName, int],
    max_mems: int,
    solver: LpSolver | None = None,
) -> tuple[dict, dict]:
    pe_exclusion_graphs = {
        op_type_name: group.exclusion_graph_from_execution_time()
        for op_type_name, group in op_groups.items()
    }

    mem_graph_nodes = list(mem_exclusion_graph.nodes())
    mem_graph_edges = list(mem_exclusion_graph.edges())

    # Create decision variables for graph coloring
    # mem_x[node][color] - whether memory variable "node" is given "color"
    # mem_c[color] - whether "color" is used
    mem_x, mem_c = _create_memory_variables(problem, mem_graph_nodes, max_mems)
    # pe_x[i][node][color] - whether PE node "node" in exclusion graph "i" is given "color"
    # pe_c[i][color] - whether "color" is used in exclusion graph "i"
    pe_x, pe_c = _create_pe_variables(problem, op_groups, max_pes)

    # Objective: minimize the total amount of colors used
    problem += lpSum(mem_c[color] for color in range(max_mems)) + lpSum(
        pe_c[op_type_name][color]
        for op_type_name in pe_exclusion_graphs
        for color in range(max_pes[op_type_name])
    )

    # Constraints (for all exclusion graphs):
    #   (1) - nodes have exactly one color
    #   (2) - adjacent nodes cannot have the same color
    #   (3) - only permit assignments if color is used
    #   (4) - reduce solution space by assigning colors to the largest clique
    #   (5 & 6) - reduce solution space by ignoring the symmetry caused
    #       by cycling the graph colors
    for node in mem_graph_nodes:
        problem += lpSum(mem_x[node][i] for i in range(max_mems)) == 1
    for u, v in mem_graph_edges:
        for color in range(max_mems):
            problem += mem_x[u][color] + mem_x[v][color] <= 1
    for node in mem_graph_nodes:
        for color in range(max_mems):
            problem += mem_x[node][color] <= mem_c[color]
    max_clique = next(nx.find_cliques(mem_exclusion_graph))
    for color, node in enumerate(max_clique):
        mem_x[node][color].setInitialValue(1)
        mem_x[node][color].fixValue()
        mem_c[color].setInitialValue(1)
        mem_c[color].fixValue()
    for color in range(max_mems):
        problem += mem_c[color] <= lpSum(mem_x[node][color] for node in mem_graph_nodes)
    for color in range(max_mems)[:-1]:
        problem += mem_c[color + 1] <= mem_c[color]

    for op_type_name, pe_exclusion_graph in pe_exclusion_graphs.items():
        nodes = list(pe_exclusion_graph.nodes())
        edges = list(pe_exclusion_graph.edges())
        for node in nodes:
            problem += (
                lpSum(
                    pe_x[op_type_name][node][color]
                    for color in range(max_pes[op_type_name])
                )
                == 1
            )
        for u, v in edges:
            for color in range(max_pes[op_type_name]):
                problem += (
                    pe_x[op_type_name][u][color] + pe_x[op_type_name][v][color] <= 1
                )
        for node in nodes:
            for color in range(max_pes[op_type_name]):
                problem += pe_x[op_type_name][node][color] <= pe_c[op_type_name][color]
        max_clique = next(nx.find_cliques(pe_exclusion_graph))
        if max_pes[op_type_name] > 1:
            for color, node in enumerate(max_clique):
                pe_x[op_type_name][node][color].setInitialValue(1)
                pe_x[op_type_name][node][color].fixValue()
                pe_c[op_type_name][color].setInitialValue(1)
                pe_c[op_type_name][color].fixValue()
        for color in range(max_pes[op_type_name]):
            problem += pe_c[op_type_name][color] <= lpSum(
                pe_x[op_type_name][node][color] for node in nodes
            )
        for color in range(max_pes[op_type_name])[:-1]:
            problem += pe_c[op_type_name][color + 1] <= pe_c[op_type_name][color]

    _solve_ilp_problem(problem, solver)

    return pe_x, mem_x


def _apply_warm_start(
    pe_x: dict,
    mem_x: dict,
    pe_c: dict,
    mem_c: dict,
    pe_warm_start: dict[TypeName, dict] | None,
    mem_warm_start: dict | None,
    max_pes: dict[TypeName, int],
    max_mems: int,
) -> None:
    def _set(var: LpVariable, val: int) -> None:
        # Skip variables already fixed by busiest-slot pinning or other constraints
        if var.lowBound == var.upBound:
            return
        var.setInitialValue(val)

    if pe_warm_start is not None:
        for op_type_name, coloring in pe_warm_start.items():
            if max_pes[op_type_name] == 1:
                continue  # already fixed as integer constants, not LpVariables
            used_colors: set[int] = set()
            for proc, color in coloring.items():
                used_colors.add(color)
                for pe_idx in range(max_pes[op_type_name]):
                    var = pe_x[op_type_name][proc][pe_idx]
                    if isinstance(var, LpVariable):
                        _set(var, 1 if pe_idx == color else 0)
            for pe_idx in range(max_pes[op_type_name]):
                var = pe_c[op_type_name][pe_idx]
                if isinstance(var, LpVariable):
                    _set(var, 1 if pe_idx in used_colors else 0)

    if mem_warm_start is not None:
        used_mem_colors: set[int] = set()
        for mem_var, color in mem_warm_start.items():
            used_mem_colors.add(color)
            for mem_idx in range(max_mems):
                var = mem_x[mem_var][mem_idx]
                if isinstance(var, LpVariable):
                    _set(var, 1 if mem_idx == color else 0)
        for mem_idx in range(max_mems):
            var = mem_c[mem_idx]
            if isinstance(var, LpVariable):
                _set(var, 1 if mem_idx in used_mem_colors else 0)

    log.info("Warm start applied from greedy coloring")


def _mux_problem(
    op_groups: dict[TypeName, ProcessCollection],
    mem_vars: ProcessCollection,
    max_pes: dict[TypeName, int],
    max_mems: int,
    direct: ProcessCollection,
    memory_total_ports: int,
    *,
    memory_port_limits: tuple[int, int, int] | None = None,
) -> tuple[dict, list, list]:
    """Build shared resource families, conflict cliques, and logical port links."""
    if memory_port_limits is None and memory_total_ports not in (1, 2):
        raise ValueError("mux minimization supports one or two total memory ports")
    if (mem_vars and max_mems < 1) or any(
        max_pes[op_type] < 1 for op_type in op_groups
    ):
        raise ValueError("Insufficient resources for mux minimization")

    counts = {
        ("pe", op_type, proc): max_pes[op_type]
        for op_type, group in op_groups.items()
        for proc in group
    }
    counts.update({("mem", var): max_mems for var in mem_vars})
    op_info = {
        proc.operation: ("pe", op_type, proc)
        for op_type, group in op_groups.items()
        for proc in group
    }
    Ts = mem_vars.schedule_time
    families = []
    for op_type, group in op_groups.items():
        slots = defaultdict(set)
        for proc in group:
            for t in range(proc.start_time, proc.start_time + proc.execution_time):
                slots[t % Ts].add(("pe", op_type, proc))
        families.append(([("pe", op_type, proc) for proc in group], slots.values()))

    reads = defaultdict(set)
    writes = defaultdict(set)
    for var in mem_vars:
        key = ("mem", var)
        writes[var.start_time % Ts].add(key)
        for t in var.read_times:
            reads[t % Ts].add(key)
    if memory_port_limits is not None:
        # Multiport conflicts require weighted capacities, added by the caller.
        mem_slots = []
    elif memory_total_ports == 1:
        for t in writes.keys() & reads.keys():
            if writes[t] & reads[t]:
                raise ValueError(
                    "Cannot read and write in same cycle with one memory port"
                )
        mem_slots = [writes[t] | reads[t] for t in writes.keys() | reads.keys()]
    else:
        mem_slots = [*writes.values(), *reads.values()]
    families.append(([("mem", var) for var in mem_vars], mem_slots))

    families = [
        (keys, list(dict.fromkeys(frozenset(slot) for slot in slots if slot)))
        for keys, slots in families
    ]
    if any(
        len(clique) > counts[keys[0]]
        for keys, cliques in families
        for clique in cliques
    ):
        raise ValueError("Insufficient resources for mux minimization")
    links = []

    def add_connection(src, dst, src_port=0, dst_port=0):
        links.append((src, dst, src_port, dst_port))

    for var in mem_vars:
        dst = ("mem", var)
        if isinstance(var.write_port, MemoryOutputPort):
            source = var.write_port.source_variable
            delay = next(
                delay
                for delay in sorted(set(source.reads.values()))
                if (source.start_time + delay) % Ts == var.start_time % Ts
            )
            add_connection(("mem", source), dst, (source, delay), (var, None))
        elif not isinstance(var.write_port.operation, DontCare):
            add_connection(
                op_info[var.write_port.operation],
                dst,
                var.write_port.index,
                (var, None),
            )
        # Use the actual read port of each chain segment, rather than all
        # consumers of its root producer. Relay reads are represented above.
        for port, delay in var.reads.items():
            if isinstance(port, InputPort):
                add_connection(dst, op_info[port.operation], (var, delay), port.index)

    for var in direct:
        if isinstance(var.write_port.operation, DontCare):
            continue
        for port, offset in var.reads.items():
            if offset == 0:
                add_connection(
                    op_info[var.write_port.operation],
                    op_info[port.operation],
                    var.write_port.index,
                    port.index,
                )

    return counts, families, list(dict.fromkeys(links))


def _physical_port(key, port, assignment, ports):
    """Resolve a logical endpoint for a complete or partial greedy assignment."""
    if key[0] == "mem":
        port = ports[port]
    return (*key[:-1], assignment[key], port)


def _greedy_min_mux(
    op_groups: dict[TypeName, ProcessCollection],
    mem_vars: ProcessCollection,
    max_pes: dict[TypeName, int],
    max_mems: int,
    direct: ProcessCollection,
    *,
    memory_total_ports: int = 2,
    memory_read_ports: int = 1,
    memory_write_ports: int = 1,
    max_mux_size: int | None = None,
    restarts: int = 8,
    max_passes: int = 20,
    seed: int = 0,
) -> tuple[dict, dict]:
    """
    Heuristically minimize physical connections as in ``_cp_min_mux`` and ``_ilp_min_mux``.

    Each start uses saturation coloring for single-port conflicts. Multiport
    memories combine unit-capacity conflict edges with aggregate load counters
    and prioritize variables that use busy cycles. Placement prefers assignments
    that reuse physical connections. Local search recolors individual processes and
    swaps pairs in the same resource family. Mux fan-in violations are minimized
    before connection count, allowing initially overfull muxes to be repaired.
    Execution and memory port conflicts are forbidden throughout the search.
    Multiport moves and swaps check their net changes to all affected read,
    write, and combined-access loads before they are accepted.

    The search is bounded by ``restarts`` and ``max_passes`` and reproducible for
    a fixed process order and ``seed``. It requires no optional solver, provides
    no optimality guarantee, and raises ValueError if no feasible assignment is
    found; this does not prove infeasibility. Resource counts are upper bounds.
    """
    if max_mux_size is not None and max_mux_size < 1:
        raise ValueError("max_mux_size must be at least 1")
    if restarts < 1 or max_passes < 0:
        raise ValueError("restarts must be positive and max_passes nonnegative")
    limits = _sanitize_port_option(
        memory_read_ports, memory_write_ports, memory_total_ports
    )
    multiport = limits[:2] != (1, 1) or limits[2] not in (1, 2)
    counts, families, links = _mux_problem(
        op_groups,
        mem_vars,
        max_pes,
        max_mems,
        direct,
        memory_total_ports,
        memory_port_limits=limits if multiport else None,
    )
    capacity_rows = (
        mem_vars._port_capacity_rows(mem_vars._validated_port_accesses(*limits), limits)
        if multiport
        else []
    )
    rows_for_key = defaultdict(list)
    pressure = defaultdict(float)
    for index, (demands, capacity) in enumerate(capacity_rows):
        total = sum(demands.values())
        for var, demand in demands.items():
            key = ("mem", var)
            rows_for_key[key].append((index, demand))
            pressure[key] += demand * total / capacity
    log.debug(
        "Greedy mux search starting: %d processes, %d logical connections, "
        "%d restarts, up to %d passes per restart, seed=%d, max_mux_size=%s",
        len(counts),
        len(links),
        restarts,
        max_passes,
        seed,
        max_mux_size,
    )
    neighbors = {key: set() for key in counts}
    peers = {}
    for keys, cliques in families:
        for key in keys:
            peers[key] = keys
        for clique in cliques:
            for key in clique:
                neighbors[key].update(clique - {key})
    # Unit-capacity rows are genuine pairwise conflicts; larger capacities
    # need aggregate load checks rather than a graph exclusion.
    for demands, capacity in capacity_rows:
        if capacity == 1:
            keys = {("mem", var) for var in demands}
            for key in keys:
                neighbors[key].update(keys - {key})

    access_groups = _memory_access_groups(mem_vars, mem_vars.schedule_time)

    def evaluate(assignment, ports):
        connections = {
            (
                _physical_port(src, src_port, assignment, ports),
                _physical_port(dst, dst_port, assignment, ports),
            )
            for src, dst, src_port, dst_port in links
            if src in assignment and dst in assignment
        }
        excess = 0
        if max_mux_size is not None:
            incoming = defaultdict(int)
            for _, dst in connections:
                incoming[dst] += 1
            excess = sum(max(0, size - max_mux_size) for size in incoming.values())
        return excess, len(connections)

    def allocate_ports(assignment):
        # Port numbers are search decisions, independent of access ordering.
        # Recoloring a bank can change its best wiring, so optimize ports for
        # every candidate bank/PE assignment, including partial placements.
        slots = []
        ports = {}
        for group in access_groups:
            by_bank = defaultdict(list)
            for access in group:
                key = ("mem", access[0])
                if key in assignment:
                    by_bank[assignment[key]].append(access)
            for accesses in by_bank.values():
                ports.update({access: port for port, access in enumerate(accesses)})
                slots.append(accesses)
        current = evaluate(assignment, ports)
        improved = True
        while improved:
            improved = False
            for accesses in slots:
                for access in accesses:
                    port_count = limits[1] if access[1] is None else limits[0]
                    for port in range(port_count):
                        original = ports[access]
                        if port == original:
                            continue
                        other = next(
                            (
                                candidate
                                for candidate in accesses
                                if ports[candidate] == port
                            ),
                            None,
                        )
                        ports[access] = port
                        if other is not None:
                            ports[other] = original
                        candidate_score = evaluate(assignment, ports)
                        if candidate_score < current:
                            current = candidate_score
                            improved = True
                        else:
                            ports[access] = original
                            if other is not None:
                                ports[other] = port
        return current, ports

    def score(assignment):
        return allocate_ports(assignment)[0]

    rng = Random(seed)
    best = None
    best_score = None
    for restart in range(1, restarts + 1):
        log.debug(
            "Greedy mux restart %d/%d: initial coloring starting", restart, restarts
        )
        assignment = {}
        loads = [defaultdict(int) for _ in capacity_rows]

        def capacity_changes(move, assignment=assignment):
            changes = defaultdict(int)
            for node, color in move.items():
                for row, demand in rows_for_key.get(node, ()):
                    if node in assignment:
                        changes[row, assignment[node]] -= demand
                    changes[row, color] += demand
            return changes

        def fits_capacity(move, loads=loads, capacity_changes=capacity_changes):
            return all(
                loads[row][color] + change <= capacity_rows[row][1]
                for (row, color), change in capacity_changes(move).items()
            )

        def apply_move(
            move, loads=loads, assignment=assignment, capacity_changes=capacity_changes
        ):
            if multiport:
                for (row, color), change in capacity_changes(move).items():
                    loads[row][color] += change
            assignment.update(move)

        order = list(counts)
        rng.shuffle(order)
        # Stable tie breaking follows the shuffled order, never set iteration.
        remaining = dict.fromkeys(order)
        while remaining:
            key = max(
                remaining,
                key=lambda k: (
                    len({assignment[n] for n in neighbors[k] if n in assignment}),
                    pressure[k] if multiport else 0,
                    len(neighbors[k]),
                ),
            )
            forbidden = {assignment[n] for n in neighbors[key] if n in assignment}
            colors = [
                color
                for color in range(counts[key])
                if color not in forbidden
                and (not multiport or fits_capacity({key: color}))
            ]
            if not colors:
                break
            rng.shuffle(colors)
            chosen = None
            chosen_score = None
            for color in colors:
                assignment[key] = color
                candidate_score = score(assignment)
                del assignment[key]
                if chosen_score is None or candidate_score < chosen_score:
                    chosen, chosen_score = color, candidate_score
            apply_move({key: chosen})
            del remaining[key]
        if remaining:
            log.debug(
                "Greedy mux restart %d/%d: initial coloring failed with "
                "%d/%d processes assigned",
                restart,
                restarts,
                len(assignment),
                len(counts),
            )
            continue

        current_score = score(assignment)
        log.debug(
            "Greedy mux restart %d/%d: initial coloring complete, "
            "mux excess=%d, connections=%d",
            restart,
            restarts,
            *current_score,
        )
        for search_pass in range(1, max_passes + 1):
            log.debug(
                "Greedy mux restart %d/%d, pass %d/%d starting",
                restart,
                restarts,
                search_pass,
                max_passes,
            )
            improved = False
            accepted_moves = 0
            rng.shuffle(order)
            for key in order:
                if counts[key] == 1:
                    continue
                original = assignment[key]
                chosen_move = None
                chosen_score = current_score
                # Swaps can escape colorings in which every resource is busy.
                moves = [
                    {key: color} for color in range(counts[key]) if color != original
                ]
                moves.extend(
                    {key: assignment[other], other: original}
                    for other in peers[key]
                    if assignment[other] != original
                )
                for move in moves:
                    if any(
                        color == move.get(n, assignment[n])
                        for node, color in move.items()
                        for n in neighbors[node]
                    ):
                        continue
                    if multiport and not fits_capacity(move):
                        continue
                    previous = {node: assignment[node] for node in move}
                    assignment.update(move)
                    candidate_score = score(assignment)
                    assignment.update(previous)
                    if candidate_score < chosen_score:
                        chosen_move, chosen_score = move, candidate_score
                if chosen_move is not None:
                    apply_move(chosen_move)
                    current_score = chosen_score
                    improved = True
                    accepted_moves += 1
            log.debug(
                "Greedy mux restart %d/%d, pass %d/%d complete: "
                "%d improving moves, mux excess=%d, connections=%d",
                restart,
                restarts,
                search_pass,
                max_passes,
                accepted_moves,
                *current_score,
            )
            if not improved:
                log.debug(
                    "Greedy mux restart %d/%d: stopping after pass %d "
                    "because no improving move was found",
                    restart,
                    restarts,
                    search_pass,
                )
                break
        if current_score[0] == 0 and (best_score is None or current_score < best_score):
            best, best_score = assignment.copy(), current_score
            log.debug(
                "Greedy mux restart %d/%d: new best feasible assignment, "
                "connections=%d",
                restart,
                restarts,
                best_score[1],
            )
        log.debug(
            "Greedy mux restart %d/%d complete: mux excess=%d, connections=%d, "
            "best feasible connections=%s",
            restart,
            restarts,
            *current_score,
            best_score[1] if best_score is not None else None,
        )

    if best is None:
        log.debug("Greedy mux search finished without a feasible assignment")
        raise ValueError(
            "No feasible assignment found by greedy_min_mux; "
            "try more restarts or use cp_min_mux."
        )
    log.info("Greedy mux connection count: %d", best_score[1])
    _, best_ports = allocate_ports(best)

    def coloring(key):
        return {idx: int(idx == best[key]) for idx in range(counts[key])}

    return (
        {
            op_type: {proc: coloring(("pe", op_type, proc)) for proc in group}
            for op_type, group in op_groups.items()
        },
        _MemoryAssignment(
            {var: coloring(("mem", var)) for var in mem_vars}, best_ports
        ),
    )


def _cp_min_mux(
    op_groups: dict[TypeName, ProcessCollection],
    mem_vars: ProcessCollection,
    max_pes: dict[TypeName, int],
    max_mems: int,
    direct: ProcessCollection,
    *,
    memory_total_ports: int = 2,
    max_mux_size: int | None = None,
    solver: str | SolverInterface | None = None,
    memory_read_ports: int = 1,
    memory_write_ports: int = 1,
    **kwargs,
) -> tuple[dict, dict]:
    """
    Minimize physical connections using CPMpy integer resource assignments.

    Resource bounds have the same meaning as for ``_ilp_min_mux``. Memories
    obey per-cycle read, write, and combined port capacities.
    Connection variables are exact ORs of their logical uses, and are created
    only for physical links that can be required by the dataflow graph.
    """
    try:
        import cpmpy as cp  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError("cp_min_mux requires CPMpy; install b-asic[cp]") from exc

    if max_mux_size is not None and max_mux_size < 1:
        raise ValueError("max_mux_size must be at least 1")
    limits = _sanitize_port_option(
        memory_read_ports, memory_write_ports, memory_total_ports
    )
    multiport = limits[:2] != (1, 1) or limits[2] not in (1, 2)
    counts, families, links = _mux_problem(
        op_groups,
        mem_vars,
        max_pes,
        max_mems,
        direct,
        memory_total_ports,
        memory_port_limits=limits if multiport else None,
    )
    accesses = mem_vars._validated_port_accesses(*limits)
    model = cp.Model()
    assignments = {
        key: cp.intvar(0, count - 1, name=f"assignment_{idx}")
        for idx, (key, count) in enumerate(counts.items())
    }
    # Include even isolated, zero-duration processes in the solver model.
    model += [assignment >= 0 for assignment in assignments.values()]

    for keys, cliques in families:
        for clique in cliques:
            if len(clique) > 1:
                model += cp.AllDifferent([assignments[key] for key in clique])
        anchor = max(cliques, key=len) if cliques else frozenset(keys[:1])
        for idx, key in enumerate(key for key in keys if key in anchor):
            model += assignments[key] == idx

    # A physical endpoint includes its resource family, index, and port.
    for demands, capacity in mem_vars._port_capacity_rows(accesses, limits):
        for memory in range(max_mems):
            model += (
                cp.sum(
                    [
                        count * (assignments["mem", var] == memory)
                        for var, count in demands.items()
                    ]
                )
                <= capacity
            )

    access_groups = _memory_access_groups(mem_vars, mem_vars.schedule_time)
    ports = {
        access: cp.intvar(
            0,
            (limits[1] if access[1] is None else limits[0]) - 1,
            name=f"memory_port_{index}",
        )
        for index, access in enumerate(
            access for group in access_groups for access in group
        )
    }
    model += [port >= 0 for port in ports.values()]
    for group in access_groups:
        for first, second in combinations(group, 2):
            model += (assignments["mem", first[0]] != assignments["mem", second[0]]) | (
                ports[first] != ports[second]
            )
    endpoints = {}

    def endpoint_options(key, port):
        if (key, port) not in endpoints:
            options = []
            for index in range(counts[key]):
                assigned = assignments[key] == index
                if key[0] == "mem":
                    port_count = limits[1] if port[1] is None else limits[0]
                    options.extend(
                        (
                            (*key[:-1], index, physical_port),
                            assigned & (ports[port] == physical_port),
                        )
                        for physical_port in range(port_count)
                    )
                else:
                    options.append(((*key[:-1], index, port), assigned))
            endpoints[key, port] = options
        return endpoints[key, port]

    uses = defaultdict(list)
    for src, dst, src_port, dst_port in links:
        for physical_src, source_used in endpoint_options(src, src_port):
            for physical_dst, destination_used in endpoint_options(dst, dst_port):
                uses[physical_src, physical_dst].append(source_used & destination_used)

    connections = []
    incoming = defaultdict(list)
    for idx, ((_, dst), witnesses) in enumerate(uses.items()):
        connection = cp.boolvar(name=f"connection_{idx}")
        model += connection == cp.any(witnesses)
        connections.append(connection)
        incoming[dst].append(connection)
    if max_mux_size is not None:
        for inputs in incoming.values():
            model += cp.sum(inputs) <= max_mux_size
    if connections:
        model.minimize(cp.sum(connections))

    log.info(
        "CP model created with %d assignments and %d possible connections",
        len(assignments),
        len(connections),
    )
    stats = _solve_cp_problem(model, solver, **kwargs)
    log.info("CP mux connection count: %s", stats.objective if connections else 0)

    def coloring(key):
        assigned = int(assignments[key].value())
        return {idx: int(idx == assigned) for idx in range(counts[key])}

    pe_x = {
        op_type: {proc: coloring(("pe", op_type, proc)) for proc in group}
        for op_type, group in op_groups.items()
    }
    mem_x = _MemoryAssignment(
        {var: coloring(("mem", var)) for var in mem_vars},
        {access: int(port.value()) for access, port in ports.items()},
    )
    return pe_x, mem_x


def _ilp_min_mux_multiport(
    problem,
    op_groups,
    mem_vars,
    max_pes,
    max_mems,
    direct,
    limits,
    max_mux_size,
    solver,
    pe_warm_start,
    mem_warm_start,
):
    """Minimize connections between individual physical memory and PE ports."""
    counts, families, links = _mux_problem(
        op_groups,
        mem_vars,
        max_pes,
        max_mems,
        direct,
        limits[2],
        memory_port_limits=limits,
    )
    assignments = {
        key: [
            problem.add_variable(f"assignment_{index}_{bank}", cat=LpBinary)
            for bank in range(count)
        ]
        for index, (key, count) in enumerate(counts.items())
    }
    initial = {}
    for key, count in counts.items():
        coloring = (
            mem_warm_start if key[0] == "mem" else (pe_warm_start or {}).get(key[1])
        )
        if coloring is not None and key[-1] in coloring and coloring[key[-1]] < count:
            initial[key] = coloring[key[-1]]
    for choices in assignments.values():
        problem += lpSum(choices) == 1
    for keys, cliques in families:
        for clique in cliques:
            for bank in range(counts[keys[0]]):
                problem += lpSum(assignments[key][bank] for key in clique) <= 1
        anchor = max(cliques, key=len) if cliques else keys[:1]
        anchored = [key for key in keys if key in anchor]
        for bank, key in enumerate(anchored):
            problem += assignments[key][bank] == 1
        if keys and all(key in initial for key in keys):
            permutation = {initial[key]: bank for bank, key in enumerate(anchored)}
            remaining = iter(
                sorted(set(range(counts[keys[0]])) - set(permutation.values()))
            )
            for bank in range(counts[keys[0]]):
                if bank not in permutation:
                    permutation[bank] = next(remaining)
            initial.update({key: permutation[initial[key]] for key in keys})
    complete_start = len(initial) == len(counts)
    for key, bank in initial.items():
        for index, assigned in enumerate(assignments[key]):
            assigned.setInitialValue(int(index == bank))
    accesses = mem_vars._validated_port_accesses(*limits)
    for demands, capacity in mem_vars._port_capacity_rows(accesses, limits):
        for bank in range(max_mems):
            problem += (
                lpSum(
                    demand * assignments["mem", var][bank]
                    for var, demand in demands.items()
                )
                <= capacity
            )

    access_groups = _memory_access_groups(mem_vars, mem_vars.schedule_time)
    initial_ports = {}
    if complete_start:
        for group in access_groups:
            loads = defaultdict(int)
            for access in group:
                bank = initial["mem", access[0]]
                initial_ports[access] = loads[bank]
                loads[bank] += 1
    endpoints = {}

    def endpoint_options(key, port):
        if (key, port) not in endpoints:
            options = []
            for bank, assigned in enumerate(assignments[key]):
                if key[0] != "mem":
                    options.append(((*key[:-1], bank, port), assigned))
                    continue
                port_count = limits[1] if port[1] is None else limits[0]
                indicators = []
                for physical_port in range(port_count):
                    used = problem.add_variable(
                        f"endpoint_{len(endpoints)}_{bank}_{physical_port}",
                        cat=LpBinary,
                    )
                    indicators.append(used)
                    options.append(((*key[:-1], bank, physical_port), used))
                    if complete_start:
                        used.setInitialValue(
                            int(
                                initial[key] == bank
                                and initial_ports[port] == physical_port
                            )
                        )
                problem.addConstraint(lpSum(indicators) == assigned)
            endpoints[key, port] = options
        return endpoints[key, port]

    # Each access chooses its bank and physical port jointly. Simultaneous
    # distinct accesses cannot select the same port of the same memory.
    for group in access_groups:
        by_endpoint = defaultdict(list)
        for access in group:
            for endpoint, used in endpoint_options(("mem", access[0]), access):
                by_endpoint[endpoint].append(used)
        for indicators in by_endpoint.values():
            problem += lpSum(indicators) <= 1

    connections = {}
    witnesses = defaultdict(list)
    incoming = defaultdict(list)
    use_count = 0
    for src, dst, src_port, dst_port in links:
        for physical_src, source_used in endpoint_options(src, src_port):
            for physical_dst, destination_used in endpoint_options(dst, dst_port):
                edge = physical_src, physical_dst
                if edge not in connections:
                    connection = problem.add_variable(
                        f"connection_{len(connections)}", cat=LpBinary
                    )
                    connections[edge] = connection
                    incoming[physical_dst].append(connection)
                witness = problem.add_variable(f"use_{use_count}", cat=LpBinary)
                use_count += 1
                problem += witness <= source_used
                problem += witness <= destination_used
                problem += witness >= source_used + destination_used - 1
                witnesses[edge].append(witness)
                problem += connections[edge] >= witness
                if complete_start:
                    witness.setInitialValue(
                        int(value(source_used) == value(destination_used) == 1)
                    )
    for edge, connection in connections.items():
        problem += connection <= lpSum(witnesses[edge])
        if complete_start:
            connection.setInitialValue(
                int(any(value(witness) for witness in witnesses[edge]))
            )
    if max_mux_size is not None:
        for inputs in incoming.values():
            problem += lpSum(inputs) <= max_mux_size
    problem += lpSum(connections.values())
    _solve_ilp_problem(problem, solver, warm_start=complete_start)
    log.info("ILP mux connection count: %s", value(problem.objective))

    def coloring(key):
        return {
            bank: round(value(assigned))
            for bank, assigned in enumerate(assignments[key])
        }

    return (
        {
            op_type: {proc: coloring(("pe", op_type, proc)) for proc in group}
            for op_type, group in op_groups.items()
        },
        _MemoryAssignment(
            {var: coloring(("mem", var)) for var in mem_vars},
            {
                access: next(
                    endpoint[-1]
                    for endpoint, used in endpoints[("mem", access[0]), access]
                    if value(used) > 0.5
                )
                for group in access_groups
                for access in group
            },
        ),
    )


def _ilp_min_mux(
    problem: LpProblem,
    op_groups: dict[TypeName, ProcessCollection],
    mem_vars: ProcessCollection,
    max_pes: dict[TypeName, int],
    max_mems: int,
    pe_operations: list[Operation],
    direct: ProcessCollection,
    max_mux_size: int | None = None,
    solver: LpSolver | None = None,
    pe_warm_start: dict[TypeName, dict] | None = None,
    mem_warm_start: dict | None = None,
    *,
    memory_read_ports: int = 1,
    memory_write_ports: int = 1,
    memory_total_ports: int = 2,
) -> tuple[dict, dict]:
    limits = _sanitize_port_option(
        memory_read_ports, memory_write_ports, memory_total_ports
    )
    if limits[:2] != (1, 1):
        return _ilp_min_mux_multiport(
            problem,
            op_groups,
            mem_vars,
            max_pes,
            max_mems,
            direct,
            limits,
            max_mux_size,
            solver,
            pe_warm_start,
            mem_warm_start,
        )
    accesses = mem_vars._validated_port_accesses(*limits)
    pe_in_cnt = {
        op_type_name: op.input_count
        for op_type_name, op in zip(op_groups.keys(), pe_operations, strict=True)
    }
    pe_out_cnt = {
        op_type_name: op.output_count
        for op_type_name, op in zip(op_groups.keys(), pe_operations, strict=True)
    }

    mem_x, mem_c = _create_memory_variables(problem, mem_vars, max_mems)
    pe_x, pe_c = _create_pe_variables(problem, op_groups, max_pes)

    # Objective: minimize the total number of mux connections
    pe_to_mem_vars = _create_pe_to_mem_connection_variables(
        problem, op_groups, max_pes, pe_out_cnt, max_mems
    )
    mem_to_pe_vars = _create_mem_to_pe_connection_variables(
        problem, max_mems, op_groups, max_pes, pe_in_cnt
    )
    pe_to_pe_vars, pe_to_pe_vars_used = _create_pe_to_pe_connection_variables(
        problem, op_groups, max_pes, pe_out_cnt, pe_in_cnt
    )
    mem_to_mem_vars = _create_mem_to_mem_connection_variables(problem, max_mems)

    problem += lpSum(
        [
            lpSum(
                pe_to_mem_vars[src_pe_port][mem_idx]
                for src_pe_port in pe_to_mem_vars
                for mem_idx in pe_to_mem_vars[src_pe_port]
            ),
            lpSum(
                var
                for mem_idx in mem_to_pe_vars
                for var in mem_to_pe_vars[mem_idx].values()
            ),
            lpSum(
                var for dst_vars in pe_to_pe_vars.values() for var in dst_vars.values()
            ),
            lpSum(
                mem_to_mem_vars[src][dst]
                for src in range(max_mems)
                for dst in range(max_mems)
            ),
        ]
    )

    log.info("Adding PE->Memory constraints")
    pe_to_mem_constraints = 0
    for op_type_name, op_group in op_groups.items():
        for pe_node in op_group:
            for src_port_idxs in range(pe_out_cnt[op_type_name]):
                mem_node = _get_mem_node(pe_node, src_port_idxs, mem_vars)
                if mem_node is None:
                    continue
                log.debug(
                    "  %s:out%d -> memory:%s",
                    pe_node.name,
                    src_port_idxs,
                    mem_node.name,
                )
                for pe_idx in range(max_pes[op_type_name]):
                    for mem_idx in range(max_mems):
                        problem += (
                            pe_to_mem_vars[(op_type_name, pe_idx, src_port_idxs)][
                                mem_idx
                            ]
                            >= pe_x[op_type_name][pe_node][pe_idx]
                            + mem_x[mem_node][mem_idx]
                            - 1
                        )
                        pe_to_mem_constraints += 1
    log.info("Total PE->Memory constraints: %d", pe_to_mem_constraints)

    log.info("Adding Memory->PE constraints")
    mem_to_pe_constraints = 0
    for mem_node in mem_vars:
        if mem_node.execution_time == 0:
            continue
        for op_type_name, op_group in op_groups.items():
            pe_pairs = _get_pe_nodes(mem_node, list(op_group))
            for pe_node, in_port_idx in pe_pairs:
                if not any(mem_node.reads.get(p) for p in pe_node.operation.inputs):
                    continue
                log.debug(
                    "  memory:%s -> %s:in%d", mem_node.name, pe_node.name, in_port_idx
                )
                for pe_idx in range(max_pes[op_type_name]):
                    for mem_idx in range(max_mems):
                        problem += (
                            mem_to_pe_vars[mem_idx][(op_type_name, pe_idx, in_port_idx)]
                            >= pe_x[op_type_name][pe_node][pe_idx]
                            + mem_x[mem_node][mem_idx]
                            - 1
                        )
                        mem_to_pe_constraints += 1
    log.info("Total Memory->PE constraints: %d", mem_to_pe_constraints)

    log.info("Adding Memory->Memory constraints")
    mem_to_mem_constraints = 0
    for var in mem_vars:
        if not isinstance(var.write_port, MemoryOutputPort):
            continue
        source_var = var.write_port.source_variable
        for src_mem_idx in range(max_mems):
            for dst_mem_idx in range(max_mems):
                problem += (
                    mem_to_mem_vars[src_mem_idx][dst_mem_idx]
                    >= mem_x[source_var][src_mem_idx] + mem_x[var][dst_mem_idx] - 1
                )
                mem_to_mem_constraints += 1
    log.info("Total Memory->Memory constraints: %d", mem_to_mem_constraints)

    log.info("Adding PE->PE constraints")
    op_info = {
        proc.operation: (op_type_name, proc)
        for op_type_name, op_group in op_groups.items()
        for proc in op_group
    }
    pe_to_pe_constraints = 0
    for dir_var in direct:
        dir_var = cast(MemoryVariable, dir_var)
        source_port = dir_var.write_port
        for dest_port, offset in dir_var.reads.items():
            if offset != 0:
                continue
            if isinstance(source_port.operation, DontCare):
                continue
            src_op_type, src_proc = op_info[source_port.operation]
            dst_op_type, dst_proc = op_info[dest_port.operation]
            log.debug(
                "  %s:out%d -> %s:in%d",
                source_port.operation.graph_id,
                source_port.index,
                dest_port.operation.graph_id,
                dest_port.index,
            )
            if max_pes[src_op_type] == 1 and max_pes[dst_op_type] == 1:
                # problem += (pe_to_pe_vars[(src_op_type, 0, source_port.index)][(dst_op_type, 0, dest_port.index)] == 1)
                pe_to_pe_vars[(src_op_type, 0, source_port.index)][
                    (dst_op_type, 0, dest_port.index)
                ].setInitialValue(1)
                pe_to_pe_vars[(src_op_type, 0, source_port.index)][
                    (dst_op_type, 0, dest_port.index)
                ].fixValue()
                pe_to_pe_vars_used[(src_op_type, 0, source_port.index)][
                    (dst_op_type, 0, dest_port.index)
                ] = True
            else:
                for src_pe_idx in range(max_pes[src_op_type]):
                    for dst_pe_idx in range(max_pes[dst_op_type]):
                        # If source op assigned to src_pe_idx AND dest op assigned to dst_pe_idx,
                        # there must be a PE->PE connection between them
                        problem += (
                            pe_to_pe_vars[(src_op_type, src_pe_idx, source_port.index)][
                                (dst_op_type, dst_pe_idx, dest_port.index)
                            ]
                            >= pe_x[src_op_type][src_proc][src_pe_idx]
                            + pe_x[dst_op_type][dst_proc][dst_pe_idx]
                            - 1
                        )
                        pe_to_pe_vars_used[
                            (src_op_type, src_pe_idx, source_port.index)
                        ][(dst_op_type, dst_pe_idx, dest_port.index)] = True
                        pe_to_pe_constraints += 1
    log.info("Total PE->PE constraints: %d", pe_to_pe_constraints)

    for src_pe_port, dst_vars in pe_to_pe_vars_used.items():
        for dst_pe_port, used in dst_vars.items():
            if not used:
                log.info(
                    "PE->PE connection variable %s -> %s is not used in any constraint, fixing to 0",
                    src_pe_port,
                    dst_pe_port,
                )
                # If the connection variable is not used in any constraint, fix it to 0 to reduce the solution space
                pe_to_pe_vars[src_pe_port][dst_pe_port].setInitialValue(0)
                pe_to_pe_vars[src_pe_port][dst_pe_port].fixValue()

    # Optional constraints to limit maximum mux fan-in
    if max_mux_size is not None:
        log.info("Adding constraints to limit maximum mux fan-in to %d", max_mux_size)
        for mem_idx in range(max_mems):
            problem += (
                lpSum(
                    pe_to_mem_vars[(op_type_name, pe_idx, out_port)][mem_idx]
                    for op_type_name in op_groups
                    for pe_idx in range(max_pes[op_type_name])
                    for out_port in range(pe_out_cnt[op_type_name])
                )
                + lpSum(mem_to_mem_vars[src][mem_idx] for src in range(max_mems))
                <= max_mux_size
            )

        # A PE input mux can be fed by memory outputs and/or direct PE outputs.
        # Use one shared fan-in bound across both source types.
        for dst_op_type in op_groups:
            for dst_pe_idx in range(max_pes[dst_op_type]):
                for in_port in range(pe_in_cnt[dst_op_type]):
                    problem += (
                        lpSum(
                            [
                                *[
                                    mem_to_pe_vars[mem_idx][
                                        (dst_op_type, dst_pe_idx, in_port)
                                    ]
                                    for mem_idx in range(max_mems)
                                ],
                                *[
                                    pe_to_pe_vars[(src_op_type, src_pe_idx, out_port)][
                                        (dst_op_type, dst_pe_idx, in_port)
                                    ]
                                    for src_op_type in op_groups
                                    for src_pe_idx in range(max_pes[src_op_type])
                                    for out_port in range(pe_out_cnt[src_op_type])
                                ],
                            ]
                        )
                        <= max_mux_size
                    )

    log.info("Adding base PE assignment constraints")
    # Memory assignment constraints:
    #  * Each memory variable assigned to exactly one memory
    #  * Only use active memories
    for var in mem_vars:
        problem += lpSum(mem_x[var][mem_idx] for mem_idx in range(max_mems)) == 1
    for var in mem_vars:
        for mem_idx in range(max_mems):
            problem += mem_x[var][mem_idx] <= mem_c[mem_idx]

    # PE assignment constraints:
    #   * Each process assigned to exactly one PE
    #   * Only use active PEs
    #   * Enforce ordering of the active PEs (performance)
    for op_type_name, op_group in op_groups.items():
        for proc in op_group:
            problem += (
                lpSum(
                    pe_x[op_type_name][proc][pe_idx]
                    for pe_idx in range(max_pes[op_type_name])
                )
                == 1
            )
        if max_pes[op_type_name] > 1:
            for proc in op_group:
                for pe_idx in range(max_pes[op_type_name]):
                    problem += (
                        pe_x[op_type_name][proc][pe_idx] <= pe_c[op_type_name][pe_idx]
                    )
            for pe_idx in range(max_pes[op_type_name] - 1):
                problem += pe_c[op_type_name][pe_idx + 1] <= pe_c[op_type_name][pe_idx]

    Ts = mem_vars.schedule_time

    # procs_in_time[op_type][t] gives the list of processes of type op_type active at time t
    procs_in_time: dict[str, dict[int, list]] = {
        op_type_name: defaultdict(list) for op_type_name in op_groups
    }
    for op_type_name, op_group in op_groups.items():
        for proc in op_group:
            for t in range(proc.start_time, proc.start_time + proc.execution_time):
                procs_in_time[op_type_name][t % Ts].append(proc)

    # Loop over the schedule and add constraints
    capacity_rows = mem_vars._port_capacity_rows(accesses, limits)
    for demands, capacity in capacity_rows:
        for mem_idx in range(max_mems):
            problem += (
                lpSum(count * mem_x[var][mem_idx] for var, count in demands.items())
                <= capacity
            )
    for t in range(Ts):
        # At most one process per PE per time slot
        for op_type_name in op_groups:
            procs_at_t = procs_in_time[op_type_name][t]
            if len(procs_at_t) > 1:
                for pe_idx in range(max_pes[op_type_name]):
                    problem += (
                        lpSum(pe_x[op_type_name][proc][pe_idx] for proc in procs_at_t)
                        <= 1
                    )

    # Only unit-capacity rows imply pairwise exclusions. Multiport read
    # groups must not be anchored to distinct memories.
    busiest_mem_vars = max(
        (list(demands) for demands, capacity in capacity_rows if capacity == 1),
        key=len,
        default=list(mem_vars)[:1],
    )
    if len(busiest_mem_vars) > max_mems:
        raise ValueError("Insufficient memories for mux minimization")
    for mem_idx, var in enumerate(busiest_mem_vars):
        # problem += mem_x[var][mem_idx] == mem_c[mem_idx] == 1
        mem_x[var][mem_idx].setInitialValue(1)
        mem_x[var][mem_idx].fixValue()
        mem_c[mem_idx].setInitialValue(1)
        mem_c[mem_idx].fixValue()
    # Enforce ordering on the active-color indicators (performance)
    for mem_idx in range(1, max_mems):
        problem += mem_c[mem_idx] <= mem_c[mem_idx - 1]

    # For each operation type, set the busiest time slot to distinct indices with == 1 (performance)
    for op_type_name in op_groups:
        busiest_pe_t = max(
            procs_in_time[op_type_name],
            key=lambda t: len(procs_in_time[op_type_name][t]),
        )
        if max_pes[op_type_name] > 1:
            for pe_idx, proc in enumerate(procs_in_time[op_type_name][busiest_pe_t]):
                # problem += pe_x[op_type_name][proc][pe_idx] == pe_c[op_type_name][pe_idx] == 1
                pe_x[op_type_name][proc][pe_idx].setInitialValue(1)
                pe_x[op_type_name][proc][pe_idx].fixValue()
                pe_c[op_type_name][pe_idx].setInitialValue(1)
                pe_c[op_type_name][pe_idx].fixValue()
            for pe_idx in range(1, max_pes[op_type_name]):
                problem += pe_c[op_type_name][pe_idx] <= pe_c[op_type_name][pe_idx - 1]

    if pe_warm_start is not None or mem_warm_start is not None:
        _apply_warm_start(
            pe_x, mem_x, pe_c, mem_c, pe_warm_start, mem_warm_start, max_pes, max_mems
        )

    log.info(
        "Model created with %d variables and %d constraints. Starting to solve with solver: %s",
        len(problem.variables()),
        len(problem.constraints()),
        solver.__class__.__name__ if solver else "default",
    )
    _solve_ilp_problem(
        problem,
        solver,
        warm_start=pe_warm_start is not None or mem_warm_start is not None,
    )

    # Log active connections
    active_pe_to_mem = [
        (op_type_name, pe_idx, out_port, mem_idx)
        for op_type_name in op_groups
        for pe_idx in range(max_pes[op_type_name])
        for out_port in range(pe_out_cnt[op_type_name])
        for mem_idx in range(max_mems)
        if round(value(pe_to_mem_vars[(op_type_name, pe_idx, out_port)][mem_idx])) == 1
    ]
    log.info("PE->Memory connections: %d", len(active_pe_to_mem))
    for op_type_name, pe_idx, out_port, mem_idx in active_pe_to_mem:
        log.info("  %s%d:out%d -> memory%d", op_type_name, pe_idx, out_port, mem_idx)

    active_mem_to_pe = [
        (mem_idx, op_type_name, pe_idx, in_port)
        for mem_idx in range(max_mems)
        for op_type_name in op_groups
        for pe_idx in range(max_pes[op_type_name])
        for in_port in range(pe_in_cnt[op_type_name])
        if round(value(mem_to_pe_vars[mem_idx][(op_type_name, pe_idx, in_port)])) == 1
    ]
    log.info("Memory->PE connections: %d", len(active_mem_to_pe))
    for mem_idx, op_type_name, pe_idx, in_port in active_mem_to_pe:
        log.info("  memory%d -> %s%d:in%d", mem_idx, op_type_name, pe_idx, in_port)

    active_pe_to_pe = [
        (src_op_type, src_pe_idx, out_port, dst_op_type, dst_pe_idx, in_port)
        for src_op_type in op_groups
        for src_pe_idx in range(max_pes[src_op_type])
        for out_port in range(pe_out_cnt[src_op_type])
        for dst_op_type in op_groups
        for dst_pe_idx in range(max_pes[dst_op_type])
        for in_port in range(pe_in_cnt[dst_op_type])
        if round(
            value(
                pe_to_pe_vars[(src_op_type, src_pe_idx, out_port)][
                    (dst_op_type, dst_pe_idx, in_port)
                ]
            )
        )
        == 1
    ]
    log.info("PE->PE connections: %d", len(active_pe_to_pe))
    for (
        src_op_type,
        src_pe_idx,
        out_port,
        dst_op_type,
        dst_pe_idx,
        in_port,
    ) in active_pe_to_pe:
        log.info(
            "  %s%d:out%d -> %s%d:in%d",
            src_op_type,
            src_pe_idx,
            out_port,
            dst_op_type,
            dst_pe_idx,
            in_port,
        )

    # Log pe_x assignments
    for op_type_name, op_group in op_groups.items():
        for proc in op_group:
            for pe_idx in range(max_pes[op_type_name]):
                log.info(
                    "  pe_x[%s][%s][%d] = %s",
                    op_type_name,
                    proc,
                    pe_idx,
                    value(pe_x[op_type_name][proc][pe_idx]),
                )

    return pe_x, mem_x


def _get_assignment_from_coloring(
    proc_group: list[ProcessCollection],
    x: dict[Process, dict[int, LpVariable]],
    max_resources: int,
    schedule_time: int,
) -> dict[int, ProcessCollection]:
    proc_res = {}
    for proc in proc_group:
        for res_idx in range(max_resources):
            if round(value(x[proc][res_idx])) == 1:
                proc_res[proc] = res_idx

    assignment = {}
    for process, res_idx in proc_res.items():
        if res_idx not in assignment:
            assignment[res_idx] = ProcessCollection([], schedule_time)
        assignment[res_idx].add_process(process)

    if isinstance(x, _MemoryAssignment):
        for res_idx, collection in assignment.items():
            collection._memory_port_assignment = {
                access: port
                for access, port in x.ports.items()
                if proc_res[access[0]] == res_idx
            }

    return assignment


def _get_mem_node(
    pe_node: Process, pe_port_index: int, mem_nodes: list[Process]
) -> Process | None:
    for mem_process in mem_nodes:
        if isinstance(mem_process.write_port, MemoryOutputPort):
            continue
        if (
            mem_process.write_port.operation.graph_id == pe_node.operation.graph_id
            and mem_process.write_port.index == pe_port_index
        ):
            return mem_process
    return None


def _get_pe_nodes(
    mem_node: Process, pe_nodes: list[Process]
) -> list[tuple[Process, int]]:
    root_port = mem_node.root_write_port
    src_op = root_port.operation
    src_port_index = root_port.index
    return [
        (pe_process, input_port.index)
        for pe_process in pe_nodes
        for input_port in pe_process.operation.inputs
        if (
            input_port.connected_source.operation.graph_id == src_op.graph_id
            and input_port.connected_source.index == src_port_index
        )
    ]


def _create_memory_variables(
    problem: LpProblem, mem_vars: list, max_mems: int
) -> tuple[dict, dict]:
    mem_x = problem.add_variable_dicts(
        "mem_x", (mem_vars, range(max_mems)), cat=LpBinary
    )
    mem_c = problem.add_variable_dicts("mem_c", range(max_mems), cat=LpBinary)
    log.info(
        "Memory variables created: mem_x with shape (%d, %s) and mem_c with shape (%s)",
        len(mem_vars),
        max_mems,
        max_mems,
    )
    return mem_x, mem_c


def _create_pe_to_mem_connection_variables(
    problem: LpProblem,
    op_groups: dict[TypeName, ProcessCollection],
    max_pes: dict[TypeName, int],
    pe_output_count: dict[TypeName, int],
    max_mems: int,
) -> dict:
    pe_to_mem_vars = {}
    for op_type_name in op_groups:
        for pe_idx in range(max_pes[op_type_name]):
            for port_idx in range(pe_output_count[op_type_name]):
                src_pe_port = (op_type_name, pe_idx, port_idx)
                pe_to_mem_vars[src_pe_port] = {}
                for mem_idx in range(max_mems):
                    var_name = f"pe_to_mem_{op_type_name}_{pe_idx}_{port_idx}_{mem_idx}"
                    pe_to_mem_vars[src_pe_port][mem_idx] = problem.add_variable(
                        var_name, cat=LpBinary
                    )
    return pe_to_mem_vars


def _create_mem_to_pe_connection_variables(
    problem: LpProblem,
    max_mems: int,
    op_groups: dict[TypeName, ProcessCollection],
    max_pes: dict[TypeName, int],
    pe_input_count: dict[TypeName, int],
) -> dict:
    mem_to_pe_vars = {}
    for mem_idx in range(max_mems):
        mem_to_pe_vars[mem_idx] = {}
        for op_type_name in op_groups:
            for pe_idx in range(max_pes[op_type_name]):
                for port_idx in range(pe_input_count[op_type_name]):
                    dst_pe_port = (op_type_name, pe_idx, port_idx)
                    var_name = f"mem_to_pe_{mem_idx}_{op_type_name}_{pe_idx}_{port_idx}"
                    mem_to_pe_vars[mem_idx][dst_pe_port] = problem.add_variable(
                        var_name, cat=LpBinary
                    )
    return mem_to_pe_vars


def _create_pe_to_pe_connection_variables(
    problem: LpProblem,
    op_groups: dict[TypeName, ProcessCollection],
    max_pes: dict[TypeName, int],
    pe_output_count: dict[TypeName, int],
    pe_input_count: dict[TypeName, int],
) -> dict:
    pe_to_pe_vars = {}
    pe_to_pe_vars_used = {}
    cnt = 0
    for src_op_type_name in op_groups:
        for src_pe_idx in range(max_pes[src_op_type_name]):
            for out_port_idx in range(pe_output_count[src_op_type_name]):
                src_pe_port = (src_op_type_name, src_pe_idx, out_port_idx)
                pe_to_pe_vars[src_pe_port] = {}
                pe_to_pe_vars_used[src_pe_port] = {}
                for dst_op_type_name in op_groups:
                    for dst_pe_idx in range(max_pes[dst_op_type_name]):
                        for in_port_idx in range(pe_input_count[dst_op_type_name]):
                            dst_pe_port = (dst_op_type_name, dst_pe_idx, in_port_idx)
                            var_name = f"pe_to_pe_{src_op_type_name}_{src_pe_idx}_{out_port_idx}_{dst_op_type_name}_{dst_pe_idx}_{in_port_idx}"
                            pe_to_pe_vars[src_pe_port][dst_pe_port] = (
                                problem.add_variable(var_name, cat=LpBinary)
                            )
                            pe_to_pe_vars_used[src_pe_port][dst_pe_port] = False
                            cnt += 1
    log.info("PE->PE connection variables created: %d", cnt)
    return pe_to_pe_vars, pe_to_pe_vars_used


def _create_mem_to_mem_connection_variables(problem: LpProblem, max_mems: int) -> dict:
    mem_to_mem_vars: dict[int, dict[int, LpVariable]] = {}
    for src in range(max_mems):
        mem_to_mem_vars[src] = {}
        for dst in range(max_mems):
            mem_to_mem_vars[src][dst] = problem.add_variable(
                f"mem_to_mem_{src}_{dst}", cat=LpBinary
            )
    log.info("Memory->Memory connection variables created: %d", max_mems * max_mems)
    return mem_to_mem_vars


def _create_pe_variables(
    problem: LpProblem,
    op_groups: dict[TypeName, ProcessCollection],
    max_pes: dict[TypeName, int],
) -> tuple[dict, dict]:
    pe_x = {}
    pe_c = {}
    for op_type_name, group in op_groups.items():
        pe_x[op_type_name] = {}
        for proc in group:
            pe_x[op_type_name][proc] = {}
            if max_pes[op_type_name] == 1:
                pe_x[op_type_name][proc][0] = 1
            else:
                for pe_idx in range(max_pes[op_type_name]):
                    pe_x[op_type_name][proc][pe_idx] = problem.add_variable(
                        f"pe_x_{op_type_name}_{proc}_{pe_idx}", cat=LpBinary
                    )

        pe_c[op_type_name] = {}
        if max_pes[op_type_name] == 1:
            pe_c[op_type_name][0] = 1
        else:
            for pe_idx in range(max_pes[op_type_name]):
                pe_c[op_type_name][pe_idx] = problem.add_variable(
                    f"pe_c_{op_type_name}_{pe_idx}", cat=LpBinary
                )
    return pe_x, pe_c
