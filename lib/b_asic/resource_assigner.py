"""
B-ASIC Resource Assigner Module.

Contains functions for joint resource assignment of processing elements and memories.
"""

import os
import shutil
import tempfile
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
        "ilp_min_total_mux",
    ] = "ilp_graph_color",
    mux_targets: set[Literal["pe_to_mem", "mem_to_pe", "pe_to_pe"]] | None = None,
    max_mux_size: int | None = None,
    resources: dict[TypeName, int] | None = None,
    max_memories: int | None = None,
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
        * "ilp_min_total_mux" - ILP-based optimal resource assignment with multiplexer minimization.

    mux_targets : set of {'pe_to_mem', 'mem_to_pe', 'pe_to_pe'}, optional
        Specifies which multiplexer types to minimize when using strategy='ilp_min_total_mux'.
        If None, all three types are minimized.
        Only valid with 'ilp_min_total_mux' strategy.

        * "pe_to_mem" - Minimize PE to Memory connections
        * "mem_to_pe" - Minimize Memory to PE connections
        * "pe_to_pe" - Minimize PE to PE direct connections

    max_mux_size : int, optional
        The maximum fan-in size for any enabled multiplexer target in
        strategy='ilp_min_total_mux'. Must be greater than or equal to 1.
        Only valid with 'ilp_min_total_mux' strategy.

    resources : dict[TypeName, int], optional
        The maximum amount of resources to assign to, used to limit the solution
        space for performance gains.

    max_memories : int, optional
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
    if mux_targets is not None and strategy != "ilp_min_total_mux":
        raise ValueError(
            "mux_targets can only be specified with strategy='ilp_min_total_mux', "
            f"not '{strategy}'"
        )

    if max_mux_size is not None and strategy != "ilp_min_total_mux":
        raise ValueError(
            "max_mux_size can only be specified with strategy='ilp_min_total_mux', "
            f"not '{strategy}'"
        )

    if max_mux_size is not None and max_mux_size < 1:
        raise ValueError(
            f"max_mux_size must be greater than or equal to 1, got {max_mux_size}"
        )

    if strategy == "ilp_min_total_mux" and mux_targets is None:
        mux_targets = {"pe_to_mem", "mem_to_pe", "pe_to_pe"}

    operations = schedule.get_operations()
    memory_variables = schedule.get_memory_variables()

    operation_groups = operations.split_on_type_name()
    direct, mem_vars = memory_variables.split_on_length()

    operations_set, memory_variable_set = _split_operations_and_variables(
        operation_groups,
        mem_vars,
        direct,
        strategy,
        mux_targets,
        max_mux_size,
        resources,
        max_memories,
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
    operation_groups: dict[TypeName, ProcessCollection],
    memory_variables: ProcessCollection,
    direct_variables: ProcessCollection,
    strategy: Literal[
        "ilp_graph_color",
        "ilp_min_total_mux",
    ] = "ilp_graph_color",
    mux_targets: set[Literal["pe_to_mem", "mem_to_pe", "pe_to_pe"]] | None = None,
    max_mux_size: int | None = None,
    resources: dict[TypeName, int] | None = None,
    max_memories: int | None = None,
    memory_read_ports: int | None = None,
    memory_write_ports: int | None = None,
    memory_total_ports: int | None = None,
    memory_type: Literal["RAM", "register"] = "RAM",
    solver: LpSolver | None = None,
) -> tuple[dict[TypeName, list[ProcessCollection]], list[ProcessCollection]]:
    for group in operation_groups.values():
        for process in group:
            if process.execution_time > group.schedule_time:
                raise ValueError(
                    f"Operation {process} has execution time greater than the schedule time."
                )

    # For RAM memories, the lifetime of a variable must not exceed the schedule time
    if memory_type == "RAM":
        for process in memory_variables:
            if process.execution_time > memory_variables.schedule_time:
                raise ValueError(
                    f"Memory variable {process} has execution time greater than the schedule time."
                )

    # Generate the exclusion graphs along with a color upper bound for PEs
    pe_exclusion_graphs = []
    pe_colors = []
    pe_operations = []
    for group in operation_groups.values():
        pe_ex_graph = group.exclusion_graph_from_execution_time()
        pe_exclusion_graphs.append(pe_ex_graph)
        operation = next(iter(group)).operation
        pe_operations.append(operation)
        if not resources or operation.type_name() not in resources:
            coloring = nx.coloring.greedy_color(
                pe_ex_graph, strategy="saturation_largest_first"
            )
            pe_colors.append(list(range(len(set(coloring.values())))))
        else:
            pe_colors.append(list(range(resources[operation.type_name()])))

    # Generate the exclusion graphs along with a color upper bound for memories
    mem_exclusion_graph = memory_variables.exclusion_graph_from_ports(
        memory_read_ports, memory_write_ports, memory_total_ports
    )
    if max_memories is None:
        coloring = nx.coloring.greedy_color(
            mem_exclusion_graph, strategy="saturation_largest_first"
        )
        max_memories = len(set(coloring.values()))
    mem_colors = list(range(max_memories))

    if strategy == "ilp_graph_color":
        # Color the graphs concurrently using ILP to minimize the total amount of resources
        pe_x, mem_x = _ilp_coloring(
            pe_exclusion_graphs,
            mem_exclusion_graph,
            mem_colors,
            pe_colors,
            solver,
        )
    elif strategy == "ilp_min_total_mux":
        # Color the graphs concurrently using ILP to minimize the amount of multiplexers
        # given the amount of resources and memories
        pe_x, mem_x = _ilp_coloring_min_mux(
            pe_exclusion_graphs,
            mem_exclusion_graph,
            mem_colors,
            pe_colors,
            pe_operations,
            direct_variables,
            mux_targets,
            max_mux_size,
            solver,
        )
    else:
        raise ValueError(f"Invalid strategy '{strategy}'")

    # Assign memories based on coloring
    mem_assignment_dict = _get_assignment_from_coloring(
        mem_exclusion_graph, mem_x, mem_colors, memory_variables.schedule_time
    )
    mem_process_collections = [
        mem_assignment_dict[i] for i in sorted(mem_assignment_dict.keys())
    ]

    # Assign PEs based on coloring
    pe_process_collections = {}
    schedule_time = next(iter(operation_groups.values())).schedule_time
    for i, graph in enumerate(pe_exclusion_graphs):
        pe_assignment_dict = _get_assignment_from_coloring(
            graph, pe_x[i], pe_colors[i], schedule_time
        )
        pe_process_collections[list(operation_groups)[i]] = [
            pe_assignment_dict[j] for j in sorted(pe_assignment_dict.keys())
        ]

    return pe_process_collections, mem_process_collections


def _ilp_coloring(
    pe_exclusion_graphs: list[nx.Graph],
    mem_exclusion_graph: nx.Graph,
    mem_colors: list[int],
    pe_colors: list[list[int]],
    solver: LpSolver | None = None,
) -> tuple[dict, dict]:
    mem_graph_nodes = list(mem_exclusion_graph.nodes())
    mem_graph_edges = list(mem_exclusion_graph.edges())

    # Create decision variables for graph coloring
    # mem_x[node][color] - whether memory variable "node" is given "color"
    # mem_c[color] - whether "color" is used
    mem_x, mem_c = _create_memory_variables(mem_graph_nodes, mem_colors)
    # pe_x[i][node][color] - whether PE node "node" in exclusion graph "i" is given "color"
    # pe_c[i][color] - whether "color" is used in exclusion graph "i"
    pe_x, pe_c = _create_pe_variables(pe_exclusion_graphs, pe_colors)

    # Objective: minimize the total amount of colors used
    problem = LpProblem()
    problem += lpSum(mem_c[color] for color in mem_colors) + lpSum(
        pe_c[i][color]
        for i in range(len(pe_exclusion_graphs))
        for color in pe_colors[i]
    )

    # Constraints (for all exclusion graphs):
    #   (1) - nodes have exactly one color
    #   (2) - adjacent nodes cannot have the same color
    #   (3) - only permit assignments if color is used
    #   (4) - reduce solution space by assigning colors to the largest clique
    #   (5 & 6) - reduce solution space by ignoring the symmetry caused
    #       by cycling the graph colors
    for node in mem_graph_nodes:
        problem += lpSum(mem_x[node][i] for i in mem_colors) == 1
    for u, v in mem_graph_edges:
        for color in mem_colors:
            problem += mem_x[u][color] + mem_x[v][color] <= 1
    for node in mem_graph_nodes:
        for color in mem_colors:
            problem += mem_x[node][color] <= mem_c[color]
    max_clique = next(nx.find_cliques(mem_exclusion_graph))
    for color, node in enumerate(max_clique):
        problem += mem_x[node][color] == mem_c[color] == 1
    for color in mem_colors:
        problem += mem_c[color] <= lpSum(mem_x[node][color] for node in mem_graph_nodes)
    for color in mem_colors[:-1]:
        problem += mem_c[color + 1] <= mem_c[color]

    for i, pe_exclusion_graph in enumerate(pe_exclusion_graphs):
        nodes = list(pe_exclusion_graph.nodes())
        edges = list(pe_exclusion_graph.edges())
        for node in nodes:
            problem += lpSum(pe_x[i][node][color] for color in pe_colors[i]) == 1
        for u, v in edges:
            for color in pe_colors[i]:
                problem += pe_x[i][u][color] + pe_x[i][v][color] <= 1
        for node in nodes:
            for color in pe_colors[i]:
                problem += pe_x[i][node][color] <= pe_c[i][color]
        max_clique = next(nx.find_cliques(pe_exclusion_graph))
        for color, node in enumerate(max_clique):
            problem += pe_x[i][node][color] == pe_c[i][color] == 1
        for color in pe_colors[i]:
            problem += pe_c[i][color] <= lpSum(pe_x[i][node][color] for node in nodes)
        for color in pe_colors[i][:-1]:
            problem += pe_c[i][color + 1] <= pe_c[i][color]

    _solve_ilp_problem(problem, solver)

    return pe_x, mem_x


def _ilp_coloring_min_mux(
    pe_exclusion_graphs: list[nx.Graph],
    mem_exclusion_graph: nx.Graph,
    mem_colors: list[int],
    pe_colors: list[list[int]],
    pe_operations: list[Operation],
    direct: ProcessCollection,
    mux_targets: set[Literal["pe_to_mem", "mem_to_pe", "pe_to_pe"]],
    max_mux_size: int | None = None,
    solver: LpSolver | None = None,
) -> tuple[dict, dict]:
    mem_graph_nodes = list(mem_exclusion_graph.nodes())
    mem_graph_edges = list(mem_exclusion_graph.edges())

    pe_in_port_indices = [range(op.input_count) for op in pe_operations]
    pe_out_port_indices = [range(op.output_count) for op in pe_operations]

    # Create decision variables for graph coloring
    # mem_x[node][color] - whether memory variable "node" is given "color"
    # mem_c[color] - whether "color" is used
    mem_x, mem_c = _create_memory_variables(mem_graph_nodes, mem_colors)
    # pe_x[i][node][color] - whether PE node "node" in exclusion graph "i" is given "color"
    # pe_c[i][color] - whether "color" is used in exclusion graph "i"
    pe_x, pe_c = _create_pe_variables(pe_exclusion_graphs, pe_colors)

    # Objective: minimize the number of connections of the specified mux_targets
    problem = LpProblem()
    objective_terms = []
    # pe_to_mem_vars[graph_idx][pe_color][out_port][mem_color]
    #   - whether the out_port-th output port of pe_color-th PE in graph_idx-th graph
    #     writes to the mem_color-th memory
    if "pe_to_mem" in mux_targets:
        pe_to_mem_vars = _create_pe_to_mem_connection_variables(
            pe_exclusion_graphs, pe_colors, pe_out_port_indices, mem_colors
        )
        objective_terms.append(
            lpSum(
                [
                    pe_to_mem_vars[i][j][k][l]
                    for i in range(len(pe_exclusion_graphs))
                    for j in pe_colors[i]
                    for k in pe_out_port_indices[i]
                    for l in mem_colors
                ]
            )
        )
    # mem_to_pe_vars[mem_color][graph_idx][pe_color][in_port]
    #   - whether the mem_color-th memory
    #     writes to the in_port-th input port of pe_color-th PE in graph_idx-th PE exclusion graph
    if "mem_to_pe" in mux_targets:
        mem_to_pe_vars = _create_mem_to_pe_connection_variables(
            mem_colors, pe_exclusion_graphs, pe_colors, pe_in_port_indices
        )
        objective_terms.append(
            lpSum(
                [
                    mem_to_pe_vars[i][j][k][l]
                    for i in mem_colors
                    for j in range(len(pe_exclusion_graphs))
                    for k in pe_colors[j]
                    for l in pe_in_port_indices[j]
                ]
            )
        )
    # pe_to_pe_vars[src_graph_idx][src_pe_color][out_port][dst_graph_idx][dst_pe_color][in_port]
    #   - whether the out_port-th output port of src_pe_color-th PE in src_graph_idx-th PE exclusion graph
    #     writes to the in_port-th input port of dst_pe_color-th PE in dst_graph_idx-th PE exclusion graph
    if "pe_to_pe" in mux_targets:
        pe_to_pe_vars = _create_pe_to_pe_connection_variables(
            pe_exclusion_graphs, pe_colors, pe_out_port_indices, pe_in_port_indices
        )
        objective_terms.append(
            lpSum(
                [
                    pe_to_pe_vars[i][j][k][l][m][n]
                    for i in range(len(pe_exclusion_graphs))
                    for j in pe_colors[i]
                    for k in pe_out_port_indices[i]
                    for l in range(len(pe_exclusion_graphs))
                    for m in pe_colors[l]
                    for n in pe_in_port_indices[l]
                ]
            )
        )
    problem += lpSum(objective_terms)

    # Coloring constraints for the memory variable exclusion graph
    for node in mem_graph_nodes:
        problem += lpSum(mem_x[node][i] for i in mem_colors) == 1
    for u, v in mem_graph_edges:
        for color in mem_colors:
            problem += mem_x[u][color] + mem_x[v][color] <= 1
    for node in mem_graph_nodes:
        for color in mem_colors:
            problem += mem_x[node][color] <= mem_c[color]

    # Connect assignment to PE→Memory connections
    if "pe_to_mem" in mux_targets:
        log.debug("Constructing PE→Memory constraints")
        pe_to_mem_constraints = 0
        for i in range(len(pe_exclusion_graphs)):
            pe_nodes = list(pe_exclusion_graphs[i].nodes())
            for pe_node in pe_nodes:
                for k in pe_out_port_indices[i]:
                    mem_node = _get_mem_node(pe_node, k, mem_graph_nodes)
                    if mem_node is not None:
                        log.debug(
                            "  %s:out%d → memory:%s", pe_node.name, k, mem_node.name
                        )
                        for j in pe_colors[i]:
                            for l in mem_colors:
                                problem += pe_to_mem_vars[i][j][k][l] >= (
                                    pe_x[i][pe_node][j] + mem_x[mem_node][l] - 1
                                )
                                pe_to_mem_constraints += 1
        log.debug("Total PE→Memory constraints: %d", pe_to_mem_constraints)

    # Connect assignment to Memory→PE connections
    if "mem_to_pe" in mux_targets:
        log.debug("Constructing Memory→PE constraints")
        mem_to_pe_constraints = 0
        for mem_graph_node in mem_graph_nodes:
            for j in range(len(pe_exclusion_graphs)):
                pe_pairs = _get_pe_nodes(mem_graph_node, pe_exclusion_graphs[j])
                for pair in pe_pairs:
                    log.debug(
                        "  memory:%s → %s:in%d",
                        mem_graph_node.name,
                        pair[0].name,
                        pair[1],
                    )
                    for k in pe_colors[j]:
                        for i in mem_colors:
                            # Check the "reads" of the memory variable to skip if it is not read by the considered operation
                            br = False
                            for input_port in pair[0].operation.inputs:
                                if mem_graph_node.reads.get(input_port):
                                    br = True
                            if not br:
                                continue
                            if mem_graph_node.execution_time == 0:
                                continue
                            problem += mem_to_pe_vars[i][j][k][pair[1]] >= (
                                pe_x[j][pair[0]][k] + mem_x[mem_graph_node][i] - 1
                            )
                            mem_to_pe_constraints += 1
        log.debug("Total Memory→PE constraints: %d", mem_to_pe_constraints)

    # Connect assignment to PE→PE direct connections
    if "pe_to_pe" in mux_targets:
        pe_op_indices = {
            op.operation: i
            for i, graph in enumerate(pe_exclusion_graphs)
            for op in graph.nodes()
        }
        pe_processes = {
            op.operation: op for graph in pe_exclusion_graphs for op in graph.nodes()
        }

        # loop over all direct connections
        # generate constraints for each connection
        pe_to_pe_constraints = 0
        for dir_var in direct:
            dir_var = cast(MemoryVariable, dir_var)
            source_port = dir_var.write_port
            for dest_port, offset in dir_var.reads.items():
                if offset != 0:
                    continue
                if isinstance(source_port.operation, DontCare):
                    continue
                src_idx = pe_op_indices[source_port.operation]
                dst_idx = pe_op_indices[dest_port.operation]
                src_proc = pe_processes[source_port.operation]
                dest_proc = pe_processes[dest_port.operation]
                log.debug(
                    "  %s:out%d → %s:in%d",
                    source_port.operation.graph_id,
                    source_port.index,
                    dest_port.operation.graph_id,
                    dest_port.index,
                )
                for source_color in pe_colors[src_idx]:
                    for dest_color in pe_colors[dst_idx]:
                        # If the source op is assigned to source_color AND the destination op is assigned to dest_color,
                        # then there must be a PE→PE connection from source_color to dest_color
                        problem += (
                            pe_to_pe_vars[src_idx][source_color][source_port.index][
                                dst_idx
                            ][dest_color][dest_port.index]
                            >= pe_x[src_idx][src_proc][source_color]
                            + pe_x[dst_idx][dest_proc][dest_color]
                            - 1
                        )
                        pe_to_pe_constraints += 1
        log.debug("Total PE→PE constraints: %d", pe_to_pe_constraints)

    # Optional constraints to limit maximum mux fan-in for enabled targets
    if max_mux_size is not None:
        if "pe_to_mem" in mux_targets:
            for mem_color in mem_colors:
                problem += (
                    lpSum(
                        pe_to_mem_vars[graph_idx][pe_color][out_port][mem_color]
                        for graph_idx in range(len(pe_exclusion_graphs))
                        for pe_color in pe_colors[graph_idx]
                        for out_port in pe_out_port_indices[graph_idx]
                    )
                    <= max_mux_size
                )

        # A PE input mux can be fed by memory outputs and/or direct PE outputs.
        # Use one shared fan-in bound across both source types.
        if "mem_to_pe" in mux_targets or "pe_to_pe" in mux_targets:
            for dst_graph_idx in range(len(pe_exclusion_graphs)):
                for dst_pe_color in pe_colors[dst_graph_idx]:
                    for in_port in pe_in_port_indices[dst_graph_idx]:
                        mux_input_terms = []
                        if "mem_to_pe" in mux_targets:
                            mux_input_terms.extend(
                                mem_to_pe_vars[mem_color][dst_graph_idx][dst_pe_color][
                                    in_port
                                ]
                                for mem_color in mem_colors
                            )
                        if "pe_to_pe" in mux_targets:
                            mux_input_terms.extend(
                                pe_to_pe_vars[src_graph_idx][src_pe_color][out_port][
                                    dst_graph_idx
                                ][dst_pe_color][in_port]
                                for src_graph_idx in range(len(pe_exclusion_graphs))
                                for src_pe_color in pe_colors[src_graph_idx]
                                for out_port in pe_out_port_indices[src_graph_idx]
                            )
                        problem += lpSum(mux_input_terms) <= max_mux_size

    # Speed
    if mem_exclusion_graph.number_of_nodes() > 0:
        max_clique = next(nx.find_cliques(mem_exclusion_graph))
        for color, node in enumerate(max_clique):
            problem += mem_x[node][color] == mem_c[color] == 1
        for color in mem_colors:
            problem += mem_c[color] <= lpSum(
                mem_x[node][color] for node in mem_graph_nodes
            )
        for clique in nx.find_cliques(mem_exclusion_graph):
            for color in mem_colors:
                problem += lpSum(mem_x[node][color] for node in clique) <= 1
        for color in mem_colors[:-1]:
            problem += mem_c[color + 1] <= mem_c[color]

    for i, pe_exclusion_graph in enumerate(pe_exclusion_graphs):
        # Coloring constraints for PE exclusion graphs
        nodes = list(pe_exclusion_graph.nodes())
        edges = list(pe_exclusion_graph.edges())
        for node in nodes:
            problem += lpSum(pe_x[i][node][color] for color in pe_colors[i]) == 1
        # for u, v in edges:
        #    for color in pe_colors[i]:
        #        problem += pe_x[i][u][color] + pe_x[i][v][color] <= 1
        for node in nodes:
            for color in pe_colors[i]:
                problem += pe_x[i][node][color] <= pe_c[i][color]
        # Speed
        max_clique = next(nx.find_cliques(pe_exclusion_graph))
        for color, node in enumerate(max_clique):
            problem += pe_x[i][node][color] == pe_c[i][color] == 1
        for color in pe_colors[i]:
            problem += pe_c[i][color] <= lpSum(pe_x[i][node][color] for node in nodes)
        for clique in nx.find_cliques(pe_exclusion_graph):
            for color in pe_colors[i]:
                problem += lpSum(pe_x[i][node][color] for node in clique) <= 1
        for color in pe_colors[i][:-1]:
            problem += pe_c[i][color + 1] <= pe_c[i][color]

    _solve_ilp_problem(problem, solver)

    # Log active connections
    pe_type_names = [op.type_name() for op in pe_operations]
    if "pe_to_mem" in mux_targets:
        active_pe_to_mem = [
            (i, j, k, l)
            for i in range(len(pe_exclusion_graphs))
            for j in pe_colors[i]
            for k in pe_out_port_indices[i]
            for l in mem_colors
            if value(pe_to_mem_vars[i][j][k][l]) == 1
        ]
        log.info("PE→Memory connections: %d", len(active_pe_to_mem))
        for i, j, k, l in active_pe_to_mem:
            log.debug("  %s%d:out%d → memory%d", pe_type_names[i], j, k, l)
    if "mem_to_pe" in mux_targets:
        active_mem_to_pe = [
            (i, j, k, l)
            for i in mem_colors
            for j in range(len(pe_exclusion_graphs))
            for k in pe_colors[j]
            for l in pe_in_port_indices[j]
            if value(mem_to_pe_vars[i][j][k][l]) == 1
        ]
        log.info("Memory→PE connections: %d", len(active_mem_to_pe))
        for i, j, k, l in active_mem_to_pe:
            log.debug("  memory%d → %s%d:in%d", i, pe_type_names[j], k, l)
    if "pe_to_pe" in mux_targets:
        active_pe_to_pe = [
            (i, j, k, l, m, n)
            for i in range(len(pe_exclusion_graphs))
            for j in pe_colors[i]
            for k in pe_out_port_indices[i]
            for l in range(len(pe_exclusion_graphs))
            for m in pe_colors[l]
            for n in pe_in_port_indices[l]
            if value(pe_to_pe_vars[i][j][k][l][m][n]) == 1
        ]
        log.info("PE→PE connections: %d", len(active_pe_to_pe))
        for i, j, k, l, m, n in active_pe_to_pe:
            log.debug(
                "  %s%d:out%d → %s%d:in%d",
                pe_type_names[i],
                j,
                k,
                pe_type_names[l],
                m,
                n,
            )

    # Log pe_x assignments
    for i, pe_exclusion_graph in enumerate(pe_exclusion_graphs):
        for node in pe_exclusion_graph.nodes():
            for color in pe_colors[i]:
                log.debug(
                    "  pe_x[%d][%s][%d] = %s",
                    i,
                    node,
                    color,
                    value(pe_x[i][node][color]),
                )

    return pe_x, mem_x


def _get_assignment_from_coloring(
    exclusion_graph: nx.Graph,
    x: dict[Process, dict[int, LpVariable]],
    colors: list[int],
    schedule_time: int,
) -> dict[int, ProcessCollection]:
    node_colors = {}
    for node in exclusion_graph.nodes():
        for color in colors:
            if value(x[node][color]) == 1:
                node_colors[node] = color

    assignment = {}
    for process, color in node_colors.items():
        if color not in assignment:
            assignment[color] = ProcessCollection([], schedule_time)
        assignment[color].add_process(process)

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


def _create_memory_variables(
    mem_graph_nodes: list, mem_colors: list[int]
) -> tuple[dict, dict]:
    mem_x = LpVariable.dicts("mem_x", (mem_graph_nodes, mem_colors), cat=LpBinary)
    mem_c = LpVariable.dicts("mem_c", mem_colors, cat=LpBinary)
    return mem_x, mem_c


def _create_pe_to_mem_connection_variables(
    pe_exclusion_graphs: list[nx.Graph],
    pe_colors: list[list[int]],
    pe_out_port_indices: list[range],
    mem_colors: list[int],
) -> dict:
    pe_to_mem_vars = {}
    for graph_idx in range(len(pe_exclusion_graphs)):
        pe_to_mem_vars[graph_idx] = {}
        for pe_color in pe_colors[graph_idx]:
            pe_to_mem_vars[graph_idx][pe_color] = {}
            for out_port in pe_out_port_indices[graph_idx]:
                pe_to_mem_vars[graph_idx][pe_color][out_port] = {}
                for mem_color in mem_colors:
                    var_name = (
                        f"pe_to_mem_{graph_idx}_{pe_color}_{out_port}_{mem_color}"
                    )
                    pe_to_mem_vars[graph_idx][pe_color][out_port][mem_color] = (
                        LpVariable(var_name, cat=LpBinary)
                    )
    return pe_to_mem_vars


def _create_mem_to_pe_connection_variables(
    mem_colors: list[int],
    pe_exclusion_graphs: list[nx.Graph],
    pe_colors: list[list[int]],
    pe_in_port_indices: list[range],
) -> dict:
    mem_to_pe_vars = {}
    for mem_color in mem_colors:
        mem_to_pe_vars[mem_color] = {}
        for graph_idx in range(len(pe_exclusion_graphs)):
            mem_to_pe_vars[mem_color][graph_idx] = {}
            for pe_color in pe_colors[graph_idx]:
                mem_to_pe_vars[mem_color][graph_idx][pe_color] = {}
                for in_port in pe_in_port_indices[graph_idx]:
                    var_name = f"mem_to_pe_{mem_color}_{graph_idx}_{pe_color}_{in_port}"
                    mem_to_pe_vars[mem_color][graph_idx][pe_color][in_port] = (
                        LpVariable(var_name, cat=LpBinary)
                    )
    return mem_to_pe_vars


def _create_pe_to_pe_connection_variables(
    pe_exclusion_graphs: list[nx.Graph],
    pe_colors: list[list[int]],
    pe_out_port_indices: list[range],
    pe_in_port_indices: list[range],
) -> dict:
    pe_to_pe_vars = {}
    for src_graph_idx in range(len(pe_exclusion_graphs)):
        pe_to_pe_vars[src_graph_idx] = {}
        for src_pe_color in pe_colors[src_graph_idx]:
            pe_to_pe_vars[src_graph_idx][src_pe_color] = {}
            for out_port in pe_out_port_indices[src_graph_idx]:
                pe_to_pe_vars[src_graph_idx][src_pe_color][out_port] = {}
                for dst_graph_idx in range(len(pe_exclusion_graphs)):
                    pe_to_pe_vars[src_graph_idx][src_pe_color][out_port][
                        dst_graph_idx
                    ] = {}
                    for dst_pe_color in pe_colors[dst_graph_idx]:
                        pe_to_pe_vars[src_graph_idx][src_pe_color][out_port][
                            dst_graph_idx
                        ][dst_pe_color] = {}
                        for in_port in pe_in_port_indices[dst_graph_idx]:
                            var_name = f"pe_to_pe_{src_graph_idx}_{src_pe_color}_{out_port}_{dst_graph_idx}_{dst_pe_color}_{in_port}"
                            pe_to_pe_vars[src_graph_idx][src_pe_color][out_port][
                                dst_graph_idx
                            ][dst_pe_color][in_port] = LpVariable(
                                var_name, cat=LpBinary
                            )
    return pe_to_pe_vars


def _create_pe_variables(
    pe_exclusion_graphs: list[nx.Graph], pe_colors: list[list[int]]
) -> tuple[dict, dict]:
    pe_x = {}
    for i, pe_exclusion_graph in enumerate(pe_exclusion_graphs):
        pe_x[i] = {}
        for node in pe_exclusion_graph.nodes():
            pe_x[i][node] = {}
            for color in pe_colors[i]:
                pe_x[i][node][color] = LpVariable(
                    f"pe_x_{i}_{node}_{color}", cat=LpBinary
                )

    pe_c = {}
    for i in range(len(pe_exclusion_graphs)):
        pe_c[i] = {}
        for color in pe_colors[i]:
            pe_c[i][color] = LpVariable(f"pe_c_{i}_{color}", cat=LpBinary)

    return pe_x, pe_c


def _solve_ilp_problem(
    problem: LpProblem,
    solver: LpSolver | None,
) -> None:
    # Default to a CBC solver if no solver is provided
    # Suppress ILP solver output if logging not set to DEBUG
    if solver is None:
        msg = 1 if log.isEnabledFor(b_asic.logger.logging.DEBUG) else 0
        solver = PULP_CBC_CMD(msg=msg)

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
        log.debug("Failed to recover interrupted ILP solution: %s", exc)
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
    recovery_name = os.path.join(recovery_dir, f"{problem.name}-{uuid4().hex}")

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
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
    recovery_dir = cast(str | None, recovery_state.get("recovery_dir"))
    if recovery_dir is not None:
        shutil.rmtree(recovery_dir, ignore_errors=True)
    try:
        os.remove("gurobi.log")
    except FileNotFoundError:
        pass


def _recover_cmd_solution_file(
    problem: LpProblem,
    solver: LpSolver,
    solution_path: str,
) -> bool:
    read_solution = getattr(solver, "readsol", None)
    if not callable(read_solution) or not os.path.exists(solution_path):
        return False

    try:
        solution = read_solution(solution_path)
    except Exception as exc:
        log.debug(
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
