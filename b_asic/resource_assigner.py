from typing import Literal, cast

import networkx as nx
from pulp import (
    GUROBI,
    PULP_CBC_CMD,
    LpBinary,
    LpProblem,
    LpStatusOptimal,
    LpVariable,
    lpSum,
    value,
)

from b_asic.architecture import Memory, ProcessingElement
from b_asic.operation import Operation
from b_asic.port import OutputPort
from b_asic.process import Process
from b_asic.resources import ProcessCollection
from b_asic.types import TypeName


def assign_processing_elements_and_memories(
    operations: ProcessCollection,
    memory_variables: ProcessCollection,
    strategy: Literal[
        "ilp_graph_color",
        "ilp_min_total_mux",
    ] = "ilp_graph_color",
    resources: dict[TypeName, int] | None = None,
    max_memories: int | None = None,
    memory_read_ports: int | None = None,
    memory_write_ports: int | None = None,
    memory_total_ports: int | None = None,
    solver: PULP_CBC_CMD | GUROBI | None = None,
) -> tuple[list[ProcessingElement], list[Memory]]:
    """
    Assign PEs and memories jointly using ILP.

    Parameters
    ----------
    operations : ProcessCollection
        All operations from a schedule.

    memory_variables : ProcessCollection
        All memory variables from a schedule.

    resources : dict[TypeName, int] | None, optional
        The maximum amount of resources to assign to, used to limit the solution
        space for performance gains.

    max_memories : int | None, optional
        The maximum amount of memories to assign to, used to limit the solution
        space for performance gains.

    memory_read_ports : int | None, optional
        The number of read ports used when splitting process collection based on
        memory variable access.

    memory_write_ports : int | None, optional
        The number of write ports used when splitting process collection based on
        memory variable access.

    memory_total_ports : int | None, optional
        The total number of ports used when splitting process collection based on
        memory variable access.

    solver : PuLP MIP solver object, optional
        Valid options are:

        * PULP_CBC_CMD() - preinstalled
        * GUROBI() - license required, but likely faster

    Returns
    -------
    A tuple containing one list of assigned PEs and one list of assigned memories.
    """
    operation_groups = operations.split_on_type_name()
    direct, mem_vars = memory_variables.split_on_length()

    operations_set, memory_variable_set = _split_operations_and_variables(
        operation_groups,
        mem_vars,
        direct,
        strategy,
        resources,
        max_memories,
        memory_read_ports,
        memory_write_ports,
        memory_total_ports,
        solver,
    )

    processing_elements = [
        ProcessingElement(op_set, f"{type_name}{i}")
        for type_name, pe_operation_sets in operations_set.items()
        for i, op_set in enumerate(pe_operation_sets)
    ]

    memories = [
        Memory(mem, memory_type="RAM", entity_name=f"memory{i}", assign=True)
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
    resources: dict[TypeName, int] | None = None,
    max_memories: int | None = None,
    memory_read_ports: int | None = None,
    memory_write_ports: int | None = None,
    memory_total_ports: int | None = None,
    solver: PULP_CBC_CMD | GUROBI | None = None,
) -> tuple[list[ProcessCollection], list[dict[TypeName, ProcessCollection]]]:
    for group in operation_groups.values():
        for process in group:
            if process.execution_time > group.schedule_time:
                raise ValueError(
                    f"Operation {process} has execution time greater than the schedule time."
                )

    for process in memory_variables:
        if process.execution_time > memory_variables.schedule_time:
            raise ValueError(
                f"Memory variable {process} has execution time greater than the schedule time."
            )

    # generate the exclusion graphs along with a color upper bound for PEs
    pe_exclusion_graphs = []
    pe_colors = []
    pe_operations = []
    for group in operation_groups.values():
        pe_ex_graph = group.exclusion_graph_from_execution_time()
        pe_exclusion_graphs.append(pe_ex_graph)
        operation = next(iter(group)).operation
        pe_operations.append(operation)
        if strategy == "ilp_graph_color":
            if not resources or operation.type_name() not in resources:
                coloring = nx.coloring.greedy_color(
                    pe_ex_graph, strategy="saturation_largest_first"
                )
                pe_colors.append(range(len(set(coloring.values()))))
            else:
                pe_colors.append(range(resources[operation.type_name()]))
        else:
            pe_colors.append(list(range(resources[operation.type_name()])))

    # generate the exclusion graphs along with a color upper bound for memories
    mem_exclusion_graph = memory_variables.exclusion_graph_from_ports(
        memory_read_ports, memory_write_ports, memory_total_ports
    )
    if max_memories is None:
        coloring = nx.coloring.greedy_color(
            mem_exclusion_graph, strategy="saturation_largest_first"
        )
        max_memories = len(set(coloring.values()))
    mem_colors = range(max_memories)

    if strategy == "ilp_graph_color":
        # color the graphs concurrently using ILP to minimize the total amount of resources
        pe_x, mem_x = _ilp_coloring(
            pe_exclusion_graphs, mem_exclusion_graph, mem_colors, pe_colors, solver
        )
    elif strategy == "ilp_min_total_mux":
        # color the graphs concurrently using ILP to minimize the amount of multiplexers
        # given the amount of resources and memories
        pe_x, mem_x = _ilp_coloring_min_mux(
            pe_exclusion_graphs,
            mem_exclusion_graph,
            mem_colors,
            pe_colors,
            pe_operations,
            direct_variables,
            solver,
        )
    else:
        raise ValueError(f"Invalid strategy '{strategy}'")

    # assign memories based on coloring
    mem_process_collections = _get_assignment_from_coloring(
        mem_exclusion_graph, mem_x, mem_colors, memory_variables.schedule_time
    )

    # assign PEs based on coloring
    pe_process_collections = {}
    schedule_time = next(iter(operation_groups.values())).schedule_time
    for i in range(len(pe_exclusion_graphs)):
        pe_assignment = _get_assignment_from_coloring(
            pe_exclusion_graphs[i], pe_x[i], pe_colors[i], schedule_time
        )
        pe_process_collections[list(operation_groups)[i]] = pe_assignment

    return pe_process_collections, mem_process_collections


def _ilp_coloring(
    pe_exclusion_graphs: list[nx.Graph],
    mem_exclusion_graph: nx.Graph,
    mem_colors: list[int],
    pe_colors: list[list[int]],
    solver: PULP_CBC_CMD | GUROBI | None = None,
) -> tuple[dict, dict]:
    mem_graph_nodes = list(mem_exclusion_graph.nodes())
    mem_graph_edges = list(mem_exclusion_graph.edges())

    # specify the ILP problem of minimizing the amount of resources

    # binary variables:
    #   mem_x[node, color] - whether node in memory exclusion graph is colored
    #       in a certain color
    #   mem_c[color] - whether color is used in the memory exclusion graph
    #   pe_x[i, node, color] - whether node in the i:th PE exclusion graph is
    #       colored in a certain color
    #   pe_c[i, color] whether color is used in the i:th PE exclusion graph

    mem_x = LpVariable.dicts("mem_x", (mem_graph_nodes, mem_colors), cat=LpBinary)
    mem_c = LpVariable.dicts("mem_c", mem_colors, cat=LpBinary)

    pe_x = {}
    for i, pe_exclusion_graph in enumerate(pe_exclusion_graphs):
        pe_x[i] = {}
        for node in list(pe_exclusion_graph.nodes()):
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

    problem = LpProblem()
    problem += lpSum(mem_c[color] for color in mem_colors) + lpSum(
        pe_c[i][color]
        for i in range(len(pe_exclusion_graphs))
        for color in pe_colors[i]
    )

    # constraints (for all exclusion graphs):
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
        max_clique = next(nx.find_cliques(pe_exclusion_graphs[i]))
        for color, node in enumerate(max_clique):
            problem += pe_x[i][node][color] == pe_c[i][color] == 1
        for color in pe_colors[i]:
            problem += pe_c[i][color] <= lpSum(pe_x[i][node][color] for node in nodes)
        for color in pe_colors[i][:-1]:
            problem += pe_c[i][color + 1] <= pe_c[i][color]

    if solver is None:
        solver = PULP_CBC_CMD()

    status = problem.solve(solver)

    if status != LpStatusOptimal:
        raise ValueError(
            "Optimal solution could not be found via ILP, use another method."
        )

    return pe_x, mem_x


def _ilp_coloring_min_mux(
    pe_exclusion_graphs: list[nx.Graph],
    mem_exclusion_graph: nx.Graph,
    mem_colors: list[int],
    pe_colors: list[list[int]],
    pe_operations: list[Operation],
    direct: ProcessCollection,
    solver: PULP_CBC_CMD | GUROBI | None = None,
) -> tuple[dict, dict]:
    mem_graph_nodes = list(mem_exclusion_graph.nodes())
    mem_graph_edges = list(mem_exclusion_graph.edges())

    pe_ops = [
        op
        for i in range(len(pe_exclusion_graphs))
        for op in list(pe_exclusion_graphs[i].nodes())
    ]

    pe_in_port_indices = [list(range(op.input_count)) for op in pe_operations]
    pe_out_port_indices = [list(range(op.output_count)) for op in pe_operations]

    # specify the ILP problem of minimizing the amount of resources

    # binary variables:
    #   mem_x[node, color] - whether node in memory exclusion graph is colored
    #       in a certain color
    #   mem_c[color] - whether color is used in the memory exclusion graph
    #   pe_x[i, node, color] - whether node in the i:th PE exclusion graph is
    #       colored in a certain color
    #   pe_c[i, color] whether color is used in the i:th PE exclusion graph
    #   a[i, j, k, l] - whether the k:th output port of the j:th PE in the i:th graph
    #       writes to the the l:th memory
    #   b[i, j, k, l] - whether the i:th memory
    #       writes to the l:th input port of the k:th PE in the j:th PE exclusion graph
    #   c[i, j, k, l, m, n] - whether the k:th output port of the j:th PE in the i:th PE exclusion graph
    #       writes to the n:th input port of the m:th PE in the l:th PE exclusion graph

    mem_x = LpVariable.dicts("mem_x", (mem_graph_nodes, mem_colors), cat=LpBinary)
    mem_c = LpVariable.dicts("mem_c", mem_colors, cat=LpBinary)

    pe_x = {}
    for i, pe_exclusion_graph in enumerate(pe_exclusion_graphs):
        pe_x[i] = {}
        for node in list(pe_exclusion_graph.nodes()):
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

    a = {}
    for i in range(len(pe_exclusion_graphs)):
        a[i] = {}
        for j in pe_colors[i]:
            a[i][j] = {}
            for k in pe_out_port_indices[i]:
                a[i][j][k] = {}
                for l in mem_colors:
                    a[i][j][k][l] = LpVariable(f"a_{i}_{j}_{k}_{l}", cat=LpBinary)

    b = {}
    for i in mem_colors:
        b[i] = {}
        for j in range(len(pe_exclusion_graphs)):
            b[i][j] = {}
            for k in pe_colors[j]:
                b[i][j][k] = {}
                for l in pe_in_port_indices[j]:
                    b[i][j][k][l] = LpVariable(f"b_{i}_{j}_{k}_{l}", cat=LpBinary)

    c = {}
    for i in range(len(pe_exclusion_graphs)):
        c[i] = {}
        for j in pe_colors[i]:
            c[i][j] = {}
            for k in pe_out_port_indices[i]:
                c[i][j][k] = {}
                for l in range(len(pe_exclusion_graphs)):
                    c[i][j][k][l] = {}
                    for m in pe_colors[l]:
                        c[i][j][k][l][m] = {}
                        for n in pe_in_port_indices[l]:
                            c[i][j][k][l][m][n] = LpVariable(
                                f"c_{i}_{j}_{k}_{l}_{m}_{n}", cat=LpBinary
                            )

    problem = LpProblem()
    problem += (
        lpSum(
            [
                a[i][j][k][l]
                for i in range(len(pe_exclusion_graphs))
                for j in pe_colors[i]
                for k in pe_out_port_indices[i]
                for l in mem_colors
            ]
        )
        + lpSum(
            [
                b[i][j][k][l]
                for i in mem_colors
                for j in range(len(pe_exclusion_graphs))
                for k in pe_colors[j]
                for l in pe_in_port_indices[j]
            ]
        )
        + lpSum(
            [
                c[i][j][k][l][m][n]
                for i in range(len(pe_exclusion_graphs))
                for j in pe_colors[i]
                for k in pe_out_port_indices[i]
                for l in range(len(pe_exclusion_graphs))
                for m in pe_colors[l]
                for n in pe_in_port_indices[l]
            ]
        )
    )

    # coloring constraints for the memory variable exclusion graph
    for node in mem_graph_nodes:
        problem += lpSum(mem_x[node][i] for i in mem_colors) == 1
    for u, v in mem_graph_edges:
        for color in mem_colors:
            problem += mem_x[u][color] + mem_x[v][color] <= 1
    for node in mem_graph_nodes:
        for color in mem_colors:
            problem += mem_x[node][color] <= mem_c[color]

    # connect assignment to "a"
    for i in range(len(pe_exclusion_graphs)):
        pe_nodes = list(pe_exclusion_graphs[i].nodes())
        for pe_node in pe_nodes:
            for k in pe_out_port_indices[i]:
                mem_node = _get_mem_node(pe_node, k, mem_exclusion_graph)
                if mem_node is not None:
                    for j in pe_colors[i]:
                        for l in mem_colors:
                            problem += a[i][j][k][l] >= (
                                pe_x[i][pe_node][j] + mem_x[mem_node][l] - 1
                            )

    # connect assignment to "b"
    for mem_node in mem_graph_nodes:
        for j in range(len(pe_exclusion_graphs)):
            pe_pairs = _get_pe_nodes(mem_node, pe_exclusion_graphs[j])
            for pair in pe_pairs:
                for k in pe_colors[j]:
                    for i in mem_colors:
                        problem += b[i][j][k][pair[1]] >= (
                            pe_x[j][pair[0]][k] + mem_x[mem_node][i] - 1
                        )

    # connect assignment to "c"
    for i in range(len(pe_exclusion_graphs)):
        pe_nodes_1 = list(pe_exclusion_graphs[i].nodes())
        for j in range(len(pe_exclusion_graphs)):
            for pe_node_1 in pe_nodes_1:
                for l in pe_in_port_indices[j]:
                    for k in pe_out_port_indices[i]:
                        pe_nodes_2 = _get_pe_to_pe_connection(
                            pe_node_1, direct, pe_ops, l, k
                        )
                        for pe_node_2 in pe_nodes_2:
                            for pe_color_1 in pe_colors[i]:
                                if pe_node_2 in pe_exclusion_graphs[j].nodes():
                                    for pe_color_2 in pe_colors[j]:
                                        problem += c[i][pe_color_1][k][j][pe_color_2][
                                            l
                                        ] >= (
                                            pe_x[i][pe_node_1][pe_color_1]
                                            + pe_x[j][pe_node_2][pe_color_2]
                                            - 1
                                        )

    # speed
    max_clique = next(nx.find_cliques(mem_exclusion_graph))
    for color, node in enumerate(max_clique):
        problem += mem_x[node][color] == mem_c[color] == 1
    for color in mem_colors:
        problem += mem_c[color] <= lpSum(mem_x[node][color] for node in mem_graph_nodes)
    for color in mem_colors[:-1]:
        problem += mem_c[color + 1] <= mem_c[color]

    for i, pe_exclusion_graph in enumerate(pe_exclusion_graphs):
        # coloring constraints for PE exclusion graphs
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
        # speed
        max_clique = next(nx.find_cliques(pe_exclusion_graphs[i]))
        for color, node in enumerate(max_clique):
            problem += pe_x[i][node][color] == pe_c[i][color] == 1
        for color in pe_colors[i]:
            problem += pe_c[i][color] <= lpSum(pe_x[i][node][color] for node in nodes)
        for color in pe_colors[i][:-1]:
            problem += pe_c[i][color + 1] <= pe_c[i][color]

    if solver is None:
        solver = PULP_CBC_CMD()

    status = problem.solve(solver)

    if status != LpStatusOptimal:
        raise ValueError(
            "Optimal solution could not be found via ILP, use another method."
        )
    return pe_x, mem_x


def _get_assignment_from_coloring(
    exclusion_graph: nx.Graph,
    x: dict[Process, dict[int, LpVariable]],
    colors: list[int],
    schedule_time: int,
) -> dict[int, ProcessCollection]:
    node_colors = {}
    for node in list(exclusion_graph.nodes()):
        for color in colors:
            if value(x[node][color]) == 1:
                node_colors[node] = color
    sorted_unique_values = sorted(set(node_colors.values()))
    coloring_mapping = {val: i for i, val in enumerate(sorted_unique_values)}
    coloring = {key: coloring_mapping[node_colors[key]] for key in node_colors}

    assignment = {}
    for process, cell in coloring.items():
        if cell not in assignment:
            assignment[cell] = ProcessCollection([], schedule_time)
        assignment[cell].add_process(process)

    return list(assignment.values())


def _get_mem_node(
    pe_node: Process, pe_port_index: int, mem_nodes: list[Process]
) -> tuple[Process, int] | tuple[None, None]:
    for mem_process in mem_nodes:
        split_name = iter(mem_process.name.split("."))
        var_name = next(split_name)
        port_index = int(next(split_name))
        if var_name == pe_node.name and pe_port_index == port_index:
            return mem_process


def _get_pe_nodes(
    mem_node: Process, pe_nodes: list[Process]
) -> tuple[Process, int] | tuple[None, None]:
    nodes = []
    split_var = iter(mem_node.name.split("."))
    var_name = next(split_var)
    port_index = int(next(split_var))
    for pe_process in pe_nodes:
        for input_port in pe_process.operation.inputs:
            input_op = input_port.connected_source.operation
            if (
                input_op.graph_id == var_name
                and input_port.connected_source.index == port_index
            ):
                nodes.append((pe_process, input_port.index))
    return nodes


def _get_pe_to_pe_connection(
    pe_node: Process,
    direct_variables: ProcessCollection,
    other_pe_nodes: list[Process],
    pe_in_port_index: int,
    pe_out_port_index: int,
) -> tuple[Process, int, int] | tuple[None, None, None]:
    nodes = []
    for direct_var in direct_variables:
        split_var = iter(direct_var.name.split("."))
        var_name = next(split_var)
        port_index = int(next(split_var))

        if var_name == pe_node.name and pe_out_port_index == port_index:
            for output_port in pe_node.operation.outputs:
                port = cast(OutputPort, output_port)
                if port.index == port_index:
                    for output_signal in port.signals:
                        if output_signal.destination.index == pe_in_port_index:
                            op = output_signal.destination_operation

                            for other_pe_node in other_pe_nodes:
                                if other_pe_node.name == op.graph_id:
                                    nodes.append(other_pe_node)
    return nodes
