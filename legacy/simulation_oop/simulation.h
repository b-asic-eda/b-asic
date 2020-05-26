#ifndef ASIC_SIMULATION_OOP_H
#define ASIC_SIMULATION_OOP_H

#include "../number.h"
#include "core_operations.h"
#include "custom_operation.h"
#include "operation.h"
#include "signal_flow_graph.h"
#include "special_operations.h"

#include <cstddef>
#include <cstdint>
#include <fmt/format.h>
#include <functional>
#include <limits>
#include <memory>
#include <optional>
#include <pybind11/functional.h>
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <variant>
#include <vector>

namespace asic {

using iteration_t = std::uint32_t;
using result_array_map = std::unordered_map<std::string, std::vector<number>>;
using input_function_t = std::function<number(iteration_t)>;
using input_provider_t = std::variant<number, std::vector<number>, input_function_t>;

class simulation final {
public:
	simulation(pybind11::handle sfg, std::optional<std::vector<std::optional<input_provider_t>>> input_providers = std::nullopt);

	void set_input(std::size_t index, input_provider_t input_provider);
	void set_inputs(std::vector<std::optional<input_provider_t>> input_providers);

	[[nodiscard]] std::vector<number> step(bool save_results, std::optional<std::size_t> bits_override, bool truncate);
	[[nodiscard]] std::vector<number> run_until(iteration_t iteration, bool save_results, std::optional<std::size_t> bits_override,
												bool truncate);
	[[nodiscard]] std::vector<number> run_for(iteration_t iterations, bool save_results, std::optional<std::size_t> bits_override,
											  bool truncate);
	[[nodiscard]] std::vector<number> run(bool save_results, std::optional<std::size_t> bits_override, bool truncate);

	[[nodiscard]] iteration_t iteration() const noexcept;
	[[nodiscard]] pybind11::dict results() const noexcept;

	void clear_results() noexcept;
	void clear_state() noexcept;

private:
	signal_flow_graph_operation m_sfg;
	result_array_map m_results;
	delay_map m_delays;
	iteration_t m_iteration = 0;
	std::vector<input_function_t> m_input_functions;
	std::optional<iteration_t> m_input_length;
};

} // namespace asic

#endif // ASIC_SIMULATION_OOP_H