"""
B-ASIC Resource Assigner Module.

Contains functions for joint resource assignment of processing elements and memories.
"""

import contextlib
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

import networkx as nx
from pulp import (
    PULP_CBC_CMD,
    LpBinary,
    LpProblem,
    LpSolver,
    LpStatusInfeasible,
    LpStatusNotSolved,
    LpStatusOptimal,
    LpVariable,
    lpSum,
    value,
)

import b_asic.logger
from b_asic.architecture import Memory, ProcessingElement
from b_asic.operation import Operation
from b_asic.process import MemoryVariable, Process
from b_asic.resources import ProcessCollection
from b_asic.schedule import Schedule
from b_asic.types import TypeName
from b_asic.utility_operations import DontCare

log = b_asic.logger.getLogger()


def assign_processing_elements_and_memories(
    schedule: Schedule,
    *,
    strategy: Literal[
        "ilp_graph_color",
        "ilp_min_mux",
        "greedy_graph_color",
        "left_edge",
    ] = "ilp_graph_color",
    max_mux_size: int | None = None,
    resources: dict[TypeName, int] | None = None,
    max_mems: int | None = None,
    memory_read_ports: int | None = None,
    memory_write_ports: int | None = None,
    memory_total_ports: int | None = None,
    memory_type: Literal["RAM", "register"] = "RAM",
    solver: LpSolver | None = None,
) -> tuple[list[ProcessingElement], list[Memory], ProcessCollection]:
    """
    Assign PEs and memories jointly using ILP.

    Parameters
    ----------
    schedule : Schedule
        The schedule containing the operations and memory variables to assign resources to.

    strategy : str, default: "ilp_graph_color"
        The strategy used when assigning resources.
        Valid options are:

        * "ilp_graph_color" - ILP-based optimal resource assignment.
        * "ilp_min_mux" - ILP-based optimal resource assignment with multiplexer minimization.
        * "greedy_graph_color" - Greedy graph coloring-based resource assignment.
        * "left_edge" - Left-edge coloring-based resource assignment.

    max_mux_size : int, optional
        The maximum fan-in size for any enabled multiplexer target in
        strategy='ilp_min_mux'. Must be greater than or equal to 1.
        Only valid with 'ilp_min_mux' strategy.

    resources : dict[TypeName, int], optional
        The maximum amount of resources to assign to, used to limit the solution
        space for performance gains.

    max_mems : int, optional
        The maximum amount of memories to assign to, used to limit the solution
        space for performance gains.

    memory_read_ports : int, optional
        The number of read ports used when splitting process collection based on
        memory variable access.

    memory_write_ports : int, optional
        The number of write ports used when splitting process collection based on
        memory variable access.

    memory_total_ports : int, optional
        The total number of ports used when splitting process collection based on
        memory variable access.

    memory_type : {'RAM', 'register'}, default: 'RAM'
        The type of memory to assign to.

    solver : :class:`~pulp.LpSolver`, optional
        Solver to use. To see which solvers are available:

        .. code-block:: python

           import pulp

           print(pulp.listSolvers(onlyAvailable=True))

    Returns
    -------
    A tuple containing one list of assigned PEs and one list of assigned memories.
    """
    if max_mux_size is not None and strategy != "ilp_min_mux":
        raise ValueError(
            "max_mux_size can only be specified with strategy='ilp_min_mux', "
            f"not '{strategy}'"
        )

    if max_mux_size is not None and max_mux_size < 1:
        raise ValueError(
            f"max_mux_size must be greater than or equal to 1, got {max_mux_size}"
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
    )

    processing_elements = [
        ProcessingElement(op_set, f"{type_name}{i}")
        for type_name, pe_operation_sets in operations_set.items()
        for i, op_set in enumerate(pe_operation_sets)
    ]

    memories = [
        Memory(mem, memory_type=memory_type, entity_name=f"memory{i}", assign=True)
        for i, mem in enumerate(memory_variable_set)
    ]

    return processing_elements, memories, direct


def _split_operations_and_variables(
    op_groups: dict[TypeName, ProcessCollection],
    mem_vars: ProcessCollection,
    direct_variables: ProcessCollection,
    strategy: Literal[
        "ilp_graph_color",
        "ilp_min_mux",
        "greedy_graph_color",
        "left_edge",
    ] = "ilp_graph_color",
    max_mux_size: int | None = None,
    resources: dict[TypeName, int] | None = None,
    max_mems: int | None = None,
    memory_read_ports: int | None = None,
    memory_write_ports: int | None = None,
    memory_total_ports: int | None = None,
    memory_type: Literal["RAM", "register"] = "RAM",
    solver: LpSolver | None = None,
) -> tuple[dict[TypeName, list[ProcessCollection]], list[ProcessCollection]]:
    log.info("Checking that operation execution times do not exceed schedule time")
    for group in op_groups.values():
        for process in group:
            if process.execution_time > group.schedule_time:
                raise ValueError(
                    f"Operation {process} has execution time greater than the schedule time."
                )

    if memory_type == "RAM":
        log.info(
            "Checking that memory variable execution times do not exceed schedule time due to RAM memory type"
        )
        for process in mem_vars:
            if process.execution_time > mem_vars.schedule_time:
                raise ValueError(
                    f"Memory variable {process} has execution time greater than the schedule time."
                )

    # Generate the color upper bound for PEs
    log.info("Generating color upper bounds")
    max_pes = {}
    pe_greedy_colorings: dict[TypeName, dict] = {}
    pe_operations = []
    for group in op_groups.values():
        operation = next(iter(group)).operation
        pe_operations.append(operation)
        pe_ex_graph = group.exclusion_graph_from_execution_time()
        coloring = nx.coloring.greedy_color(
            pe_ex_graph, strategy="saturation_largest_first"
        )
        pe_greedy_colorings[operation.type_name()] = coloring
        if not resources or operation.type_name() not in resources:
            max_pes[operation.type_name()] = len(set(coloring.values()))
        else:
            max_pes[operation.type_name()] = resources[operation.type_name()]
    log.info("Upper bounds on PE colors: %s", max_pes)

    log.info("Generating memory variable exclusion graph")
    mem_exclusion_graph = mem_vars.exclusion_graph_from_ports(
        memory_read_ports, memory_write_ports, memory_total_ports
    )
    mem_greedy_coloring = nx.coloring.greedy_color(
        mem_exclusion_graph, strategy="saturation_largest_first"
    )
    if max_mems is None:
        log.info(
            "max_mems not provided, using greedy graph coloring to determine upper bound on memory colors"
        )
        max_mems = len(set(mem_greedy_coloring.values()))
    log.info(
        "Upper bound on memory colors: %d, maximum number of memory reads: %d and memory writes: %d",
        max_mems,
        mem_vars.read_ports_bound(),
        mem_vars.write_ports_bound(),
    )

    log.info("Using strategy '%s' for resource assignment", strategy)
    if strategy == "ilp_graph_color":
        # Color the graphs concurrently using ILP to minimize the total amount of resources
        pe_x, mem_x = _ilp_coloring(
            op_groups, mem_exclusion_graph, max_pes, max_mems, solver
        )
    elif strategy == "ilp_min_mux":
        # Color the graphs concurrently using ILP to minimize the amount of multiplexers
        # given the amount of resources and memories
        pe_x, mem_x = _ilp_min_mux(
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
        )
    elif strategy == "greedy_graph_color":
        pe_x = {}
        for op_type_name, group in op_groups.items():
            pe_ex_graph = group.exclusion_graph_from_execution_time()
            coloring = nx.coloring.greedy_color(
                pe_ex_graph, strategy="saturation_largest_first"
            )
            pe_x[op_type_name] = {
                node: {
                    color: 1 if color == node_color else 0
                    for color in range(max_pes[op_type_name])
                }
                for node, node_color in coloring.items()
            }
        mem_coloring = nx.coloring.greedy_color(
            mem_exclusion_graph, strategy="saturation_largest_first"
        )
        mem_x = {
            node: {color: 1 if color == node_color else 0 for color in range(max_mems)}
            for node, node_color in mem_coloring.items()
        }
    elif strategy == "left_edge":
        mem_process_collections = mem_vars.split_on_ports(
            strategy="left_edge",
            read_ports=memory_read_ports,
            write_ports=memory_write_ports,
            total_ports=memory_total_ports,
        )
        pe_process_collections = {}
        for op_type_name, group in op_groups.items():
            pe_process_collections[op_type_name] = group.split_on_execution_time(
                strategy="left_edge"
            )
        return pe_process_collections, mem_process_collections
    else:
        raise ValueError(f"Invalid strategy '{strategy}'")

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
    mem_x, mem_c = _create_memory_variables(mem_graph_nodes, max_mems)
    # pe_x[i][node][color] - whether PE node "node" in exclusion graph "i" is given "color"
    # pe_c[i][color] - whether "color" is used in exclusion graph "i"
    pe_x, pe_c = _create_pe_variables(op_groups, max_pes)

    # Objective: minimize the total amount of colors used
    problem = LpProblem()
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
        problem += mem_x[node][color] == mem_c[color] == 1
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
        for color, node in enumerate(max_clique):
            problem += (
                pe_x[op_type_name][node][color] == pe_c[op_type_name][color] == 1
            )  # TODO FIXVALUE
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


def _ilp_min_mux(
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
) -> tuple[dict, dict]:
    pe_in_cnt = {
        op_type_name: op.input_count
        for op_type_name, op in zip(op_groups.keys(), pe_operations, strict=True)
    }
    pe_out_cnt = {
        op_type_name: op.output_count
        for op_type_name, op in zip(op_groups.keys(), pe_operations, strict=True)
    }

    mem_x, mem_c = _create_memory_variables(mem_vars, max_mems)
    pe_x, pe_c = _create_pe_variables(op_groups, max_pes)

    # Objective: minimize the total number of mux connections
    pe_to_mem_vars = _create_pe_to_mem_connection_variables(
        op_groups, max_pes, pe_out_cnt, max_mems
    )
    mem_to_pe_vars = _create_mem_to_pe_connection_variables(
        max_mems, op_groups, max_pes, pe_in_cnt
    )
    pe_to_pe_vars, pe_to_pe_vars_used = _create_pe_to_pe_connection_variables(
        op_groups, max_pes, pe_out_cnt, pe_in_cnt
    )

    problem = LpProblem()
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

    # mem_writes_in_time[t] / mem_reads_in_time[t]: variables written/read at time t
    mem_writes_in_time: dict[int, list] = defaultdict(list)
    mem_reads_in_time: dict[int, list] = defaultdict(list)
    Ts = mem_vars.schedule_time
    for var in mem_vars:
        mem_writes_in_time[var.start_time % Ts].append(var)
        for rt in var.read_times:
            mem_reads_in_time[rt % Ts].append(var)

    # procs_in_time[op_type][t] gives the list of processes of type op_type active at time t
    procs_in_time: dict[str, dict[int, list]] = {
        op_type_name: defaultdict(list) for op_type_name in op_groups
    }
    for op_type_name, op_group in op_groups.items():
        for proc in op_group:
            for t in range(proc.start_time, proc.start_time + proc.execution_time):
                procs_in_time[op_type_name][t % Ts].append(proc)

    # Loop over the schedule and add constraints
    for t in range(Ts):
        # At most one read/write per memory per time slot
        for vars_at_t in (mem_writes_in_time[t], mem_reads_in_time[t]):
            if len(vars_at_t) > 1:
                for mem_idx in range(max_mems):
                    problem += lpSum(mem_x[var][mem_idx] for var in vars_at_t) <= 1
        # At most one process per PE per time slot
        for op_type_name in op_groups:
            procs_at_t = procs_in_time[op_type_name][t]
            if len(procs_at_t) > 1:
                for pe_idx in range(max_pes[op_type_name]):
                    problem += (
                        lpSum(pe_x[op_type_name][proc][pe_idx] for proc in procs_at_t)
                        <= 1
                    )

    # Set the busiest time slot to distinct indices with == 1 (performance)
    # Use whichever of reads/writes is largest at the busiest time step
    all_mem_times = list(
        dict.fromkeys(list(mem_writes_in_time) + list(mem_reads_in_time))
    )
    busiest_mem_t = max(
        all_mem_times,
        key=lambda t: max(len(mem_writes_in_time[t]), len(mem_reads_in_time[t])),
    )
    busiest_mem_vars = (
        mem_reads_in_time[busiest_mem_t]
        if len(mem_reads_in_time[busiest_mem_t])
        > len(mem_writes_in_time[busiest_mem_t])
        else mem_writes_in_time[busiest_mem_t]
    )
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
        len(problem.constraints),
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

    return assignment


def _get_mem_node(
    pe_node: Process, pe_port_index: int, mem_nodes: list[Process]
) -> Process | None:
    for mem_process in mem_nodes:
        parts = mem_process.name.split(".")
        var_name, port_str = parts[0], parts[1]
        if var_name == pe_node.operation.graph_id and int(port_str) == pe_port_index:
            return mem_process
    return None


def _get_pe_nodes(
    mem_node: Process, pe_nodes: list[Process]
) -> list[tuple[Process, int]]:
    nodes = []
    parts = mem_node.name.split(".")
    var_name = parts[0]
    port_index = int(parts[1])
    for pe_process in pe_nodes:
        for input_port in pe_process.operation.inputs:
            input_op = input_port.connected_source.operation
            if (
                input_op.graph_id == var_name
                and input_port.connected_source.index == port_index
            ):
                nodes.append((pe_process, input_port.index))
    return nodes


def _create_memory_variables(mem_vars: list, max_mems: list[int]) -> tuple[dict, dict]:
    mem_x = LpVariable.dicts("mem_x", (mem_vars, range(max_mems)), cat=LpBinary)
    mem_c = LpVariable.dicts("mem_c", range(max_mems), cat=LpBinary)
    log.info(
        "Memory variables created: mem_x with shape (%d, %s) and mem_c with shape (%s)",
        len(mem_vars),
        max_mems,
        max_mems,
    )
    return mem_x, mem_c


def _create_pe_to_mem_connection_variables(
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
                    pe_to_mem_vars[src_pe_port][mem_idx] = LpVariable(
                        var_name, cat=LpBinary
                    )
    return pe_to_mem_vars


def _create_mem_to_pe_connection_variables(
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
                    mem_to_pe_vars[mem_idx][dst_pe_port] = LpVariable(
                        var_name, cat=LpBinary
                    )
    return mem_to_pe_vars


def _create_pe_to_pe_connection_variables(
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
                            pe_to_pe_vars[src_pe_port][dst_pe_port] = LpVariable(
                                var_name, cat=LpBinary
                            )
                            pe_to_pe_vars_used[src_pe_port][dst_pe_port] = False
                            cnt += 1
    log.info("PE->PE connection variables created: %d", cnt)
    return pe_to_pe_vars, pe_to_pe_vars_used


def _create_pe_variables(
    op_groups: dict[TypeName, ProcessCollection], max_pes: list[int]
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
                    pe_x[op_type_name][proc][pe_idx] = LpVariable(
                        f"pe_x_{op_type_name}_{proc}_{pe_idx}", cat=LpBinary
                    )

        pe_c[op_type_name] = {}
        if max_pes[op_type_name] == 1:
            pe_c[op_type_name][0] = 1
        else:
            for pe_idx in range(max_pes[op_type_name]):
                pe_c[op_type_name][pe_idx] = LpVariable(
                    f"pe_c_{op_type_name}_{pe_idx}", cat=LpBinary
                )
    return pe_x, pe_c


def _solve_ilp_problem(
    problem: LpProblem,
    solver: LpSolver | None,
    warm_start: bool = False,
) -> None:
    # Default to a CBC solver if no solver is provided
    # Suppress ILP solver output if logging not set to DEBUG
    if solver is None:
        msg = 1 if log.isEnabledFor(b_asic.logger.logging.DEBUG) else 0
        solver = PULP_CBC_CMD(msg=msg, warmStart=warm_start)
    elif warm_start and isinstance(solver, PULP_CBC_CMD):
        solver.warmStart = True

    recovery_state = _prepare_interrupted_recovery(problem, solver)

    # Solve the ILP problem
    status = None
    interrupted = False
    try:
        status = problem.solve(solver)
    except KeyboardInterrupt:
        interrupted = True
        log.warning(
            "ILP solver interrupted; attempting to keep best feasible solution."
        )
        status = _recover_interrupted_solution(problem, solver, recovery_state)
    finally:
        _restore_interrupted_recovery(problem, solver, recovery_state)

    if _has_feasible_solution(problem):
        if interrupted or status == LpStatusNotSolved:
            log.warning("Using best feasible ILP solution found before solver stopped.")
        return

    if interrupted:
        raise ValueError(
            "No feasible ILP solution was found before the solver stopped."
        )

    if status not in (LpStatusOptimal, LpStatusNotSolved):
        raise ValueError("Solution could not be found via ILP, use another method.")

    raise ValueError("No feasible ILP solution was found before the solver stopped.")


def _recover_interrupted_solution(
    problem: LpProblem,
    solver: LpSolver,
    recovery_state: dict[str, object] | None,
) -> int | None:
    solution_path = None
    if recovery_state is not None:
        solution_path = cast(str | None, recovery_state.get("solution_path"))
    if solution_path and _recover_cmd_solution_file(problem, solver, solution_path):
        return problem.status

    find_solution_values = getattr(solver, "findSolutionValues", None)
    if not callable(find_solution_values):
        return None

    try:
        return cast(int, find_solution_values(problem))
    except Exception as exc:
        log.info("Failed to recover interrupted ILP solution: %s", exc)
        return None


def _prepare_interrupted_recovery(
    problem: LpProblem,
    solver: LpSolver,
) -> dict[str, object] | None:
    if not hasattr(solver, "keepFiles") or not hasattr(solver, "create_tmp_files"):
        return None

    original_keep_files = cast(bool, solver.keepFiles)
    original_name = problem.name
    recovery_dir = tempfile.mkdtemp(prefix="b_asic_ilp_recovery_")
    recovery_name = str(Path(recovery_dir) / f"{problem.name}-{uuid4().hex}")

    solver.keepFiles = True
    problem.name = recovery_name
    solution_path = next(solver.create_tmp_files(recovery_name, "sol"))

    return {
        "original_keep_files": original_keep_files,
        "original_name": original_name,
        "recovery_name": recovery_name,
        "recovery_dir": recovery_dir,
        "solution_path": solution_path,
        "temp_paths": tuple(solver.create_tmp_files(recovery_name, "lp", "sol", "mst")),
    }


def _restore_interrupted_recovery(
    problem: LpProblem,
    solver: LpSolver,
    recovery_state: dict[str, object] | None,
) -> None:
    if recovery_state is None:
        return

    problem.name = cast(str, recovery_state["original_name"])
    solver.keepFiles = recovery_state["original_keep_files"]

    if cast(bool, recovery_state["original_keep_files"]):
        return

    for path in cast(tuple[str, ...], recovery_state["temp_paths"]):
        with contextlib.suppress(FileNotFoundError):
            Path(path).unlink()
    recovery_dir = cast(str | None, recovery_state.get("recovery_dir"))
    if recovery_dir is not None:
        shutil.rmtree(recovery_dir, ignore_errors=True)
    with contextlib.suppress(FileNotFoundError):
        Path("gurobi.log").unlink()


def _recover_cmd_solution_file(
    problem: LpProblem,
    solver: LpSolver,
    solution_path: str,
) -> bool:
    read_solution = getattr(solver, "readsol", None)
    if not callable(read_solution) or not Path(solution_path).exists():
        return False

    try:
        solution = read_solution(solution_path)
    except Exception as exc:
        log.info(
            "Failed to parse interrupted solver solution file %s: %s",
            solution_path,
            exc,
        )
        return False

    if not isinstance(solution, tuple) or len(solution) < 2:
        return False

    status = cast(int, solution[0])
    values = cast(dict[str, float], solution[1])
    reduced_costs = cast(dict[str, float], solution[2]) if len(solution) > 2 else {}
    shadow_prices = cast(dict[str, float], solution[3]) if len(solution) > 3 else {}
    slacks = cast(dict[str, float], solution[4]) if len(solution) > 4 else {}

    if status != LpStatusInfeasible:
        problem.assignVarsVals(values)
        if reduced_costs:
            problem.assignVarsDj(reduced_costs)
        if shadow_prices:
            problem.assignConsPi(shadow_prices)
        if slacks:
            problem.assignConsSlack(slacks)
    problem.assignStatus(status)
    return _has_feasible_solution(problem)


def _has_feasible_solution(problem: LpProblem) -> bool:
    if value(problem.objective) is not None:
        return True

    variables = problem.variables()
    return bool(variables) and all(var.varValue is not None for var in variables)
