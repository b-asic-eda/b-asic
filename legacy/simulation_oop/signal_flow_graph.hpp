#ifndef ASIC_SIMULATION_SIGNAL_FLOW_GRAPH_HPP
#define ASIC_SIMULATION_SIGNAL_FLOW_GRAPH_HPP

#include "../algorithm.hpp"
#include "../debug.hpp"
#include "../number.hpp"
#include "core_operations.hpp"
#include "custom_operation.hpp"
#include "operation.hpp"
#include "special_operations.hpp"

#define NOMINMAX
#include <Python.h>
#include <cstddef>
#include <fmt/format.h>
#include <functional>
#include <memory>
#include <pybind11/pybind11.h>
#include <stdexcept>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace asic {

class signal_flow_graph_operation final : public abstract_operation {
public:
	using added_operation_cache = std::unordered_map<PyObject const*, std::shared_ptr<operation>>;

	signal_flow_graph_operation(result_key key);

	void create(pybind11::handle sfg, added_operation_cache& added);

	[[nodiscard]] std::vector<std::shared_ptr<input_operation>> const& inputs() noexcept;
	[[nodiscard]] std::size_t output_count() const noexcept final;

	[[nodiscard]] number evaluate_output(std::size_t index, evaluation_context const& context) const final;

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t index, evaluation_context const& context) const final;

	[[nodiscard]] static signal_source make_source(pybind11::handle op, std::size_t input_index, added_operation_cache& added,
												   std::string_view prefix);

	template <typename Operation, typename... Args>
	[[nodiscard]] static std::shared_ptr<Operation> add_operation(pybind11::handle op, added_operation_cache& added, Args&&... args) {
		return std::static_pointer_cast<Operation>(
			added.try_emplace(op.ptr(), std::make_shared<Operation>(std::forward<Args>(args)...)).first->second);
	}

	template <typename Operation, typename... Args>
	[[nodiscard]] static std::shared_ptr<Operation> add_unary_operation(pybind11::handle op, added_operation_cache& added,
																		std::string_view prefix, Args&&... args) {
		auto new_op = add_operation<Operation>(op, added, std::forward<Args>(args)...);
		new_op->connect(make_source(op, 0, added, prefix));
		return new_op;
	}

	template <typename Operation, typename... Args>
	[[nodiscard]] static std::shared_ptr<Operation> add_binary_operation(pybind11::handle op, added_operation_cache& added,
																		 std::string_view prefix, Args&&... args) {
		auto new_op = add_operation<Operation>(op, added, std::forward<Args>(args)...);
		new_op->connect(make_source(op, 0, added, prefix), make_source(op, 1, added, prefix));
		return new_op;
	}

	[[nodiscard]] static std::shared_ptr<operation> add_signal_flow_graph_operation(pybind11::handle sfg, added_operation_cache& added,
																					std::string_view prefix, result_key key);

	[[nodiscard]] static std::shared_ptr<custom_operation> add_custom_operation(pybind11::handle op, added_operation_cache& added,
																				std::string_view prefix, result_key key);

	[[nodiscard]] static std::shared_ptr<operation> make_operation(pybind11::handle op, added_operation_cache& added,
																   std::string_view prefix);

	std::vector<output_operation> m_output_operations{};
	std::vector<std::shared_ptr<input_operation>> m_input_operations{};
};

} // namespace asic

#endif // ASIC_SIMULATION_SIGNAL_FLOW_GRAPH_HPP
