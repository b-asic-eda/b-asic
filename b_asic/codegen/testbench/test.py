"""
B-ASIC Codegen Testing Module.
"""
#!/usr/bin/env python3

from os.path import abspath, dirname
from sys import argv

from vunit import VUnit

# Absolute path of the testbench directory
testbench_path = dirname(abspath(__file__))

vu = VUnit.from_argv(argv=["--output-path", f"{testbench_path}/vunit_out"] + argv[1:])

lib = vu.add_library("lib")
lib.add_source_files(
    [
        f"{testbench_path}/*.vhdl",
    ]
)
lib.set_compile_option("modelsim.vcom_flags", ["-2008"])

vu.main()
