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
from b_asic.process import Process
from b_asic.resources import ProcessCollection
from b_asic.types import TypeName


def assign_processing_elements_and_memories(
    operations: ProcessCollection,
    memory_variables: ProcessCollection,
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
        Only used if strategy is an ILP method.
        Valid options are

        * PULP_CBC_CMD() - preinstalled
        * GUROBI() - license required, but likely faster

    Returns
    -------
    A tuple containing one list of assigned PEs and one list of assigned memories.
    """
    operation_groups = operations.split_on_type_name()

    operations_set, memory_variable_set = _split_operations_and_variables(
        operation_groups,
        memory_variables,
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

    return processing_elements, memories


def _split_operations_and_variables(
    operation_groups: dict[TypeName, ProcessCollection],
    memory_variables: ProcessCollection,
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
    for group in operation_groups.values():
        pe_ex_graph = group.create_exclusion_graph_from_execution_time()
        pe_exclusion_graphs.append(pe_ex_graph)
        pe_op_type = next(iter(group)).operation.type_name()
        if pe_op_type in resources:
            coloring = nx.coloring.greedy_color(
                pe_ex_graph, strategy="saturation_largest_first"
            )
            pe_colors.append(range(len(set(coloring.values()))))
        else:
            pe_colors.append(range(resources[pe_op_type]))

    # generate the exclusion graphs along with a color upper bound for memories
    mem_exclusion_graph = memory_variables.create_exclusion_graph_from_ports(
        memory_read_ports, memory_write_ports, memory_total_ports
    )
    if max_memories is None:
        coloring = nx.coloring.greedy_color(
            mem_exclusion_graph, strategy="saturation_largest_first"
        )
        max_memories = len(set(coloring.values()))
    mem_colors = range(max_memories)

    # color the graphs concurrently using ILP to minimize the total amount of resources
    pe_x, mem_x = _ilp_coloring(
        pe_exclusion_graphs, mem_exclusion_graph, mem_colors, pe_colors, solver
    )

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
    pe_exclusion_graphs,
    mem_exclusion_graph,
    mem_colors,
    pe_colors,
    solver,
):
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

    mem_x = LpVariable.dicts("x", (mem_graph_nodes, mem_colors), cat=LpBinary)
    mem_c = LpVariable.dicts("c", mem_colors, cat=LpBinary)

    pe_x = {}
    for i, pe_exclusion_graph in enumerate(pe_exclusion_graphs):
        pe_x[i] = {}
        for node in list(pe_exclusion_graph.nodes()):
            pe_x[i][node] = {}
            for color in pe_colors[i]:
                pe_x[i][node][color] = LpVariable(f"x_{i}_{node}_{color}", cat=LpBinary)

    pe_c = {}
    for i in range(len(pe_exclusion_graphs)):
        pe_c[i] = {}
        for color in pe_colors[i]:
            pe_c[i][color] = LpVariable(f"x_{i}_{color}", cat=LpBinary)

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
