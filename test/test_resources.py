import matplotlib.pyplot as plt
import networkx as nx
import pytest

from b_asic.research.interleaver import (
    generate_matrix_transposer,
    generate_random_interleaver,
)
from b_asic.resources import draw_exclusion_graph_coloring


class TestProcessCollectionPlainMemoryVariable:
    @pytest.mark.mpl_image_compare(style='mpl20')
    def test_draw_process_collection(self, simple_collection):
        fig, ax = plt.subplots()
        simple_collection.draw_lifetime_chart(ax=ax)
        return fig

    def test_draw_proces_collection(self, simple_collection):
        _, ax = plt.subplots(1, 2)
        simple_collection.draw_lifetime_chart(ax=ax[0])
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

    @pytest.mark.mpl_image_compare(style='mpl20')
    def test_draw_matrix_transposer_4(self):
        fig, ax = plt.subplots()
        generate_matrix_transposer(4).draw_lifetime_chart(ax=ax)
        return fig

    def test_generate_random_interleaver(self):
        return
        for _ in range(10):
            for size in range(5, 20, 5):
                assert (
                    len(
                        generate_random_interleaver(size).split(
                            read_ports=1, write_ports=1
                        )
                    )
                    == 1
                )
                assert (
                    len(generate_random_interleaver(size).split(total_ports=1))
                    == 2
                )
