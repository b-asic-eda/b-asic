from collections import Counter
from random import Random

import pytest

from b_asic.process import PlainMemoryVariable
from b_asic.resources import ProcessCollection


def assert_valid_assignment(original, groups, read_ports, write_ports, total_ports):
    assigned = [process for group in groups for process in group]
    assert Counter(assigned) == Counter(original)
    for group in groups:
        assert group.schedule_time == original.schedule_time
        assert group._cyclic == original._cyclic
        reads = Counter(
            time % original.schedule_time
            for process in group
            for time in process.read_times
        )
        writes = Counter(
            process.start_time % original.schedule_time for process in group
        )
        assert max(reads.values(), default=0) <= read_ports
        assert max(writes.values(), default=0) <= write_ports
        assert max((reads + writes).values(), default=0) <= total_ports


def test_multiple_read_ports_reduce_memory_count():
    collection = ProcessCollection(
        [PlainMemoryVariable(time, 0, {0: 4 - time}, str(time)) for time in range(3)],
        schedule_time=8,
    )
    single = collection.split_on_ports(
        strategy="greedy_port_packing", read_ports=1, write_ports=1
    )
    multiple = collection.split_on_ports(
        strategy="greedy_port_packing", read_ports=2, write_ports=1
    )
    assert len(single) == 3
    assert len(multiple) == 2
    assert_valid_assignment(collection, multiple, 2, 1, 3)


@pytest.mark.parametrize(
    "ports", [(1, 1, 1), (2, 1, 2), (2, 1, 3), (3, 2, 3), (3, 2, 5)]
)
def test_randomized_packing_is_feasible_and_no_worse_than_left_edge(ports):
    rng = Random(5)
    collection = ProcessCollection(
        [
            PlainMemoryVariable(
                rng.randrange(16),
                0,
                dict(enumerate(rng.sample(range(1, 8), rng.randrange(1, 5)))),
                f"var{index}",
            )
            for index in range(40)
        ],
        schedule_time=8,
        cyclic=True,
    )
    read_ports, write_ports, total_ports = ports
    options = {
        "read_ports": read_ports,
        "write_ports": write_ports,
        "total_ports": total_ports,
    }
    packed = collection.split_on_ports(strategy="greedy_port_packing", **options)
    baseline = collection.split_on_ports(strategy="left_edge", **options)
    assert len(packed) <= len(baseline)
    assert_valid_assignment(collection, packed, *ports)
    assert_valid_assignment(collection, baseline, *ports)
    repeated = collection.split_on_ports(strategy="greedy_port_packing", **options)
    assert [set(group) for group in packed] == [set(group) for group in repeated]


@pytest.mark.parametrize("strategy", ["left_edge", "greedy_port_packing"])
def test_folded_candidate_reads_are_counted_together(strategy):
    collection = ProcessCollection(
        [
            PlainMemoryVariable(0, 0, {0: 1}, "single"),
            PlainMemoryVariable(2, 0, {0: 7, 1: 15}, "double"),
        ],
        schedule_time=8,
        cyclic=True,
    )
    groups = collection.split_on_ports(strategy=strategy, read_ports=2, write_ports=1)
    assert len(groups) == 2
    assert_valid_assignment(collection, groups, 2, 1, 3)


@pytest.mark.parametrize("strategy", ["left_edge", "greedy_port_packing"])
@pytest.mark.parametrize(
    ("reads", "ports"),
    [({0: 1, 1: 9}, (1, 1, 2)), ({0: 0}, (1, 1, 1)), ({0: 0, 1: 8}, (2, 1, 2))],
)
def test_individually_infeasible_variable_is_rejected(strategy, reads, ports):
    collection = ProcessCollection([PlainMemoryVariable(0, 0, reads, "oversized")], 8)
    with pytest.raises(ValueError, match="exceeds the port limits of a single memory"):
        collection.split_on_ports(
            strategy=strategy,
            read_ports=ports[0],
            write_ports=ports[1],
            total_ports=ports[2],
        )


def test_folded_writes_and_shared_ports():
    collection = ProcessCollection(
        [
            PlainMemoryVariable(0, 0, {0: 1}, "first"),
            PlainMemoryVariable(8, 0, {0: 2}, "second"),
        ],
        8,
    )
    groups = collection.split_on_ports(
        strategy="greedy_port_packing", read_ports=2, write_ports=1
    )
    assert len(groups) == 2
    assert_valid_assignment(collection, groups, 2, 1, 3)

    simultaneous = ProcessCollection(
        [PlainMemoryVariable(0, 0, {0: 0}, "same-cycle")], 8
    )
    groups = simultaneous.split_on_ports(strategy="greedy_port_packing", total_ports=2)
    assert_valid_assignment(simultaneous, groups, 2, 2, 2)


@pytest.mark.parametrize("restarts", [-1, 1.5])
def test_invalid_restarts(restarts):
    collection = ProcessCollection([], 8)
    with pytest.raises(ValueError, match="restarts must be a nonnegative integer"):
        collection.split_on_ports(
            strategy="greedy_port_packing",
            total_ports=2,
            strat_params={"restarts": restarts},
        )


@pytest.mark.parametrize("ports", [(0, 1, 1), (1, 0, 1), (-1, 1, 2)])
def test_invalid_port_limits(ports):
    with pytest.raises(ValueError, match="must be positive"):
        ProcessCollection([], 8).split_on_ports(
            strategy="greedy_port_packing",
            read_ports=ports[0],
            write_ports=ports[1],
            total_ports=ports[2],
        )


def test_empty_collection_and_zero_restarts():
    assert (
        ProcessCollection([], 8).split_on_ports(
            strategy="greedy_port_packing",
            total_ports=2,
            strat_params={"restarts": 0, "seed": 3},
        )
        == []
    )


@pytest.mark.parametrize(
    "strategy", ["left_edge_min_pe_to_mem", "left_edge_min_mem_to_pe"]
)
@pytest.mark.parametrize("ports", [(1, 2, 3), (2, 1, 3)])
def test_connection_heuristics_respect_asymmetric_port_limits(strategy, ports):
    collection = ProcessCollection(
        [PlainMemoryVariable(time, 0, {0: 4 - time}, str(time)) for time in range(3)],
        schedule_time=8,
    )
    groups = collection.split_on_ports(
        strategy=strategy,
        read_ports=ports[0],
        write_ports=ports[1],
        total_ports=ports[2],
        strat_params={"processing_elements": []},
    )
    assert len(groups) == (3 if ports[0] == 1 else 2)
    assert_valid_assignment(collection, groups, *ports)


def test_nonempty_collection_with_zero_restarts():
    collection = ProcessCollection([PlainMemoryVariable(0, 0, {0: 1}, "one")], 8)
    groups = collection.split_on_ports(
        strategy="greedy_port_packing",
        total_ports=2,
        strat_params={"restarts": 0, "seed": 3},
    )
    assert len(groups) == 1
    assert_valid_assignment(collection, groups, 2, 2, 2)


def test_exclusion_graph_remains_single_read_single_write(simple_collection):
    with pytest.raises(ValueError, match="read and write ports not equal to one"):
        simple_collection.exclusion_graph_from_ports(read_ports=2, write_ports=1)
