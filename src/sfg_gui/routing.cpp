#include "engine.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <queue>

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
// Build visibility coordinates lazily and cap expansion for interactive dragging.
Path search(Point start, Point end, const std::vector<Rect>& obstacles, const Segments& occupied, const Segments& shared, double grid) {
	std::set<double> xx{start[0], end[0]}, yy{start[1], end[1]};
	for (const auto& r : obstacles) {
		xx.insert(r[0]);
		xx.insert(r[2]);
		yy.insert(r[1]);
		yy.insert(r[3]);
	}
	for (const auto& s : occupied)
		for (auto p : s)
			for (double offset : {-grid, 0.0, grid}) {
				xx.insert(p[0] + offset);
				yy.insert(p[1] + offset);
			}
	std::vector<double> xs(xx.begin(), xx.end()), ys(yy.begin(), yy.end());
	using Cell = std::pair<std::size_t, std::size_t>;
	Cell origin{std::lower_bound(xs.begin(), xs.end(), start[0]) - xs.begin(),
				std::lower_bound(ys.begin(), ys.end(), start[1]) - ys.begin()};
	Cell target{std::lower_bound(xs.begin(), xs.end(), end[0]) - xs.begin(), std::lower_bound(ys.begin(), ys.end(), end[1]) - ys.begin()};
	// Reaching a cell horizontally or vertically can have different future bend
	// costs. Keep both arrivals rather than discarding one based on length alone.
	using State = std::pair<Cell, int>; // Incoming axis: 0 at origin, 1 horizontal, 2 vertical.
	State initial{origin, 0};
	using Entry = std::tuple<Cost, std::size_t, State>;
	std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> queue;
	std::size_t serial = 0;
	queue.push({{0, 0}, serial++, initial});
	std::map<State, Cost> distances{{initial, {0, 0}}};
	std::map<State, State> previous;
	std::set<State> settled;
	std::map<Segment, Cost> cache;
	// Allow two arrival axes for the previous budget of 512 visibility cells.
	while (!queue.empty() && settled.size() < 1024) {
		auto state = std::get<2>(queue.top());
		auto node = state.first;
		queue.pop();
		if (!settled.insert(state).second)
			continue;
		if (node == target) {
			Path path{{xs[node.first], ys[node.second]}};
			while (previous.count(state)) {
				state = previous.at(state);
				node = state.first;
				path.push_back({xs[node.first], ys[node.second]});
			}
			std::reverse(path.begin(), path.end());
			return simplify(path);
		}
		Point point{xs[node.first], ys[node.second]};
		for (auto offset : {std::array<int, 2>{-1, 0}, {1, 0}, {0, 1}, {0, -1}}) {
			auto i = static_cast<long>(node.first) + offset[0], j = static_cast<long>(node.second) + offset[1];
			if (i < 0 || j < 0 || i >= static_cast<long>(xs.size()) || j >= static_cast<long>(ys.size()))
				continue;
			int axis = offset[0] ? 1 : 2;
			State next{{static_cast<std::size_t>(i), static_cast<std::size_t>(j)}, axis};
			Point neighbor{xs[i], ys[j]};
			if (blocked(point, neighbor, obstacles))
				continue;
			Segment segment = point < neighbor ? Segment{point, neighbor} : Segment{neighbor, point};
			if (!cache.count(segment))
				cache[segment] = segment_cost(point, neighbor, occupied, shared, grid);
			auto step = cache.at(segment), old = distances.at(state);
			double turn = state.second && state.second != axis ? bend_penalty : 0;
			Cost cost{old.first + step.first, old.second + step.second + turn};
			if (!distances.count(next) || cost < distances.at(next)) {
				distances[next] = cost;
				previous[next] = state;
				queue.push({{cost.first, cost.second + length(neighbor, end) * (shared.empty() ? 1 : 0.25)}, serial++, next});
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
	Path best;
	Cost best_cost{std::numeric_limits<double>::infinity(), std::numeric_limits<double>::infinity()};
	auto consider = [&](Path path) {
		path = simplify(path);
		if (!clear(path, obstacles))
			return;
		auto c = route_cost(path, occupied, shared, grid);
		if (c < best_cost) {
			best = std::move(path);
			best_cost = c;
		}
	};
	// Cheap straight/elbow/two-bend candidates resolve most wires without search.
	for (auto x : xs)
		consider({start, {x, start[1]}, {x, end[1]}, end});
	for (auto y : ys)
		consider({start, {start[0], y}, {end[0], y}, end});
	if (!best.empty() && best_cost.first == 0)
		return best;
	auto found = search(start, end, obstacles, occupied, shared, grid);
	if (!found.empty() && (best.empty() || route_cost(found, occupied, shared, grid) < best_cost))
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
