"""Adapt native containers for geometric assertions in GUI tests."""

from b_asic import _sfg_gui as native

# Native geometry fixtures use an eight-unit scene grid and require no Qt.
TEST_GRID = 8

route_is_clear = native.route_is_clear
overlap_length = native.overlap_length


def route_orthogonal(start, end, obstacles, occupied=(), shared=()):
    return [
        tuple(p)
        for p in native.route_orthogonal(
            start, end, obstacles, occupied, shared, TEST_GRID
        )
    ]


def route_cost(path, occupied, shared=()):
    return native.route_cost(path, occupied, shared, TEST_GRID)


def junction_points(paths):
    return {tuple(p) for p in native.junction_points(paths)}
