#include "simulation.hpp"

#include "../algorithm.hpp"
#include "../debug.hpp"
#include "compile.hpp"
#include "run.hpp"

#define NOMINMAX
#include <fmt/format.h>
#include <limits>
#include <pybind11/numpy.h>
#include <utility>

namespace py = pybind11;

namespace asic {

simulation::simulation(pybind11::handle sfg, std::optional<std::vector<std::optional<input_provider_type>>> input_providers)
	: m_code(compile_simulation(sfg))
	, m_input_functions(sfg.attr("input_count").cast<std::size_t>(), [](iteration_type) -> number { return number{}; }) {
	m_delays.reserve(m_code.delays.size());
	for (auto const& delay : m_code.delays) {
		m_delays.push_back(delay.initial_value);
	}
	if (input_providers) {
		this->set_inputs(std::move(*input_providers));
	}
}

void simulation::set_input(std::size_t index, input_provider_type input_provider) {
	if (index >= m_input_functions.size()) {
		throw py::index_error{fmt::format("Input index out of range (expected 0-{}, got {})", m_input_functions.size() - 1, index)};
	}
	if (auto* const callable = std::get_if<input_function_type>(&input_provider)) {
		m_input_functions[index] = std::move(*callable);
	} else if (auto* const numeric = std::get_if<number>(&input_provider)) {
		m_input_functions[index] = [value = *numeric](iteration_type) -> number {
			return value;
		};
	} else if (auto* const list = std::get_if<std::vector<number>>(&input_provider)) {
		if (!m_input_length) {
			m_input_length = static_cast<iteration_type>(list->size());
		} else if (*m_input_length != static_cast<iteration_type>(list->size())) {
			throw py::value_error{fmt::format("Inconsistent input length for simulation (was {}, got {})", *m_input_length, list->size())};
		}
		m_input_functions[index] = [values = std::move(*list)](iteration_type n) -> number {
			return values.at(n);
		};
	}
}

void simulation::set_inputs(
	std::vector<std::optional<input_provider_type>> input_providers) { // NOLINT(performance-unnecessary-value-param)
	if (input_providers.size() != m_input_functions.size()) {
		throw py::value_error{fmt::format(
			"Wrong number of inputs supplied to simulation (expected {}, got {})", m_input_functions.size(), input_providers.size())};
	}
	for (auto&& [i, input_provider] : enumerate(input_providers)) {
		if (input_provider) {
			this->set_input(i, std::move(*input_provider));
		}
	}
}

std::vector<number> simulation::step(bool save_results, std::optional<std::uint8_t> bits_override, bool quantize) {
	return this->run_for(1, save_results, bits_override, quantize);
}

std::vector<number> simulation::run_until(iteration_type iteration, bool save_results, std::optional<std::uint8_t> bits_override,
										  bool quantize) {
	auto result = std::vector<number>{};
	while (m_iteration < iteration) {
		ASIC_DEBUG_MSG("Running simulation iteration.");
		auto inputs = std::vector<number>(m_code.input_count);
		for (auto&& [input, function] : zip(inputs, m_input_functions)) {
			input = function(m_iteration);
		}
		auto state = run_simulation(m_code, inputs, m_delays, bits_override, quantize);
		result = std::move(state.stack);
		if (save_results) {
			m_results.push_back(std::move(state.results));
		}
		++m_iteration;
	}
	return result;
}

std::vector<number> simulation::run_for(iteration_type iterations, bool save_results, std::optional<std::uint8_t> bits_override,
										bool quantize) {
	if (iterations > std::numeric_limits<iteration_type>::max() - m_iteration) {
		throw py::value_error("Simulation iteration type overflow!");
	}
	return this->run_until(m_iteration + iterations, save_results, bits_override, quantize);
}

std::vector<number> simulation::run(bool save_results, std::optional<std::uint8_t> bits_override, bool quantize) {
	if (m_input_length) {
		return this->run_until(*m_input_length, save_results, bits_override, quantize);
	}
	throw py::index_error{"Tried to run unlimited simulation"};
}

iteration_type simulation::iteration() const noexcept {
	return m_iteration;
}

pybind11::dict simulation::results() const noexcept {
	auto results = py::dict{};
	if (!m_results.empty()) {
		for (auto const& [i, key] : enumerate(m_code.result_keys)) {
			auto values = std::vector<number>{};
			values.reserve(m_results.size());
			for (auto const& result : m_results) {
				values.push_back(result[i]);
			}
			results[py::str{key}] = py::array{static_cast<py::ssize_t>(values.size()), values.data()};
		}
	}
	return results;
}

void simulation::clear_results() noexcept {
	m_results.clear();
}

void simulation::clear_state() noexcept {
	m_delays.clear();
}

} // namespace asic
