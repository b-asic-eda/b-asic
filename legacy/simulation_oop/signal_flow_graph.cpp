#include "signal_flow_graph.hpp"

#include "../debug.hpp"

namespace py = pybind11;

namespace asic {

signal_flow_graph_operation::signal_flow_graph_operation(result_key key)
	: abstract_operation(std::move(key)) {}

void signal_flow_graph_operation::create(pybind11::handle sfg, added_operation_cache& added) {
	ASIC_DEBUG_MSG("Creating SFG.");
	for (auto const& [i, op] : enumerate(sfg.attr("output_operations"))) {
		ASIC_DEBUG_MSG("Adding output op.");
		m_output_operations.emplace_back(this->key_of_output(i)).connect(make_source(op, 0, added, this->key_base()));
	}
	for (auto const& op : sfg.attr("input_operations")) {
		ASIC_DEBUG_MSG("Adding input op.");
		if (!m_input_operations.emplace_back(std::dynamic_pointer_cast<input_operation>(make_operation(op, added, this->key_base())))) {
			throw py::value_error{"Invalid input operation in SFG."};
		}
	}
}

std::vector<std::shared_ptr<input_operation>> const& signal_flow_graph_operation::inputs() noexcept {
	return m_input_operations;
}

std::size_t signal_flow_graph_operation::output_count() const noexcept {
	return m_output_operations.size();
}

number signal_flow_graph_operation::evaluate_output(std::size_t index, evaluation_context const& context) const {
	ASIC_DEBUG_MSG("Evaluating SFG.");
	return m_output_operations.at(index).evaluate_output(0, context);
}

number signal_flow_graph_operation::evaluate_output_impl(std::size_t, evaluation_context const&) const {
	return number{};
}

signal_source signal_flow_graph_operation::make_source(pybind11::handle op, std::size_t input_index, added_operation_cache& added,
													   std::string_view prefix) {
	auto const signal = py::object{op.attr("inputs")[py::int_{input_index}].attr("signals")[py::int_{0}]};
	auto const src = py::handle{signal.attr("source")};
	auto const operation = py::handle{src.attr("operation")};
	auto const index = src.attr("index").cast<std::size_t>();
	auto bits = std::optional<std::size_t>{};
	if (!signal.attr("bits").is_none()) {
		bits = signal.attr("bits").cast<std::size_t>();
	}
	return signal_source{make_operation(operation, added, prefix), index, bits};
}

std::shared_ptr<operation> signal_flow_graph_operation::add_signal_flow_graph_operation(pybind11::handle sfg, added_operation_cache& added,
																						std::string_view prefix, result_key key) {
	auto const new_op = add_operation<signal_flow_graph_operation>(sfg, added, std::move(key));
	new_op->create(sfg, added);
	for (auto&& [i, input] : enumerate(new_op->inputs())) {
		input->connect(make_source(sfg, i, added, prefix));
	}
	return new_op;
}

std::shared_ptr<custom_operation> signal_flow_graph_operation::add_custom_operation(pybind11::handle op, added_operation_cache& added,
																					std::string_view prefix, result_key key) {
	auto const input_count = op.attr("input_count").cast<std::size_t>();
	auto const output_count = op.attr("output_count").cast<std::size_t>();
	auto new_op = add_operation<custom_operation>(
		op, added, std::move(key), op.attr("evaluate_output"), op.attr("truncate_input"), output_count);
	auto inputs = std::vector<signal_source>{};
	inputs.reserve(input_count);
	for (auto const i : range(input_count)) {
		inputs.push_back(make_source(op, i, added, prefix));
	}
	new_op->connect(std::move(inputs));
	return new_op;
}

std::shared_ptr<operation> signal_flow_graph_operation::make_operation(pybind11::handle op, added_operation_cache& added,
																	   std::string_view prefix) {
	if (auto const it = added.find(op.ptr()); it != added.end()) {
		ASIC_ASSERT(it->second);
		return it->second;
	}
	auto const graph_id = op.attr("graph_id").cast<std::string_view>();
	auto const type_name = op.attr("type_name")().cast<std::string_view>();
	auto key = (prefix.empty()) ? result_key{graph_id} : fmt::format("{}.{}", prefix, graph_id);
	if (type_name == "c") {
		auto const value = op.attr("value").cast<number>();
		return add_operation<constant_operation>(op, added, std::move(key), value);
	}
	if (type_name == "add") {
		return add_binary_operation<addition_operation>(op, added, prefix, std::move(key));
	}
	if (type_name == "sub") {
		return add_binary_operation<subtraction_operation>(op, added, prefix, std::move(key));
	}
	if (type_name == "mul") {
		return add_binary_operation<multiplication_operation>(op, added, prefix, std::move(key));
	}
	if (type_name == "div") {
		return add_binary_operation<division_operation>(op, added, prefix, std::move(key));
	}
	if (type_name == "min") {
		return add_binary_operation<min_operation>(op, added, prefix, std::move(key));
	}
	if (type_name == "max") {
		return add_binary_operation<max_operation>(op, added, prefix, std::move(key));
	}
	if (type_name == "sqrt") {
		return add_unary_operation<square_root_operation>(op, added, prefix, std::move(key));
	}
	if (type_name == "conj") {
		return add_unary_operation<complex_conjugate_operation>(op, added, prefix, std::move(key));
	}
	if (type_name == "abs") {
		return add_unary_operation<absolute_operation>(op, added, prefix, std::move(key));
	}
	if (type_name == "cmul") {
		auto const value = op.attr("value").cast<number>();
		return add_unary_operation<constant_multiplication_operation>(op, added, prefix, std::move(key), value);
	}
	if (type_name == "bfly") {
		return add_binary_operation<butterfly_operation>(op, added, prefix, std::move(key));
	}
	if (type_name == "in") {
		return add_operation<input_operation>(op, added, std::move(key));
	}
	if (type_name == "out") {
		return add_unary_operation<output_operation>(op, added, prefix, std::move(key));
	}
	if (type_name == "t") {
		auto const initial_value = op.attr("initial_value").cast<number>();
		return add_unary_operation<delay_operation>(op, added, prefix, std::move(key), initial_value);
	}
	if (type_name == "sfg") {
		return add_signal_flow_graph_operation(op, added, prefix, std::move(key));
	}
	return add_custom_operation(op, added, prefix, std::move(key));
}

} // namespace asic
