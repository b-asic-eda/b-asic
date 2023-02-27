import pickle

import matplotlib.pyplot as plt
import pytest

from b_asic.research.interleaver import (
    generate_matrix_transposer,
    generate_random_interleaver,
)
from b_asic.resources import ProcessCollection


class TestProcessCollectionPlainMemoryVariable:
    @pytest.mark.mpl_image_compare(style='mpl20')
    def test_draw_process_collection(self, simple_collection):
        fig, ax = plt.subplots()
        simple_collection.plot(ax=ax, show_markers=False)
        return fig

    @pytest.mark.mpl_image_compare(style='mpl20')
    def test_draw_matrix_transposer_4(self):
        fig, ax = plt.subplots()
        generate_matrix_transposer(4).plot(ax=ax)
        return fig

    def test_split_memory_variable(self, simple_collection: ProcessCollection):
        collection_split = simple_collection.split_ports(
            heuristic="graph_color", read_ports=1, write_ports=1, total_ports=2
        )
        assert len(collection_split) == 3

    @pytest.mark.mpl_image_compare(style='mpl20')
    def test_left_edge_cell_assignment(self, simple_collection: ProcessCollection):
        fig, ax = plt.subplots(1, 2)
        assignment = simple_collection.left_edge_cell_assignment()
        for cell in assignment.keys():
            assignment[cell].plot(ax=ax[1], row=cell)
        simple_collection.plot(ax[0])
        return fig

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

    def test_len_process_collection(self, simple_collection: ProcessCollection):
        assert len(simple_collection) == 7
