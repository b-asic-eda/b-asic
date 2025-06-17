#include "compile.hpp"

#include "../algorithm.hpp"
#include "../debug.hpp"
#include "../span.hpp"
#include "format_code.hpp"

#define NOMINMAX
#include <Python.h>
#include <fmt/format.h>
#include <limits>
#include <optional>
#include <string_view>
#include <tuple>
#include <unordered_map>
#include <utility>

namespace py = pybind11;

namespace asic {

[[nodiscard]] static result_key key_base(py::handle op, std::string_view prefix) {
	auto const graph_id = op.attr("graph_id").cast<std::string_view>();
	return (prefix.empty()) ? result_key{graph_id} : fmt::format("{}.{}", prefix, graph_id);
}

[[nodiscard]] static result_key key_of_output(py::handle op, std::size_t output_index, std::string_view prefix) {
	auto base = key_base(op, prefix);
	if (base.empty()) {
		return fmt::to_string(output_index);
	}
	if (op.attr("output_count").cast<std::size_t>() == 1) {
		return base;
	}
	return fmt::format("{}.{}", base, output_index);
}

class compiler final {
public:
	simulation_code compile(py::handle sfg) {
		ASIC_DEBUG_MSG("Compiling code...");
		this->initialize_code(sfg.attr("input_count").cast<std::size_t>(), sfg.attr("output_count").cast<std::size_t>());
		auto deferred_delays = delay_queue{};
		this->add_outputs(sfg, deferred_delays);
		this->add_deferred_delays(std::move(deferred_delays));
		this->resolve_invalid_result_indices();
		ASIC_DEBUG_MSG("Compiled code:\n{}\n", format_compiled_simulation_code(m_code));
		return std::move(m_code);
	}

private:
	struct sfg_info final {
		py::handle sfg;
		std::size_t prefix_length;

		sfg_info(py::handle sfg, std::size_t prefix_length)
			: sfg(sfg)
			, prefix_length(prefix_length) {}

		[[nodiscard]] std::size_t find_input_operation_index(py::handle op) const {
			for (auto const& [i, in] : enumerate(sfg.attr("input_operations"))) {
				if (in.is(op)) {
					return i;
				}
			}
			throw py::value_error{"Stray Input operation in simulation SFG"};
		}
	};

	using sfg_info_stack = std::vector<sfg_info>;
	using delay_queue = std::vector<std::tuple<std::size_t, py::handle, std::string, sfg_info_stack>>;
	using added_output_cache = std::unordered_set<PyObject const*>;
	using added_result_cache = std::unordered_map<PyObject const*, result_index_type>;
	using added_custom_operation_cache = std::unordered_map<PyObject const*, std::size_t>;

	static constexpr auto no_result_index = std::numeric_limits<result_index_type>::max();

	void initialize_code(std::size_t input_count, std::size_t output_count) {
		m_code.required_stack_size = 0;
		m_code.input_count = input_count;
		m_code.output_count = output_count;
	}

	void add_outputs(py::handle sfg, delay_queue& deferred_delays) {
		for (auto const i : range(m_code.output_count)) {
			this->add_operation_output(sfg, i, std::string_view{}, sfg_info_stack{}, deferred_delays);
		}
	}

	void add_deferred_delays(delay_queue&& deferred_delays) {
		while (!deferred_delays.empty()) {
			auto new_deferred_delays = delay_queue{};
			for (auto const& [delay_index, op, prefix, sfg_stack] : deferred_delays) {
				this->add_source(op, 0, prefix, sfg_stack, deferred_delays);
				this->add_instruction(instruction_type::update_delay, no_result_index, -1).index = delay_index;
			}
			deferred_delays = new_deferred_delays;
		}
	}

	void resolve_invalid_result_indices() {
		for (auto& instruction : m_code.instructions) {
			if (instruction.result_index == no_result_index) {
				instruction.result_index = static_cast<result_index_type>(m_code.result_keys.size());
			}
		}
	}

	[[nodiscard]] static sfg_info_stack push_sfg(sfg_info_stack const& sfg_stack, py::handle sfg, std::size_t prefix_length) {
		auto const new_size = static_cast<std::size_t>(sfg_stack.size() + 1);
		auto new_sfg_stack = sfg_info_stack{};
		new_sfg_stack.reserve(new_size);
		for (auto const& info : sfg_stack) {
			new_sfg_stack.push_back(info);
		}
		new_sfg_stack.emplace_back(sfg, prefix_length);
		return new_sfg_stack;
	}

	[[nodiscard]] static sfg_info_stack pop_sfg(sfg_info_stack const& sfg_stack) {
		ASIC_ASSERT(!sfg_stack.empty());
		auto const new_size = static_cast<std::size_t>(sfg_stack.size() - 1);
		auto new_sfg_stack = sfg_info_stack{};
		new_sfg_stack.reserve(new_size);
		for (auto const& info : span{sfg_stack}.first(new_size)) {
			new_sfg_stack.push_back(info);
		}
		return new_sfg_stack;
	}

	instruction& add_instruction(instruction_type type, result_index_type result_index, std::ptrdiff_t stack_diff) {
		m_stack_depth += stack_diff;
		if (m_stack_depth < 0) {
			throw py::value_error{"Detected input/output count mismatch in simulation SFG"};
		}
		if (auto const stack_size = static_cast<std::size_t>(m_stack_depth); stack_size > m_code.required_stack_size) {
			m_code.required_stack_size = stack_size;
		}
		auto& instruction = m_code.instructions.emplace_back();
		instruction.type = type;
		instruction.result_index = result_index;
		return instruction;
	}

	[[nodiscard]] std::optional<result_index_type> begin_operation_output(py::handle op, std::size_t output_index,
																		  std::string_view prefix) {
		auto* const pointer = op.attr("outputs")[py::int_{output_index}].ptr();
		if (m_incomplete_outputs.count(pointer) != 0) {
			// Make sure the output doesn't depend on its own value, unless it's a delay operation.
			if (op.attr("type_name")().cast<std::string_view>() != "t") {
				throw py::value_error{"Direct feedback loop detected in simulation SFG"};
			}
		}
		// Try to add a new result.
		auto const [it, inserted] = m_added_results.try_emplace(pointer, static_cast<result_index_type>(m_code.result_keys.size()));
		if (inserted) {
			if (m_code.result_keys.size() >= static_cast<std::size_t>(std::numeric_limits<result_index_type>::max())) {
				throw py::value_error{fmt::format("Simulation SFG requires too many outputs to be stored (limit: {})",
												  std::numeric_limits<result_index_type>::max())};
			}
			m_code.result_keys.push_back(key_of_output(op, output_index, prefix));
			m_incomplete_outputs.insert(pointer);
			return it->second;
		}
		// If the result has already been added, we re-use the old result and
		// return std::nullopt to indicate that we don't need to add all the required instructions again.
		this->add_instruction(instruction_type::push_result, it->second, 1).index = static_cast<std::size_t>(it->second);
		return std::nullopt;
	}

	void end_operation_output(py::handle op, std::size_t output_index) {
		auto* const pointer = op.attr("outputs")[py::int_{output_index}].ptr();
		[[maybe_unused]] auto const erased = m_incomplete_outputs.erase(pointer);
		ASIC_ASSERT(erased == 1);
	}

	[[nodiscard]] std::size_t try_add_custom_operation(py::handle op) {
		auto const [it, inserted] = m_added_custom_operations.try_emplace(op.ptr(), m_added_custom_operations.size());
		if (inserted) {
			auto& custom_operation = m_code.custom_operations.emplace_back();
			custom_operation.evaluate_output = op.attr("evaluate_output");
			custom_operation.input_count = op.attr("input_count").cast<std::size_t>();
			custom_operation.output_count = op.attr("output_count").cast<std::size_t>();
		}
		return it->second;
	}

	[[nodiscard]] std::size_t add_delay_info(number initial_value, result_index_type result_index) {
		auto const delay_index = m_code.delays.size();
		auto& delay = m_code.delays.emplace_back();
		delay.initial_value = initial_value;
		delay.result_index = result_index;
		return delay_index;
	}

	void add_source(py::handle op, std::size_t input_index, std::string_view prefix, sfg_info_stack const& sfg_stack,
					delay_queue& deferred_delays) {
		auto const signal = py::object{op.attr("inputs")[py::int_{input_index}].attr("signals")[py::int_{0}]};
		auto const src = py::handle{signal.attr("source")};
		auto const operation = py::handle{src.attr("operation")};
		auto const index = src.attr("index").cast<std::size_t>();
		this->add_operation_output(operation, index, prefix, sfg_stack, deferred_delays);
		if (!signal.attr("bits").is_none()) {
			auto const bits = signal.attr("bits").cast<std::size_t>();
			if (bits > 64) {
				throw py::value_error{"Cannot quantize to more than 64 bits"};
			}
			this->add_instruction(instruction_type::quantize, no_result_index, 0).bit_mask = static_cast<std::int64_t>(
				(std::int64_t{1} << bits) - 1);
		}
	}

	void add_unary_operation_output(py::handle op, result_index_type result_index, std::string_view prefix, sfg_info_stack const& sfg_stack,
									delay_queue& deferred_delays, instruction_type type) {
		this->add_source(op, 0, prefix, sfg_stack, deferred_delays);
		this->add_instruction(type, result_index, 0);
	}

	void add_binary_operation_output(py::handle op, result_index_type result_index, std::string_view prefix,
									 sfg_info_stack const& sfg_stack, delay_queue& deferred_delays, instruction_type type) {
		this->add_source(op, 0, prefix, sfg_stack, deferred_delays);
		this->add_source(op, 1, prefix, sfg_stack, deferred_delays);
		this->add_instruction(type, result_index, -1);
	}

	void add_operation_output(py::handle op, std::size_t output_index, std::string_view prefix, sfg_info_stack const& sfg_stack,
							  delay_queue& deferred_delays) {
		auto const type_name = op.attr("type_name")().cast<std::string_view>();
		if (type_name == "out") {
			this->add_source(op, 0, prefix, sfg_stack, deferred_delays);
		} else if (auto const result_index = this->begin_operation_output(op, output_index, prefix)) {
			if (type_name == "c") {
				this->add_instruction(instruction_type::push_constant, *result_index, 1).value = op.attr("value").cast<number>();
			} else if (type_name == "add") {
				this->add_binary_operation_output(op, *result_index, prefix, sfg_stack, deferred_delays, instruction_type::addition);
			} else if (type_name == "sub") {
				this->add_binary_operation_output(op, *result_index, prefix, sfg_stack, deferred_delays, instruction_type::subtraction);
			} else if (type_name == "mul") {
				this->add_binary_operation_output(op, *result_index, prefix, sfg_stack, deferred_delays, instruction_type::multiplication);
			} else if (type_name == "div") {
				this->add_binary_operation_output(op, *result_index, prefix, sfg_stack, deferred_delays, instruction_type::division);
			} else if (type_name == "min") {
				this->add_binary_operation_output(op, *result_index, prefix, sfg_stack, deferred_delays, instruction_type::min);
			} else if (type_name == "max") {
				this->add_binary_operation_output(op, *result_index, prefix, sfg_stack, deferred_delays, instruction_type::max);
			} else if (type_name == "sqrt") {
				this->add_unary_operation_output(op, *result_index, prefix, sfg_stack, deferred_delays, instruction_type::square_root);
			} else if (type_name == "conj") {
				this->add_unary_operation_output(
					op, *result_index, prefix, sfg_stack, deferred_delays, instruction_type::complex_conjugate);
			} else if (type_name == "abs") {
				this->add_unary_operation_output(op, *result_index, prefix, sfg_stack, deferred_delays, instruction_type::absolute);
			} else if (type_name == "cmul") {
				this->add_source(op, 0, prefix, sfg_stack, deferred_delays);
				this->add_instruction(instruction_type::constant_multiplication, *result_index, 0).value = op.attr("value").cast<number>();
			} else if (type_name == "bfly") {
				if (output_index == 0) {
					this->add_source(op, 0, prefix, sfg_stack, deferred_delays);
					this->add_source(op, 1, prefix, sfg_stack, deferred_delays);
					this->add_instruction(instruction_type::addition, *result_index, -1);
				} else {
					this->add_source(op, 0, prefix, sfg_stack, deferred_delays);
					this->add_source(op, 1, prefix, sfg_stack, deferred_delays);
					this->add_instruction(instruction_type::subtraction, *result_index, -1);
				}
			} else if (type_name == "in") {
				if (sfg_stack.empty()) {
					throw py::value_error{"Encountered Input operation outside SFG in simulation"};
				}
				auto const& info = sfg_stack.back();
				auto const input_index = info.find_input_operation_index(op);
				if (sfg_stack.size() == 1) {
					this->add_instruction(instruction_type::push_input, *result_index, 1).index = input_index;
				} else {
					this->add_source(info.sfg, input_index, prefix.substr(0, info.prefix_length), pop_sfg(sfg_stack), deferred_delays);
					this->add_instruction(instruction_type::forward_value, *result_index, 0);
				}
			} else if (type_name == "t") {
				auto const delay_index = this->add_delay_info(op.attr("initial_value").cast<number>(), *result_index);
				deferred_delays.emplace_back(delay_index, op, std::string{prefix}, sfg_stack);
				this->add_instruction(instruction_type::push_delay, *result_index, 1).index = delay_index;
			} else if (type_name == "sfg") {
				auto const output_op = py::handle{op.attr("output_operations")[py::int_{output_index}]};
				this->add_source(output_op, 0, key_base(op, prefix), push_sfg(sfg_stack, op, prefix.size()), deferred_delays);
				this->add_instruction(instruction_type::forward_value, *result_index, 0);
			} else {
				auto const custom_operation_index = this->try_add_custom_operation(op);
				auto const& custom_operation = m_code.custom_operations[custom_operation_index];
				for (auto const i : range(custom_operation.input_count)) {
					this->add_source(op, i, prefix, sfg_stack, deferred_delays);
				}
				auto const custom_source_index = m_code.custom_sources.size();
				auto& custom_source = m_code.custom_sources.emplace_back();
				custom_source.custom_operation_index = custom_operation_index;
				custom_source.output_index = output_index;
				auto const stack_diff = std::ptrdiff_t{1} - static_cast<std::ptrdiff_t>(custom_operation.input_count);
				this->add_instruction(instruction_type::custom, *result_index, stack_diff).index = custom_source_index;
			}
			this->end_operation_output(op, output_index);
		}
	}

	simulation_code m_code{};
	added_output_cache m_incomplete_outputs{};
	added_result_cache m_added_results{};
	added_custom_operation_cache m_added_custom_operations{};
	std::ptrdiff_t m_stack_depth = 0;
};

simulation_code compile_simulation(pybind11::handle sfg) {
	return compiler{}.compile(sfg);
}

} // namespace asic
