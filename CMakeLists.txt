cmake_minimum_required(VERSION 3.8)
project("B-ASIC"
	VERSION 1.0.0
	DESCRIPTION "Better ASIC Toolbox for Python 3"
	LANGUAGES C CXX)

option(ASIC_USE_FETCHCONTENT "Automatically download dependencies" ON)
option(ASIC_USE_CLANG_TIDY "Use clang-tidy for static analysis" OFF)
option(ASIC_BUILDING_PYTHON_DISTRIBUTION "Don't copy compiled binaries to project directory" OFF)

set(LIBRARY_NAME "b_asic") # Name of the python library directory.
set(TARGET_NAME "_${LIBRARY_NAME}") # Name of this extension module.

# Find dependencies.
if(ASIC_USE_FETCHCONTENT)
	add_subdirectory(dependencies)
else()
	find_package(fmt REQUIRED)
	find_package(pybind11 CONFIG REQUIRED)
endif()

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
pybind11_add_module("${TARGET_NAME}"
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
target_include_directories("${TARGET_NAME}" PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")

# Use C++17.
target_compile_features("${TARGET_NAME}" PRIVATE cxx_std_17)

# Set compiler-specific options using generator expressions.
target_compile_options("${TARGET_NAME}" PRIVATE
	$<$<CXX_COMPILER_ID:GNU>:   -std=c++17  -Wall -Wextra   -Wpedantic      -Werror -Wno-psabi      $<$<CONFIG:Debug>:-Og -g>   $<$<CONFIG:Release>:-O3>    $<$<CONFIG:MinSizeRel>:-Os> $<$<CONFIG:RelWithDebInfo>:-O3 -g>>
	$<$<CXX_COMPILER_ID:Clang>: -std=c++17  -Wall -Wextra   -Wpedantic      -Werror                 $<$<CONFIG:Debug>:-Og -g>   $<$<CONFIG:Release>:-O3>    $<$<CONFIG:MinSizeRel>:-Os> $<$<CONFIG:RelWithDebInfo>:-O3 -g>>
	$<$<CXX_COMPILER_ID:MSVC>:  /std:c++17  /W3             /permissive-    /WX     /wd4996 /utf-8  $<$<CONFIG:Debug>:/Od>      $<$<CONFIG:Release>:/Ot>    $<$<CONFIG:MinSizeRel>:/Os> $<$<CONFIG:RelWithDebInfo>:/Ot /Od>>)

# Add libraries. Note: pybind11 is already added in pybind11_add_module.
if(ASIC_USE_FETCHCONTENT)
	target_link_libraries("${TARGET_NAME}" PRIVATE
		dependency_fmt)
else()
	target_link_libraries("${TARGET_NAME}" PRIVATE
		$<TARGET_NAME_IF_EXISTS:fmt::fmt-header-only>
		$<$<NOT:$<TARGET_EXISTS:fmt::fmt-header-only>>:fmt::fmt>)
endif()

# Set up clang-tidy.
if(ASIC_USE_CLANG_TIDY)
	find_program(CLANG_TIDY NAMES clang-tidy REQUIRED)
	set_property(TARGET "${TARGET_NAME}" PROPERTY CXX_CLANG_TIDY ${CLANG_TIDY})
	if(MSVC)
		set_target_properties("${TARGET_NAME}" PROPERTIES
			VS_GLOBAL_RunCodeAnalysis true
			VS_GLOBAL_EnableMicrosoftCodeAnalysis false
			VS_GLOBAL_EnableClangTidyCodeAnalysis true
			VS_GLOBAL_ClangTidyToolExe "${CLANG_TIDY}")
	endif()
endif()

# Copy binaries to project folder for debugging during development.
if(NOT ASIC_BUILDING_PYTHON_DISTRIBUTION)
	add_custom_target(copy_binaries ALL
		COMMAND ${CMAKE_COMMAND} -E copy "$<TARGET_FILE:${TARGET_NAME}>" "${CMAKE_CURRENT_LIST_DIR}"
		COMMENT "Copying binaries to ${CMAKE_CURRENT_LIST_DIR}"
		DEPENDS "${TARGET_NAME}")
endif()
