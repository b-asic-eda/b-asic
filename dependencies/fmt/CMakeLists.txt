message(STATUS "Fetching fmt...")

FetchContent_Declare(fmt
	GIT_REPOSITORY https://github.com/fmtlib/fmt
	GIT_TAG 9.1.0
)
FetchContent_MakeAvailable(fmt)

add_library(dependency_fmt INTERFACE)
target_include_directories(dependency_fmt SYSTEM INTERFACE $<TARGET_PROPERTY:fmt-header-only,INTERFACE_INCLUDE_DIRECTORIES>)
target_link_libraries(dependency_fmt INTERFACE fmt-header-only)
