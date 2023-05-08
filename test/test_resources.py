import pickle
import re

import matplotlib.pyplot as plt
import pytest

from b_asic.core_operations import ConstantMultiplication
from b_asic.process import PlainMemoryVariable
from b_asic.research.interleaver import (
    generate_matrix_transposer,
    generate_random_interleaver,
)
from b_asic.resources import ProcessCollection, _ForwardBackwardTable


class TestProcessCollectionPlainMemoryVariable:
    @pytest.mark.mpl_image_compare(style='mpl20')
    def test_draw_process_collection(self, simple_collection):
        fig, ax = plt.subplots()
        simple_collection.plot(ax=ax, show_markers=False)
        return fig

    @pytest.mark.mpl_image_compare(style='mpl20')
    def test_draw_matrix_transposer_4(self):
        fig, ax = plt.subplots()
        generate_matrix_transposer(4).plot(ax=ax)  # type: ignore
        return fig

    def test_split_memory_variable(self, simple_collection: ProcessCollection):
        collection_split = simple_collection.split_on_ports(
            heuristic="graph_color", read_ports=1, write_ports=1, total_ports=2
        )
        assert len(collection_split) == 3

    @pytest.mark.mpl_image_compare(style='mpl20')
    def test_left_edge_cell_assignment(self, simple_collection: ProcessCollection):
        fig, ax = plt.subplots(1, 2)
        assignment = simple_collection.left_edge_cell_assignment()
        for cell in assignment:
            assignment[cell].plot(ax=ax[1], row=cell)  # type: ignore
        simple_collection.plot(ax[0])  # type:ignore
        return fig

    def test_cell_assignment_matrix_transposer(self):
        collection = generate_matrix_transposer(4, min_lifetime=5)
        assignment_left_edge = collection.left_edge_cell_assignment()
        assignment_graph_color = collection.graph_color_cell_assignment(
            coloring_strategy='saturation_largest_first'
        )
        assert len(assignment_left_edge.keys()) == 18
        assert len(assignment_graph_color) == 16

    def test_generate_memory_based_vhdl(self):
        for rows in [2, 3, 4, 5, 7]:
            collection = generate_matrix_transposer(rows, min_lifetime=0)
            assignment = collection.graph_color_cell_assignment()
            collection.generate_memory_based_storage_vhdl(
                filename=f'b_asic/codegen/testbench/streaming_matrix_transposition_memory_{rows}x{rows}.vhdl',
                entity_name=f'streaming_matrix_transposition_memory_{rows}x{rows}',
                assignment=assignment,
                word_length=16,
            )

    def test_generate_register_based_vhdl(self):
        for rows in [2, 3, 4, 5, 7]:
            generate_matrix_transposer(
                rows, min_lifetime=0
            ).generate_register_based_storage_vhdl(
                filename=f'b_asic/codegen/testbench/streaming_matrix_transposition_register_{rows}x{rows}.vhdl',
                entity_name=f'streaming_matrix_transposition_register_{rows}x{rows}',
                word_length=16,
            )

    def test_rectangular_matrix_transposition(self):
        collection = generate_matrix_transposer(rows=4, cols=8, min_lifetime=2)
        assignment = collection.graph_color_cell_assignment()
        collection.generate_memory_based_storage_vhdl(
            filename='b_asic/codegen/testbench/streaming_matrix_transposition_memory_4x8.vhdl',
            entity_name='streaming_matrix_transposition_memory_4x8',
            assignment=assignment,
            word_length=16,
        )
        collection.generate_register_based_storage_vhdl(
            filename='b_asic/codegen/testbench/streaming_matrix_transposition_register_4x8.vhdl',
            entity_name='streaming_matrix_transposition_register_4x8',
            word_length=16,
        )

    def test_forward_backward_table_to_string(self):
        collection = ProcessCollection(
            collection={
                PlainMemoryVariable(0, 0, {0: 5}, name="PC0"),
                PlainMemoryVariable(1, 0, {0: 4}, name="PC1"),
                PlainMemoryVariable(2, 0, {0: 3}, name="PC2"),
                PlainMemoryVariable(3, 0, {0: 6}, name="PC3"),
                PlainMemoryVariable(4, 0, {0: 6}, name="PC4"),
                PlainMemoryVariable(5, 0, {0: 5}, name="PC5"),
            },
            schedule_time=7,
            cyclic=True,
        )
        t = _ForwardBackwardTable(collection)
        process_names = {match.group(0) for match in re.finditer(r'PC[0-9]+', str(t))}
        register_names = {match.group(0) for match in re.finditer(r'R[0-9]+', str(t))}
        assert len(process_names) == 6  # 6 process in the collection
        assert len(register_names) == 5  # 5 register required
        for i, process in enumerate(sorted(process_names)):
            assert process == f'PC{i}'
        for i, register in enumerate(sorted(register_names)):
            assert register == f'R{i}'

    def test_generate_random_interleaver(self):
        return
        for _ in range(10):
            for size in range(5, 20, 5):
                collection = generate_random_interleaver(size)
                assert len(collection.split_on_ports(read_ports=1, write_ports=1)) == 1
                if any(var.execution_time for var in collection.collection):
                    assert len(collection.split_on_ports(total_ports=1)) == 2

    def test_len_process_collection(self, simple_collection: ProcessCollection):
        assert len(simple_collection) == 7

    def test_get_by_type_name(self, secondorder_iir_schedule_with_execution_times):
        pc = secondorder_iir_schedule_with_execution_times.get_operations()
        pc_cmul = pc.get_by_type_name(ConstantMultiplication.type_name())
        assert len(pc_cmul) == 7
        assert all(
            isinstance(operand.operation, ConstantMultiplication)
            for operand in pc_cmul.collection
        )

    def test_show(self, simple_collection: ProcessCollection):
        simple_collection.show()

    def test_add_remove_process(self, simple_collection: ProcessCollection):
        new_proc = PlainMemoryVariable(1, 0, {0: 3})
        assert len(simple_collection) == 7
        assert new_proc not in simple_collection

        simple_collection.add_process(new_proc)
        assert len(simple_collection) == 8
        assert new_proc in simple_collection

        simple_collection.remove_process(new_proc)
        assert len(simple_collection) == 7
        assert new_proc not in simple_collection
