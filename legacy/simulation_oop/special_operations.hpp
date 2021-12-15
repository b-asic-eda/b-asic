#ifndef ASIC_SIMULATION_SPECIAL_OPERATIONS_HPP
#define ASIC_SIMULATION_SPECIAL_OPERATIONS_HPP

#include "../debug.hpp"
#include "../number.hpp"
#include "operation.hpp"

#include <cassert>
#include <cstddef>
#include <utility>

namespace asic {

class input_operation final : public unary_operation {
public:
	explicit input_operation(result_key key);

	[[nodiscard]] std::size_t output_count() const noexcept final;
	[[nodiscard]] number value() const noexcept;
	void value(number value) noexcept;

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t index, evaluation_context const& context) const final;

	number m_value{};
};

class output_operation final : public unary_operation {
public:
	explicit output_operation(result_key key);

	[[nodiscard]] std::size_t output_count() const noexcept final;

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t index, evaluation_context const& context) const final;
};

class delay_operation final : public unary_operation {
public:
	delay_operation(result_key key, number initial_value);

	[[nodiscard]] std::size_t output_count() const noexcept final;

	[[nodiscard]] std::optional<number> current_output(std::size_t index, delay_map const& delays) const final;
	[[nodiscard]] number evaluate_output(std::size_t index, evaluation_context const& context) const final;

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t index, evaluation_context const& context) const final;

	number m_initial_value;
};

} // namespace asic

#endif // ASIC_SIMULATION_SPECIAL_OPERATIONS_HPP
