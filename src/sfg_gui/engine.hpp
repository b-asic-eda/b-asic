#ifndef ASIC_SFG_GUI_ENGINE_HPP
#define ASIC_SFG_GUI_ENGINE_HPP

#include <array>
#include <cstdint>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <string>
#include <tuple>
#include <vector>

namespace asic::gui {

using Id = std::uint64_t;
using Point = std::array<double, 2>;
using Rect = std::array<double, 4>;
using Path = std::vector<Point>;
using Segment = std::array<Point, 2>;
using Segments = std::vector<Segment>;
using Cost = std::pair<double, double>;
using Edges = std::vector<std::array<std::size_t, 2>>;
// Records use stable GUI object IDs; rectangles are left/top/right/bottom.
// Node: ID, scene bounds, unrotated size, delay, default/current rotation, flip, terminal kind.
enum class TerminalKind { Operation, Input, Output, LocalSource, Sink };
using NodeRecord = std::tuple<Id, Rect, Point, bool, int, int, bool, TerminalKind>;
// Port: ID, owning node, scene anchor, outward axis unit vector.
using PortRecord = std::tuple<Id, Id, Point, Point>;
// Wire: ID, source/target ports, parent wire (zero if none), branch fraction.
using WireRecord = std::tuple<Id, Id, Id, Id, double>;
using RouteUpdate = std::tuple<Id, Path, bool>;
// Only changed paths cross the binding; absent junctions mean unchanged dots.
using RouteResult = std::pair<std::vector<RouteUpdate>, std::optional<Path>>;
using LayoutUpdate = std::tuple<Id, Point, int, bool>;

struct Node {
	Rect box;
	Point size;
	bool delay;
	int default_rotation, rotation;
	bool flipped;
	TerminalKind terminal;
};
struct Port {
	Id node;
	Point position, direction;
};
struct Wire {
	Id source, target, parent;
	double fraction;
	Path path;
	bool blocked = false;
};
struct Graph {
	std::vector<std::vector<std::size_t>> next, previous;
	explicit Graph(std::size_t count, const Edges& edges);
};

bool contains(const Rect& rect, const Point& point);
bool intersects(const Rect& a, const Rect& b);
Rect expanded(Rect rect, double amount);
Rect bounds(const Path& path, double margin = 0);
bool clear(const Path& path, const std::vector<Rect>& obstacles);
double overlap(const Segment& a, const Segment& b);
Cost route_cost(const Path& path, const Segments& occupied, const Segments& shared, double grid);
Path orthogonal(Point start, Point end, const std::vector<Rect>& obstacles, const Segments& occupied, const Segments& shared, double grid);
Path prefix(const Path& path, double fraction);
std::set<Point> junctions(const std::vector<Path>& paths);
std::pair<Path, bool> signal_route(Point start, Point end, Point source_direction, Point target_direction, const std::vector<Rect>& boxes,
								   const std::vector<Rect>& ports, const Segments& occupied, const Segments& shared, const Path& parent,
								   double fraction, double grid);

std::vector<bool> feedback(const Graph& graph, const std::vector<bool>& delays);
std::vector<bool> vertical_feedback(const Graph& graph, const std::vector<bool>& delays);
std::vector<Point> place(const Graph& graph, const std::vector<Point>& sizes, const std::vector<bool>& delays, double spacing, double grid,
						 const std::vector<bool>& vertical = {});
std::vector<std::pair<int, bool>> orient(const Graph& graph, const std::vector<Point>& positions, const std::vector<Point>& sizes,
										 const std::vector<bool>& delays, double spacing);

// The editor sends deltas. Graph, obstacles, ports, reservations, dirty regions,
// branches and route buffers remain here between events; no Python callbacks.
class Engine {
public:
	explicit Engine(double grid, double spacing);
	void update(const std::vector<NodeRecord>& nodes, const std::vector<PortRecord>& ports, const std::vector<WireRecord>& wires,
				const std::vector<Id>& removed_nodes, const std::vector<Id>& removed_ports, const std::vector<Id>& removed_wires);
	RouteResult route(bool incremental = false, bool force = false);
	std::vector<LayoutUpdate> layout();
	void reset();
	std::map<std::string, std::size_t> statistics() const;
	Path wire_path(Id id) const;
	std::vector<Id> routed_ids() const;
	std::vector<std::pair<Id, Path>> crossing_updates() const;

private:
	double grid_, spacing_;
	mutable std::mutex mutex_;
	std::map<Id, Node> nodes_;
	std::map<Id, Port> ports_;
	std::map<Id, Wire> wires_;
	std::vector<Id> node_order_, wire_order_;
	std::vector<Rect> dirty_regions_;
	std::set<Id> dirty_wires_;
	std::map<Id, std::set<Point>> junctions_;
	std::set<Point> last_junctions_;
	std::map<Id, Path> crossings_;
	std::vector<std::pair<Id, Path>> crossing_updates_;
	bool topology_dirty_ = true, last_incremental_ = false;
	std::size_t routed_last_ = 0, updated_last_ = 0;
	std::vector<Id> routed_ids_;
};
} // namespace asic::gui
#endif
