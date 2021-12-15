#ifndef ASIC_NUMBER_HPP
#define ASIC_NUMBER_HPP

#define NOMINMAX
#include <complex>
#include <pybind11/complex.h>

namespace asic {

using number = std::complex<double>;

} // namespace asic

#endif // ASIC_NUMBER_HPP
