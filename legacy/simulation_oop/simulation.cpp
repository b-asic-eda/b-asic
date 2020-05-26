#define NOMINMAX
#include "simulation.h"

#include "../debug.h"

namespace py = pybind11;

namespace asic {

simulation::simulation(pybind11::handle sfg, std::optional<std::vector<std::optional<input_provider_t>>> input_providers)
	: m_sfg("")
	, m_input_functions(sfg.attr("input_count").cast<std::size_t>(), [](iteration_t) -> number { return number{}; }) {
	if (input_providers) {
		this->set_inputs(std::move(*input_providers));
	}
	auto added = signal_flow_graph_operation::added_operation_cache{};
	m_sfg.create(sfg, added);
}

void simulation::set_input(std::size_t index, input_provider_t input_provider) {
	if (index >= m_input_functions.size()) {
		throw py::index_error{fmt::format("Input index out of range (expected 0-{}, got {})", m_input_functions.size() - 1, index)};
	}
	if (auto* const callable = std::get_if<input_function_t>(&input_provider)) {
		m_input_functions[index] = std::move(*callable);
	} else if (auto* const numeric = std::get_if<number>(&input_provider)) {
		m_input_functions[index] = [value = *numeric](iteration_t) -> number {
			return value;
		};
	} else if (auto* const list = std::get_if<std::vector<number>>(&input_provider)) {
		if (!m_input_length) {
			m_input_length = static_cast<iteration_t>(list->size());
		} else if (*m_input_length != static_cast<iteration_t>(list->size())) {
			throw py::value_error{fmt::format("Inconsistent input length for simulation (was {}, got {})", *m_input_length, list->size())};
		}
		m_input_functions[index] = [values = std::move(*list)](iteration_t n) -> number {
			return values.at(n);
		};
	}
}

void simulation::set_inputs(std::vector<std::optional<input_provider_t>> input_providers) {
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

std::vector<number> simulation::step(bool save_results, std::optional<std::size_t> bits_override, bool truncate) {
	return this->run_for(1, save_results, bits_override, truncate);
}

std::vector<number> simulation::run_until(iteration_t iteration, bool save_results, std::optional<std::size_t> bits_override,
										  bool truncate) {
	auto result = std::vector<number>{};
	while (m_iteration < iteration) {
		ASIC_DEBUG_MSG("Running simulation iteration.");
		for (auto&& [input, function] : zip(m_sfg.inputs(), m_input_functions)) {
			input->value(function(m_iteration));
		}

		result.clear();
		result.reserve(m_sfg.output_count());

		auto results = result_map{};
		auto deferred_delays = delay_queue{};
		auto context = evaluation_context{};
		context.results = &results;
		context.delays = &m_delays;
		context.deferred_delays = &deferred_delays;
		context.bits_override = bits_override;
		context.truncate = truncate;

		for (auto const i : range(m_sfg.output_count())) {
			result.push_back(m_sfg.evaluate_output(i, context));
		}

		while (!deferred_delays.empty()) {
			auto new_deferred_delays = delay_queue{};
			context.deferred_delays = &new_deferred_delays;
			for (auto const& [key, src] : deferred_delays) {
				ASIC_ASSERT(src);
				m_delays[key] = src->evaluate_output(context);
			}
			deferred_delays = std::move(new_deferred_delays);
		}

		if (save_results) {
			for (auto const& [key, value] : results) {
				m_results[key].push_back(value.value());
			}
		}
		++m_iteration;
	}
	return result;
}

std::vector<number> simulation::run_for(iteration_t iterations, bool save_results, std::optional<std::size_t> bits_override,
										bool truncate) {
	if (iterations > std::numeric_limits<iteration_t>::max() - m_iteration) {
		throw py::value_error("Simulation iteration type overflow!");
	}
	return this->run_until(m_iteration + iterations, save_results, bits_override, truncate);
}

std::vector<number> simulation::run(bool save_results, std::optional<std::size_t> bits_override, bool truncate) {
	if (m_input_length) {
		return this->run_until(*m_input_length, save_results, bits_override, truncate);
	}
	throw py::index_error{"Tried to run unlimited simulation"};
}

iteration_t simulation::iteration() const noexcept {
	return m_iteration;
}

pybind11::dict simulation::results() const noexcept {
	auto results = py::dict{};
	for (auto const& [key, values] : m_results) {
		results[py::str{key}] = py::array{static_cast<py::ssize_t>(values.size()), values.data()};
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
