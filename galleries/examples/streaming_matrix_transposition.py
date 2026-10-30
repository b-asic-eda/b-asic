"""
==============================
Streaming Matrix Transposition
==============================

In some systems, circuits for data-shuffling of streaming data are needed.
Although not computational algorithms,
data-shuffling circuits can be designed using B-ASIC.

Here, designs for streaming matrix transposition are derived.
First lifetime diagrams for memory variables are generated and shown.
Afterwards, the process exclusion graph is shown, and memory-cell sharing
for a 4x4 streaming matrix transposer is illustrated.
Finally, designs for a few different matrix sizes are generated using both
memory-based (RAM) and register-based storage.
"""

from pathlib import Path

import matplotlib.pyplot as plt

from b_asic.research.interleaver import generate_matrix_transposer
from b_asic.resources import ProcessCollection, draw_exclusion_graph_coloring


def plot_lifetimes(groups, schedule_time, colors):
    """Plot one row per group, keeping each element's colour consistent."""
    _, axes = plt.subplots(layout="constrained")
    for row, group in enumerate(groups):
        for element in group:
            ProcessCollection([element], schedule_time, cyclic=True).plot(
                ax=axes,
                row=row,
                bar_color=colors[element.name],
            )
    return axes


SIZE = 4
WL = 16 # Use fixed-point with 1 integer bit and 15 fractional bits throughout
output_dir = Path("generated")
output_dir.mkdir(parents=True, exist_ok=True)

# %%
# Variable lifetimes
# ---------------
# Samples arrive sequentially and leave in transposed order. Bars show how long
# each value must remain in storage. Labels identify arrival order, and colours
# stay consistent across all three diagrams.

example_collection = generate_matrix_transposer(SIZE)
elements = sorted(example_collection, key=lambda element: element.start_time)
element_cmap = plt.get_cmap("turbo", len(elements))
element_colors = {
    element.name: element_cmap(element_index)
    for element_index, element in enumerate(elements)
}

ax_lifetimes = plot_lifetimes(
    [[element] for element in elements],
    example_collection.schedule_time,
    element_colors,
)

# %%
# Variable exclusion graph
# -----------------------
# Nodes represent values. An edge means their lifetimes overlap, so the pair
# cannot share a memory cell.

exclusion_graph = example_collection.exclusion_graph_from_execution_time()
_, ax_exclusion = plt.subplots(layout="constrained")
draw_exclusion_graph_coloring(
    exclusion_graph,
    color_dict={element: index for index, element in enumerate(elements)},
    color_list=[element_colors[element.name][:3] for element in elements],
    ax=ax_exclusion,
    labels={element: element.name for element in elements},
)

# %%
# Sharing memory cells
# --------------------
# Graph colouring groups non-overlapping values into collections, one per memory
# cell. Each row now represents a physical cell.

example_assignment = example_collection.split_on_execution_time(
    strategy="greedy_graph_color"
)
ax_assignment = plot_lifetimes(
    example_assignment, example_collection.schedule_time, element_colors
)

# %%
# Generate memory-based VHDL
# --------------------------
# Generate RAM-based designs for the sizes below.

SIZES = ((2, 2), (3, 3), (4, 4), (5, 5), (7, 7), (4, 8))
for rows, cols in SIZES:
    collection = generate_matrix_transposer(rows, cols)
    assignment = collection.split_on_execution_time(strategy="greedy_graph_color")
    entity_name = f"streaming_matrix_transposition_memory_{rows}x{cols}"
    collection.generate_memory_based_storage_vhdl(
        filename=str(output_dir / f"{entity_name}.vhdl"),
        entity_name=entity_name,
        assignment=assignment,
        word_length=WL,
    )

# %%
# Generate register-based VHDL
# ----------------------------
# Same thing but using register-based storage.

for rows, cols in SIZES:
    collection = generate_matrix_transposer(rows, cols)
    entity_name = f"streaming_matrix_transposition_register_{rows}x{cols}"
    collection.generate_register_based_storage_vhdl(
        filename=str(output_dir / f"{entity_name}.vhdl"),
        entity_name=entity_name,
        word_length=WL,
    )
