#ifndef ASIC_SIMULATION_FORMAT_CODE_HPP
#define ASIC_SIMULATION_FORMAT_CODE_HPP

#include "../algorithm.hpp"
#include "../debug.hpp"
#include "../number.hpp"
#include "compile.hpp"
#include "instruction.hpp"

#include <fmt/format.h>
#include <string>

namespace asic {

[[nodiscard]] inline std::string format_number(number const& value) {
	if (value.imag() == 0) {
		return fmt::to_string(value.real());
	}
	if (value.real() == 0) {
		return fmt::format("{}j", value.imag());
	}
	if (value.imag() < 0) {
		return fmt::format("{}-{}j", value.real(), -value.imag());
	}
	return fmt::format("{}+{}j", value.real(), value.imag());
}

[[nodiscard]] inline std::string format_compiled_simulation_code_result_keys(simulation_code const& code) {
	auto result = std::string{};
	for (auto const& [i, result_key] : enumerate(code.result_keys)) {
		result += fmt::format("{:>2}: \"{}\"\n", i, result_key);
	}
	return result;
}

[[nodiscard]] inline std::string format_compiled_simulation_code_delays(simulation_code const& code) {
	auto result = std::string{};
	for (auto const& [i, delay] : enumerate(code.delays)) {
		ASIC_ASSERT(delay.result_index < code.result_keys.size());
		result += fmt::format("{:>2}: Initial value: {}, Result: {}: \"{}\"\n",
							  i,
							  format_number(delay.initial_value),
							  delay.result_index,
							  code.result_keys[delay.result_index]);
	}
	return result;
}

[[nodiscard]] inline std::string format_compiled_simulation_code_instruction(instruction const& instruction) {
	// clang-format off
	switch (instruction.type) {
		case instruction_type::push_input:              return fmt::format("push_input inputs[{}]", instruction.index);
		case instruction_type::push_result:             return fmt::format("push_result results[{}]", instruction.index);
		case instruction_type::push_delay:              return fmt::format("push_delay delays[{}]", instruction.index);
		case instruction_type::push_constant:           return fmt::format("push_constant {}", format_number(instruction.value));
		case instruction_type::truncate:                return fmt::format("truncate {:#018x}", instruction.bit_mask);
		case instruction_type::addition:                return "addition";
		case instruction_type::subtraction:             return "subtraction";
		case instruction_type::multiplication:          return "multiplication";
		case instruction_type::division:                return "division";
		case instruction_type::min:                     return "min";
		case instruction_type::max:                     return "max";
		case instruction_type::square_root:             return "square_root";
		case instruction_type::complex_conjugate:       return "complex_conjugate";
		case instruction_type::absolute:                return "absolute";
		case instruction_type::constant_multiplication: return fmt::format("constant_multiplication {}", format_number(instruction.value));
		case instruction_type::update_delay:            return fmt::format("update_delay delays[{}]", instruction.index);
		case instruction_type::custom:                  return fmt::format("custom custom_sources[{}]", instruction.index);
		case instruction_type::forward_value:           return "forward_value";
	}
	// clang-format on
	return std::string{};
}

[[nodiscard]] inline std::string format_compiled_simulation_code_instructions(simulation_code const& code) {
	auto result = std::string{};
	for (auto const& [i, instruction] : enumerate(code.instructions)) {
		auto instruction_string = format_compiled_simulation_code_instruction(instruction);
		if (instruction.result_index < code.result_keys.size()) {
			instruction_string = fmt::format(
				"{:<26} -> {}: \"{}\"", instruction_string, instruction.result_index, code.result_keys[instruction.result_index]);
		}
		result += fmt::format("{:>2}: {}\n", i, instruction_string);
	}
	return result;
}

[[nodiscard]] inline std::string format_compiled_simulation_code(simulation_code const& code) {
	return fmt::format(
		"==============================================\n"
		"> Code stats\n"
		"==============================================\n"
		"Input count: {}\n"
		"Output count: {}\n"
		"Instruction count: {}\n"
		"Required stack size: {}\n"
		"Delay count: {}\n"
		"Result count: {}\n"
		"Custom operation count: {}\n"
		"Custom source count: {}\n"
		"==============================================\n"
		"> Delays\n"
		"==============================================\n"
		"{}"
		"==============================================\n"
		"> Result keys\n"
		"==============================================\n"
		"{}"
		"==============================================\n"
		"> Instructions\n"
		"==============================================\n"
		"{}"
		"==============================================",
		code.input_count,
		code.output_count,
		code.instructions.size(),
		code.required_stack_size,
		code.delays.size(),
		code.result_keys.size(),
		code.custom_operations.size(),
		code.custom_sources.size(),
		format_compiled_simulation_code_delays(code),
		format_compiled_simulation_code_result_keys(code),
		format_compiled_simulation_code_instructions(code));
}

} // namespace asic

#endif // ASIC_SIMULATION_FORMAT_CODE_HPP
