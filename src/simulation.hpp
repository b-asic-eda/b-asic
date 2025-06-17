#ifndef ASIC_SIMULATION_HPP
#define ASIC_SIMULATION_HPP

#define NOMINMAX
#include <pybind11/pybind11.h>

namespace asic {

void define_simulation_class(pybind11::module& module);

} // namespace asic

#endif // ASIC_SIMULATION_HPP
