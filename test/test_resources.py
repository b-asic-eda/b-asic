import pickle

import matplotlib.pyplot as plt
import networkx as nx
import pytest

from b_asic.process import Process
from b_asic.research.interleaver import (
    generate_matrix_transposer,
    generate_random_interleaver,
)
from b_asic.resources import ProcessCollection, draw_exclusion_graph_coloring


class TestProcessCollectionPlainMemoryVariable:
    @pytest.mark.mpl_image_compare(style='mpl20')
    def test_draw_process_collection(self, simple_collection):
        fig, ax = plt.subplots()
        simple_collection.draw_lifetime_chart(ax=ax, show_markers=False)
        return fig

    @pytest.mark.mpl_image_compare(style='mpl20')
    def test_draw_matrix_transposer_4(self):
        fig, ax = plt.subplots()
        generate_matrix_transposer(4).draw_lifetime_chart(ax=ax)
        return fig

    def test_split_memory_variable(self, simple_collection: ProcessCollection):
        collection_split = simple_collection.split_ports(
            heuristic="graph_color", read_ports=1, write_ports=1, total_ports=2
        )
        assert len(collection_split) == 3

    # Issue: #175
    def test_interleaver_issue175(self):
        with open('test/fixtures/interleaver-two-port-issue175.p', 'rb') as f:
            interleaver_collection: ProcessCollection = pickle.load(f)
            assert len(interleaver_collection.split_ports(total_ports=1)) == 2

    def test_generate_random_interleaver(self):
        for _ in range(10):
            for size in range(5, 20, 5):
                collection = generate_random_interleaver(size)
                assert len(collection.split_ports(read_ports=1, write_ports=1)) == 1
                if any(var.execution_time for var in collection.collection):
                    assert len(collection.split_ports(total_ports=1)) == 2
