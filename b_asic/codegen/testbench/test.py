#!/usr/bin/env python3

from vunit import VUnit

vu = VUnit.from_argv()

lib = vu.add_library("lib")
lib.add_source_files(
    [
        "*.vhdl",
    ]
)
lib.set_compile_option("modelsim.vcom_flags", ["-2008"])

vu.main()
