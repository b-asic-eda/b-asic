#ifndef ASIC_SIMULATION_CORE_OPERATIONS_HPP
#define ASIC_SIMULATION_CORE_OPERATIONS_HPP

#include "../debug.hpp"
#include "../number.hpp"
#include "operation.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <stdexcept>
#include <utility>

namespace asic {

class constant_operation final : public abstract_operation {
public:
	constant_operation(result_key key, number value)
		: abstract_operation(std::move(key))
		, m_value(value) {}

	[[nodiscard]] std::size_t output_count() const noexcept final {
		return 1;
	}

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t, evaluation_context const&) const final {
		ASIC_DEBUG_MSG("Evaluating constant.");
		return m_value;
	}

	number m_value;
};

class addition_operation final : public binary_operation {
public:
	explicit addition_operation(result_key key)
		: binary_operation(std::move(key)) {}

	[[nodiscard]] std::size_t output_count() const noexcept final {
		return 1;
	}

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t, evaluation_context const& context) const final {
		ASIC_DEBUG_MSG("Evaluating addition.");
		return this->evaluate_lhs(context) + this->evaluate_rhs(context);
	}
};

class subtraction_operation final : public binary_operation {
public:
	explicit subtraction_operation(result_key key)
		: binary_operation(std::move(key)) {}

	[[nodiscard]] std::size_t output_count() const noexcept final {
		return 1;
	}

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t, evaluation_context const& context) const final {
		ASIC_DEBUG_MSG("Evaluating subtraction.");
		return this->evaluate_lhs(context) - this->evaluate_rhs(context);
	}
};

class multiplication_operation final : public binary_operation {
public:
	explicit multiplication_operation(result_key key)
		: binary_operation(std::move(key)) {}

	[[nodiscard]] std::size_t output_count() const noexcept final {
		return 1;
	}

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t, evaluation_context const& context) const final {
		ASIC_DEBUG_MSG("Evaluating multiplication.");
		return this->evaluate_lhs(context) * this->evaluate_rhs(context);
	}
};

class division_operation final : public binary_operation {
public:
	explicit division_operation(result_key key)
		: binary_operation(std::move(key)) {}

	[[nodiscard]] std::size_t output_count() const noexcept final {
		return 1;
	}

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t, evaluation_context const& context) const final {
		ASIC_DEBUG_MSG("Evaluating division.");
		return this->evaluate_lhs(context) / this->evaluate_rhs(context);
	}
};

class min_operation final : public binary_operation {
public:
	explicit min_operation(result_key key)
		: binary_operation(std::move(key)) {}

	[[nodiscard]] std::size_t output_count() const noexcept final {
		return 1;
	}

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t, evaluation_context const& context) const final {
		ASIC_DEBUG_MSG("Evaluating min.");
		auto const lhs = this->evaluate_lhs(context);
		if (lhs.imag() != 0) {
			throw std::runtime_error{"Min does not support complex numbers."};
		}
		auto const rhs = this->evaluate_rhs(context);
		if (rhs.imag() != 0) {
			throw std::runtime_error{"Min does not support complex numbers."};
		}
		return std::min(lhs.real(), rhs.real());
	}
};

class max_operation final : public binary_operation {
public:
	explicit max_operation(result_key key)
		: binary_operation(std::move(key)) {}

	[[nodiscard]] std::size_t output_count() const noexcept final {
		return 1;
	}

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t, evaluation_context const& context) const final {
		ASIC_DEBUG_MSG("Evaluating max.");
		auto const lhs = this->evaluate_lhs(context);
		if (lhs.imag() != 0) {
			throw std::runtime_error{"Max does not support complex numbers."};
		}
		auto const rhs = this->evaluate_rhs(context);
		if (rhs.imag() != 0) {
			throw std::runtime_error{"Max does not support complex numbers."};
		}
		return std::max(lhs.real(), rhs.real());
	}
};

class square_root_operation final : public unary_operation {
public:
	explicit square_root_operation(result_key key)
		: unary_operation(std::move(key)) {}

	[[nodiscard]] std::size_t output_count() const noexcept final {
		return 1;
	}

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t, evaluation_context const& context) const final {
		ASIC_DEBUG_MSG("Evaluating sqrt.");
		return std::sqrt(this->evaluate_input(context));
	}
};

class complex_conjugate_operation final : public unary_operation {
public:
	explicit complex_conjugate_operation(result_key key)
		: unary_operation(std::move(key)) {}

	[[nodiscard]] std::size_t output_count() const noexcept final {
		return 1;
	}

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t, evaluation_context const& context) const final {
		ASIC_DEBUG_MSG("Evaluating conj.");
		return std::conj(this->evaluate_input(context));
	}
};

class absolute_operation final : public unary_operation {
public:
	explicit absolute_operation(result_key key)
		: unary_operation(std::move(key)) {}

	[[nodiscard]] std::size_t output_count() const noexcept final {
		return 1;
	}

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t, evaluation_context const& context) const final {
		ASIC_DEBUG_MSG("Evaluating abs.");
		return std::abs(this->evaluate_input(context));
	}
};

class constant_multiplication_operation final : public unary_operation {
public:
	constant_multiplication_operation(result_key key, number value)
		: unary_operation(std::move(key))
		, m_value(value) {}

	[[nodiscard]] std::size_t output_count() const noexcept final {
		return 1;
	}

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t, evaluation_context const& context) const final {
		ASIC_DEBUG_MSG("Evaluating cmul.");
		return this->evaluate_input(context) * m_value;
	}

	number m_value;
};

class butterfly_operation final : public binary_operation {
public:
	explicit butterfly_operation(result_key key)
		: binary_operation(std::move(key)) {}

	[[nodiscard]] std::size_t output_count() const noexcept final {
		return 2;
	}

private:
	[[nodiscard]] number evaluate_output_impl(std::size_t index, evaluation_context const& context) const final {
		ASIC_DEBUG_MSG("Evaluating bfly.");
		if (index == 0) {
			return this->evaluate_lhs(context) + this->evaluate_rhs(context);
		}
		return this->evaluate_lhs(context) - this->evaluate_rhs(context);
	}
};

} // namespace asic

#endif // ASIC_SIMULATION_CORE_OPERATIONS_HPP
