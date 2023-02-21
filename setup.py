import os
import shutil
import subprocess
import sys

import setuptools
from setuptools import Extension
from setuptools.command.build_ext import build_ext


class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=""):
        super().__init__(name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)


class CMakeBuild(build_ext):
    def build_extension(self, ext):
        CMAKE_EXE = os.environ.get(
            "CMAKE_EXE", shutil.which("cmake3") or shutil.which("cmake")
        )
        if not isinstance(ext, CMakeExtension):
            return super().build_extension(ext)

        if not CMAKE_EXE:
            raise RuntimeError(
                f"Cannot build extension {ext.name}: CMake executable not "
                "found! Set the CMAKE_EXE environment variable or update your "
                "path."
            )

        cmake_build_type = "Debug" if self.debug else "Release"
        cmake_output_dir = os.path.abspath(
            os.path.dirname(self.get_ext_fullpath(ext.name))
        )
        cmake_configure_argv = [
            CMAKE_EXE,
            ext.sourcedir,
            "-DASIC_BUILDING_PYTHON_DISTRIBUTION=ON",
            "-DCMAKE_BUILD_TYPE=" + cmake_build_type,
            "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY=" + cmake_output_dir,
            "-DPYTHON_EXECUTABLE=" + sys.executable,
        ]
        cmake_build_argv = [
            CMAKE_EXE,
            "--build",
            ".",
            "--config",
            cmake_build_type,
        ]

        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)

        env = os.environ.copy()

        print(f"=== Configuring {ext.name} ===")
        print(f"Temp dir: {self.build_temp}")
        print(f"Output dir: {cmake_output_dir}")
        subprocess.check_call(cmake_configure_argv, cwd=self.build_temp, env=env)

        print(f"=== Building {ext.name} ===")
        print(f"Temp dir: {self.build_temp}")
        print(f"Output dir: {cmake_output_dir}")
        print(f"Build type: {cmake_build_type}")
        subprocess.check_call(cmake_build_argv, cwd=self.build_temp, env=env)

        print()


setuptools.setup(
    author=(
        "Adam Jakobsson, Angus Lothian, Arvid Westerlund, Felix Goding, Ivar Härnqvist,"
        " Jacob Wahlman, Kevin Scott, Rasmus Karlsson, Oscar Gustafsson, Andreas Bolin,"
        " Mikael Henriksson, Frans Skarman, Petter Källström, Olle Hansson"
    ),
    author_email=(
        "adaja901@student.liu.se, anglo547@student.liu.se, arvwe160@student.liu.se,"
        " felgo673@student.liu.se, ivaha717@student.liu.se, jacwa448@student.liu.se,"
        " kevsc634@student.liu.se, raska119@student.liu.se, oscar.gustafsson@liu.se,"
        " andbo467@student.liu.se, mikael.henriksson@liu.se, frans.skarman@liu.se,"
        " petter.kallstrom@liu.se, olle.hansson@liu.se"
    ),
    ext_modules=[CMakeExtension("_b_asic")],
    cmdclass={"build_ext": CMakeBuild},
)
