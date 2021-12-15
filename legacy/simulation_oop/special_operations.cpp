#include "special_operations.hpp"

#include "../debug.hpp"

namespace asic {

input_operation::input_operation(result_key key)
	: unary_operation(std::move(key)) {}

std::size_t input_operation::output_count() const noexcept {
	return 1;
}

number input_operation::value() const noexcept {
	return m_value;
}

void input_operation::value(number value) noexcept {
	m_value = value;
}

number input_operation::evaluate_output_impl(std::size_t, evaluation_context const& context) const {
	ASIC_DEBUG_MSG("Evaluating input.");
	if (this->connected()) {
		return this->evaluate_input(context);
	}
	return m_value;
}

output_operation::output_operation(result_key key)
	: unary_operation(std::move(key)) {}

std::size_t output_operation::output_count() const noexcept {
	return 1;
}

number output_operation::evaluate_output_impl(std::size_t, evaluation_context const& context) const {
	ASIC_DEBUG_MSG("Evaluating output.");
	return this->evaluate_input(context);
}

delay_operation::delay_operation(result_key key, number initial_value)
	: unary_operation(std::move(key))
	, m_initial_value(initial_value) {}

std::size_t delay_operation::output_count() const noexcept {
	return 1;
}

std::optional<number> delay_operation::current_output(std::size_t index, delay_map const& delays) const {
	auto const key = this->key_of_output(index);
	if (auto const it = delays.find(key); it != delays.end()) {
		return it->second;
	}
	return m_initial_value;
}

number delay_operation::evaluate_output(std::size_t index, evaluation_context const& context) const {
	ASIC_DEBUG_MSG("Evaluating delay.");
	ASIC_ASSERT(index == 0);
	ASIC_ASSERT(context.results);
	ASIC_ASSERT(context.delays);
	ASIC_ASSERT(context.deferred_delays);
	auto key = this->key_of_output(index);
	auto const value = context.delays->try_emplace(key, m_initial_value).first->second;
	auto const& [it, inserted] = context.results->try_emplace(key, value);
	if (inserted) {
		context.deferred_delays->emplace_back(std::move(key), &this->input());
		return value;
	}
	return it->second.value();
}

[[nodiscard]] number delay_operation::evaluate_output_impl(std::size_t, evaluation_context const&) const {
	return number{};
}

} // namespace asic
