import re

import matplotlib.pyplot as plt
import matplotlib.testing.decorators
import pytest

from b_asic.core_operations import ConstantMultiplication
from b_asic.process import PlainMemoryVariable
from b_asic.research.interleaver import (
    generate_matrix_transposer,
    generate_random_interleaver,
)
from b_asic.resources import ProcessCollection, _ForwardBackwardTable


class TestProcessCollectionPlainMemoryVariable:
    @matplotlib.testing.decorators.image_comparison(
        ["test_draw_process_collection.png"]
    )
    def test_draw_process_collection(self, simple_collection):
        fig, ax = plt.subplots()
        simple_collection.plot(ax=ax, show_markers=False)
        return fig

    @matplotlib.testing.decorators.image_comparison(
        ["test_draw_matrix_transposer_4.png"]
    )
    def test_draw_matrix_transposer_4(self):
        fig, ax = plt.subplots()
        generate_matrix_transposer(4).plot(ax=ax)  # type: ignore
        return fig

    def test_split_memory_variable_greedy_graph_color(
        self, simple_collection: ProcessCollection
    ):
        collection_split = simple_collection.split_on_ports(
            strategy="greedy_graph_color", read_ports=1, write_ports=1, total_ports=2
        )
        assert len(collection_split) == 3

    def test_contains(self):
        collection = ProcessCollection([], schedule_time=10, cyclic=True)
        m1 = PlainMemoryVariable(0, 0, {0: 3})
        assert m1 not in collection
        collection.add_process(m1)
        assert m1 in collection
        collection.remove_process(m1)
        assert m1 not in collection

    def test_split_sequence_raises(self, simple_collection: ProcessCollection):
        with pytest.raises(KeyError, match="processes in `sequence` must be"):
            simple_collection.split_ports_sequentially(
                read_ports=1, write_ports=1, total_ports=2, sequence=[]
            )

    def test_split_memory_variable_left_edge(
        self, simple_collection: ProcessCollection
    ):
        split = simple_collection.split_on_ports(
            strategy="left_edge", read_ports=1, write_ports=1, total_ports=2
        )
        assert len(split) == 3

        split = simple_collection.split_on_ports(
            strategy="left_edge", read_ports=1, write_ports=2, total_ports=2
        )
        assert len(split) == 3

        split = simple_collection.split_on_ports(
            strategy="left_edge", read_ports=2, write_ports=2, total_ports=2
        )
        assert len(split) == 2

    def test_split_memory_variable_raises(self, simple_collection: ProcessCollection):
        with pytest.raises(
            ValueError,
            match="processing_elements must be provided if strategy = 'ilp_min_input_mux'",
        ):
            simple_collection.split_on_ports(
                strategy="ilp_min_input_mux", total_ports=1
            )

        with pytest.raises(
            ValueError,
            match="processing_elements must be provided if strategy = 'ilp_min_output_mux'",
        ):
            simple_collection.split_on_ports(
                strategy="ilp_min_output_mux", total_ports=1
            )

        with pytest.raises(
            ValueError,
            match="processing_elements must be provided if strategy = 'ilp_min_total_mux'",
        ):
            simple_collection.split_on_ports(
                strategy="ilp_min_total_mux", total_ports=1
            )

        with pytest.raises(
            ValueError,
            match="processing_elements must be provided if strategy = 'left_edge_min_pe_to_mem'",
        ):
            simple_collection.split_on_ports(
                strategy="left_edge_min_pe_to_mem", total_ports=1
            )

        with pytest.raises(
            ValueError,
            match="processing_elements must be provided if strategy = 'left_edge_min_mem_to_pe'",
        ):
            simple_collection.split_on_ports(
                strategy="left_edge_min_mem_to_pe", total_ports=1
            )

        with pytest.raises(ValueError, match="Invalid strategy provided."):
            simple_collection.split_on_ports(strategy="foo", total_ports=1)

    @matplotlib.testing.decorators.image_comparison(
        ["test_left_edge_cell_assignment.png"]
    )
    def test_left_edge_cell_assignment(self, simple_collection: ProcessCollection):
        fig, ax = plt.subplots(1, 2)
        assignment = list(simple_collection._left_edge_assignment())
        for i, cell in enumerate(assignment):
            cell.plot(ax=ax[1], row=i)  # type: ignore
        simple_collection.plot(ax[0])  # type:ignore
        return fig

    def test_cell_assignment_matrix_transposer(self):
        collection = generate_matrix_transposer(4, min_lifetime=5)
        assignment_left_edge = collection._left_edge_assignment()
        assignment_graph_color = collection.split_on_execution_time(
            strategy="greedy_graph_color", coloring_strategy="saturation_largest_first"
        )
        assert len(assignment_left_edge) == 18
        assert len(assignment_graph_color) == 16

    def test_generate_memory_based_vhdl(self):
        # fmt: off
        variants = [
            #  rows ,  cols , #mux  , #pipe  #
            # ------------------------------ #
            (   2   ,   2   ,  None ,  None ),
            (   3   ,   3   ,   1   ,   0   ),
            (   4   ,   4   ,   4   ,   1   ),
            (   5   ,   5   ,   4   ,   2   ),
            (   7   ,   7   ,   4   ,   3   ),
            (   4   ,   8   ,   2   ,   2   ),
        ]
        # fmt: on
        for rows, cols, mux_size, pipe_depth in variants:
            collection = generate_matrix_transposer(
                rows=rows, cols=cols, min_lifetime=0
            )
            assignment = collection.split_on_execution_time(
                strategy="greedy_graph_color"
            )
            collection.generate_memory_based_storage_vhdl(
                filename=(
                    "b_asic/codegen/testbench/"
                    f"streaming_matrix_transposition_memory_{rows}x{cols}.vhdl"
                ),
                entity_name=f"streaming_matrix_transposition_memory_{rows}x{cols}",
                assignment=assignment,
                word_length=16,
                adr_mux_size=mux_size,
                adr_pipe_depth=pipe_depth,
            )

    def test_generate_register_based_vhdl(self):
        for rows in [2, 3, 4, 5, 7]:
            generate_matrix_transposer(
                rows, min_lifetime=0
            ).generate_register_based_storage_vhdl(
                filename=(
                    "b_asic/codegen/testbench/streaming_matrix_transposition_"
                    f"register_{rows}x{rows}.vhdl"
                ),
                entity_name=f"streaming_matrix_transposition_register_{rows}x{rows}",
                word_length=16,
            )

    def test_rectangular_matrix_transposition(self):
        collection = generate_matrix_transposer(rows=4, cols=8, min_lifetime=2)
        collection.generate_register_based_storage_vhdl(
            filename=(
                "b_asic/codegen/testbench/streaming_matrix_transposition_register_"
                "4x8.vhdl"
            ),
            entity_name="streaming_matrix_transposition_register_4x8",
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
        process_names = {match.group(0) for match in re.finditer(r"PC[0-9]+", str(t))}
        register_names = {match.group(0) for match in re.finditer(r"R[0-9]+", str(t))}
        assert len(process_names) == 6  # 6 process in the collection
        assert len(register_names) == 5  # 5 register required
        for i, process in enumerate(sorted(process_names)):
            assert process == f"PC{i}"
        for i, register in enumerate(sorted(register_names)):
            assert register == f"R{i}"

    def test_generate_random_interleaver(self):
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

    def test_show_total_execution_times(self, simple_collection: ProcessCollection):
        simple_collection.show_total_execution_times()

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

    @matplotlib.testing.decorators.image_comparison(
        ["test_max_min_lifetime_bar_plot.png"]
    )
    def test_max_min_lifetime_bar_plot(self):
        fig, ax = plt.subplots()
        collection = ProcessCollection(
            {
                # Process starting exactly at schedule start
                PlainMemoryVariable(0, 0, {0: 0}, "S1"),
                PlainMemoryVariable(0, 0, {0: 5}, "S2"),
                # Process starting somewhere between schedule start and end
                PlainMemoryVariable(2, 0, {0: 0}, "M1"),
                PlainMemoryVariable(2, 0, {0: 5}, "M2"),
                # Process starting at the schedule end
                PlainMemoryVariable(5, 0, {0: 0}, "E1"),
                PlainMemoryVariable(5, 0, {0: 5}, "E2"),
            },
            schedule_time=5,
        )
        collection.plot(ax)
        return fig

    def test_multiple_reads_exclusion_greaph(self):
        # Initial collection
        p0 = PlainMemoryVariable(0, 0, {0: 3}, "P0")
        p1 = PlainMemoryVariable(1, 0, {0: 2}, "P1")
        p2 = PlainMemoryVariable(2, 0, {0: 2}, "P2")
        p3 = PlainMemoryVariable(3, 0, {0: 3}, "P3")
        collection = ProcessCollection({p0, p1, p2, p3}, 5, cyclic=True)
        exclusion_graph = collection.exclusion_graph_from_ports(
            read_ports=1,
            write_ports=1,
            total_ports=1,
        )
        for p in [p0, p1, p2, p3]:
            assert p in exclusion_graph
        assert exclusion_graph.degree(p0) == 2
        assert exclusion_graph.degree(p1) == 2
        assert exclusion_graph.degree(p2) == 0
        assert exclusion_graph.degree(p3) == 2

        # Add multi-read process
        p4 = PlainMemoryVariable(0, 0, {0: 1, 1: 2, 2: 3, 3: 4}, "P4")
        collection.add_process(p4)
        exclusion_graph = collection.exclusion_graph_from_ports(
            read_ports=1,
            write_ports=1,
            total_ports=1,
        )
        for p in [p0, p1, p2, p3, p4]:
            assert p in exclusion_graph
        assert exclusion_graph.degree(p0) == 3
        assert exclusion_graph.degree(p1) == 3
        assert exclusion_graph.degree(p2) == 1
        assert exclusion_graph.degree(p3) == 3

    def test_processing_element_bound(self):
        a = PlainMemoryVariable(2, 0, {0: 1}, "cmul1.0")
        b = PlainMemoryVariable(4, 0, {0: 7}, "cmul4.0")
        c = PlainMemoryVariable(5, 0, {0: 4}, "cmul5.0")
        collection = ProcessCollection([a, b, c], schedule_time=7, cyclic=True)
        assert collection.processing_element_bound() == 2

        a = PlainMemoryVariable(2, 0, {0: 1}, "cmul1.0")
        b = PlainMemoryVariable(2, 0, {0: 2}, "cmul2.0")
        c = PlainMemoryVariable(2, 0, {0: 3}, "cmul3.0")
        collection = ProcessCollection([a, b, c], schedule_time=5, cyclic=True)
        assert collection.processing_element_bound() == 3

    def test_split_on_execution_time_maximum_lifetime(self):
        a = PlainMemoryVariable(2, 0, {0: 1}, "cmul1.0")
        b = PlainMemoryVariable(4, 0, {0: 7}, "cmul4.0")
        c = PlainMemoryVariable(5, 0, {0: 4}, "cmul5.0")
        collection = ProcessCollection([a, b, c], schedule_time=7, cyclic=True)
        for strategy in ("greedy_graph_color", "left_edge", "ilp_graph_color"):
            assignment = collection.split_on_execution_time(strategy)
            assert len(assignment) == 2
            a_idx = 0 if a in assignment[0] else 1
            assert b not in assignment[a_idx]
            assert c in assignment[a_idx]

    def test_split_on_execution_lifetime_assert(self):
        a = PlainMemoryVariable(3, 0, {0: 10}, "MV0")
        collection = ProcessCollection([a], schedule_time=9, cyclic=True)
        for strategy in ("greedy_graph_color", "left_edge", "ilp_graph_color"):
            with pytest.raises(
                ValueError,
                match="MV0 has execution time greater than the schedule time",
            ):
                collection.split_on_execution_time(strategy)

    def test_split_on_length(self):
        # Test 1: Exclude a zero-time access time
        collection = ProcessCollection(
            collection=[PlainMemoryVariable(0, 1, {0: 1, 1: 2, 2: 3})],
            schedule_time=4,
        )
        short, long = collection.split_on_length(0)
        assert len(short) == 0
        assert len(long) == 1
        for split_time in [1, 2]:
            short, long = collection.split_on_length(split_time)
            assert len(short) == 1
            assert len(long) == 1
        short, long = collection.split_on_length(3)
        assert len(short) == 1
        assert len(long) == 0

        # Test 2: Include a zero-time access time
        collection = ProcessCollection(
            collection=[PlainMemoryVariable(0, 1, {0: 0, 1: 1, 2: 2, 3: 3})],
            schedule_time=4,
        )
        short, long = collection.split_on_length(0)
        assert len(short) == 1
        assert len(long) == 1
        for split_time in [1, 2]:
            short, long = collection.split_on_length(split_time)
            assert len(short) == 1
            assert len(long) == 1

    def test_from_name(self):
        a = PlainMemoryVariable(0, 0, {0: 2}, name="cool name 1337")
        collection = ProcessCollection([a], schedule_time=5, cyclic=True)
        with pytest.raises(KeyError, match="epic_name not in ..."):
            collection.from_name("epic_name")
        assert a == collection.from_name("cool name 1337")
