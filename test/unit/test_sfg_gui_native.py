"""Exercise native algorithms without Qt, including retained design state."""

import math
import random
from itertools import pairwise

import pytest

from b_asic import _sfg_gui as native
from test.sfg_gui_helpers import route_is_clear


def node(identity, x=0, y=0, size=(64, 64), delay=False, rotation=0):
    return (
        identity,
        (x, y, x + size[0], y + size[1]),
        size,
        delay,
        rotation,
        0,
        False,
        native.TerminalKind.OPERATION,
    )


def design():
    engine = native.PlaceRouteEngine(8, 24)
    engine.update(
        [node(1), node(2, 320), node(3, 0, 400), node(4, 320, 400)],
        [
            (11, 1, (80, 32), (1, 0)),
            (12, 2, (304, 32), (-1, 0)),
            (13, 3, (80, 432), (1, 0)),
            (14, 4, (304, 432), (-1, 0)),
        ],
        [(21, 11, 12, 0, 0.5), (22, 13, 14, 0, 0.5)],
    )
    return engine


def test_retained_routes_only_return_changed_paths():
    engine = design()
    updates, dots = engine.route()
    assert {update[0] for update in updates} == {21, 22}
    assert dots is None
    before = engine.wire_path(22)
    assert engine.route() == ([], None)
    engine.update([node(1, 0, 8)], [(11, 1, (80, 40), (1, 0))], [])
    updates, _ = engine.route(incremental=True)
    assert engine.routed_ids() == [21]
    assert [update[0] for update in updates] == [21]
    assert engine.wire_path(21)[0] == [80, 40]
    assert engine.wire_path(22) == before
    engine.route()  # Release: optimize every source again.
    assert set(engine.routed_ids()) == {21, 22}
    final = [engine.wire_path(wire) for wire in (21, 22)]
    assert engine.route(force=True)[0] == []
    assert [engine.wire_path(wire) for wire in (21, 22)] == final


def test_obstacle_deltas_reroute_only_nearby_sources():
    engine = design()
    engine.update([node(5, 800, 800)], [], [])
    engine.route()
    engine.update([node(5, 160)], [], [])
    engine.route(incremental=True)
    assert engine.routed_ids() == [21]
    assert route_is_clear(engine.wire_path(21), [(160, 0, 224, 64)])


def test_parent_before_child_and_junction_removal():
    engine = native.PlaceRouteEngine(8, 24)
    engine.update(
        [node(1), node(2, 320), node(3, 320, 160)],
        [
            (11, 1, (80, 32), (1, 0)),
            (12, 2, (304, 32), (-1, 0)),
            (13, 3, (304, 192), (-1, 0)),
        ],
        [(22, 11, 13, 21, 0.5), (21, 11, 12, 0, 0.5)],
    )
    updates, dots = engine.route()
    assert engine.routed_ids() == [21, 22]
    assert {update[0] for update in updates} == {21, 22}
    assert [192, 32] in dots
    assert [192, 32] in engine.wire_path(22)
    engine.update([], [], [], removed_wires=[22])
    assert engine.route()[1] == []
    assert engine.statistics()["wires"] == 1
    engine.update([], [], [], removed_nodes=[3], removed_ports=[13])
    assert engine.statistics()["nodes"] == 2
    engine.reset()
    assert not any(engine.statistics().values())
    assert engine.layout() == []


@pytest.mark.parametrize(
    "change", ["nan", "direction", "orphan", "cycle", "parent_source", "missing_port"]
)
def test_invalid_updates_are_atomic(change):
    engine = design()
    engine.route()
    stats, path = engine.statistics(), engine.wire_path(21)
    changes = {
        "nan": (([node(1, math.nan)], [], []), {}, "finite"),
        "direction": (([], [(11, 1, (80, 32), (1, 1))], []), {}, "direction"),
        "orphan": (([], [], []), {"removed_nodes": [1]}, "ports"),
        "cycle": (([], [], [(21, 11, 12, 21, 0.5)]), {}, "Cyclic"),
        "parent_source": (([], [], [(21, 11, 12, 22, 0.5)]), {}, "source"),
        "missing_port": (([], [], [(21, 11, 999, 0, 0.5)]), {}, "endpoints"),
    }
    args, kwargs, message = changes[change]
    with pytest.raises(ValueError, match=message):
        engine.update(*args, **kwargs)
    assert engine.statistics() == stats
    assert engine.wire_path(21) == path
    assert engine.route() == ([], None)


@pytest.mark.parametrize("seed", range(20))
def test_native_routing_preserves_clear_orthogonal_paths(seed):
    rng = random.Random(seed)
    start, end = (0, 0), (320, 160)
    obstacles = []
    for _ in range(8):
        x, y = 8 * rng.randrange(4, 32), 8 * rng.randrange(-8, 28)
        obstacles.append((x, y, x + 24, y + 24))
    result = native.route_orthogonal(start, end, obstacles, [], [], 8)
    assert result
    if result:
        assert result[0] == list(start)
        assert result[-1] == list(end)
        assert route_is_clear(result, obstacles)
        assert all(a[0] == b[0] or a[1] == b[1] for a, b in pairwise(result))


def test_native_junctions_find_long_shared_trunk_branches():
    paths = [
        [(0, 0), (240, 0), (240, 80)],
        [(0, 0), (80, 0), (80, -80)],
        [(0, 0), (240, 0), (240, -80)],
    ]
    assert {tuple(p) for p in native.junction_points(paths)} == {(80, 0), (240, 0)}


@pytest.mark.parametrize("transpose", [False, True])
def test_maze_route_avoids_extra_bends_along_operation_contours(transpose):
    obstacles = [
        (-10, -20, 30, -10),
        (-10, 10, 30, 20),
        (-20, -20, -10, 20),
        (70, -20, 110, -10),
        (70, 10, 110, 20),
        (110, -20, 120, 20),
        (40, -30, 60, 30),
    ]
    start, end = (0, 0), (100, 0)
    simpler = [(0, 0), (30, 0), (30, 30), (70, 30), (70, 0), (100, 0)]
    if transpose:
        obstacles = [
            (top, left, bottom, right) for left, top, right, bottom in obstacles
        ]
        end = end[::-1]
        simpler = [p[::-1] for p in simpler]
    assert route_is_clear(simpler, obstacles)
    path = native.route_orthogonal(start, end, obstacles, [], [], 8)
    assert path[0] == list(start)
    assert path[-1] == list(end)
    assert route_is_clear(path, obstacles)
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in pairwise(path))
    assert len(path) <= len(simpler)
    assert native.route_cost(path, [], [], 8) <= native.route_cost(simpler, [], [], 8)


def test_native_placement_balances_heights_and_feedback():
    result = native.place_graph(
        3, [(0, 1), (1, 2)], [(64, 32), (64, 64), (64, 32)], [False] * 3, 24, 8
    )
    assert result[0][1] + 16 == result[1][1] + 32 == result[2][1] + 16
    engine = native.PlaceRouteEngine(8, 24)
    engine.update(
        [node(1, size=(64, 112), rotation=90), node(2, size=(48, 48), delay=True)],
        [
            (11, 1, (80, 16), (1, 0)),
            (12, 1, (-16, 16), (-1, 0)),
            (13, 2, (64, 24), (1, 0)),
            (14, 2, (-16, 24), (-1, 0)),
        ],
        [(21, 11, 14, 0, 0.5), (22, 13, 12, 0, 0.5)],
    )
    layout = {
        identity: (point, angle, flip)
        for identity, point, angle, flip in engine.layout()
    }
    assert layout[1][1:] == (90, False)
    assert layout[2][2] is True
    assert all(
        coordinate % 8 == 0 for point, _, _ in layout.values() for coordinate in point
    )
    assert layout == {
        identity: (point, angle, flip)
        for identity, point, angle, flip in engine.layout()
    }


@pytest.mark.parametrize("grid", [0, -8, math.inf, math.nan])
def test_invalid_configuration(grid):
    with pytest.raises(ValueError, match=r"positive|finite"):
        native.PlaceRouteEngine(grid, 24)
    with pytest.raises(ValueError, match=r"positive|finite"):
        native.route_orthogonal((0, 0), (8, 8), [], [], [], grid)


def test_invalid_graph_arrays_and_geometry():
    with pytest.raises(ValueError, match="unknown node"):
        native.place_graph(1, [(0, 2)], [(64, 64)], [False], 24, 8)
    with pytest.raises(ValueError, match="match graph size"):
        native.choose_orientations(1, [], [], [(64, 64)], [False], 24)
    with pytest.raises(ValueError, match=r"positive|finite"):
        native.route_orthogonal((0, 0), (8, 8), [], [((0, math.nan), (8, 0))], [], 8)


@pytest.mark.parametrize("seed", range(10))
def test_mixed_size_cyclic_layouts_stay_separate_on_grid(seed):
    rng = random.Random(seed)
    count = 24
    edges = [
        (a, b)
        for a in range(count)
        for b in range(count)
        if a != b and rng.random() < 0.045
    ]
    sizes = [
        (rng.choice([48, 64, 112]), rng.choice([32, 48, 64, 112])) for _ in range(count)
    ]
    flags = native.feedback_delays(
        count, edges, [rng.random() < 0.3 for _ in range(count)]
    )
    positions = native.place_graph(count, edges, sizes, flags, 24, 8)
    assert all(coordinate % 8 == 0 for point in positions for coordinate in point)
    for a, (x, y) in enumerate(positions):
        for b, (u, v) in enumerate(positions[:a]):
            assert (
                x >= u + sizes[b][0]
                or u >= x + sizes[a][0]
                or y >= v + sizes[b][1]
                or v >= y + sizes[a][1]
            )
