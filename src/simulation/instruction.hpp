#ifndef ASIC_SIMULATION_INSTRUCTION_HPP
#define ASIC_SIMULATION_INSTRUCTION_HPP

#include "../number.hpp"

#include <cstddef>
#include <cstdint>
#include <optional>

namespace asic {

enum class instruction_type : std::uint8_t {
	push_input,              // push(inputs[index])
	push_result,             // push(results[index])
	push_delay,              // push(delays[index])
	push_constant,           // push(value)
	quantize,                // push(trunc(pop(), bit_mask))
	addition,                // rhs=pop(), lhs=pop(), push(lhs + rhs)
	subtraction,             // rhs=pop(), lhs=pop(), push(lhs - rhs)
	multiplication,          // rhs=pop(), lhs=pop(), push(lhs * rhs)
	division,                // rhs=pop(), lhs=pop(), push(lhs / rhs)
	min,                     // rhs=pop(), lhs=pop(), push(min(lhs, rhs))
	max,                     // rhs=pop(), lhs=pop(), push(max(lhs, rhs))
	square_root,             // push(sqrt(pop()))
	complex_conjugate,       // push(conj(pop()))
	absolute,                // push(abs(pop()))
	constant_multiplication, // push(pop() * value)
	update_delay,            // delays[index] = pop()
	custom,                  // Custom operation. Uses custom_source[index].
	forward_value            // Forward the current value on the stack (push(pop()), i.e. do nothing).
};

using result_index_type = std::uint16_t;

struct instruction final {
	constexpr instruction() noexcept // NOLINT(cppcoreguidelines-pro-type-member-init)
		: index(0) {}

	union {
		// Index used by push_input, push_result, delay and custom.
		std::size_t index;
		// Bit mask used by quantize.
		std::int64_t bit_mask;
		// Constant value used by push_constant and constant_multiplication.
		number value;
	};
	// Index into where the result of the instruction will be stored. If the result should be ignored, this index will be one past the last valid result index.
	result_index_type result_index = 0;
	// Specifies what kind of operation the instruction should execute.
	instruction_type type = instruction_type::forward_value;
};

} // namespace asic

#endif // ASIC_SIMULATION_INSTRUCTION_HPP
