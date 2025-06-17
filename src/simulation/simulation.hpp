#ifndef ASIC_SIMULATION_DOD_HPP
#define ASIC_SIMULATION_DOD_HPP

#include "../number.hpp"
#include "compile.hpp"

#define NOMINMAX
#include <cstddef>
#include <cstdint>
#include <functional>
#include <optional>
#include <pybind11/functional.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <variant>
#include <vector>

namespace asic {

using iteration_type = std::uint32_t;
using input_function_type = std::function<number(iteration_type)>;
using input_provider_type = std::variant<number, std::vector<number>, input_function_type>;

class simulation final {
public:
	simulation(pybind11::handle sfg, std::optional<std::vector<std::optional<input_provider_type>>> input_providers = std::nullopt);

	void set_input(std::size_t index, input_provider_type input_provider);
	void set_inputs(std::vector<std::optional<input_provider_type>> input_providers);

	[[nodiscard]] std::vector<number> step(bool save_results, std::optional<std::uint8_t> bits_override, bool quantize);
	[[nodiscard]] std::vector<number> run_until(iteration_type iteration, bool save_results, std::optional<std::uint8_t> bits_override,
												bool quantize);
	[[nodiscard]] std::vector<number> run_for(iteration_type iterations, bool save_results, std::optional<std::uint8_t> bits_override,
											  bool quantize);
	[[nodiscard]] std::vector<number> run(bool save_results, std::optional<std::uint8_t> bits_override, bool quantize);

	[[nodiscard]] iteration_type iteration() const noexcept;
	[[nodiscard]] pybind11::dict results() const noexcept;

	void clear_results() noexcept;
	void clear_state() noexcept;

private:
	simulation_code m_code;
	std::vector<input_function_type> m_input_functions;
	std::vector<number> m_delays{};
	std::optional<iteration_type> m_input_length{};
	iteration_type m_iteration = 0;
	std::vector<std::vector<number>> m_results{};
};

} // namespace asic

#endif // ASIC_SIMULATION_DOD_HPP
