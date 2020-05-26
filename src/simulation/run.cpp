#define NOMINMAX
#include "run.h"

#include "../algorithm.h"
#include "../debug.h"
#include "format_code.h"

#include <algorithm>
#include <complex>
#include <cstddef>
#include <fmt/format.h>
#include <iterator>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <stdexcept>

namespace py = pybind11;

namespace asic {

[[nodiscard]] static number truncate_value(number value, std::int64_t bit_mask) {
	if (value.imag() != 0) {
		throw py::type_error{"Complex value cannot be truncated"};
	}
	return number{static_cast<number::value_type>(static_cast<std::int64_t>(value.real()) & bit_mask)};
}

[[nodiscard]] static std::int64_t setup_truncation_parameters(bool& truncate, std::optional<std::uint8_t>& bits_override) {
	if (truncate && bits_override) {
		truncate = false; // Ignore truncate instructions, they will be truncated using bits_override instead.
		if (*bits_override > 64) {
			throw py::value_error{"Cannot truncate to more than 64 bits"};
		}
		return static_cast<std::int64_t>((std::int64_t{1} << *bits_override) - 1); // Return the bit mask override to use.
	}
	bits_override.reset(); // Don't use bits_override if truncate is false.
	return std::int64_t{};
}

simulation_state run_simulation(simulation_code const& code, span<number const> inputs, span<number> delays,
								std::optional<std::uint8_t> bits_override, bool truncate) {
	ASIC_ASSERT(inputs.size() == code.input_count);
	ASIC_ASSERT(delays.size() == code.delays.size());
	ASIC_ASSERT(code.output_count <= code.required_stack_size);

	auto state = simulation_state{};

	// Setup results.
	state.results.resize(code.result_keys.size() + 1); // Add one space to store ignored results.
	// Initialize delay results to their current values.
	for (auto const& [i, delay] : enumerate(code.delays)) {
		state.results[delay.result_index] = delays[i];
	}

	// Setup stack.
	state.stack.resize(code.required_stack_size);
	auto stack_pointer = state.stack.data();

	// Utility functions to make the stack manipulation code below more readable.
	// Should hopefully be inlined by the compiler.
	auto const push = [&](number value) -> void {
		ASIC_ASSERT(std::distance(state.stack.data(), stack_pointer) < static_cast<std::ptrdiff_t>(state.stack.size()));
		*stack_pointer++ = value;
	};
	auto const pop = [&]() -> number {
		ASIC_ASSERT(std::distance(state.stack.data(), stack_pointer) > std::ptrdiff_t{0});
		return *--stack_pointer;
	};
	auto const peek = [&]() -> number {
		ASIC_ASSERT(std::distance(state.stack.data(), stack_pointer) > std::ptrdiff_t{0});
		ASIC_ASSERT(std::distance(state.stack.data(), stack_pointer) <= static_cast<std::ptrdiff_t>(state.stack.size()));
		return *(stack_pointer - 1);
	};

	// Check if results should be truncated.
	auto const bit_mask_override = setup_truncation_parameters(truncate, bits_override);

	// Hot instruction evaluation loop.
	for (auto const& instruction : code.instructions) {
		ASIC_DEBUG_MSG("Evaluating {}.", format_compiled_simulation_code_instruction(instruction));
		// Execute the instruction.
		switch (instruction.type) {
			case instruction_type::push_input:
				push(inputs[instruction.index]);
				break;
			case instruction_type::push_result:
				push(state.results[instruction.index]);
				break;
			case instruction_type::push_delay:
				push(delays[instruction.index]);
				break;
			case instruction_type::push_constant:
				push(instruction.value);
				break;
			case instruction_type::truncate:
				if (truncate) {
					push(truncate_value(pop(), instruction.bit_mask));
				}
				break;
			case instruction_type::addition:
				push(pop() + pop());
				break;
			case instruction_type::subtraction:
				push(pop() - pop());
				break;
			case instruction_type::multiplication:
				push(pop() * pop());
				break;
			case instruction_type::division:
				push(pop() / pop());
				break;
			case instruction_type::min: {
				auto const lhs = pop();
				auto const rhs = pop();
				if (lhs.imag() != 0 || rhs.imag() != 0) {
					throw std::runtime_error{"Min does not support complex numbers."};
				}
				push(std::min(lhs.real(), rhs.real()));
				break;
			}
			case instruction_type::max: {
				auto const lhs = pop();
				auto const rhs = pop();
				if (lhs.imag() != 0 || rhs.imag() != 0) {
					throw std::runtime_error{"Max does not support complex numbers."};
				}
				push(std::max(lhs.real(), rhs.real()));
				break;
			}
			case instruction_type::square_root:
				push(std::sqrt(pop()));
				break;
			case instruction_type::complex_conjugate:
				push(std::conj(pop()));
				break;
			case instruction_type::absolute:
				push(number{std::abs(pop())});
				break;
			case instruction_type::constant_multiplication:
				push(pop() * instruction.value);
				break;
			case instruction_type::update_delay:
				delays[instruction.index] = pop();
				break;
			case instruction_type::custom: {
				using namespace pybind11::literals;
				auto const& src = code.custom_sources[instruction.index];
				auto const& op = code.custom_operations[src.custom_operation_index];
				auto input_values = std::vector<number>{};
				input_values.reserve(op.input_count);
				for (auto i = std::size_t{0}; i < op.input_count; ++i) {
					input_values.push_back(pop());
				}
				push(op.evaluate_output(src.output_index, std::move(input_values), "truncate"_a = truncate).cast<number>());
				break;
			}
			case instruction_type::forward_value:
				// Do nothing, since doing push(pop()) would be pointless.
				break;
		}
		// If we've been given a global override for how many bits to use, always truncate the result.
		if (bits_override) {
			push(truncate_value(pop(), bit_mask_override));
		}
		// Store the result.
		state.results[instruction.result_index] = peek();
	}

	// Remove the space that we used for ignored results.
	state.results.pop_back();
	// Erase the portion of the stack that does not contain the output values.
	state.stack.erase(state.stack.begin() + static_cast<std::ptrdiff_t>(code.output_count), state.stack.end());
	return state;
}

} // namespace asic