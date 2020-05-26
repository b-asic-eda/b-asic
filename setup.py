import os
import sys
import shutil
import subprocess
import setuptools
from setuptools import Extension
from setuptools.command.build_ext import build_ext

CMAKE_EXE = os.environ.get("CMAKE_EXE", shutil.which("cmake"))


class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=""):
        super().__init__(name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)


class CMakeBuild(build_ext):
    def build_extension(self, ext):
        if not isinstance(ext, CMakeExtension):
            return super().build_extension(ext)

        if not CMAKE_EXE:
            raise RuntimeError(
                f"Cannot build extension {ext.name}: CMake executable not found! Set the CMAKE_EXE environment variable or update your path.")

        cmake_build_type = "Debug" if self.debug else "Release"
        cmake_output_dir = os.path.abspath(
            os.path.dirname(self.get_ext_fullpath(ext.name)))
        cmake_configure_argv = [
            CMAKE_EXE, ext.sourcedir,
            "-DASIC_BUILDING_PYTHON_DISTRIBUTION=true",
            "-DCMAKE_BUILD_TYPE=" + cmake_build_type,
            "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY=" + cmake_output_dir,
            "-DPYTHON_EXECUTABLE=" + sys.executable,
        ]
        cmake_build_argv = [
            CMAKE_EXE, "--build", ".",
            "--config", cmake_build_type
        ]

        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)

        env = os.environ.copy()

        print(f"=== Configuring {ext.name} ===")
        print(f"Temp dir: {self.build_temp}")
        print(f"Output dir: {cmake_output_dir}")
        subprocess.check_call(cmake_configure_argv,
                              cwd=self.build_temp, env=env)

        print(f"=== Building {ext.name} ===")
        print(f"Temp dir: {self.build_temp}")
        print(f"Output dir: {cmake_output_dir}")
        print(f"Build type: {cmake_build_type}")
        subprocess.check_call(cmake_build_argv, cwd=self.build_temp, env=env)

        print()


setuptools.setup(
    name="b-asic",
    version="1.0.0",
    author="Adam Jakobsson, Angus Lothian, Arvid Westerlund, Felix Goding, Ivar Härnqvist, Jacob Wahlman, Kevin Scott, Rasmus Karlsson",
    author_email="adaja901@student.liu.se, anglo547@student.liu.se, arvwe160@student.liu.se, felgo673@student.liu.se, ivaha717@student.liu.se, jacwa448@student.liu.se, kevsc634@student.liu.se, raska119@student.liu.se",
    description="Better ASIC Toolbox",
    long_description=open("README.md", "r").read(),
    long_description_content_type="text/markdown",
    url="https://gitlab.liu.se/PUM_TDDD96/B-ASIC",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "pybind11>=2.3.0",
        "numpy",
        "pyside2",
        "graphviz",
        "matplotlib"
    ],
    packages=["b_asic", "b_asic/GUI"],
    ext_modules=[CMakeExtension("b_asic")],
    cmdclass={"build_ext": CMakeBuild},
    zip_safe=False,
    include_package_data=True
)
