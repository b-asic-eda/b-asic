#include "simulation.hpp"

#include "simulation/simulation.hpp"

namespace py = pybind11;

namespace asic {

void define_simulation_class(pybind11::module& module) {
	// clang-format off
	py::class_<simulation>(module, "FastSimulation")
		.def(py::init<py::handle>(),
			py::arg("sfg"),
			"SFG Constructor.")

		.def(py::init<py::handle, std::optional<std::vector<std::optional<input_provider_type>>>>(),
			py::arg("sfg"), py::arg("input_providers"),
			"SFG Constructor.")

		.def("set_input", &simulation::set_input,
			py::arg("index"), py::arg("input_provider"),
			"Set the input function used to get values for the specific input at the given index to the internal SFG.")

		.def("set_inputs", &simulation::set_inputs,
			py::arg("input_providers"),
			"Set the input functions used to get values for the inputs to the internal SFG.")

		.def("step", &simulation::step,
			py::arg("save_results") = true, py::arg("bits_override") = py::none{}, py::arg("truncate") = true,
			"Run one iteration of the simulation and return the resulting output values.")

		.def("run_until", &simulation::run_until,
			py::arg("iteration"), py::arg("save_results") = true, py::arg("bits_override") = py::none{}, py::arg("truncate") = true,
			"Run the simulation until its iteration is greater than or equal to the given iteration\n"
			"and return the output values of the last iteration.")

		.def("run_for", &simulation::run_for,
			py::arg("iterations"), py::arg("save_results") = true, py::arg("bits_override") = py::none{}, py::arg("truncate") = true,
			"Run a given number of iterations of the simulation and return the output values of the last iteration.")

		.def("run", &simulation::run,
			py::arg("save_results") = true, py::arg("bits_override") = py::none{}, py::arg("truncate") = true,
			"Run the simulation until the end of its input arrays and return the output values of the last iteration.")

		.def_property_readonly("iteration", &simulation::iteration,
			"Get the current iteration number of the simulation.")

		.def_property_readonly("results", &simulation::results,
			"Get a mapping from result keys to numpy arrays containing all results, including intermediate values,\n"
			"calculated for each iteration up until now that was run with save_results enabled.\n"
			"The mapping is indexed using the key() method of Operation with the appropriate output index.\n"
			"Example result after 3 iterations: {\"c1\": [3, 6, 7], \"c2\": [4, 5, 5], \"bfly1.0\": [7, 0, 0], \"bfly1.1\": [-1, 0, 2], \"0\": [7, -2, -1]}")

		.def("clear_results", &simulation::clear_results,
			"Clear all results that were saved until now.")

		.def("clear_state", &simulation::clear_state,
			"Clear all current state of the simulation, except for the results and iteration.");
	// clang-format on
}

} // namespace asic
