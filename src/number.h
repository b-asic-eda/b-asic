#ifndef ASIC_NUMBER_H
#define ASIC_NUMBER_H

#include <complex>
#include <pybind11/complex.h>

namespace asic {

using number = std::complex<double>;

} // namespace asic

#endif // ASIC_NUMBER_H