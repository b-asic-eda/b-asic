#ifndef ASIC_SIMULATION_RUN_H
#define ASIC_SIMULATION_RUN_H

#include "../number.h"
#include "../span.h"
#include "compile.h"

#include <cstdint>
#include <vector>

namespace asic {

struct simulation_state final {
	std::vector<number> stack;
	std::vector<number> results;
};

simulation_state run_simulation(simulation_code const& code, span<number const> inputs, span<number> delays,
								std::optional<std::uint8_t> bits_override, bool truncate);

} // namespace asic

#endif // ASIC_SIMULATION_RUN_H