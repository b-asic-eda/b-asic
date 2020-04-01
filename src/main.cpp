#include <pybind11/pybind11.h>

namespace py = pybind11;

namespace asic {

int add(int a, int b) {
	return a + b;
}

int sub(int a, int b) {
	return a - b;
}

} // namespace asic

PYBIND11_MODULE(_b_asic, m) {
	m.doc() = "Better ASIC Toolbox Extension Module.";
	m.def("add", &asic::add, "A function which adds two numbers.", py::arg("a"), py::arg("b"));
	m.def("sub", &asic::sub, "A function which subtracts two numbers.", py::arg("a"), py::arg("b"));
}