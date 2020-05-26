#ifndef ASIC_SIMULATION_INSTRUCTION_H
#define ASIC_SIMULATION_INSTRUCTION_H

#include "../number.h"

#include <cstddef>
#include <cstdint>
#include <optional>

namespace asic {

enum class instruction_type : std::uint8_t {
	push_input,              // push(inputs[index])
	push_result,             // push(results[index])
	push_delay,              // push(delays[index])
	push_constant,           // push(value)
	truncate,                // push(trunc(pop(), bit_mask))
	addition,                // push(pop() + pop())
	subtraction,             // push(pop() - pop())
	multiplication,          // push(pop() * pop())
	division,                // push(pop() / pop())
	min,                     // push(min(pop(), pop()))
	max,                     // push(max(pop(), pop()))
	square_root,             // push(sqrt(pop()))
	complex_conjugate,       // push(conj(pop()))
	absolute,                // push(abs(pop()))
	constant_multiplication, // push(pop() * value)
	update_delay,            // delays[index] = pop()
	custom,                  // Custom operation. Uses custom_source[index].
	forward_value            // Forward the current value on the stack (push(pop()), i.e. do nothing).
};

using result_index_t = std::uint16_t;

struct instruction final {
	constexpr instruction() noexcept
		: index(0)
		, result_index(0)
		, type(instruction_type::forward_value) {}

	union {
		// Index used by push_input, push_result, delay and custom.
		std::size_t index;
		// Bit mask used by truncate.
		std::int64_t bit_mask;
		// Constant value used by push_constant and constant_multiplication.
		number value;
	};
	// Index into where the result of the instruction will be stored. If the result should be ignored, this index will be one past the last valid result index.
	result_index_t result_index;
	// Specifies what kind of operation the instruction should execute.
	instruction_type type;
};

} // namespace asic

#endif // ASIC_SIMULATION_INSTRUCTION_H