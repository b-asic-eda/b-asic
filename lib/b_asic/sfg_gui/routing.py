"""Orthogonal visibility routing independent of the graphics scene."""

from heapq import heappop, heappush
from itertools import count, pairwise

Point = tuple[float, float]
Rect = tuple[float, float, float, float]
Segment = tuple[Point, Point]


def overlap_length(a: Point, b: Point, c: Point, d: Point) -> float:
    """Return the length shared by two collinear orthogonal segments."""
    if a[1] == b[1] == c[1] == d[1]:
        return max(
            0,
            min(max(a[0], b[0]), max(c[0], d[0]))
            - max(min(a[0], b[0]), min(c[0], d[0])),
        )
    if a[0] == b[0] == c[0] == d[0]:
        return max(
            0,
            min(max(a[1], b[1]), max(c[1], d[1]))
            - max(min(a[1], b[1]), min(c[1], d[1])),
        )
    return 0


def route_orthogonal(
    start: Point,
    end: Point,
    obstacles: list[Rect],
    occupied: list[Segment] | None = None,
    shared: list[Segment] | None = None,
) -> list[Point]:
    """
    Find a short rectilinear route avoiding rectangle interiors.

    Rectangle edges and parallel wire lanes form the visibility graph.
    Routes avoid unrelated wires and favor reusing wires from the same output.
    Return an empty route if an endpoint is enclosed by an obstacle.
    """
    occupied = occupied or []
    shared = shared or []
    wire_xs = {
        p[0] + offset for segment in occupied for p in segment for offset in (-8, 0, 8)
    }
    wire_ys = {
        p[1] + offset for segment in occupied for p in segment for offset in (-8, 0, 8)
    }
    xs = sorted(
        {start[0], end[0]}
        | {x for r in obstacles for x in (r[0], r[2])}
        | wire_xs
        | {p[0] for segment in shared for p in segment}
    )
    ys = sorted(
        {start[1], end[1]}
        | {y for r in obstacles for y in (r[1], r[3])}
        | wire_ys
        | {p[1] for segment in shared for p in segment}
    )
    points = {
        (x, y)
        for x in xs
        for y in ys
        if not any(l < x < r and t < y < b for l, t, r, b in obstacles)
    }
    if start not in points or end not in points:
        return []
    neighbors = {p: [] for p in points}
    for lanes in (
        [[(x, y) for x in xs if (x, y) in points] for y in ys],
        [[(x, y) for y in ys if (x, y) in points] for x in xs],
    ):
        for lane in lanes:
            for a, b in pairwise(lane):
                blocked = any(
                    (t < a[1] < bottom and max(a[0], l) < min(b[0], r))
                    if a[1] == b[1]
                    else (l < a[0] < r and max(a[1], t) < min(b[1], bottom))
                    for l, t, r, bottom in obstacles
                )
                if not blocked:
                    neighbors[a].append(b)
                    neighbors[b].append(a)
    serial = count()
    queue = [((0.0, 0.0), next(serial), start, -1)]
    distances = {(start, -1): (0.0, 0.0)}
    previous = {}
    while queue:
        cost, _, point, direction = heappop(queue)
        state = (point, direction)
        if cost != distances[state]:
            continue
        if point == end:
            path = [point]
            while state in previous:
                state = previous[state]
                path.append(state[0])
            path.reverse()
            result = []
            for p in path:
                if len(result) >= 2 and (
                    result[-2][0] == result[-1][0] == p[0]
                    or result[-2][1] == result[-1][1] == p[1]
                ):
                    result.pop()
                result.append(p)
            return result
        for neighbor in neighbors[point]:
            axis = int(neighbor[0] == point[0])
            distance = abs(neighbor[0] - point[0]) + abs(neighbor[1] - point[1])
            overlap = sum(overlap_length(point, neighbor, a, b) for a, b in occupied)
            reused = min(
                distance, sum(overlap_length(point, neighbor, a, b) for a, b in shared)
            )
            candidate = (
                cost[0] + overlap,
                cost[1]
                + distance
                - 0.75 * reused
                + (20 if direction not in (-1, axis) else 0),
            )
            next_state = (neighbor, axis)
            if candidate < distances.get(next_state, (float("inf"), float("inf"))):
                distances[next_state] = candidate
                previous[next_state] = state
                heappush(queue, (candidate, next(serial), neighbor, axis))
    return []


def junction_points(paths: list[list[Point]]) -> set[Point]:
    """
    Find branches in the union of paths belonging to a single output port.

    Count outgoing geometric directions, rather than paths, so coincident
    trunks and ordinary bends do not create spurious junctions.
    """
    segments = [
        segment
        for path in paths
        for segment in pairwise(path)
        if segment[0] != segment[1]
    ]
    candidates = {point for path in paths for point in path}
    horizontal = [(a, b) for a, b in segments if a[1] == b[1]]
    vertical = [(a, b) for a, b in segments if a[0] == b[0]]
    for a, b in horizontal:
        for c, d in vertical:
            if min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(c[1], d[1]) <= a[
                1
            ] <= max(c[1], d[1]):
                candidates.add((c[0], a[1]))
    junctions = set()
    for x, y in candidates:
        directions = set()
        for a, b in segments:
            if a[1] == b[1] == y and min(a[0], b[0]) <= x <= max(a[0], b[0]):
                if min(a[0], b[0]) < x:
                    directions.add((-1, 0))
                if x < max(a[0], b[0]):
                    directions.add((1, 0))
            if a[0] == b[0] == x and min(a[1], b[1]) <= y <= max(a[1], b[1]):
                if min(a[1], b[1]) < y:
                    directions.add((0, -1))
                if y < max(a[1], b[1]):
                    directions.add((0, 1))
        if len(directions) >= 3:
            junctions.add((x, y))
    return junctions
