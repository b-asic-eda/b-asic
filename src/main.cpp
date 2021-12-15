#include "simulation.hpp"

#define NOMINMAX
#include <pybind11/pybind11.h>

PYBIND11_MODULE(_b_asic, module) { // NOLINT
	module.doc() = "Better ASIC Toolbox Extension Module.";
	asic::define_simulation_class(module);
}
