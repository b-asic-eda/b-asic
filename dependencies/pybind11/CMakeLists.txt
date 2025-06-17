message(STATUS "Fetching pybind11...")

FetchContent_Declare(pybind11
	GIT_REPOSITORY https://github.com/pybind/pybind11
	GIT_TAG v2.10.3
)
FetchContent_MakeAvailable(pybind11)
