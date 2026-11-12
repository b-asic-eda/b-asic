#include "engine.hpp"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <functional>
#include <limits>

namespace asic::gui {
namespace {
constexpr double bend_penalty = 20;

double length(Point a, Point b) {
	return std::abs(a[0] - b[0]) + std::abs(a[1] - b[1]);
}
Segments segments(const Path& path) {
	Segments result;
	for (std::size_t i = 1; i < path.size(); ++i)
		if (path[i - 1] != path[i])
			result.push_back({path[i - 1], path[i]});
	return result;
}
bool blocked(Point a, Point b, const std::vector<Rect>& obstacles) {
	for (const auto& r : obstacles) {
		if (a[1] == b[1]) {
			if (r[1] < a[1] && a[1] < r[3] && std::max(std::min(a[0], b[0]), r[0]) < std::min(std::max(a[0], b[0]), r[2]))
				return true;
		} else if (r[0] < a[0] && a[0] < r[2] && std::max(std::min(a[1], b[1]), r[1]) < std::min(std::max(a[1], b[1]), r[3]))
			return true;
	}
	return false;
}
Path simplify(const Path& path) {
	Path result;
	for (auto p : path) {
		if (!result.empty() && p == result.back())
			continue;
		if (result.size() > 1) {
			auto a = result[result.size() - 2], b = result.back();
			if ((a[0] == b[0] && b[0] == p[0]) || (a[1] == b[1] && b[1] == p[1]))
				result.pop_back();
		}
		result.push_back(p);
	}
	return result;
}
Cost segment_cost(Point a, Point b, const Segments& occupied, const Segments& shared, double grid) {
	double congestion = 0, reuse = 0, distance = length(a, b);
	for (const auto& s : occupied) {
		Point c = s[0], d = s[1];
		double offset, projection;
		if (a[1] == b[1] && c[1] == d[1]) {
			offset = std::abs(a[1] - c[1]);
			if (offset >= grid)
				continue;
			projection = overlap({a, b}, {{{c[0], a[1]}, {d[0], a[1]}}});
		} else if (a[0] == b[0] && c[0] == d[0]) {
			offset = std::abs(a[0] - c[0]);
			if (offset >= grid)
				continue;
			projection = overlap({a, b}, {{{a[0], c[1]}, {a[0], d[1]}}});
		} else
			continue;
		congestion += projection * (1 - offset / grid);
	}
	for (const auto& s : shared)
		reuse += overlap({a, b}, s);
	return {congestion, distance - 0.75 * std::min(distance, reuse)};
}
// Index parallel wire lanes and cache the merged obstacle intervals on each
// visibility row/column. Candidate routes and search reuse the same queries.
class RouteGeometry {
	const std::vector<Rect>& obstacles_;
	double grid_;
	std::array<std::map<double, Segments>, 2> occupied_, shared_;
	std::array<std::map<double, std::vector<Point>>, 2> blocked_;

public:
	RouteGeometry(const std::vector<Rect>& obstacles, const Segments& occupied, const Segments& shared, double grid)
		: obstacles_(obstacles), grid_(grid) {
		auto index = [](const Segments& segments, auto& lanes) {
			for (const auto& s : segments) {
				if (s[0][0] != s[1][0] && s[0][1] != s[1][1])
					continue;
				int axis = s[0][1] == s[1][1] ? 0 : 1;
				lanes[axis][s[0][1 - axis]].push_back(s);
			}
		};
		index(occupied, occupied_);
		index(shared, shared_);
	}
	bool blocked(Point a, Point b) {
		int axis = a[1] == b[1] ? 0 : 1;
		double lane = a[1 - axis];
		auto& rows = blocked_[axis];
		auto [it, inserted] = rows.try_emplace(lane);
		if (inserted) {
			auto& intervals = it->second;
			for (auto r : obstacles_)
				if (r[1 - axis] < lane && lane < r[3 - axis] && r[axis] < r[axis + 2])
					intervals.push_back({r[axis], r[axis + 2]});
			std::sort(intervals.begin(), intervals.end());
			std::vector<Point> merged;
			for (auto p : intervals) {
				if (!merged.empty() && p[0] <= merged.back()[1])
					merged.back()[1] = std::max(merged.back()[1], p[1]);
				else
					merged.push_back(p);
			}
			intervals = std::move(merged);
		}
		const auto& intervals = it->second;
		double low = std::min(a[axis], b[axis]), high = std::max(a[axis], b[axis]);
		auto hit = std::upper_bound(intervals.begin(), intervals.end(), low, [](double x, Point p) { return x < p[1]; });
		return low < high && hit != intervals.end() && (*hit)[0] < high;
	}
	bool clear(const Path& path) {
		for (std::size_t i = 1; i < path.size(); ++i)
			if (blocked(path[i - 1], path[i]))
				return false;
		return !path.empty();
	}
	Cost cost(Point a, Point b) const {
		int axis = a[1] == b[1] ? 0 : 1;
		double lane = a[1 - axis], congestion = 0, reuse = 0, distance = length(a, b);
		const auto& lanes = occupied_[axis];
		for (auto it = lanes.upper_bound(lane - grid_); it != lanes.end() && it->first < lane + grid_; ++it)
			for (const auto& s : it->second) {
				auto c = s[0], d = s[1];
				c[1 - axis] = d[1 - axis] = lane;
				congestion += overlap({a, b}, {c, d}) * (1 - std::abs(lane - it->first) / grid_);
			}
		auto shared = shared_[axis].find(lane);
		if (shared != shared_[axis].end())
			for (const auto& s : shared->second)
				reuse += overlap({a, b}, s);
		return {congestion, distance - 0.75 * std::min(distance, reuse)};
	}
	Cost cost(const Path& path) const {
		Cost result{0, path.size() > 2 ? bend_penalty * (path.size() - 2) : 0};
		for (std::size_t i = 1; i < path.size(); ++i) {
			auto c = cost(path[i - 1], path[i]);
			result.first += c.first;
			result.second += c.second;
		}
		return result;
	}
};
// State and edge storage follows the expansion budget, never xs.size() *
// ys.size(). Compact IDs address contiguous records; open addressing locates
// the few visibility cells actually visited, without one allocation per state.
constexpr std::size_t search_limit = 1024;
using SearchId = std::uint32_t;
constexpr SearchId no_search_id = std::numeric_limits<SearchId>::max();
using SearchCell = std::array<std::size_t, 2>;
using SearchEntry = std::tuple<Cost, std::size_t, SearchId>;

struct SearchState {
	Cost distance{std::numeric_limits<double>::infinity(), std::numeric_limits<double>::infinity()};
	SearchId previous = no_search_id;
	bool settled = false;
};
struct SearchEdge {
	Cost cost{0, 0};
	SearchId neighbor = no_search_id;
	unsigned char status = 0; // Unknown, blocked, clear.
};
struct SearchCellRecord {
	SearchCell coordinates;
	std::array<SearchState, 3> states; // Origin, horizontal arrival, vertical arrival.
	std::array<SearchEdge, 4> edges;
};
struct SearchWorkspace {
	static constexpr std::size_t max_cells = 1 + 4 * search_limit;
	static constexpr std::size_t slot_count = 16384;
	static_assert(slot_count >= 2 * max_cells && (slot_count & (slot_count - 1)) == 0);
	static_assert(3 * max_cells < no_search_id);
	std::array<SearchId, slot_count> slots;
	std::vector<SearchCellRecord> cells;
	std::vector<SearchEntry> queue;
	std::vector<double> xs, ys;

	SearchWorkspace() {
		// Each expansion discovers at most four neighbors. Reserving that
		// bound also keeps cell references stable during neighbor insertion.
		cells.reserve(max_cells);
		queue.reserve(max_cells);
	}
	void reset() {
		slots.fill(no_search_id);
		cells.clear();
		queue.clear();
		xs.clear();
		ys.clear();
	}
	SearchId cell(SearchCell coordinates) {
		std::uint64_t hash = coordinates[0] * UINT64_C(0x9e3779b97f4a7c15) ^ coordinates[1] * UINT64_C(0xc2b2ae3d27d4eb4f);
		hash ^= hash >> 32;
		std::size_t slot = hash & (slots.size() - 1);
		while (slots[slot] != no_search_id) {
			if (cells[slots[slot]].coordinates == coordinates)
				return slots[slot];
			slot = (slot + 1) & (slots.size() - 1);
		}
		assert(cells.size() < max_cells);
		auto id = static_cast<SearchId>(cells.size());
		cells.push_back({coordinates, {}, {}});
		slots[slot] = id;
		return id;
	}
	void push(SearchEntry entry) {
		queue.push_back(entry);
		std::push_heap(queue.begin(), queue.end(), std::greater<SearchEntry>{});
	}
	SearchEntry pop() {
		std::pop_heap(queue.begin(), queue.end(), std::greater<SearchEntry>{});
		auto entry = queue.back();
		queue.pop_back();
		return entry;
	}
};
// Build visibility coordinates lazily and cap expansion for interactive dragging.
Path search(Point start, Point end, const std::vector<Rect>& obstacles, const Segments& occupied, const Segments& shared, double grid,
			RouteGeometry& geometry) {
	// Standalone bindings may run concurrently with the GIL released. Each
	// thread reuses its own arena, with no shared mutable search state.
	thread_local SearchWorkspace workspace;
	workspace.reset();
	auto& xs = workspace.xs;
	auto& ys = workspace.ys;
	xs.insert(xs.end(), {start[0], end[0]});
	ys.insert(ys.end(), {start[1], end[1]});
	for (const auto& r : obstacles) {
		xs.insert(xs.end(), {r[0], r[2]});
		ys.insert(ys.end(), {r[1], r[3]});
	}
	for (const auto& s : occupied)
		for (auto p : s)
			for (double offset : {-grid, 0.0, grid}) {
				xs.push_back(p[0] + offset);
				ys.push_back(p[1] + offset);
			}
	for (auto coordinates : {&xs, &ys}) {
		std::sort(coordinates->begin(), coordinates->end());
		coordinates->erase(std::unique(coordinates->begin(), coordinates->end()), coordinates->end());
	}
	SearchCell origin{static_cast<std::size_t>(std::lower_bound(xs.begin(), xs.end(), start[0]) - xs.begin()),
					  static_cast<std::size_t>(std::lower_bound(ys.begin(), ys.end(), start[1]) - ys.begin())};
	SearchCell target{static_cast<std::size_t>(std::lower_bound(xs.begin(), xs.end(), end[0]) - xs.begin()),
					  static_cast<std::size_t>(std::lower_bound(ys.begin(), ys.end(), end[1]) - ys.begin())};
	// Reaching a cell horizontally or vertically can have different future bend
	// costs. Keep both arrivals rather than discarding one based on length alone.
	SearchId initial = workspace.cell(origin) * 3;
	std::size_t serial = 0;
	workspace.push({{0, 0}, serial++, initial});
	workspace.cells[initial / 3].states[initial % 3].distance = {0, 0};
	std::size_t settled = 0;
	// Allow two arrival axes for the previous budget of 512 visibility cells.
	while (!workspace.queue.empty() && settled < search_limit) {
		auto state = std::get<2>(workspace.pop());
		auto cell_id = state / 3;
		auto& cell = workspace.cells[cell_id];
		auto& record = cell.states[state % 3];
		auto node = cell.coordinates;
		if (record.settled)
			continue;
		record.settled = true;
		++settled;
		if (node == target) {
			Path path;
			while (state != no_search_id) {
				const auto& previous_cell = workspace.cells[state / 3];
				auto coordinates = previous_cell.coordinates;
				path.push_back({xs[coordinates[0]], ys[coordinates[1]]});
				state = previous_cell.states[state % 3].previous;
			}
			std::reverse(path.begin(), path.end());
			return simplify(path);
		}
		Point point{xs[node[0]], ys[node[1]]};
		constexpr std::array<std::array<int, 2>, 4> offsets{{{-1, 0}, {1, 0}, {0, 1}, {0, -1}}};
		for (std::size_t direction = 0; direction < offsets.size(); ++direction) {
			auto offset = offsets[direction];
			if ((offset[0] < 0 && node[0] == 0) || (offset[0] > 0 && node[0] + 1 == xs.size()) ||
				(offset[1] < 0 && node[1] == 0) || (offset[1] > 0 && node[1] + 1 == ys.size()))
				continue;
			auto i = node[0] + offset[0], j = node[1] + offset[1];
			auto axis = offset[0] ? 1u : 2u;
			auto& edge = cell.edges[direction];
			if (edge.neighbor == no_search_id) {
				edge.neighbor = workspace.cell({i, j});
				workspace.cells[edge.neighbor].edges[direction ^ 1].neighbor = cell_id;
			}
			SearchId next = edge.neighbor * 3 + axis;
			Point neighbor{xs[i], ys[j]};
			if (!edge.status) {
				edge.status = geometry.blocked(point, neighbor) ? 1 : 2;
				if (edge.status == 2)
					edge.cost = geometry.cost(point, neighbor);
				auto& reverse = workspace.cells[edge.neighbor].edges[direction ^ 1];
				reverse.status = edge.status;
				reverse.cost = edge.cost;
			}
			if (edge.status == 1)
				continue;
			auto step = edge.cost, old = record.distance;
			double turn = state % 3 && state % 3 != axis ? bend_penalty : 0;
			Cost cost{old.first + step.first, old.second + step.second + turn};
			auto& next_record = workspace.cells[edge.neighbor].states[axis];
			if (cost < next_record.distance) {
				next_record.distance = cost;
				next_record.previous = state;
				workspace.push({{cost.first, cost.second + length(neighbor, end) * (shared.empty() ? 1 : 0.25)}, serial++, next});
			}
		}
	}
	return {};
}
} // namespace

bool contains(const Rect& r, const Point& p) {
	return r[0] < p[0] && p[0] < r[2] && r[1] < p[1] && p[1] < r[3];
}
bool intersects(const Rect& a, const Rect& b) {
	return a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
}
Rect expanded(Rect r, double d) {
	return {r[0] - d, r[1] - d, r[2] + d, r[3] + d};
}
Rect bounds(const Path& path, double margin) {
	if (path.empty())
		return {0, 0, 0, 0};
	Rect result{path[0][0], path[0][1], path[0][0], path[0][1]};
	for (auto p : path) {
		result[0] = std::min(result[0], p[0]);
		result[1] = std::min(result[1], p[1]);
		result[2] = std::max(result[2], p[0]);
		result[3] = std::max(result[3], p[1]);
	}
	return expanded(result, margin);
}
bool clear(const Path& path, const std::vector<Rect>& obstacles) {
	if (path.empty())
		return false;
	for (std::size_t i = 1; i < path.size(); ++i)
		if (blocked(path[i - 1], path[i], obstacles))
			return false;
	return true;
}
double overlap(const Segment& s, const Segment& t) {
	auto a = s[0], b = s[1], c = t[0], d = t[1];
	int axis;
	if (a[1] == b[1] && b[1] == c[1] && c[1] == d[1])
		axis = 0;
	else if (a[0] == b[0] && b[0] == c[0] && c[0] == d[0])
		axis = 1;
	else
		return 0;
	return std::max(0.0,
					std::min(std::max(a[axis], b[axis]), std::max(c[axis], d[axis])) -
						std::max(std::min(a[axis], b[axis]), std::min(c[axis], d[axis])));
}
Cost route_cost(const Path& path, const Segments& occupied, const Segments& shared, double grid) {
	Cost result{0, 0};
	for (std::size_t i = 1; i < path.size(); ++i) {
		auto c = segment_cost(path[i - 1], path[i], occupied, shared, grid);
		result.first += c.first;
		result.second += c.second;
	}
	if (path.size() > 2)
		result.second += bend_penalty * (path.size() - 2);
	return result;
}
Path orthogonal(Point start, Point end, const std::vector<Rect>& obstacles, const Segments& occupied, const Segments& shared, double grid) {
	for (auto r : obstacles)
		if (contains(r, start) || contains(r, end))
			return {};
	if (start == end)
		return {start};
	if (shared.empty() && (start[0] == end[0] || start[1] == end[1]) && !blocked(start, end, obstacles) &&
		segment_cost(start, end, occupied, shared, grid).first == 0)
		return {start, end};
	Path best;
	RouteGeometry geometry(obstacles, occupied, shared, grid);
	Cost best_cost{std::numeric_limits<double>::infinity(), std::numeric_limits<double>::infinity()};
	auto consider = [&](Path path) {
		path = simplify(path);
		if (!geometry.clear(path))
			return;
		auto c = geometry.cost(path);
		if (c < best_cost) {
			best = std::move(path);
			best_cost = c;
		}
	};
	// Resolve ordinary elbows and centered lanes before enumerating every
	// obstacle coordinate. A clear shortest two-bend path cannot be improved
	// once both one-bend possibilities have been scored (without trunk reuse).
	consider({start, {end[0], start[1]}, end});
	consider({start, {start[0], end[1]}, end});
	consider({start, {(start[0] + end[0]) / 2, start[1]}, {(start[0] + end[0]) / 2, end[1]}, end});
	consider({start, {start[0], (start[1] + end[1]) / 2}, {end[0], (start[1] + end[1]) / 2}, end});
	if (shared.empty() && !best.empty() && best_cost.first == 0 && best_cost.second <= length(start, end) + 2 * bend_penalty)
		return best;
	// Collect global visibility coordinates only when the simple routes fail.
	std::set<double> xs{(start[0] + end[0]) / 2, start[0], end[0]}, ys{(start[1] + end[1]) / 2, start[1], end[1]};
	for (auto r : obstacles) {
		xs.insert(r[0]);
		xs.insert(r[2]);
		ys.insert(r[1]);
		ys.insert(r[3]);
	}
	for (auto s : occupied) {
		if (s[0][0] == s[1][0]) {
			xs.insert(s[0][0] - grid);
			xs.insert(s[0][0] + grid);
		} else {
			ys.insert(s[0][1] - grid);
			ys.insert(s[0][1] + grid);
		}
	}
	for (auto s : shared)
		for (auto p : s) {
			xs.insert(p[0]);
			ys.insert(p[1]);
		}
	// Cheap straight/elbow/two-bend candidates resolve most wires without search.
	for (auto x : xs)
		consider({start, {x, start[1]}, {x, end[1]}, end});
	for (auto y : ys)
		consider({start, {start[0], y}, {end[0], y}, end});
	if (!best.empty() && best_cost.first == 0)
		return best;
	auto found = search(start, end, obstacles, occupied, shared, grid, geometry);
	if (!found.empty() && (best.empty() || geometry.cost(found) < best_cost))
		return found;
	return best;
}
Path prefix(const Path& path, double fraction) {
	double remaining = 0;
	for (std::size_t i = 1; i < path.size(); ++i)
		remaining += length(path[i - 1], path[i]);
	remaining *= fraction;
	Path result;
	for (auto p : path) {
		if (!result.empty()) {
			auto a = result.back();
			double distance = length(a, p);
			if (distance > remaining) {
				result.push_back({a[0] + remaining / distance * (p[0] - a[0]), a[1] + remaining / distance * (p[1] - a[1])});
				break;
			}
			remaining -= distance;
		}
		result.push_back(p);
	}
	return result;
}
std::set<Point> junctions(const std::vector<Path>& paths) {
	std::set<Point> candidates, result;
	Segments all;
	for (const auto& path : paths) {
		candidates.insert(path.begin(), path.end());
		auto s = segments(path);
		all.insert(all.end(), s.begin(), s.end());
	}
	for (auto s : all)
		if (s[0][1] == s[1][1])
			for (auto t : all)
				if (t[0][0] == t[1][0]) {
					Point p{t[0][0], s[0][1]};
					if (std::min(s[0][0], s[1][0]) <= p[0] && p[0] <= std::max(s[0][0], s[1][0]) && std::min(t[0][1], t[1][1]) <= p[1] &&
						p[1] <= std::max(t[0][1], t[1][1]))
						candidates.insert(p);
				}
	for (auto p : candidates) {
		unsigned directions = 0;
		for (auto s : all) {
			auto a = s[0], b = s[1];
			if (a[1] == b[1] && a[1] == p[1] && std::min(a[0], b[0]) <= p[0] && p[0] <= std::max(a[0], b[0])) {
				if (std::min(a[0], b[0]) < p[0])
					directions |= 1;
				if (p[0] < std::max(a[0], b[0]))
					directions |= 2;
			}
			if (a[0] == b[0] && a[0] == p[0] && std::min(a[1], b[1]) <= p[1] && p[1] <= std::max(a[1], b[1])) {
				if (std::min(a[1], b[1]) < p[1])
					directions |= 4;
				if (p[1] < std::max(a[1], b[1]))
					directions |= 8;
			}
		}
		int count = 0;
		for (; directions; directions >>= 1)
			count += directions & 1;
		if (count >= 3)
			result.insert(p);
	}
	return result;
}
std::pair<Path, bool> signal_route(Point start, Point end, Point sd, Point td, const std::vector<Rect>& boxes,
								   const std::vector<Rect>& ports, const Segments& occupied, const Segments& shared, const Path& parent,
								   double fraction, double grid) {
	auto obstacles = boxes;
	obstacles.insert(obstacles.end(), ports.begin(), ports.end());
	Point a{start[0] + sd[0] * grid, start[1] + sd[1] * grid}, b{end[0] + td[0] * grid, end[1] + td[1] * grid};
	Segments stubs{{start, a}, {b, end}};
	Path trunk = prefix(parent, fraction);
	if (!trunk.empty()) {
		a = trunk.back();
		stubs = segments(parent);
		stubs.push_back({b, end});
	}
	auto complete = [&](const Path& middle, bool forced = false) {
		if (middle.empty())
			return Path{};
		Path p = trunk.empty() ? Path{start} : Path(trunk.begin(), trunk.end() - 1);
		p.insert(p.end(), middle.begin(), middle.end());
		if (forced)
			p.push_back(end);
		p.erase(std::unique(p.begin(), p.end()), p.end());
		return p;
	};
	Point fs = trunk.empty() ? start : trunk.back();
	Segments constraints = occupied;
	if (!trunk.empty())
		constraints.insert(constraints.end(), stubs.begin(), stubs.end() - 1);
	Path points, direct{fs, end};
	if (fs != end && (fs[0] == end[0] || fs[1] == end[1]) && clear(direct, obstacles) &&
		route_cost(direct, constraints, shared, grid).first == 0)
		points = complete(direct);
	else {
		auto reserved = occupied;
		reserved.insert(reserved.end(), stubs.begin(), stubs.end());
		points = complete(orthogonal(a, b, obstacles, reserved, shared, grid), true);
		if (!clear(points, obstacles))
			points.clear();
	}
	if (points.empty() || route_cost(points, occupied, shared, grid).first > 0) {
		auto flexible = complete(orthogonal(fs, end, obstacles, constraints, shared, grid));
		if (!flexible.empty() &&
			(points.empty() || route_cost(flexible, occupied, shared, grid) < route_cost(points, occupied, shared, grid)))
			points = std::move(flexible);
	}
	bool is_blocked = false;
	if (points.empty()) {
		std::vector<Rect> bodies;
		for (auto r : boxes)
			bodies.push_back(expanded(r, -6));
		bodies.insert(bodies.end(), ports.begin(), ports.end());
		points = complete(orthogonal(fs, end, bodies, constraints, shared, grid));
		if (points.empty()) {
			is_blocked = true;
			points = complete(orthogonal(fs, end, ports, constraints, shared, grid));
		}
	}
	if (points.size() < 2) {
		std::vector<Path> loops, clean, port_clean;
		for (double dx : {-grid, grid})
			for (double dy : {-grid, grid}) {
				Path p{fs, {fs[0] + dx, fs[1]}, {fs[0] + dx, fs[1] + dy}, {fs[0], fs[1] + dy}, fs};
				loops.push_back(p);
				if (clear(p, obstacles))
					clean.push_back(p);
				if (clear(p, ports))
					port_clean.push_back(p);
			}
		is_blocked = clean.empty();
		const auto& candidates = !clean.empty() ? clean : (!port_clean.empty() ? port_clean : loops);
		points = *std::min_element(candidates.begin(), candidates.end(), [&](const Path& x, const Path& y) {
			return route_cost(x, occupied, shared, grid) < route_cost(y, occupied, shared, grid);
		});
	}
	if (!clear(points, ports)) {
		is_blocked = true;
		points = orthogonal(start, end, ports, occupied, shared, grid);
	}
	return {points, is_blocked};
}
} // namespace asic::gui
