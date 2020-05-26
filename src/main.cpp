#include "simulation.h"
#include <pybind11/pybind11.h>

namespace py = pybind11;

PYBIND11_MODULE(_b_asic, module) {
	module.doc() = "Better ASIC Toolbox Extension Module.";
	asic::define_simulation_class(module);
}