"""
Module for generating VHDL code for described architectures.
"""

import io
from pathlib import Path

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.code_printer.printer import Printer
from b_asic.code_printer.vhdl import (
    common,
    memory_storage,
    processing_element,
    test_bench,
    top_level,
)
from b_asic.data_type import DataType


class VhdlPrinter(Printer):
    def __init__(self, dt: DataType) -> None:
        super().__init__(dt=dt)

    def print(self, path: str | Path, arch: Architecture, *args, **kwargs) -> None:
        path = Path(path)
        counter = 0
        dir_path = path / f"{arch.entity_name}_{counter}"
        while dir_path.exists():
            counter += 1
            dir_path = path / f"{arch.entity_name}_{counter}"
        dir_path.mkdir(parents=True)

        # TODO: USE?
        # with (dir_path / "types.vhd").open("w") as f:
        #     types.package(f, wl)

        for pe in arch.processing_elements:
            with (dir_path / f"{pe.entity_name}.vhd").open("w") as f:
                common.write(f, 0, self.print_ProcessingElement(pe))

        for mem in arch.memories:
            with (dir_path / f"{mem.entity_name}.vhd").open("w") as f:
                common.write(f, 0, self.print_Memory(mem))

        with (dir_path / f"{arch.entity_name}.vhd").open("w") as f:
            common.write(f, 0, self.print_Architecture(arch))

        with (dir_path / f"{arch.entity_name}_tb.vhd").open("w") as f:
            common.write(f, 0, self.print_test_bench(arch))

    def print_Architecture(self, arch: Architecture, *args, **kwargs) -> str | None:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f)
        # lines.append("use work.types.all;") # TODO: USE?

        top_level.entity(f, arch, self._dt)
        top_level.architecture(f, arch, self._dt)
        return f.getvalue()

    def print_Memory(self, mem: Memory, *args, **kwargs) -> str | None:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f)

        memory_storage.entity(f, mem, self._dt)
        memory_storage.architecture(
            f, mem, self._dt, input_sync=False, output_sync=False
        )
        return f.getvalue()

    def print_ProcessingElement(
        self, pe: ProcessingElement, *args, **kwargs
    ) -> str | None:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f)

        processing_element.entity(f, pe, self._dt)
        processing_element.architecture(f, pe, self._dt)
        return f.getvalue()

    def print_test_bench(self, arch: Architecture, *args, **kwargs) -> str | None:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f)

        test_bench.entity(f, arch)
        test_bench.architecture(f, arch, self._dt)
        return f.getvalue()
