#include "custom_operation.hpp"

#define NOMINMAX
#include <pybind11/stl.h>

namespace asic {

custom_operation::custom_operation(result_key key, pybind11::object evaluate_output, pybind11::object truncate_input,
								   std::size_t output_count)
	: nary_operation(std::move(key))
	, m_evaluate_output(std::move(evaluate_output))
	, m_truncate_input(std::move(truncate_input))
	, m_output_count(output_count) {}

std::size_t custom_operation::output_count() const noexcept {
	return m_output_count;
}

number custom_operation::evaluate_output_impl(std::size_t index, evaluation_context const& context) const {
	using namespace pybind11::literals;
	auto input_values = this->evaluate_inputs(context);
	return m_evaluate_output(index, std::move(input_values), "truncate"_a = false).cast<number>();
}

number custom_operation::truncate_input(std::size_t index, number value, std::size_t bits) const {
	return m_truncate_input(index, value, bits).cast<number>();
}

} // namespace asic
