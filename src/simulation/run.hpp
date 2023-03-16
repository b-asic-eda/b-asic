#ifndef ASIC_SIMULATION_RUN_HPP
#define ASIC_SIMULATION_RUN_HPP

#include "../number.hpp"
#include "../span.hpp"
#include "compile.hpp"

#include <cstdint>
#include <vector>

namespace asic {

struct simulation_state final {
	std::vector<number> stack{};
	std::vector<number> results{};
};

simulation_state run_simulation(simulation_code const& code, span<number const> inputs, span<number> delays,
								std::optional<std::uint8_t> bits_override, bool quantize);

} // namespace asic

#endif // ASIC_SIMULATION_RUN_HPP
