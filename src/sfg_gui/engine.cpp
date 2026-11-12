#include "engine.hpp"

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <stdexcept>

namespace asic::gui {
namespace {
void finite(double x) {
	if (!std::isfinite(x))
		throw std::invalid_argument("Geometry must be finite");
}
void positive(double x) {
	finite(x);
	if (x <= 0)
		throw std::invalid_argument("Grid, spacing and sizes must be positive");
}
void point(Point p) {
	for (auto x : p)
		finite(x);
}
Rect port_box(Point p) {
	return {p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6};
}
template <class Map>
std::set<Id> keys(const Map& map) {
	std::set<Id> result;
	for (const auto& item : map)
		result.insert(item.first);
	return result;
}
template <class Map>
void remove_ids(Map& map, std::vector<Id>& order, const std::vector<Id>& removed) {
	for (auto id : removed)
		map.erase(id);
	order.erase(std::remove_if(order.begin(), order.end(), [&](auto id) { return !map.count(id); }), order.end());
}
void reserve(std::set<Segment>& segments, const Path& path) {
	for (std::size_t i = 1; i < path.size(); ++i)
		if (path[i - 1] != path[i])
			segments.insert(path[i - 1] < path[i] ? Segment{path[i - 1], path[i]} : Segment{path[i], path[i - 1]});
}
} // namespace

Engine::Engine(double grid, double spacing)
	: grid_(grid)
	, spacing_(spacing) {
	positive(grid);
	positive(spacing);
}
void Engine::update(const std::vector<NodeRecord>& nodes, const std::vector<PortRecord>& ports, const std::vector<WireRecord>& wires,
					const std::vector<Id>& removed_nodes, const std::vector<Id>& removed_ports, const std::vector<Id>& removed_wires) {
	std::lock_guard<std::mutex> lock(mutex_);
	// Validate the entire transaction before mutating persistent state.
	auto node_ids = keys(nodes_), port_ids = keys(ports_), wire_ids = keys(wires_);
	for (auto id : removed_nodes)
		node_ids.erase(id);
	for (auto id : removed_ports)
		port_ids.erase(id);
	for (auto id : removed_wires)
		wire_ids.erase(id);
	std::map<Id, Port> next_ports;
	std::map<Id, std::pair<Id, Id>> links;
	for (const auto& [id, w] : wires_)
		if (wire_ids.count(id))
			links[id] = {w.source, w.parent};
	for (const auto& record : nodes) {
		const auto& [id, box, size, delay, default_rotation, rotation, flipped, terminal] = record;
		if (!id)
			throw std::invalid_argument("Zero is reserved for no parent");
		for (auto x : box)
			finite(x);
		positive(size[0]);
		positive(size[1]);
		if (box[0] >= box[2] || box[1] >= box[3] || default_rotation % 90 || rotation % 90 || terminal < TerminalKind::Operation ||
			terminal > TerminalKind::Sink)
			throw std::invalid_argument("Invalid operation geometry or rotation");
		node_ids.insert(id);
	}
	for (const auto& record : ports) {
		const auto& [id, node, position, direction] = record;
		point(position);
		point(direction);
		if (!id || !node_ids.count(node))
			throw std::invalid_argument("Port refers to an unknown operation");
		if (std::abs(direction[0]) + std::abs(direction[1]) != 1 || (direction[0] != 0 && direction[1] != 0))
			throw std::invalid_argument("Port direction must be an axis unit vector");
		port_ids.insert(id);
		next_ports[id] = {node, position, direction};
	}
	for (const auto& [id, p] : ports_)
		if (port_ids.count(id) && !next_ports.count(id) && !node_ids.count(p.node))
			throw std::invalid_argument("Remove an operation's ports with it");
	for (const auto& record : wires) {
		const auto& [id, source, target, parent, fraction] = record;
		finite(fraction);
		if (!id || !port_ids.count(source) || !port_ids.count(target) || fraction < 0 || fraction > 1)
			throw std::invalid_argument("Invalid wire endpoints or branch fraction");
		wire_ids.insert(id);
		links[id] = {source, parent};
	}
	for (const auto& [id, w] : wires_)
		if (wire_ids.count(id) && !std::any_of(wires.begin(), wires.end(), [&](const auto& r) { return std::get<0>(r) == id; }) &&
			(!port_ids.count(w.source) || !port_ids.count(w.target)))
			throw std::invalid_argument("Remove a port's wires with it");
	for (const auto& [id, link] : links) {
		std::set<Id> seen;
		Id parent = id;
		while (parent) {
			if (!seen.insert(parent).second)
				throw std::invalid_argument("Cyclic branch parent");
			auto it = links.find(parent);
			if (it == links.end() || it->second.first != link.first)
				throw std::invalid_argument("Branch parent must exist and share its source");
			parent = it->second.second;
		}
	}
	for (auto id : removed_nodes)
		if (nodes_.count(id))
			dirty_regions_.push_back(expanded(nodes_.at(id).box, 6));
	for (auto id : removed_ports)
		if (ports_.count(id))
			dirty_regions_.push_back(port_box(ports_.at(id).position));
	if (!removed_nodes.empty() || !removed_ports.empty() || !removed_wires.empty())
		topology_dirty_ = true;
	remove_ids(nodes_, node_order_, removed_nodes);
	remove_ids(wires_, wire_order_, removed_wires);
	for (auto id : removed_ports)
		ports_.erase(id);
	for (const auto& record : nodes) {
		const auto& [id, box, size, delay, default_rotation, rotation, flipped, terminal] = record;
		auto it = nodes_.find(id);
		if (it == nodes_.end()) {
			node_order_.push_back(id);
			topology_dirty_ = true;
		} else
			dirty_regions_.push_back(expanded(it->second.box, 6));
		dirty_regions_.push_back(expanded(box, 6));
		nodes_[id] = {box, size, delay, default_rotation, rotation, flipped, terminal};
	}
	for (const auto& record : ports) {
		const auto& [id, node, position, direction] = record;
		if (ports_.count(id))
			dirty_regions_.push_back(port_box(ports_.at(id).position));
		else
			topology_dirty_ = true;
		dirty_regions_.push_back(port_box(position));
		ports_[id] = {node, position, direction};
		for (const auto& [wire_id, w] : wires_)
			if (w.source == id || w.target == id)
				dirty_wires_.insert(wire_id);
	}
	for (const auto& record : wires) {
		const auto& [id, source, target, parent, fraction] = record;
		if (!wires_.count(id)) {
			wire_order_.push_back(id);
			wires_[id] = {source, target, parent, fraction, {}, false};
			topology_dirty_ = true;
		} else {
			auto& w = wires_.at(id);
			w.source = source;
			w.target = target;
			w.parent = parent;
			w.fraction = fraction;
		}
		dirty_wires_.insert(id);
	}
}
RouteResult Engine::route(bool incremental, bool force) {
	std::lock_guard<std::mutex> lock(mutex_);
	crossing_updates_.clear();
	if (!force && !topology_dirty_ && dirty_regions_.empty() && dirty_wires_.empty() && incremental == last_incremental_)
		return {};
	std::set<Id> dirty_sources;
	bool full = force || !incremental || topology_dirty_;
	for (const auto& [id, w] : wires_) {
		auto path_bounds = bounds(w.path, grid_);
		if (full || dirty_wires_.count(id) || w.path.empty() ||
			std::any_of(dirty_regions_.begin(), dirty_regions_.end(), [&](auto r) { return intersects(path_bounds, r); }))
			dirty_sources.insert(w.source);
	}
	std::vector<Rect> boxes;
	for (auto id : node_order_)
		boxes.push_back(expanded(nodes_.at(id).box, 6));
	std::map<Id, std::set<Segment>> reservations;
	for (auto id : wire_order_) {
		const auto& w = wires_.at(id);
		if (!dirty_sources.count(w.source))
			reserve(reservations[w.source], w.path);
	}
	std::vector<Id> order;
	std::set<Id> seen;
	std::function<void(Id)> visit = [&](Id id) {
		if (!seen.insert(id).second)
			return;
		const auto& w = wires_.at(id);
		if (w.parent)
			visit(w.parent);
		order.push_back(id);
	};
	for (auto id : wire_order_)
		visit(id);
	RouteResult result;
	routed_last_ = updated_last_ = 0;
	routed_ids_.clear();
	for (auto id : order) {
		auto& w = wires_.at(id);
		if (dirty_sources.count(w.source)) {
			Segments occupied, shared;
			for (const auto& [source, segments] : reservations) {
				auto& into = source == w.source ? shared : occupied;
				into.insert(into.end(), segments.begin(), segments.end());
			}
			std::vector<Rect> port_boxes;
			for (const auto& [port_id, p] : ports_)
				if (port_id != w.source && port_id != w.target)
					port_boxes.push_back(port_box(p.position));
			const auto& source = ports_.at(w.source);
			const auto& target = ports_.at(w.target);
			auto routed = signal_route(source.position,
									   target.position,
									   source.direction,
									   target.direction,
									   boxes,
									   port_boxes,
									   occupied,
									   shared,
									   w.parent ? wires_.at(w.parent).path : Path{},
									   w.fraction,
									   grid_);
			++routed_last_;
			routed_ids_.push_back(id);
			if (routed.first != w.path || routed.second != w.blocked) {
				w.path = std::move(routed.first);
				w.blocked = routed.second;
				result.first.emplace_back(id, w.path, w.blocked);
				++updated_last_;
			}
		}
		reserve(reservations[w.source], w.path);
	}
	std::map<Id, std::vector<Path>> paths;
	for (const auto& [id, w] : wires_)
		paths[w.source].push_back(w.path);
	for (auto it = junctions_.begin(); it != junctions_.end();)
		if (!paths.count(it->first))
			it = junctions_.erase(it);
		else
			++it;
	for (auto source : dirty_sources)
		if (paths.count(source))
			junctions_[source] = paths.at(source).size() > 1 ? junctions(paths.at(source)) : std::set<Point>{};
	std::set<Point> dots;
	for (const auto& [source, points] : junctions_)
		dots.insert(points.begin(), points.end());
	if (dots != last_junctions_) {
		result.second = Path(dots.begin(), dots.end());
		last_junctions_ = std::move(dots);
	}
	// Sweep vertical segments through horizontal rows. Only unrelated nets
	// receive crossing gaps; shared trunks keep their junction dots intact.
	using Track = std::tuple<Id, Id, double, double>;
	std::map<double, std::vector<Track>> horizontal;
	for (const auto& [id, w] : wires_)
		for (std::size_t i = 1; i < w.path.size(); ++i) {
			auto a = w.path[i - 1], b = w.path[i];
			if (a[1] == b[1] && a[0] != b[0])
				horizontal[a[1]].emplace_back(id, w.source, std::min(a[0], b[0]), std::max(a[0], b[0]));
		}
	std::map<Id, Path> crossings;
	std::map<Id, std::set<Point>> crossing_points;
	for (const auto& [id, w] : wires_) {
		for (std::size_t i = 1; i < w.path.size(); ++i) {
			auto a = w.path[i - 1], b = w.path[i];
			if (a[0] != b[0] || a[1] == b[1])
				continue;
			for (auto row = horizontal.lower_bound(std::min(a[1], b[1]));
				 row != horizontal.end() && row->first <= std::max(a[1], b[1]); ++row)
				for (const auto& [other, source, left, right] : row->second)
					if (source != w.source && left <= a[0] && a[0] <= right) {
						Point p{a[0], row->first};
						// Keep actual branch dots and corners continuous. Break
						// the other wire when the vertical net owns the junction.
						bool vertical_junction = junctions_.count(w.source) && junctions_.at(w.source).count(p);
						crossing_points[vertical_junction || p == a || p == b ? other : id].insert(p);
					}
		}
	}
	for (const auto& [id, points] : crossing_points)
		crossings[id] = Path(points.begin(), points.end());
	for (const auto& [id, w] : wires_) {
		auto old = crossings_.find(id), next = crossings.find(id);
		if (old == crossings_.end() && next == crossings.end())
			continue;
		if (old == crossings_.end() || next == crossings.end() || old->second != next->second)
			crossing_updates_.emplace_back(id, next == crossings.end() ? Path{} : next->second);
	}
	crossings_ = std::move(crossings);
	dirty_regions_.clear();
	dirty_wires_.clear();
	topology_dirty_ = false;
	last_incremental_ = incremental;
	return result;
}
std::vector<LayoutUpdate> Engine::layout() {
	std::lock_guard<std::mutex> lock(mutex_);
	const auto count = node_order_.size();
	std::map<Id, std::size_t> indices;
	std::vector<Point> sizes, positions(count);
	std::vector<bool> delays;
	for (auto id : node_order_) {
		indices[id] = sizes.size();
		sizes.push_back(nodes_.at(id).size);
		delays.push_back(nodes_.at(id).delay);
	}
	Edges edges;
	for (auto id : wire_order_) {
		const auto& w = wires_.at(id);
		edges.push_back({indices.at(ports_.at(w.source).node), indices.at(ports_.at(w.target).node)});
	}
	Graph graph(count, edges);
	auto heads = vertical_feedback(graph, delays);
	std::vector<bool> stacked(count);
	for (std::size_t head = 0; head < count; ++head)
		if (heads[head]) {
			auto reachable = [&](const auto& links) {
				std::vector<bool> seen(count);
				std::vector<std::size_t> pending{head};
				seen[head] = true;
				for (std::size_t i = 0; i < pending.size(); ++i)
					for (auto m : links[pending[i]])
						if (!seen[m]) {
							seen[m] = true;
							pending.push_back(m);
						}
				return seen;
			};
			auto next = reachable(graph.next), previous = reachable(graph.previous);
			for (std::size_t n = 0; n < count; ++n)
				stacked[n] = stacked[n] || (next[n] && previous[n]);
		}
	// Terminal leaves should not create fork bands or pull the main flow down.
	// Place the operation graph first, then attach terminals to actual pin axes.
	std::vector<std::size_t> core, mapping(count, count);
	std::vector<Point> core_sizes;
	std::vector<bool> core_delays, core_heads;
	for (std::size_t n = 0; n < count; ++n)
		if (nodes_.at(node_order_[n]).terminal == TerminalKind::Operation || nodes_.at(node_order_[n]).terminal == TerminalKind::Input) {
			mapping[n] = core.size();
			core.push_back(n);
			core_sizes.push_back(sizes[n]);
			core_delays.push_back(delays[n]);
			core_heads.push_back(heads[n]);
		}
	Edges core_edges;
	for (auto edge : edges)
		if (mapping[edge[0]] < count && mapping[edge[1]] < count)
			core_edges.push_back({mapping[edge[0]], mapping[edge[1]]});
	Graph core_graph(core.size(), core_edges);
	core_delays = feedback(core_graph, core_delays);
	auto initial = place(core_graph, core_sizes, core_delays, spacing_, grid_, core_heads);
	auto angles = orient(core_graph, initial, core_sizes, core_delays, spacing_);
	std::vector<std::pair<int, bool>> orientations(count, {0, false});
	bool sizes_changed = false;
	for (std::size_t i = 0; i < core.size(); ++i) {
		auto n = core[i];
		auto angle = nodes_.at(node_order_[n]).default_rotation;
		if (stacked[n] && !delays[n])
			angles[i] = {angle ? angle : 90, false};
		else if (angle)
			angles[i] = {angle, false};
		orientations[n] = angles[i];
		if (angles[i].first % 180) {
			sizes_changed |= core_sizes[i][0] != core_sizes[i][1];
			std::swap(core_sizes[i][0], core_sizes[i][1]);
		}
		sizes[n] = core_sizes[i];
	}
	auto placed_core = sizes_changed ? place(core_graph, core_sizes, core_delays, spacing_, grid_, core_heads) : std::move(initial);
	std::vector<bool> placed(count);
	double bottom = 3 * spacing_;
	for (std::size_t i = 0; i < core.size(); ++i) {
		auto n = core[i];
		positions[n] = placed_core[i];
		placed[n] = true;
		bottom = std::max(bottom, positions[n][1] + sizes[n][1]);
	}
	// Leave a local source gutter before its consumer's column. Without this
	// space, collision avoidance pushes constants back past the whole design.
	std::map<double, std::set<Id>> gutters;
	for (auto wire_id : wire_order_) {
		const auto& w = wires_.at(wire_id);
		auto source = ports_.at(w.source).node;
		auto target = indices.at(ports_.at(w.target).node);
		if (nodes_.at(source).terminal == TerminalKind::LocalSource && placed[target])
			gutters[positions[target][0]].insert(source);
	}
	std::vector<double> shifts(count);
	for (const auto& [column, sources] : gutters) {
		double width = 0;
		for (auto source : sources)
			width += nodes_.at(source).size[0] + 2 * grid_;
		for (auto n : core)
			if (positions[n][0] >= column)
				shifts[n] += width;
	}
	for (auto n : core)
		positions[n][0] += shifts[n];
	if (core.empty())
		positions = place(graph, sizes, std::vector<bool>(count), spacing_, grid_);
	// Recover each pin's centered local coordinate from retained scene geometry,
	// then apply the proposed flip/rotation. No Qt queries or callbacks are needed.
	auto rotate = [](Point p, int angle) {
		for (int turn = 0; turn < ((angle % 360 + 360) % 360) / 90; ++turn)
			p = {-p[1], p[0]};
		return p;
	};
	auto pin_offset = [&](Id id) {
		const auto& port = ports_.at(id);
		const auto& node = nodes_.at(port.node);
		auto n = indices.at(port.node);
		Point p{port.position[0] - (node.box[0] + node.box[2]) / 2, port.position[1] - (node.box[1] + node.box[3]) / 2};
		p = rotate(p, -node.rotation);
		if (node.flipped != orientations[n].second)
			p[0] = -p[0];
		p = rotate(p, orientations[n].first);
		return Point{p[0] + sizes[n][0] / 2, p[1] + sizes[n][1] / 2};
	};
	auto snap = [&](double x) {
		return grid_ * std::nearbyint(x / grid_);
	};
	auto pin_direction = [&](Id id) {
		const auto& port = ports_.at(id);
		const auto& node = nodes_.at(port.node);
		auto n = indices.at(port.node);
		auto p = rotate(port.direction, -node.rotation);
		if (node.flipped != orientations[n].second)
			p[0] = -p[0];
		return rotate(p, orientations[n].first);
	};
	for (auto kind : {TerminalKind::Input, TerminalKind::LocalSource, TerminalKind::Output, TerminalKind::Sink})
		for (std::size_t n = 0; n < count; ++n)
			if (nodes_.at(node_order_[n]).terminal == kind) {
				bool source = kind == TerminalKind::Input || kind == TerminalKind::LocalSource;
				bool local = kind == TerminalKind::LocalSource || kind == TerminalKind::Sink;
				bool left = source;
				double x = 0, y = 0;
				std::size_t neighbors = 0;
				for (auto wire_id : wire_order_) {
					const auto& w = wires_.at(wire_id);
					auto own = source ? w.source : w.target;
					auto other = source ? w.target : w.source;
					if (ports_.at(own).node != node_order_[n])
						continue;
					auto m = indices.at(ports_.at(other).node);
					if (!placed[m])
						continue;
					auto offset = pin_offset(other);
					if (local && !neighbors) {
						auto direction = pin_direction(other);
						left = direction[0] < 0 || (direction[0] == 0 && offset[0] < sizes[m][0] / 2);
						orientations[n] = {(source != left) ? 180 : 0, false};
					}
					auto own_offset = pin_offset(own);
					y += positions[m][1] + offset[1] - own_offset[1];
					double candidate;
					if (local)
						candidate = positions[m][0] + offset[0] - own_offset[0] + (left ? -2 : 2) * spacing_;
					else
						candidate = source ? positions[m][0] - sizes[n][0] - 3 * spacing_ : positions[m][0] + sizes[m][0] + 3 * spacing_;
					x = !neighbors ? candidate : (left ? std::min(x, candidate) : std::max(x, candidate));
					++neighbors;
				}
				Point desired;
				if (neighbors)
					desired = {snap(x), snap(y / neighbors)};
				else if (core.empty() || placed[n])
					desired = positions[n];
				else {
					desired = {snap(3 * spacing_), snap(bottom + 4 * spacing_)};
					bottom = desired[1] + sizes[n][1];
				}
				if (kind == TerminalKind::Input && placed[n])
					desired[0] = std::min(desired[0], positions[n][0]);
				// Keep the pin's height, using space on the appropriate side of its
				// actual producer/consumer rather than a global source/sink column.
				for (;;) {
					bool collision = false;
					for (std::size_t m = 0; m < count; ++m)
						if (placed[m] && m != n) {
							Rect a{desired[0], desired[1], desired[0] + sizes[n][0], desired[1] + sizes[n][1]};
							Rect b{positions[m][0], positions[m][1], positions[m][0] + sizes[m][0], positions[m][1] + sizes[m][1]};
							if (intersects(expanded(a, local ? grid_ : spacing_), b)) {
								desired[0] = grid_ *
									(left ? std::floor((b[0] - sizes[n][0] - 3 * spacing_) / grid_) :
											std::ceil((b[2] + 3 * spacing_) / grid_));
								collision = true;
								break;
							}
						}
					if (!collision)
						break;
				}
				positions[n] = desired;
				placed[n] = true;
			}
	std::vector<LayoutUpdate> result;
	for (std::size_t i = 0; i < count; ++i)
		result.emplace_back(node_order_[i], positions[i], orientations[i].first, orientations[i].second);
	return result;
}
void Engine::reset() {
	std::lock_guard<std::mutex> lock(mutex_);
	nodes_.clear();
	ports_.clear();
	wires_.clear();
	node_order_.clear();
	wire_order_.clear();
	dirty_regions_.clear();
	dirty_wires_.clear();
	junctions_.clear();
	last_junctions_.clear();
	crossings_.clear();
	crossing_updates_.clear();
	routed_ids_.clear();
	routed_last_ = updated_last_ = 0;
	topology_dirty_ = true;
	last_incremental_ = false;
}
std::map<std::string, std::size_t> Engine::statistics() const {
	std::lock_guard<std::mutex> lock(mutex_);
	std::size_t points = 0;
	for (const auto& [id, w] : wires_)
		points += w.path.size();
	return {{"nodes", nodes_.size()},
			{"ports", ports_.size()},
			{"wires", wires_.size()},
			{"route_points", points},
			{"routed_last", routed_last_},
			{"updated_last", updated_last_}};
}
Path Engine::wire_path(Id id) const {
	std::lock_guard<std::mutex> lock(mutex_);
	if (!wires_.count(id))
		throw std::out_of_range("Unknown wire");
	return wires_.at(id).path;
}
std::vector<Id> Engine::routed_ids() const {
	std::lock_guard<std::mutex> lock(mutex_);
	return routed_ids_;
}
std::vector<std::pair<Id, Path>> Engine::crossing_updates() const {
	std::lock_guard<std::mutex> lock(mutex_);
	return crossing_updates_;
}
} // namespace asic::gui
