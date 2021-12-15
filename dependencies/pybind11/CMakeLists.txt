message(STATUS "Fetching pybind11...")

FetchContent_Declare(pybind11
	GIT_REPOSITORY https://github.com/pybind/pybind11
	GIT_TAG f7b499615e14d70ab098a20deb0cdb3889998a1a # 2.8.1
)
FetchContent_MakeAvailable(pybind11)
