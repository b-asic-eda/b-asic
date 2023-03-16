#include "operation.hpp"

#include "../debug.hpp"

#define NOMINMAX
#include <pybind11/pybind11.h>

namespace py = pybind11;

namespace asic {

signal_source::signal_source(std::shared_ptr<const operation> op, std::size_t index, std::optional<std::size_t> bits)
	: m_operation(std::move(op))
	, m_index(index)
	, m_bits(bits) {}

signal_source::operator bool() const noexcept {
	return static_cast<bool>(m_operation);
}

std::optional<number> signal_source::current_output(delay_map const& delays) const {
	ASIC_ASSERT(m_operation);
	return m_operation->current_output(m_index, delays);
}

number signal_source::evaluate_output(evaluation_context const& context) const {
	ASIC_ASSERT(m_operation);
	return m_operation->evaluate_output(m_index, context);
}

std::optional<std::size_t> signal_source::bits() const noexcept {
	return m_bits;
}

abstract_operation::abstract_operation(result_key key)
	: m_key(std::move(key)) {}

std::optional<number> abstract_operation::current_output(std::size_t, delay_map const&) const {
	return std::nullopt;
}

number abstract_operation::evaluate_output(std::size_t index, evaluation_context const& context) const {
	ASIC_ASSERT(index < this->output_count());
	ASIC_ASSERT(context.results);
	auto const key = this->key_of_output(index);
	if (auto const it = context.results->find(key); it != context.results->end()) {
		if (it->second) {
			return *it->second;
		}
		throw std::runtime_error{"Direct feedback loop detected when evaluating simulation operation."};
	}
	auto& result = context.results->try_emplace(key, this->current_output(index, *context.delays))
					   .first->second; // Use a reference to avoid potential iterator invalidation caused by evaluate_output_impl.
	auto const value = this->evaluate_output_impl(index, context);
	ASIC_ASSERT(&context.results->at(key) == &result);
	result = value;
	return value;
}

number abstract_operation::quantize_input(std::size_t index, number value, std::size_t bits) const {
	if (value.imag() != 0) {
		throw py::type_error{
			fmt::format("Complex value cannot be quantized to {} bits as requested by the signal connected to input #{}", bits, index)};
	}
	if (bits > 64) {
		throw py::value_error{
			fmt::format("Cannot quantize to {} (more than 64) bits as requested by the singal connected to input #{}", bits, index)};
	}
	return number{static_cast<number::value_type>(static_cast<std::int64_t>(value.real()) & ((std::int64_t{1} << bits) - 1))};
}

result_key const& abstract_operation::key_base() const {
	return m_key;
}

result_key abstract_operation::key_of_output(std::size_t index) const {
	if (m_key.empty()) {
		return fmt::to_string(index);
	}
	if (this->output_count() == 1) {
		return m_key;
	}
	return fmt::format("{}.{}", m_key, index);
}

unary_operation::unary_operation(result_key key)
	: abstract_operation(std::move(key)) {}

void unary_operation::connect(signal_source in) {
	m_in = std::move(in);
}

bool unary_operation::connected() const noexcept {
	return static_cast<bool>(m_in);
}

signal_source const& unary_operation::input() const noexcept {
	return m_in;
}

number unary_operation::evaluate_input(evaluation_context const& context) const {
	auto const value = m_in.evaluate_output(context);
	auto const bits = context.bits_override.value_or(m_in.bits().value_or(0));
	return (context.quantize && bits != 0) ? this->quantize_input(0, value, bits) : value;
}

binary_operation::binary_operation(result_key key)
	: abstract_operation(std::move(key)) {}

void binary_operation::connect(signal_source lhs, signal_source rhs) {
	m_lhs = std::move(lhs);
	m_rhs = std::move(rhs);
}

signal_source const& binary_operation::lhs() const noexcept {
	return m_lhs;
}

signal_source const& binary_operation::rhs() const noexcept {
	return m_rhs;
}

number binary_operation::evaluate_lhs(evaluation_context const& context) const {
	auto const value = m_lhs.evaluate_output(context);
	auto const bits = context.bits_override.value_or(m_lhs.bits().value_or(0));
	return (context.quantize && bits != 0) ? this->quantize_input(0, value, bits) : value;
}

number binary_operation::evaluate_rhs(evaluation_context const& context) const {
	auto const value = m_rhs.evaluate_output(context);
	auto const bits = context.bits_override.value_or(m_rhs.bits().value_or(0));
	return (context.quantize && bits != 0) ? this->quantize_input(0, value, bits) : value;
}

nary_operation::nary_operation(result_key key)
	: abstract_operation(std::move(key)) {}

void nary_operation::connect(std::vector<signal_source> inputs) {
	m_inputs = std::move(inputs);
}

span<signal_source const> nary_operation::inputs() const noexcept {
	return m_inputs;
}

std::vector<number> nary_operation::evaluate_inputs(evaluation_context const& context) const {
	auto values = std::vector<number>{};
	values.reserve(m_inputs.size());
	for (auto const& input : m_inputs) {
		auto const value = input.evaluate_output(context);
		auto const bits = context.bits_override.value_or(input.bits().value_or(0));
		values.push_back((context.quantize && bits != 0) ? this->quantize_input(0, value, bits) : value);
	}
	return values;
}

} // namespace asic
