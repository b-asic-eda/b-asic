import matplotlib.pyplot as plt
import networkx as nx
import pytest

from b_asic.process import PlainMemoryVariable
from b_asic.resources import ProcessCollection, draw_exclusion_graph_coloring


class TestProcessCollectionPlainMemoryVariable:
    @pytest.mark.mpl_image_compare(style='mpl20')
    def test_draw_process_collection(self, simple_collection):
        fig, ax = plt.subplots()
        simple_collection.draw_lifetime_chart(ax=ax)
        return fig

    def test_draw_proces_collection(self, simple_collection):
        _, ax = plt.subplots(1, 2)
        simple_collection.draw_lifetime_chart(schedule_time=8, ax=ax[0])
        exclusion_graph = (
            simple_collection.create_exclusion_graph_from_overlap()
        )
        color_dict = nx.coloring.greedy_color(exclusion_graph)
        draw_exclusion_graph_coloring(exclusion_graph, color_dict, ax=ax[1])

    def test_split_memory_variable(self, simple_collection):
        collection_split = simple_collection.split(
            read_ports=1, write_ports=1, total_ports=2
        )
        assert len(collection_split) == 3
