#ifndef ASIC_SIMULATION_COMPILE_H
#define ASIC_SIMULATION_COMPILE_H

#include "instruction.h"

#include <cstddef>
#include <pybind11/pybind11.h>
#include <string>
#include <vector>

namespace asic {

using result_key = std::string;

struct simulation_code final {
	struct custom_operation final {
		// Python function used to evaluate the custom operation.
		pybind11::object evaluate_output;
		// Number of inputs that the custom operation takes.
		std::size_t input_count;
		// Number of outputs that the custom operation gives.
		std::size_t output_count;
	};

	struct custom_source final {
		// Index into custom_operations where the custom_operation corresponding to this custom_source is located.
		std::size_t custom_operation_index;
		// Output index of the custom_operation that this source gets it value from.
		std::size_t output_index;
	};

	struct delay_info final {
		// Initial value to set at the start of the simulation.
		number initial_value;
		// The result index where the current value should be stored at the start of each iteration.
		result_index_t result_index;
	};

	// Instructions to execute for one full iteration of the simulation.
	std::vector<instruction> instructions;
	// Custom operations used by the simulation.
	std::vector<custom_operation> custom_operations;
	// Signal sources that use custom operations.
	std::vector<custom_source> custom_sources;
	// Info about the delay operations used in the simulation.
	std::vector<delay_info> delays;
	// Keys for each result produced by the simulation. The index of the key matches the index of the result in the simulation state.
	std::vector<result_key> result_keys;
	// Number of values expected as input to the simulation.
	std::size_t input_count;
	// Number of values given as output from the simulation. This will be the number of values left on the stack after a full iteration of the simulation has been run.
	std::size_t output_count;
	// Maximum number of values that need to be able to fit on the stack in order to run a full iteration of the simulation.
	std::size_t required_stack_size;
};

[[nodiscard]] simulation_code compile_simulation(pybind11::handle sfg);

} // namespace asic

#endif // ASIC_SIMULATION_COMPILE_H