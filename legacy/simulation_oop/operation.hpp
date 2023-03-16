#ifndef ASIC_SIMULATION_OPERATION_HPP
#define ASIC_SIMULATION_OPERATION_HPP

#include "../number.hpp"
#include "../span.hpp"

#include <cstddef>
#include <cstdint>
#include <fmt/format.h>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace asic {

class operation;
class signal_source;

using result_key = std::string;
using result_map = std::unordered_map<result_key, std::optional<number>>;
using delay_map = std::unordered_map<result_key, number>;
using delay_queue = std::vector<std::pair<result_key, signal_source const*>>;

struct evaluation_context final {
	result_map* results = nullptr;
	delay_map* delays = nullptr;
	delay_queue* deferred_delays = nullptr;
	std::optional<std::size_t> bits_override{};
	bool quantize = false;
};

class signal_source final {
public:
	signal_source() noexcept = default;
	signal_source(std::shared_ptr<const operation> op, std::size_t index, std::optional<std::size_t> bits);

	[[nodiscard]] explicit operator bool() const noexcept;

	[[nodiscard]] std::optional<number> current_output(delay_map const& delays) const;
	[[nodiscard]] number evaluate_output(evaluation_context const& context) const;

	[[nodiscard]] std::optional<std::size_t> bits() const noexcept;

private:
	std::shared_ptr<const operation> m_operation{};
	std::size_t m_index = 0;
	std::optional<std::size_t> m_bits{};
};

class operation { // NOLINT(cppcoreguidelines-special-member-functions)
public:
	operation() noexcept = default;
	virtual ~operation() = default;

	[[nodiscard]] virtual std::size_t output_count() const noexcept = 0;
	[[nodiscard]] virtual std::optional<number> current_output(std::size_t index, delay_map const& delays) const = 0;
	[[nodiscard]] virtual number evaluate_output(std::size_t index, evaluation_context const& context) const = 0;
};

class abstract_operation : public operation { // NOLINT(cppcoreguidelines-special-member-functions)
public:
	explicit abstract_operation(result_key key);
	~abstract_operation() override = default;

	[[nodiscard]] std::optional<number> current_output(std::size_t, delay_map const&) const override;
	[[nodiscard]] number evaluate_output(std::size_t index, evaluation_context const& context) const override;

protected:
	[[nodiscard]] virtual number evaluate_output_impl(std::size_t index, evaluation_context const& context) const = 0;
	[[nodiscard]] virtual number quantize_input(std::size_t index, number value, std::size_t bits) const;

	[[nodiscard]] result_key const& key_base() const;
	[[nodiscard]] result_key key_of_output(std::size_t index) const;

private:
	result_key m_key;
};

class unary_operation : public abstract_operation { // NOLINT(cppcoreguidelines-special-member-functions)
public:
	explicit unary_operation(result_key key);
	~unary_operation() override = default;

	void connect(signal_source in);

protected:
	[[nodiscard]] bool connected() const noexcept;
	[[nodiscard]] signal_source const& input() const noexcept;
	[[nodiscard]] number evaluate_input(evaluation_context const& context) const;

private:
	signal_source m_in;
};

class binary_operation : public abstract_operation { // NOLINT(cppcoreguidelines-special-member-functions)
public:
	explicit binary_operation(result_key key);
	~binary_operation() override = default;

	void connect(signal_source lhs, signal_source rhs);

protected:
	[[nodiscard]] signal_source const& lhs() const noexcept;
	[[nodiscard]] signal_source const& rhs() const noexcept;
	[[nodiscard]] number evaluate_lhs(evaluation_context const& context) const;
	[[nodiscard]] number evaluate_rhs(evaluation_context const& context) const;

private:
	signal_source m_lhs;
	signal_source m_rhs;
};

class nary_operation : public abstract_operation { // NOLINT(cppcoreguidelines-special-member-functions)
public:
	explicit nary_operation(result_key key);
	~nary_operation() override = default;

	void connect(std::vector<signal_source> inputs);

protected:
	[[nodiscard]] span<signal_source const> inputs() const noexcept;
	[[nodiscard]] std::vector<number> evaluate_inputs(evaluation_context const& context) const;

private:
	std::vector<signal_source> m_inputs{};
};

} // namespace asic

#endif // ASIC_SIMULATION_OPERATION_HPP
