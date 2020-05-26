#ifndef ASIC_SIMULATION_CUSTOM_OPERATION_H
#define ASIC_SIMULATION_CUSTOM_OPERATION_H

#include "../algorithm.h"
#include "../debug.h"
#include "../number.h"
#include "operation.h"

#include <cstddef>
#include <fmt/format.h>
#include <functional>
#include <pybind11/pybind11.h>
#include <stdexcept>
#include <utility>

namespace asic {

class custom_operation final : public nary_operation {
public:
	custom_operation(result_key key, pybind11::object evaluate_output, pybind11::object truncate_input, std::size_t output_count);

	[[nodiscard]] std::size_t output_count() const noexcept final;

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t index, evaluation_context const& context) const final;
	[[nodiscard]] number truncate_input(std::size_t index, number value, std::size_t bits) const final;

	pybind11::object m_evaluate_output;
	pybind11::object m_truncate_input;
	std::size_t m_output_count;
};

} // namespace asic

#endif // ASIC_SIMULATION_CUSTOM_OPERATION_H