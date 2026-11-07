#include "engine.hpp"

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <numeric>
#include <stdexcept>

namespace asic::gui {
Graph::Graph(std::size_t count, const Edges& edges)
	: next(count)
	, previous(count) {
	for (auto edge : edges) {
		auto a = edge[0], b = edge[1];
		if (a >= count || b >= count)
			throw std::invalid_argument("Edge refers to an unknown node");
		if (std::find(next[a].begin(), next[a].end(), b) == next[a].end()) {
			next[a].push_back(b);
			previous[b].push_back(a);
		}
	}
}
namespace {
using Index = std::size_t;
std::vector<std::vector<Index>> components(const Graph& g) {
	std::vector<int> index(g.next.size(), -1), low(index);
	std::vector<bool> on_stack(g.next.size());
	std::vector<Index> stack;
	std::vector<std::vector<Index>> result;
	int serial = 0;
	std::function<void(Index)> visit = [&](Index n) {
		low[n] = index[n] = serial++;
		stack.push_back(n);
		on_stack[n] = true;
		for (auto other : g.next[n]) {
			if (index[other] < 0) {
				visit(other);
				low[n] = std::min(low[n], low[other]);
			} else if (on_stack[other])
				low[n] = std::min(low[n], index[other]);
		}
		if (low[n] == index[n]) {
			std::vector<Index> group;
			for (;;) {
				auto other = stack.back();
				stack.pop_back();
				on_stack[other] = false;
				group.push_back(other);
				if (other == n)
					break;
			}
			std::sort(group.begin(), group.end());
			result.push_back(std::move(group));
		}
	};
	for (Index n = 0; n < g.next.size(); ++n)
		if (index[n] < 0)
			visit(n);
	return result;
}
std::vector<Index> topological(const Graph& g, const std::vector<bool>& active) {
	std::vector<Index> degree(g.next.size()), queue, result;
	for (Index n = 0; n < degree.size(); ++n)
		if (active[n]) {
			for (auto p : g.previous[n])
				if (active[p])
					++degree[n];
			if (!degree[n])
				queue.push_back(n);
		}
	for (Index i = 0; i < queue.size(); ++i) {
		auto n = queue[i];
		result.push_back(n);
		for (auto m : g.next[n])
			if (active[m] && !--degree[m])
				queue.push_back(m);
	}
	return result;
}
struct Block {
	std::map<Index, Point> positions;
	Point size{0, 0};
	double axis = 0;
};
// A return-to-entry section has its external waves at one head. Grow such a
// section down the page, with delays in a parallel return lane on the right.
Block stack_feedback(const Graph& g, const std::vector<Index>& members, const std::vector<Point>& sizes, const std::vector<bool>& delays,
					 double spacing) {
	Block block;
	std::set<Index> inside(members.begin(), members.end());
	Index head = members.front();
	for (auto n : members)
		if (!delays[n] && std::any_of(g.previous[n].begin(), g.previous[n].end(), [&](auto m) { return !inside.count(m); })) {
			head = n;
			break;
		}
	// The caller may have removed boundary terminals; the marked head is first.
	std::vector<Index> queue{head};
	std::map<Index, Index> distance{{head, 0}};
	for (Index i = 0; i < queue.size(); ++i) {
		auto n = queue[i];
		auto visit = [&](Index m) {
			if (inside.count(m) && !distance.count(m)) {
				distance[m] = distance[n] + 1;
				queue.push_back(m);
			}
		};
		for (auto m : g.next[n])
			visit(m);
		for (auto m : g.previous[n])
			visit(m);
	}
	std::map<Index, std::vector<Index>> layers;
	for (auto n : members)
		if (!delays[n])
			layers[distance.at(n)].push_back(n);
	double width = 0;
	for (const auto& [rank, layer] : layers) {
		double w = 2 * spacing * (layer.size() - 1);
		for (auto n : layer)
			w += sizes[n][0];
		width = std::max(width, w);
	}
	double y = 0;
	for (const auto& [rank, layer] : layers) {
		double w = 2 * spacing * (layer.size() - 1), height = 0;
		for (auto n : layer)
			w += sizes[n][0];
		double x = (width - w) / 2;
		for (auto n : layer) {
			block.positions[n] = {x, y};
			x += sizes[n][0] + 2 * spacing;
			height = std::max(height, sizes[n][1]);
		}
		y += height + 3 * spacing;
	}
	std::vector<Index> pending;
	std::vector<Point> intervals;
	for (auto n : queue)
		if (delays[n])
			pending.push_back(n);
	for (auto n : pending) {
		std::set<Index> neighbors(g.next[n].begin(), g.next[n].end());
		neighbors.insert(g.previous[n].begin(), g.previous[n].end());
		double sum = 0;
		Index count = 0;
		for (auto m : neighbors)
			if (block.positions.count(m)) {
				sum += block.positions[m][1] + sizes[m][1] / 2;
				++count;
			}
		double desired = std::max(0.0, (count ? sum / count : y) - sizes[n][1] / 2);
		std::vector<double> candidates{desired};
		for (auto interval : intervals) {
			candidates.push_back(interval[1] + 2 * spacing);
			candidates.push_back(interval[0] - sizes[n][1] - 2 * spacing);
		}
		double best = std::numeric_limits<double>::infinity(), chosen = desired;
		for (auto candidate : candidates) {
			if (candidate < 0 ||
				std::any_of(
					intervals.begin(),
					intervals.end(),
					[&](auto interval) {
						return candidate < interval[1] + 2 * spacing && candidate + sizes[n][1] + 2 * spacing > interval[0];
					}))
				continue;
			if (std::abs(candidate - desired) < best) {
				best = std::abs(candidate - desired);
				chosen = candidate;
			}
		}
		block.positions[n] = {width + 3 * spacing, chosen};
		intervals.push_back({chosen, chosen + sizes[n][1]});
	}
	for (auto [n, p] : block.positions) {
		block.size[0] = std::max(block.size[0], p[0] + sizes[n][0]);
		block.size[1] = std::max(block.size[1], p[1] + sizes[n][1]);
	}
	block.axis = block.positions.at(head)[1] + sizes[head][1] / 2;
	return block;
}
Block pack(const Graph& g, const std::vector<Index>& members, const std::vector<Point>& sizes, const std::vector<bool>& delays,
		   double spacing, const std::vector<bool>& vertical) {
	Block block;
	if (members.size() == 1) {
		auto n = members[0];
		block.positions[n] = {0, 0};
		block.size = sizes[n];
		block.axis = sizes[n][1] / 2;
		return block;
	}
	for (auto n : members)
		if (vertical[n]) {
			auto ordered = members;
			std::rotate(ordered.begin(), std::find(ordered.begin(), ordered.end(), n), ordered.end());
			return stack_feedback(g, ordered, sizes, delays, spacing);
		}
	std::vector<bool> inside(g.next.size()), forward(g.next.size());
	bool has_delays = false;
	for (auto n : members) {
		inside[n] = true;
		forward[n] = !delays[n];
		has_delays |= delays[n];
	}
	auto order = topological(g, forward);
	if (has_delays && !order.empty() && order.size() == static_cast<Index>(std::count(forward.begin(), forward.end(), true))) {
		std::map<Index, std::vector<Index>> layers;
		std::vector<Index> rank(g.next.size());
		for (auto n : order) {
			for (auto p : g.previous[n])
				if (forward[p])
					rank[n] = std::max(rank[n], rank[p] + 1);
			layers[rank[n]].push_back(n);
		}
		double max_height = 0;
		auto layer_height = [&](const std::vector<Index>& layer) {
			double height = 2 * spacing * (layer.size() - 1);
			for (auto n : layer)
				height += sizes[n][1];
			return height;
		};
		for (const auto& layer : layers)
			max_height = std::max(max_height, layer_height(layer.second));
		double x = 0;
		for (const auto& item : layers) {
			double y = (max_height - layer_height(item.second)) / 2, width = 0;
			for (auto n : item.second) {
				block.positions[n] = {x, y};
				y += sizes[n][1] + 2 * spacing;
				width = std::max(width, sizes[n][0]);
			}
			x += width + 3 * spacing;
		}
		double return_y = max_height + 2 * spacing;
		std::vector<Index> pending;
		std::vector<Rect> occupied;
		for (auto n : members)
			if (delays[n])
				pending.push_back(n);
		while (!pending.empty()) {
			auto chosen = pending.begin();
			for (auto it = pending.begin(); it != pending.end(); ++it) {
				if (std::any_of(g.previous[*it].begin(), g.previous[*it].end(), [&](auto p) { return block.positions.count(p); })) {
					chosen = it;
					break;
				}
			}
			auto n = *chosen;
			pending.erase(chosen);
			double total = 0;
			Index count = 0;
			for (auto p : g.previous[n])
				if (block.positions.count(p)) {
					total += block.positions[p][0] + sizes[p][0] / 2;
					++count;
				}
			double px = count ? total / count - sizes[n][0] / 2 : 0, py = return_y;
			for (;;) {
				bool collision = false;
				for (auto r : occupied)
					if (px < r[2] + 3 * spacing && px + sizes[n][0] + 3 * spacing > r[0] && py < r[3] + 2 * spacing &&
						py + sizes[n][1] + 2 * spacing > r[1]) {
						collision = true;
						break;
					}
				if (!collision)
					break;
				py += sizes[n][1] + 2 * spacing;
			}
			block.positions[n] = {px, py};
			occupied.push_back({px, py, px + sizes[n][0], py + sizes[n][1]});
		}
	} else {
		Index entry = members[0];
		for (auto n : members)
			if (std::any_of(g.previous[n].begin(), g.previous[n].end(), [&](auto p) { return !inside[p]; })) {
				entry = n;
				break;
			}
		std::vector<Index> traversal;
		std::vector<bool> seen(g.next.size());
		std::function<void(Index)> visit = [&](Index n) {
			seen[n] = true;
			traversal.push_back(n);
			for (auto m : g.next[n])
				if (inside[m] && !seen[m])
					visit(m);
		};
		visit(entry);
		Index columns = static_cast<Index>(std::ceil(std::sqrt(traversal.size()))), rows = (traversal.size() + columns - 1) / columns;
		std::vector<double> widths(columns), heights(rows), xs(columns + 1), ys(rows + 1);
		std::map<Index, std::pair<Index, Index>> cells;
		for (Index i = 0; i < traversal.size(); ++i) {
			auto row = i / columns, col = i % columns;
			if (row % 2)
				col = columns - 1 - col;
			auto n = traversal[i];
			cells[n] = {row, col};
			widths[col] = std::max(widths[col], sizes[n][0]);
			heights[row] = std::max(heights[row], sizes[n][1]);
		}
		for (Index i = 0; i < columns; ++i)
			xs[i + 1] = xs[i] + std::ceil(widths[i] / spacing) * spacing + 3 * spacing;
		for (Index i = 0; i < rows; ++i)
			ys[i + 1] = ys[i] + std::ceil(heights[i] / spacing) * spacing + 2 * spacing;
		for (auto [n, cell] : cells)
			block.positions[n] = {xs[cell.second], ys[cell.first] + (heights[cell.first] - sizes[n][1]) / 2};
		block.size = {xs.back() - 3 * spacing, ys.back() - 2 * spacing};
	}
	double left = 0, axis = 0;
	Index count = 0;
	for (auto [n, p] : block.positions)
		left = std::min(left, p[0]);
	for (auto& item : block.positions) {
		auto n = item.first;
		auto& p = item.second;
		p[0] -= left;
		block.size[0] = std::max(block.size[0], p[0] + sizes[n][0]);
		block.size[1] = std::max(block.size[1], p[1] + sizes[n][1]);
		if (!delays[n]) {
			axis += p[1] + sizes[n][1] / 2;
			++count;
		}
	}
	if (!count)
		for (auto [n, p] : block.positions) {
			axis += p[1] + sizes[n][1] / 2;
			++count;
		}
	block.axis = axis / count;
	return block;
}
} // namespace

std::vector<bool> feedback(const Graph& g, const std::vector<bool>& delays) {
	if (delays.size() != g.next.size())
		throw std::invalid_argument("Delay flags must match graph size");
	std::vector<bool> result(g.next.size());
	for (const auto& group : components(g)) {
		bool cyclic = group.size() > 1;
		for (auto n : group)
			cyclic |= std::find(g.next[n].begin(), g.next[n].end(), n) != g.next[n].end();
		if (cyclic)
			for (auto n : group)
				result[n] = delays[n];
	}
	return result;
}
std::vector<bool> vertical_feedback(const Graph& g, const std::vector<bool>& delays) {
	if (delays.size() != g.next.size())
		throw std::invalid_argument("Delay flags must match graph size");
	std::vector<bool> result(g.next.size());
	for (const auto& members : components(g)) {
		std::set<Index> inside(members.begin(), members.end()), entries, exits;
		Index forward = 0;
		bool has_delay = false;
		for (auto n : members) {
			forward += !delays[n];
			has_delay |= delays[n];
			for (auto m : g.previous[n])
				if (!inside.count(m))
					entries.insert(n);
			for (auto m : g.next[n])
				if (!inside.count(m))
					exits.insert(n);
		}
		if (has_delay && forward > 1 && entries.size() == 1 && entries == exits && !delays[*entries.begin()])
			result[*entries.begin()] = true;
	}
	return result;
}
std::vector<Point> place(const Graph& g, const std::vector<Point>& sizes, const std::vector<bool>& delays, double spacing, double grid,
						 const std::vector<bool>& vertical) {
	Index count = g.next.size();
	if (sizes.size() != count || delays.size() != count)
		throw std::invalid_argument("Node sizes and delay flags must match graph size");
	if (!count)
		return {};
	auto stacked = vertical.empty() ? vertical_feedback(g, delays) : vertical;
	if (stacked.size() != count)
		throw std::invalid_argument("Vertical flags must match graph size");
	// Collapse feedback loops into blocks before assigning forward layers.
	auto groups = components(g);
	Index nc = groups.size();
	std::vector<Index> mapping(count);
	for (Index i = 0; i < nc; ++i)
		for (auto n : groups[i])
			mapping[n] = i;
	Edges edges;
	for (Index n = 0; n < count; ++n)
		for (auto m : g.next[n])
			if (mapping[n] != mapping[m])
				edges.push_back({mapping[n], mapping[m]});
	Graph dag(nc, edges);
	auto order = topological(dag, std::vector<bool>(nc, true));
	std::vector<Block> blocks;
	for (const auto& members : groups)
		blocks.push_back(pack(g, members, sizes, delays, spacing, stacked));
	std::vector<Index> ranks(nc), indices(nc);
	for (Index i = 0; i < order.size(); ++i) {
		auto n = order[i];
		indices[n] = i;
		for (auto p : dag.previous[n])
			ranks[n] = std::max(ranks[n], ranks[p] + 1);
	}
	// Descendants owned by one fork branch get their own vertical band,
	// keeping parallel filters together until their paths merge.
	using Signature = std::vector<std::pair<Index, Index>>;
	std::vector<Signature> signatures(nc);
	for (auto fork : order)
		if (dag.next[fork].size() > 1) {
			std::vector<std::vector<Index>> owners(nc);
			for (Index branch = 0; branch < dag.next[fork].size(); ++branch) {
				std::vector<Index> pending{dag.next[fork][branch]};
				std::vector<bool> seen(nc);
				while (!pending.empty()) {
					auto n = pending.back();
					pending.pop_back();
					if (seen[n])
						continue;
					seen[n] = true;
					owners[n].push_back(branch);
					pending.insert(pending.end(), dag.next[n].begin(), dag.next[n].end());
				}
			}
			for (Index n = 0; n < nc; ++n)
				if (owners[n].size() == 1)
					signatures[n].push_back({indices[fork], owners[n][0]});
		}
	std::map<Index, double> xs;
	double x = 3 * spacing;
	for (Index rank = 0; rank <= *std::max_element(ranks.begin(), ranks.end()); ++rank) {
		double width = 0;
		xs[rank] = x;
		for (auto n : order)
			if (ranks[n] == rank)
				width = std::max(width, blocks[n].size[0]);
		x += width + 3 * spacing;
	}
	std::vector<bool> seen(nc);
	std::vector<Point> result(count);
	double top = 3 * spacing;
	for (Index seed = 0; seed < nc; ++seed)
		if (!seen[seed]) {
			std::set<Index> members;
			std::vector<Index> pending{seed};
			while (!pending.empty()) {
				auto n = pending.back();
				pending.pop_back();
				if (seen[n])
					continue;
				seen[n] = true;
				members.insert(n);
				pending.insert(pending.end(), dag.next[n].begin(), dag.next[n].end());
				pending.insert(pending.end(), dag.previous[n].begin(), dag.previous[n].end());
			}
			std::vector<Index> nodes;
			for (auto n : order)
				if (members.count(n))
					nodes.push_back(n);
			std::map<Signature, std::vector<Index>> bands;
			for (auto n : nodes)
				if (!signatures[n].empty())
					bands[signatures[n]].push_back(n);
			if (bands.empty())
				bands[{}] = nodes;
			std::map<Index, double> ys;
			std::map<Index, Point> limits;
			std::map<Index, std::vector<Point>> occupied;
			double band_top = 0;
			for (const auto& band : bands) {
				std::map<Index, std::vector<Index>> layers;
				for (auto n : band.second)
					layers[ranks[n]].push_back(n);
				auto height_of = [&](const std::vector<Index>& layer) {
					double h = 2 * spacing * (layer.size() - 1);
					for (auto n : layer)
						h += blocks[n].size[1];
					return h;
				};
				double band_height = 0;
				for (const auto& layer : layers)
					band_height = std::max(band_height, height_of(layer.second));
				for (const auto& layer : layers) {
					double y = band_top + (band_height - height_of(layer.second)) / 2;
					for (auto n : layer.second) {
						ys[n] = y;
						limits[n] = {band_top, band_top + band_height};
						occupied[ranks[n]].push_back({y, y + blocks[n].size[1]});
						y += blocks[n].size[1] + 2 * spacing;
					}
				}
				band_top += band_height + 4 * spacing;
			}
			for (auto n : nodes)
				if (!ys.count(n)) {
					std::set<Index> neighbors(dag.next[n].begin(), dag.next[n].end());
					neighbors.insert(dag.previous[n].begin(), dag.previous[n].end());
					double sum = 0;
					Index num = 0;
					for (auto m : neighbors)
						if (ys.count(m)) {
							sum += ys[m] + blocks[m].axis;
							++num;
						}
					double height = blocks[n].size[1], desired = (num ? sum / num : (band_top - 4 * spacing) / 2) - blocks[n].axis;
					auto& intervals = occupied[ranks[n]];
					std::vector<double> candidates{desired};
					for (auto interval : intervals) {
						candidates.push_back(interval[1] + 2 * spacing);
						candidates.push_back(interval[0] - height - 2 * spacing);
					}
					bool found = false;
					double best = 0;
					for (auto y : candidates) {
						bool valid = true;
						for (auto interval : intervals)
							if (!(y + height + 2 * spacing <= interval[0] || y >= interval[1] + 2 * spacing)) {
								valid = false;
								break;
							}
						if (valid &&
							(!found || std::make_pair(std::abs(y - desired), y) < std::make_pair(std::abs(best - desired), best))) {
							found = true;
							best = y;
						}
					}
					ys[n] = best;
					intervals.push_back({best, best + height});
				}
			double low = ys.begin()->second, high = low;
			for (auto n : nodes) {
				low = std::min(low, ys[n]);
				high = std::max(high, ys[n] + blocks[n].size[1]);
			}
			for (auto n : nodes)
				if (!limits.count(n))
					limits[n] = {low, high};
			std::map<Index, std::vector<Index>> layers;
			for (auto n : nodes)
				layers[ranks[n]].push_back(n);
			std::map<Index, Index> before, after;
			for (auto& layer : layers) {
				auto& list = layer.second;
				std::stable_sort(list.begin(), list.end(), [&](auto a, auto b) { return ys[a] < ys[b]; });
				for (Index i = 1; i < list.size(); ++i) {
					after[list[i - 1]] = list[i];
					before[list[i]] = list[i - 1];
				}
			}
			std::map<Index, std::set<Index>> neighbors;
			for (auto n : nodes) {
				std::set<Index> all(dag.next[n].begin(), dag.next[n].end()), same;
				all.insert(dag.previous[n].begin(), dag.previous[n].end());
				for (auto m : all)
					if (limits[m] == limits[n])
						same.insert(m);
				neighbors[n] = same.empty() ? all : same;
			}
			// Align signal axes with neighboring blocks, constrained by band bounds
			// and fixed layer order so balancing cannot introduce overlaps.
			for (int pass = 0; pass < 8; ++pass) {
				auto sweep = nodes;
				if (pass % 2)
					std::reverse(sweep.begin(), sweep.end());
				for (auto n : sweep)
					if (!neighbors[n].empty()) {
						double lo = limits[n][0], hi = limits[n][1] - blocks[n].size[1];
						if (before.count(n)) {
							auto m = before[n];
							lo = std::max(lo, ys[m] + blocks[m].size[1] + 2 * spacing);
						}
						if (after.count(n))
							hi = std::min(hi, ys[after[n]] - blocks[n].size[1] - 2 * spacing);
						if (lo > hi)
							continue;
						double sum = 0;
						for (auto m : neighbors[n])
							sum += ys[m] + blocks[m].axis;
						ys[n] = std::min(hi, std::max(lo, sum / neighbors[n].size() - blocks[n].axis));
					}
			}
			low = ys.begin()->second;
			high = low;
			for (auto n : nodes) {
				low = std::min(low, ys[n]);
				high = std::max(high, ys[n] + blocks[n].size[1]);
			}
			for (auto n : nodes)
				for (auto [op, p] : blocks[n].positions)
					result[op] = {grid * std::nearbyint((xs[ranks[n]] + p[0]) / grid),
								  grid * std::nearbyint((top + ys[n] - low + p[1]) / grid)};
			top += high - low + 6 * spacing;
		}
	return result;
}
std::vector<std::pair<int, bool>> orient(const Graph& g, const std::vector<Point>& positions, const std::vector<Point>& sizes,
										 const std::vector<bool>& delays, double spacing) {
	auto count = g.next.size();
	if (positions.size() != count || sizes.size() != count || delays.size() != count)
		throw std::invalid_argument("Orientation arrays must match graph size");
	std::vector<std::pair<int, bool>> result(count, {0, false});
	std::vector<Point> centers;
	for (Index i = 0; i < count; ++i)
		centers.push_back({positions[i][0] + sizes[i][0] / 2, positions[i][1] + sizes[i][1] / 2});
	for (Index n = 0; n < count; ++n)
		if (delays[n]) {
			double best = std::numeric_limits<double>::infinity();
			for (auto candidate :
				 {std::tuple<int, bool, Point>{0, true, {-1, 0}}, {0, false, {1, 0}}, {90, false, {0, 1}}, {270, false, {0, -1}}}) {
				double score = 0;
				auto d = std::get<2>(candidate);
				for (int sign : {-1, 1})
					for (auto m : sign < 0 ? g.previous[n] : g.next[n])
						if (m != n) {
							double x = centers[m][0] - centers[n][0], y = centers[m][1] - centers[n][1],
								   projection = (x * d[0] + y * d[1]) * sign;
							score += std::abs(x * d[1] - y * d[0]) * 0.25 + std::max(0.0, -projection) + (projection < 0 ? 4 * spacing : 0);
						}
				if (score < best) {
					best = score;
					result[n] = {std::get<0>(candidate), std::get<1>(candidate)};
				}
			}
		}
	return result;
}
} // namespace asic::gui
