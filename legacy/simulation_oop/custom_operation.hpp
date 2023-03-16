#ifndef ASIC_SIMULATION_CUSTOM_OPERATION_HPP
#define ASIC_SIMULATION_CUSTOM_OPERATION_HPP

#include "../algorithm.hpp"
#include "../debug.hpp"
#include "../number.hpp"
#include "operation.hpp"

#define NOMINMAX
#include <cstddef>
#include <fmt/format.h>
#include <functional>
#include <pybind11/pybind11.h>
#include <stdexcept>
#include <utility>

namespace asic {

class custom_operation final : public nary_operation {
public:
	custom_operation(result_key key, pybind11::object evaluate_output, pybind11::object quantize_input, std::size_t output_count);

	[[nodiscard]] std::size_t output_count() const noexcept final;

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t index, evaluation_context const& context) const final;
	[[nodiscard]] number quantize_input(std::size_t index, number value, std::size_t bits) const final;

	pybind11::object m_evaluate_output;
	pybind11::object m_quantize_input;
	std::size_t m_output_count;
};

} // namespace asic

#endif // ASIC_SIMULATION_CUSTOM_OPERATION_HPP
