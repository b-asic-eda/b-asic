"""
B-ASIC Codegen Testing Module.
"""
#!/usr/bin/env python3

from pathlib import Path
from sys import argv

from vunit import VUnit

# Absolute path of the testbench directory
testbench_path = Path(__file__).resolve().parent

vu = VUnit.from_argv(
    argv=["--output-path", str(testbench_path / "vunit_out"), *argv[1:]],
    compile_builtins=False,
)
vu.add_vhdl_builtins()

lib = vu.add_library("lib")
lib.add_source_files(
    [
        f"{testbench_path}/*.vhdl",
    ]
)
lib.set_compile_option("modelsim.vcom_flags", ["-2008"])

vu.main()
