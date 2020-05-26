cmake_minimum_required(VERSION 3.8)

project(
	"B-ASIC"
	VERSION 1.0.0
	DESCRIPTION "Better ASIC Toolbox for Python 3"
	LANGUAGES C CXX
)

# Find dependencies.
find_package(fmt REQUIRED)
find_package(pybind11 CONFIG REQUIRED)

set(LIBRARY_NAME "b_asic") # Name of the python library directory.
set(TARGET_NAME "_${LIBRARY_NAME}") # Name of this extension module.

# Set output directory for compiled binaries.
if(NOT CMAKE_LIBRARY_OUTPUT_DIRECTORY)
	include(GNUInstallDirs)
	set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_INSTALL_LIBDIR}")
endif()
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_DEBUG "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_RELEASE "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
set(CMAKE_PDB_OUTPUT_DIRECTORY "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
set(CMAKE_PDB_OUTPUT_DIRECTORY_DEBUG "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
set(CMAKE_PDB_OUTPUT_DIRECTORY_RELEASE "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")

# Add files to be compiled into Python module.
pybind11_add_module(
	"${TARGET_NAME}"

	# Main files.
	"${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp"
	"${CMAKE_CURRENT_SOURCE_DIR}/src/simulation.cpp"
	
	# For DOD simulation.
	"${CMAKE_CURRENT_SOURCE_DIR}/src/simulation/compile.cpp"
	"${CMAKE_CURRENT_SOURCE_DIR}/src/simulation/run.cpp"
	"${CMAKE_CURRENT_SOURCE_DIR}/src/simulation/simulation.cpp"

	# For OOP simulation (see legacy folder).
	#"${CMAKE_CURRENT_SOURCE_DIR}/src/simulation/custom_operation.cpp"
	#"${CMAKE_CURRENT_SOURCE_DIR}/src/simulation/operation.cpp"
	#"${CMAKE_CURRENT_SOURCE_DIR}/src/simulation/signal_flow_graph.cpp"
	#"${CMAKE_CURRENT_SOURCE_DIR}/src/simulation/simulation.cpp"
	#"${CMAKE_CURRENT_SOURCE_DIR}/src/simulation/special_operations.cpp"
)

# Include headers.
target_include_directories(
	"${TARGET_NAME}"
    PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/src"
)

# Use C++17.
target_compile_features(
	"${TARGET_NAME}"
	PRIVATE
		cxx_std_17
)

# Set compiler-specific options using generator expressions.
target_compile_options(
	"${TARGET_NAME}"
	PRIVATE
		$<$<OR:$<CXX_COMPILER_ID:GNU>,$<CXX_COMPILER_ID:Clang>>:
			-W -Wall -Wextra -Werror -Wno-psabi
			$<$<CONFIG:Debug>:-g>
			$<$<NOT:$<CONFIG:Debug>>:-O3>
		>
		$<$<CXX_COMPILER_ID:MSVC>:
			/W3 /WX /permissive- /utf-8
			$<$<CONFIG:Debug>:/Od>
			$<$<NOT:$<CONFIG:Debug>>:/Ot>
		>
)

# Add libraries. Note: pybind11 is already added in pybind11_add_module.
target_link_libraries(
	"${TARGET_NAME}"
	PRIVATE
		$<TARGET_NAME_IF_EXISTS:fmt::fmt-header-only>
		$<$<NOT:$<TARGET_EXISTS:fmt::fmt-header-only>>:fmt::fmt>
)

# Copy binaries to project folder for debugging during development.
if(NOT ASIC_BUILDING_PYTHON_DISTRIBUTION)
	add_custom_target(
		copy_binaries ALL
		COMMAND ${CMAKE_COMMAND} -E copy "$<TARGET_FILE:${TARGET_NAME}>" "${CMAKE_CURRENT_LIST_DIR}"
		COMMENT "Copying binaries to ${CMAKE_CURRENT_LIST_DIR}"
		DEPENDS "${TARGET_NAME}"
	)
endif()
