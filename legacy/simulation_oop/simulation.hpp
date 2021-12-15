#ifndef ASIC_SIMULATION_OOP_HPP
#define ASIC_SIMULATION_OOP_HPP

#include "../number.hpp"
#include "core_operations.hpp"
#include "custom_operation.hpp"
#include "operation.hpp"
#include "signal_flow_graph.hpp"
#include "special_operations.hpp"

#define NOMINMAX
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

using iteration_type = std::uint32_t;
using result_array_map = std::unordered_map<std::string, std::vector<number>>;
using input_function_type = std::function<number(iteration_type)>;
using input_provider_type = std::variant<number, std::vector<number>, input_function_type>;

class simulation final {
public:
	simulation(pybind11::handle sfg, std::optional<std::vector<std::optional<input_provider_type>>> input_providers = std::nullopt);

	void set_input(std::size_t index, input_provider_type input_provider);
	void set_inputs(std::vector<std::optional<input_provider_type>> input_providers);

	[[nodiscard]] std::vector<number> step(bool save_results, std::optional<std::size_t> bits_override, bool truncate);
	[[nodiscard]] std::vector<number> run_until(iteration_type iteration, bool save_results, std::optional<std::size_t> bits_override,
												bool truncate);
	[[nodiscard]] std::vector<number> run_for(iteration_type iterations, bool save_results, std::optional<std::size_t> bits_override,
											  bool truncate);
	[[nodiscard]] std::vector<number> run(bool save_results, std::optional<std::size_t> bits_override, bool truncate);

	[[nodiscard]] iteration_type iteration() const noexcept;
	[[nodiscard]] pybind11::dict results() const noexcept;

	void clear_results() noexcept;
	void clear_state() noexcept;

private:
	signal_flow_graph_operation m_sfg{""};
	result_array_map m_results{};
	delay_map m_delays{};
	iteration_type m_iteration = 0;
	std::optional<iteration_type> m_input_length{};
	std::vector<input_function_type> m_input_functions;
};

} // namespace asic

#endif // ASIC_SIMULATION_OOP_HPP
