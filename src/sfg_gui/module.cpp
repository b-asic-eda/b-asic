#include "engine.hpp"

#include <cmath>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <stdexcept>

namespace py = pybind11;
using namespace asic::gui;
namespace {
void configuration(double grid, double spacing) {
	if (!std::isfinite(grid) || !std::isfinite(spacing) || grid <= 0 || spacing <= 0)
		throw std::invalid_argument("Grid and spacing must be positive and finite");
}
void sizes_valid(const std::vector<Point>& sizes) {
	for (auto p : sizes)
		for (auto x : p)
			if (!std::isfinite(x) || x <= 0)
				throw std::invalid_argument("Sizes must be positive and finite");
}
void point_valid(Point point) {
	for (auto x : point)
		if (!std::isfinite(x))
			throw std::invalid_argument("Coordinates must be finite");
}
void obstacles_valid(const std::vector<Rect>& obstacles) {
	for (auto rect : obstacles) {
		point_valid({rect[0], rect[1]});
		point_valid({rect[2], rect[3]});
		if (rect[0] > rect[2] || rect[1] > rect[3])
			throw std::invalid_argument("Obstacle bounds must be ordered");
	}
}
void segments_valid(const Segments& segments) {
	for (auto segment : segments)
		for (auto point : segment)
			point_valid(point);
}
void direction_valid(Point direction) {
	point_valid(direction);
	if (std::abs(direction[0]) + std::abs(direction[1]) != 1 || (direction[0] != 0 && direction[1] != 0))
		throw std::invalid_argument("Port direction must be an axis unit vector");
}
} // namespace
PYBIND11_MODULE(_sfg_gui, module) {
	module.doc() = "Persistent native place-and-route engine for the SFG editor.";
	py::enum_<TerminalKind>(module, "TerminalKind")
		.value("OPERATION", TerminalKind::Operation)
		.value("INPUT", TerminalKind::Input)
		.value("OUTPUT", TerminalKind::Output)
		.value("LOCAL_SOURCE", TerminalKind::LocalSource)
		.value("SINK", TerminalKind::Sink);
	py::class_<Engine>(module, "PlaceRouteEngine")
		.def(py::init<double, double>(), py::arg("grid"), py::arg("spacing"))
		.def("update",
			 &Engine::update,
			 py::arg("nodes"),
			 py::arg("ports"),
			 py::arg("wires"),
			 py::arg("removed_nodes") = std::vector<Id>{},
			 py::arg("removed_ports") = std::vector<Id>{},
			 py::arg("removed_wires") = std::vector<Id>{},
			 py::call_guard<py::gil_scoped_release>())
		.def("route", &Engine::route, py::arg("incremental") = false, py::arg("force") = false, py::call_guard<py::gil_scoped_release>())
		.def("layout", &Engine::layout, py::call_guard<py::gil_scoped_release>())
		.def("reset", &Engine::reset, py::call_guard<py::gil_scoped_release>())
		.def("statistics", &Engine::statistics, py::call_guard<py::gil_scoped_release>())
		.def("wire_path", &Engine::wire_path, py::call_guard<py::gil_scoped_release>())
		.def("routed_ids", &Engine::routed_ids, py::call_guard<py::gil_scoped_release>());
	module.def(
		"place_graph",
		[](std::size_t count,
		   const Edges& edges,
		   const std::vector<Point>& sizes,
		   const std::vector<bool>& delays,
		   double spacing,
		   double grid) {
			configuration(grid, spacing);
			sizes_valid(sizes);
			return place(Graph(count, edges), sizes, delays, spacing, grid);
		},
		py::call_guard<py::gil_scoped_release>());
	module.def(
		"feedback_delays",
		[](std::size_t count, const Edges& edges, const std::vector<bool>& delays) { return feedback(Graph(count, edges), delays); },
		py::call_guard<py::gil_scoped_release>());
	module.def(
		"choose_orientations",
		[](std::size_t count,
		   const Edges& edges,
		   const std::vector<Point>& positions,
		   const std::vector<Point>& sizes,
		   const std::vector<bool>& delays,
		   double spacing) {
			configuration(spacing, spacing);
			sizes_valid(sizes);
			for (auto p : positions)
				for (auto x : p)
					if (!std::isfinite(x))
						throw std::invalid_argument("Positions must be finite");
			return orient(Graph(count, edges), positions, sizes, delays, spacing);
		},
		py::call_guard<py::gil_scoped_release>());
	module.def(
		"route_orthogonal",
		[](Point start, Point end, const std::vector<Rect>& obstacles, const Segments& occupied, const Segments& shared, double grid) {
			configuration(grid, grid);
			point_valid(start);
			point_valid(end);
			obstacles_valid(obstacles);
			segments_valid(occupied);
			segments_valid(shared);
			return orthogonal(start, end, obstacles, occupied, shared, grid);
		},
		py::call_guard<py::gil_scoped_release>());
	module.def(
		"route_signal",
		[](Point start,
		   Point end,
		   Point source_direction,
		   Point target_direction,
		   const std::vector<Rect>& boxes,
		   const std::vector<Rect>& ports,
		   const Segments& occupied,
		   const Segments& shared,
		   const Path& parent,
		   double fraction,
		   double grid) {
			configuration(grid, grid);
			point_valid(start);
			point_valid(end);
			direction_valid(source_direction);
			direction_valid(target_direction);
			obstacles_valid(boxes);
			obstacles_valid(ports);
			segments_valid(occupied);
			segments_valid(shared);
			for (auto p : parent)
				point_valid(p);
			if (!std::isfinite(fraction) || fraction < 0 || fraction > 1)
				throw std::invalid_argument("Branch fraction must be between zero and one");
			return signal_route(start, end, source_direction, target_direction, boxes, ports, occupied, shared, parent, fraction, grid);
		},
		py::call_guard<py::gil_scoped_release>());
	module.def(
		"junction_points",
		[](const std::vector<Path>& paths) {
			for (const auto& path : paths)
				for (auto p : path)
					point_valid(p);
			auto result = junctions(paths);
			return Path(result.begin(), result.end());
		},
		py::call_guard<py::gil_scoped_release>());
	module.def(
		"route_is_clear",
		[](const Path& path, const std::vector<Rect>& obstacles) {
			for (auto p : path)
				point_valid(p);
			obstacles_valid(obstacles);
			return clear(path, obstacles);
		},
		py::call_guard<py::gil_scoped_release>());
	module.def(
		"overlap_length",
		[](Point a, Point b, Point c, Point d) {
			for (auto p : {a, b, c, d})
				point_valid(p);
			return overlap({a, b}, {c, d});
		},
		py::call_guard<py::gil_scoped_release>());
	module.def(
		"route_cost",
		[](const Path& path, const Segments& occupied, const Segments& shared, double grid) {
			configuration(grid, grid);
			for (auto p : path)
				point_valid(p);
			segments_valid(occupied);
			segments_valid(shared);
			return route_cost(path, occupied, shared, grid);
		},
		py::call_guard<py::gil_scoped_release>());
}
