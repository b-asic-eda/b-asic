#ifndef ASIC_DEBUG_H
#define ASIC_DEBUG_H

#ifndef NDEBUG
#define ASIC_ENABLE_DEBUG_LOGGING 1
#define ASIC_ENABLE_ASSERTS 1
#else
#define ASIC_ENABLE_DEBUG_LOGGING 0
#define ASIC_ENABLE_ASSERTS 0
#endif // NDEBUG

#if ASIC_ENABLE_DEBUG_LOGGING
#include <filesystem>
#include <fmt/format.h>
#include <fstream>
#include <ostream>
#include <string_view>
#include <utility>
#endif // ASIC_ENABLE_DEBUG_LOGGING

#if ASIC_ENABLE_ASSERTS
#include <filesystem>
#include <cstdlib>
#include <cstdio>
#include <string_view>
#include <fmt/format.h>
#endif // ASIC_ENABLE_ASSERTS

namespace asic {

constexpr auto debug_log_filename = "_b_asic_debug_log.txt";

namespace detail {

#if ASIC_ENABLE_DEBUG_LOGGING
inline void log_debug_msg_string(std::string_view file, int line, std::string_view string) {
	static auto log_file = std::ofstream{debug_log_filename, std::ios::trunc};
	log_file << fmt::format("{:<40}: {}", fmt::format("{}:{}", std::filesystem::path{file}.filename().generic_string(), line), string)
			 << std::endl;
}

template <typename Format, typename... Args>
inline void log_debug_msg(std::string_view file, int line, Format&& format, Args&&... args) {
	log_debug_msg_string(file, line, fmt::format(std::forward<Format>(format), std::forward<Args>(args)...));
}
#endif // ASIC_ENABLE_DEBUG_LOGGING

#if ASIC_ENABLE_ASSERTS
inline void fail_assert(std::string_view file, int line, std::string_view condition_string) {
#if ASIC_ENABLE_DEBUG_LOGGING
	log_debug_msg(file, line, "Assertion failed: {}", condition_string);
#endif // ASIC_ENABLE_DEBUG_LOGGING
	fmt::print(stderr, "{}:{}: Assertion failed: {}\n", std::filesystem::path{file}.filename().generic_string(), line, condition_string);
	std::abort();
}

template <typename BoolConvertible>
inline void check_assert(std::string_view file, int line, std::string_view condition_string, BoolConvertible&& condition) {
	if (!static_cast<bool>(condition)) {
		fail_assert(file, line, condition_string);
	}
}
#endif // ASIC_ENABLE_ASSERTS

} // namespace detail
} // namespace asic

#if ASIC_ENABLE_DEBUG_LOGGING
#define ASIC_DEBUG_MSG(...) (asic::detail::log_debug_msg(__FILE__, __LINE__, __VA_ARGS__))
#else
#define ASIC_DEBUG_MSG(...) ((void)0)
#endif // ASIC_ENABLE_DEBUG_LOGGING

#if ASIC_ENABLE_ASSERTS
#define ASIC_ASSERT(condition) (asic::detail::check_assert(__FILE__, __LINE__, #condition, (condition)))
#else
#define ASIC_ASSERT(condition) ((void)0)
#endif

#endif // ASIC_DEBUG_H