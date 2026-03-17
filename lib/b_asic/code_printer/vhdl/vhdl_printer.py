"""
Module for generating VHDL code for described architectures.
"""

import io
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from b_asic.code_printer.printer import CODE, WLS, Printer
from b_asic.code_printer.vhdl import (
    common,
    memory_storage,
    processing_element,
    register_storage,
    top_level,
)
from b_asic.code_printer.vhdl.util import signed_type
from b_asic.data_type import DataType, NumRepresentation, _VhdlDataType
from b_asic.quantization import OverflowMode, QuantizationMode
from b_asic.special_operations import Output

if TYPE_CHECKING:
    from b_asic.architecture import Architecture, Memory, ProcessingElement


class VhdlPrinter(Printer):
    _dt: _VhdlDataType

    CUSTOM_PRINTER_PREFIX = "_vhdl"

    def __init__(
        self,
        dt: DataType,
        vhdl_2008: bool = False,
    ) -> None:
        self._vhdl_2008 = vhdl_2008
        self._fp_backend = ""
        self._register_split: tuple[int, int] | None = None
        super().__init__(dt=dt)

    def set_data_type(self, dt: DataType) -> None:
        base = {k: v for k, v in dt.__dict__.items() if k != "vhdl_2008"}
        self._dt = _VhdlDataType(**base, vhdl_2008=self._vhdl_2008)

    def print(
        self,
        arch: "Architecture",
        *,
        path: str | Path = Path(),
        **kwargs,
    ) -> None:
        """
        Write VHDL files for *arch* into *path*.

        Arguments:
        ---------
        arch : Architecture
            The architecture to generate code for.
        path : str | Path
            Directory to write VHDL files into. Defaults to current directory.
        kwargs : dict
            Additional keyword arguments for code generation.
        """
        dir_path = Path(path)

        if self.is_complex:
            with (dir_path / "types.vhdl").open("w") as f:
                common.write(f, 0, self.print_types(), end="")

        for pe in arch.processing_elements:
            with (dir_path / f"{pe.entity_name}.vhdl").open("w") as f:
                common.write(f, 0, self.print_ProcessingElement(pe, **kwargs))

        for mem in arch.memories:
            with (dir_path / f"{mem.entity_name}.vhdl").open("w") as f:
                common.write(f, 0, self.print_Memory(mem, **kwargs))

        with (dir_path / f"{arch.entity_name}.vhdl").open("w") as f:
            common.write(f, 0, self.print_Architecture(arch, **kwargs))

    def get_compile_order(self, arch: "Architecture") -> list[str]:
        order = []
        order.extend(["types.vhdl"] if self.is_complex else [])
        order.extend(f"{mem.entity_name}.vhdl" for mem in arch.memories)
        order.extend(f"{pe.entity_name}.vhdl" for pe in arch.processing_elements)
        order.append(f"{arch.entity_name}.vhdl")
        return order

    def print_types(self) -> str:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self.vhdl_2008)

        common.write(f, 0, "package types is")
        common.write(f, 1, "type complex is record")
        common.write(f, 2, f"re : {self.scalar_type_str};")
        common.write(f, 2, f"im : {self.scalar_type_str};")
        common.write(f, 1, "end record;")
        common.write(f, 0, "end package types;")

        return f.getvalue()

    def print_Architecture(self, arch: "Architecture", **kwargs) -> str | None:
        io_registers = bool(kwargs.get("io_registers", False))
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self.vhdl_2008)
        if self.is_complex:
            common.package_header(f, "types")

        top_level.entity(f, arch, self._dt)
        top_level.architecture(f, arch, self._dt, io_registers)
        return f.getvalue()

    def print_Memory(self, mem: "Memory", **kwargs) -> str | None:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self.vhdl_2008)
        if self.is_complex:
            common.package_header(f, "types")

        if mem._memory_type == "RAM":
            # Extract known kwargs for memory_storage, pass through others
            memory_kwargs = {
                "input_sync": kwargs.get("input_sync", False),
                "output_sync": kwargs.get("output_sync", True),
                "external_schedule_counter": kwargs.get(
                    "external_schedule_counter", True
                ),
                "std_logic_vector": kwargs.get("std_logic_vector", False),
            }
            # Add optional parameters if provided
            for key in [
                "adr_mux_size",
                "adr_pipe_depth",
                "vivado_ram_style",
                "quartus_ram_style",
            ]:
                if key in kwargs:
                    memory_kwargs[key] = kwargs[key]

            memory_storage.entity(
                f,
                mem,
                self._dt,
                external_schedule_counter=memory_kwargs["external_schedule_counter"],
                std_logic_vector=memory_kwargs["std_logic_vector"],
            )
            memory_storage.architecture(f, mem, self._dt, **memory_kwargs)
        elif mem._memory_type == "register":
            if mem._forward_backward_table is None:
                raise ValueError(
                    "Memory assignment must be performed before generating register-based code. "
                    "Call memory.assign() first."
                )
            register_kwargs = {
                "sync_rst": kwargs.get("sync_rst", False),
                "async_rst": kwargs.get("async_rst", False),
                "external_schedule_counter": kwargs.get(
                    "external_schedule_counter", True
                ),
                "std_logic_vector": kwargs.get("std_logic_vector", False),
            }
            register_storage.entity(
                f,
                mem,
                self._dt,
                external_schedule_counter=register_kwargs["external_schedule_counter"],
                std_logic_vector=register_kwargs["std_logic_vector"],
            )
            register_storage.architecture(
                f, mem._forward_backward_table, mem, self._dt, **register_kwargs
            )
        else:
            raise ValueError(f"Unknown memory type: {mem._memory_type}")

        return f.getvalue()

    def print_ProcessingElement(self, pe: "ProcessingElement", **kwargs) -> str | None:
        # Check if a custom floating-point IP backend is specified for this PE
        fp_backend = kwargs.get("fp_backend", "")
        if isinstance(fp_backend, dict):
            fp_backend = fp_backend.get(pe.entity_name, "")
        self._fp_backend = str(fp_backend).lower()

        # Check if a per-PE register split is specified via pe_registers
        pe_registers: dict[str, tuple[int, int]] = kwargs.get("pe_registers", {})
        self._register_split = self._resolve_pe_registers(pe, pe_registers)

        # Generate and return VHDL code for the PE
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self.vhdl_2008)
        if self.is_complex:
            common.package_header(f, "types")
        processing_element.entity(f, pe, self._dt)
        core_code = self.print_operation(pe)
        processing_element.architecture(
            f,
            pe,
            self._dt,
            core_code,
            register_split=self._register_split,
        )
        return f.getvalue()

    def print_default(self) -> tuple[str, str]:
        return [self._dt.wl], ("", "")

    def _resolve_pe_registers(
        self,
        pe: "ProcessingElement",
        pe_registers: dict[str, tuple[int, int]],
    ) -> "tuple[int, int]":
        # Extract register split for this PE, entity-name takes prio over type-name
        split: tuple[int, int] | None = None
        matched_key: str | None = None
        if pe.entity_name in pe_registers:
            split = pe_registers[pe.entity_name]
            matched_key = pe.entity_name
        else:
            for key, val in pe_registers.items():
                if key == pe._type_name:
                    split = val
                    matched_key = key
                    break

        if split is None:
            # Default to latency-based register insertion
            latency = pe._latency
            return (latency - 1, 1) if latency > 0 else (0, 0)

        n_in, n_out = split
        # Sanity check the provided split values
        if (
            not isinstance(n_in, int)
            or not isinstance(n_out, int)
            or n_in < 0
            or n_out < 0
        ):
            raise ValueError(
                f"pe_registers[{matched_key!r}] must be a tuple of two non-negative "
                f"integers (n_in, n_out), got {split!r}"
            )
        latency = pe._latency
        total = n_in + n_out
        if total > latency:
            raise ValueError(
                f"pe_registers[{matched_key!r}] requests {total} register(s) "
                f"({n_in} input + {n_out} output) but the operation latency of "
                f"{pe.entity_name!r} is only {latency}."
            )
        if total < latency:
            warnings.warn(
                f"pe_registers[{matched_key!r}] requests {total} register(s) "
                f"({n_in} input + {n_out} output) which is less than the operation "
                f"latency of {pe.entity_name!r} ({latency}). ",
                UserWarning,
                stacklevel=4,
            )
        return n_in, n_out

    # ------------------------------
    # Fixed-point operation printers
    # ------------------------------

    def print_Input_fixed_point_real(self, pe: "ProcessingElement") -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        common.signal_declaration(declarations, "res_arith_0", self._dt.type_str)
        common.write(
            code, 1, f"res_arith_0 <= resize({self.type_name}(p_0_in), {self.bits});"
        )
        return [self._dt.wl], (declarations.getvalue(), code.getvalue())

    def print_Input_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        common.signal_declaration(
            declarations,
            "res_arith_0_re, res_arith_0_im",
            self.get_scalar_type(self.bits),
        )
        common.write(
            code, 1, f"res_arith_0_re <= resize(signed(p_0_in_re), {self.bits});"
        )
        common.write(
            code, 1, f"res_arith_0_im <= resize(signed(p_0_in_im), {self.bits});"
        )
        return [self._dt.wl], (declarations.getvalue(), code.getvalue())

    def print_Output_fixed_point_real(self, pe: "ProcessingElement") -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        common.signal_declaration(declarations, "res_arith_0", self._dt.type_str)
        common.write(code, 1, "res_arith_0 <= op_0;")
        common.write(code, 1, "p_0_out <= std_logic_vector(res_overflow_0);")
        wls = [(self._dt.wl[0], self._dt.wl[1])]
        return wls, (declarations.getvalue(), code.getvalue())

    def print_Output_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        common.signal_declaration(
            declarations,
            "res_arith_0_re, res_arith_0_im",
            self.get_scalar_type(self.bits),
        )
        common.write(code, 1, "res_arith_0_re <= op_0.re;")
        common.write(code, 1, "res_arith_0_im <= op_0.im;")
        common.write(code, 1, "p_0_out_re <= std_logic_vector(res_overflow_0.re);")
        common.write(code, 1, "p_0_out_im <= std_logic_vector(res_overflow_0.im);")
        wls = [(self._dt.wl[0], self._dt.wl[1])]
        return wls, (declarations.getvalue(), code.getvalue())

    def print_DontCare(self, pe: "ProcessingElement") -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        common.signal_declaration(declarations, "res_arith_0", self._dt.type_str)
        common.write(code, 1, f"res_arith_0 <= {self._dt.dontcare_str};")
        wls = [(self._dt.wl[0], self._dt.wl[1])]
        return wls, (declarations.getvalue(), code.getvalue())

    def print_Addition_fixed_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()

        common.signal_declaration(declarations, "tmp_res", signed_type(self.bits + 1))
        common.signal_declaration(
            declarations, "res_arith_0", signed_type(self.bits + 1)
        )

        common.write(
            code,
            1,
            "tmp_res <= resize(op_0, op_0'length + 1) + resize(op_1, op_1'length + 1);",
        )
        common.write(
            code,
            1,
            "res_arith_0 <= shift_right(tmp_res, to_integer(shift_output));",
        )

        wls = [(self.int_bits + 1, self.frac_bits)]
        return wls, (declarations.getvalue(), code.getvalue())

    def print_AddSub_fixed_point_real(self, pe: "ProcessingElement") -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()

        common.signal_declaration(
            declarations, "op_b", f"{self.type_name}({self.bits} downto 0)"
        )
        common.signal_declaration(
            declarations, "tmp_res", f"{self.type_name}({self.bits + 1} downto 0)"
        )
        common.signal_declaration(
            declarations, "tmp_res_shifted", f"{self.type_name}({self.bits} downto 0)"
        )
        common.signal_declaration(
            declarations, "res_arith_0", f"{self.type_name}({self.bits} downto 0)"
        )

        common.write(
            code,
            1,
            f"op_b <= resize(op_1, {self.bits + 1}) when is_add = '1' else not resize(op_1, {self.bits + 1});",
        )
        common.write(code, 1, "tmp_res <= (op_0 & '1') + (op_b & not is_add);")
        common.write(code, 1, f"tmp_res_shifted <= tmp_res({self.bits + 1} downto 1);")
        common.write(
            code,
            1,
            "res_arith_0 <= shift_right(tmp_res_shifted, to_integer(shift_output));",
        )

        wls = [(self.int_bits + 1, self.frac_bits)]
        return wls, (declarations.getvalue(), code.getvalue())

    def print_AddSub_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()

        for part in "re", "im":
            common.signal_declaration(
                declarations,
                f"{part}_op_b",
                f"{self.scalar_type_name}({self.bits} downto 0)",
            )
            common.signal_declaration(
                declarations,
                f"{part}_tmp_res",
                f"{self.scalar_type_name}({self.bits + 1} downto 0)",
            )
            common.signal_declaration(
                declarations,
                f"{part}_tmp_res_shifted",
                f"{self.scalar_type_name}({self.bits} downto 0)",
            )
            common.signal_declaration(
                declarations,
                f"res_arith_0_{part}",
                f"{self.scalar_type_name}({self.bits} downto 0)",
            )

            common.write(
                code,
                1,
                f"{part}_op_b <= resize(op_1.{part}, {self.bits + 1}) when is_add = '1' else not resize(op_1.{part}, {self.bits + 1});",
            )
            common.write(
                code,
                1,
                f"{part}_tmp_res <= (op_0.{part} & '1') + ({part}_op_b & not is_add);",
            )
            common.write(
                code,
                1,
                f"{part}_tmp_res_shifted <= {part}_tmp_res({self.bits + 1} downto 1);",
            )
            common.write(
                code,
                1,
                f"res_arith_0_{part} <= shift_right({part}_tmp_res_shifted, to_integer(shift_output));",
            )
        wls = [(self.int_bits + 1, self.frac_bits)]
        return wls, (declarations.getvalue(), code.getvalue())

    def print_ShiftAddSub_fixed_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        common.signal_declaration(
            declarations, "op_a", f"{self.type_name}({self.bits} downto 0)"
        )
        common.signal_declaration(
            declarations, "op_b", f"{self.type_name}({self.bits} downto 0)"
        )
        common.signal_declaration(
            declarations, "tmp_res", f"{self.type_name}({self.bits + 1} downto 0)"
        )
        common.signal_declaration(
            declarations, "res_arith_0", f"{self.type_name}({self.bits} downto 0)"
        )
        common.write(code, 1, f"op_a <= resize(op_0, {self.bits + 1});")
        common.write(
            code,
            1,
            f"op_b <= resize(op_1, {self.bits + 1}) when is_add = '1' else not resize(op_1, {self.bits + 1});",
        )

        # Handle shift: if static, use the value directly; otherwise convert signal to unsigned
        shift_entry = pe.control_table["shift"]
        if shift_entry.is_static:
            shift_val = int(shift_entry.get_static_value())
            shift_expr = str(shift_val)
        elif shift_entry.bits == 1:
            # Single bit std_logic needs to be converted to unsigned(0 downto 0)
            shift_expr = "to_integer(unsigned'(0 => shift))"
        else:
            shift_expr = "to_integer(shift)"

        common.write(
            code,
            1,
            f"tmp_res <= (op_a & '1') + (shift_right(op_b, {shift_expr}) & not is_add);",
        )

        common.signal_declaration(
            declarations, "tmp_res_shifted", f"{self.type_name}({self.bits} downto 0)"
        )
        common.write(
            code,
            1,
            f"tmp_res_shifted <= tmp_res({self.bits + 1} downto 1);",
        )
        common.write(
            code,
            1,
            "res_arith_0 <= shift_right(tmp_res_shifted, to_integer(shift_output));",
        )

        wls = [(self.int_bits + 1, self.frac_bits)]
        return wls, (declarations.getvalue(), code.getvalue())

    def print_ShiftAddSub_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        for part in "re", "im":
            common.signal_declaration(
                declarations,
                f"op_a_{part}, op_b_{part}",
                f"{self.scalar_type_name}({self.bits} downto 0)",
            )
            common.signal_declaration(
                declarations,
                f"tmp_res_{part}",
                f"{self.scalar_type_name}({self.bits + 1} downto 0)",
            )
            common.signal_declaration(declarations, f"cin_{part}", "std_logic")

        common.signal_declaration(
            declarations,
            "res_arith_0_re, res_arith_0_im",
            f"{self.scalar_type_name}({self.bits} downto 0)",
        )
        # declare a select signal
        common.signal_declaration(declarations, "sel", "std_logic_vector(1 downto 0)")
        # assign the select signal
        common.write(code, 1, "sel <= mul_j & is_add;")
        # op_a_re and op_a_im
        common.write(
            code, 1, f"op_a_re <= resize(op_0.re, {self.bits + 1});", start="\n"
        )
        common.write(
            code, 1, f"op_a_im <= resize(op_0.im, {self.bits + 1});", end="\n\n"
        )
        # op_b_re
        common.write(code, 1, "with sel select")
        common.write(code, 2, "op_b_re <=")
        common.write(code, 2, f'not resize(op_1.re, {self.bits + 1}) when "00",')
        common.write(code, 2, f'resize(op_1.re, {self.bits + 1}) when "01",')
        common.write(code, 2, f'resize(op_1.im, {self.bits + 1}) when "10",')
        common.write(code, 2, f'not resize(op_1.im, {self.bits + 1}) when "11",')
        common.write(code, 2, "(others => '-') when others;", end="\n\n")
        # op_b_im
        common.write(code, 1, "with sel select")
        common.write(code, 2, "op_b_im <=")
        common.write(code, 2, f'not resize(op_1.im, {self.bits + 1}) when "00",')
        common.write(code, 2, f'resize(op_1.im, {self.bits + 1}) when "01",')
        common.write(code, 2, f'not resize(op_1.re, {self.bits + 1}) when "10",')
        common.write(code, 2, f'resize(op_1.re, {self.bits + 1}) when "11",')
        common.write(code, 2, "(others => '-') when others;", end="\n\n")
        # cin_re
        common.write(code, 1, "with sel select")
        common.write(code, 2, "cin_re <=")
        common.write(code, 2, "'1' when \"00\",")
        common.write(code, 2, "'0' when \"01\",")
        common.write(code, 2, "'0' when \"10\",")
        common.write(code, 2, "'1' when \"11\",")
        common.write(code, 2, "'-' when others;", end="\n\n")
        # cin_im
        common.write(code, 1, "with sel select")
        common.write(code, 2, "cin_im <=")
        common.write(code, 2, "'1' when \"00\",")
        common.write(code, 2, "'0' when \"01\",")
        common.write(code, 2, "'1' when \"10\",")
        common.write(code, 2, "'0' when \"11\",")
        common.write(code, 2, "'-' when others;", end="\n\n")

        # Handle shift: if static, use the value directly; otherwise convert signal to unsigned
        shift_entry = pe.control_table["shift"]
        if shift_entry.is_static:
            shift_val = int(shift_entry.get_static_value())
            shift_expr = str(shift_val)
        elif shift_entry.bits == 1:
            # Single bit std_logic needs to be converted to unsigned(0 downto 0)
            shift_expr = "to_integer(unsigned'(0 => shift))"
        else:
            shift_expr = "to_integer(shift)"

        for part in "re", "im":
            common.write(
                code,
                1,
                f"tmp_res_{part} <= (op_a_{part} & '1') + (shift_right(op_b_{part}, {shift_expr}) & cin_{part});",
            )

        # Declare tmp_res_shifted signals and slice/assign to res_arith_0
        for part in "re", "im":
            common.signal_declaration(
                declarations,
                f"{part}_tmp_res_shifted",
                f"{self.scalar_type_name}({self.bits} downto 0)",
            )
        for part in "re", "im":
            common.write(
                code,
                1,
                f"{part}_tmp_res_shifted <= tmp_res_{part}({self.bits + 1} downto 1);",
            )
        for part in "re", "im":
            common.write(
                code,
                1,
                f"res_arith_0_{part} <= shift_right({part}_tmp_res_shifted, to_integer(shift_output));",
            )

        wls = [(self.int_bits + 1, self.frac_bits)]
        return wls, (declarations.getvalue(), code.getvalue())

    def print_ConstantMultiplication_fixed_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        value = pe.control_table["value"]
        extend_value = self._dt.is_signed and not value.is_signed
        coeff_bits = value.bits + (1 if extend_value else 0)
        res_bits = self.bits + coeff_bits
        declarations, code = io.StringIO(), io.StringIO()

        result_is_signed = self._dt.is_signed or value.is_signed
        res_type = (
            signed_type(res_bits)
            if result_is_signed
            else f"{self.type_name}({res_bits - 1} downto 0)"
        )

        common.signal_declaration(
            declarations,
            "res_arith_0",
            res_type,
        )

        if extend_value:
            common.write(code, 1, "res_arith_0 <= op_0 * signed('0' & value);")
        else:
            common.write(code, 1, "res_arith_0 <= op_0 * value;")

        wls = [
            (
                self.int_bits + value.wl[0] + (1 if extend_value else 0),
                self.frac_bits + value.wl[1],
            )
        ]
        return wls, (declarations.getvalue(), code.getvalue())

    def print_ConstantMultiplication_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()

        is_real = any(
            p.operation.value.imag == 0 and p.operation.value.real != 0
            for p in pe.collection
        )
        is_imag = any(
            p.operation.value.real == 0 and p.operation.value.imag != 0
            for p in pe.collection
        )
        is_complex = any(
            p.operation.value.real != 0 and p.operation.value.imag != 0
            for p in pe.collection
        )

        control_table = pe.control_table
        if "value" in control_table:
            real_entry = control_table["value"]
            imag_entry = 0
        else:
            real_entry = pe.control_table["value_real"]
            imag_entry = pe.control_table["value_imag"]

        extend_real = self._dt.is_signed and not real_entry.is_signed
        extend_imag = (
            imag_entry != 0 and self._dt.is_signed and not imag_entry.is_signed
        )

        real_coeff_bits = real_entry.bits + (1 if extend_real else 0)
        imag_coeff_bits = (imag_entry.bits if imag_entry != 0 else 0) + (
            1 if extend_imag else 0
        )

        res_bits = self.bits + max(real_coeff_bits, imag_coeff_bits)

        result_is_signed = (
            self._dt.is_signed
            or real_entry.is_signed
            or (imag_entry != 0 and imag_entry.is_signed)
        )
        res_type = (
            signed_type(res_bits)
            if result_is_signed
            else f"{self.scalar_type_name}({res_bits - 1} downto 0)"
        )

        common.signal_declaration(declarations, "a, b", self.scalar_type_str)

        if pe._latency > 2 and not is_complex and is_real and is_imag:
            # Handle a special case where pipelining is done in the middle
            common.write(code, 1, f"a <= p_0_in_reg_{pe._latency - 3}.re;")
            common.write(code, 1, f"b <= p_0_in_reg_{pe._latency - 3}.im;")
        else:
            common.write(code, 1, "a <= op_0.re;")
            common.write(code, 1, "b <= op_0.im;")

        def mul_statement(
            res: str, op: str, value: str, extend: bool, value_entry
        ) -> None:
            if extend:
                # Check if value is a single bit std_logic
                if isinstance(value_entry, int) or (
                    hasattr(value_entry, "bits") and value_entry.bits == 1
                ):
                    common.write(
                        code, 1, f"{res} <= {op} * signed(unsigned'('0', {value}));"
                    )
                else:
                    common.write(code, 1, f"{res} <= {op} * signed('0' & {value});")
            else:
                common.write(code, 1, f"{res} <= {op} * {value};")

        # Multiplication logic
        if is_complex:
            common.signal_declaration(declarations, "ac, bc, ad, bd", res_type)
            common.signal_declaration(
                declarations, "res_arith_0_re, res_arith_0_im", res_type
            )

            mul_statement("ac", "a", "value_real", extend_real, real_entry)
            mul_statement("bc", "b", "value_real", extend_real, real_entry)
            mul_statement("ad", "a", "value_imag", extend_imag, imag_entry)
            mul_statement("bd", "b", "value_imag", extend_imag, imag_entry)

            common.write(code, 1, "res_arith_0_re <= ac - bd;")
            common.write(code, 1, "res_arith_0_im <= ad + bc;")

        else:
            common.signal_declaration(
                declarations, "res_arith_0_re, res_arith_0_im", res_type
            )

            if is_real and not is_imag:
                mul_statement("res_arith_0_re", "a", "value", extend_real, real_entry)
                mul_statement("res_arith_0_im", "b", "value", extend_real, real_entry)

            elif is_imag and not is_real:
                # (a + jb) * (j*c) = -bc + j*ac
                common.signal_declaration(declarations, "tmp_re, tmp_im", res_type)
                mul_statement("tmp_re", "b", "value_imag", extend_imag, imag_entry)
                mul_statement("tmp_im", "a", "value_imag", extend_imag, imag_entry)
                common.write(code, 1, "res_arith_0_re <= -tmp_re;")
                common.write(code, 1, "res_arith_0_im <= tmp_im;")

            elif is_real and is_imag:
                value_real_str = (
                    "signed(value_real)" if not real_entry.is_signed else "value_real"
                )
                value_imag_str = (
                    "signed(value_imag)" if not imag_entry.is_signed else "value_imag"
                )

                max_coeff_bits = max(real_coeff_bits, imag_coeff_bits)
                mul_res_type = signed_type(self.bits + max_coeff_bits)

                # op_a signals should be sized to data width, op_b to coefficient width
                common.signal_declaration(
                    declarations,
                    "op_a_re, op_a_re_reg, op_a_im, op_a_im_reg",
                    self.scalar_type_str,
                )
                common.signal_declaration(
                    declarations,
                    "op_b_re, op_b_re_reg, op_b_im, op_b_im_reg",
                    signed_type(max_coeff_bits),
                )
                common.signal_declaration(declarations, "res_re, res_im", mul_res_type)
                common.signal_declaration(declarations, "is_real", "std_logic")
                common.write(code, 1, "is_real <= '1' when value_imag = 0 else '0';")

                common.write(
                    code,
                    1,
                    "op_a_re <= resize(a, op_a_re'length) when is_real = '1' else resize(-b, op_a_re'length);",
                )
                common.write(
                    code,
                    1,
                    f"op_b_re <= resize({value_real_str}, op_b_re'length) when is_real = '1' else resize({value_imag_str}, op_b_re'length);",
                )
                common.write(
                    code,
                    1,
                    "op_a_im <= resize(b, op_a_im'length) when is_real = '1' else resize(a, op_a_im'length);",
                )
                common.write(
                    code,
                    1,
                    f"op_b_im <= resize({value_real_str}, op_b_im'length) when is_real = '1' else resize({value_imag_str}, op_b_im'length);",
                )

                if pe._latency > 2:
                    common.write(code, 1, "res_re <= op_a_re_reg * op_b_re_reg;")
                    common.write(code, 1, "res_im <= op_a_im_reg * op_b_im_reg;")
                else:
                    common.write(code, 1, "res_re <= op_a_re * op_b_re;")
                    common.write(code, 1, "res_im <= op_a_im * op_b_im;")

                common.write(code, 1, "res_arith_0_re <= res_re;")
                common.write(code, 1, "res_arith_0_im <= res_im;")

                if pe._latency > 2:
                    common.synchronous_process_prologue(code)
                    common.write(code, 3, "op_a_re_reg <= op_a_re;")
                    common.write(code, 3, "op_b_re_reg <= op_b_re;")
                    common.write(code, 3, "op_a_im_reg <= op_a_im;")
                    common.write(code, 3, "op_b_im_reg <= op_b_im;")
                    common.synchronous_process_epilogue(code)

        max_coeff_wl = max(real_entry.wl[0], imag_entry.wl[0] if imag_entry != 0 else 0)
        max_frac_wl = max(real_entry.wl[1], imag_entry.wl[1] if imag_entry != 0 else 0)

        wls = [
            (
                self.int_bits + max_coeff_wl + (1 if extend_real or extend_imag else 0),
                self.frac_bits + max_frac_wl,
            )
        ]

        return wls, (declarations.getvalue(), code.getvalue())

    def print_MADS_fixed_point_real(self, pe: "ProcessingElement") -> tuple[WLS, CODE]:
        declarations, code = io.StringIO(), io.StringIO()

        mul_res_bits = 2 * self.bits
        common.signal_declaration(
            declarations,
            "mul_res",
            f"{self.type_name}({mul_res_bits - 1} downto 0)",
        )
        common.signal_declaration(declarations, "mul_res_quant", self.type_str)
        common.signal_declaration(
            declarations, "op_b", f"{self.type_name}({mul_res_bits} downto 0)"
        )
        common.signal_declaration(
            declarations, "tmp_res", f"{self.type_name}({mul_res_bits + 1} downto 0)"
        )
        common.signal_declaration(
            declarations, "add_res", f"{self.type_name}({mul_res_bits} downto 0)"
        )
        common.signal_declaration(declarations, "res_arith_0", self.type_str)

        common.write(code, 1, "mul_res <= op_1 * op_2;")
        common.write(
            code,
            1,
            f"mul_res_quant <= resize(mul_res, {self.bits});",
        )
        common.write(
            code,
            1,
            f"op_b <= resize(mul_res, {mul_res_bits + 1}) when is_add = '1' else not resize(mul_res, {mul_res_bits + 1});",
        )
        common.write(code, 1, "tmp_res <= (op_0 & '1') + (op_b & not is_add);")
        common.write(code, 1, f"add_res <= tmp_res({mul_res_bits + 1} downto 1);")
        common.write(
            code,
            1,
            "res_arith_0 <= resize(add_res, res_arith_0'length) when do_addsub = '1' else mul_res_quant;",
        )

        wls = [self._dt.wl]
        return wls, (declarations.getvalue(), code.getvalue())

    def print_SymmetricTwoportAdaptor_fixed_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()

        value = pe.control_table["value"]
        value_int_bits = value.wl[0]
        value_frac_bits = value.wl[1]
        value_bits = value_int_bits + value_frac_bits

        # declare signals
        common.signal_declaration(
            declarations, "u0", f"{self.type_name}({self.bits} downto 0)"
        )
        common.signal_declaration(
            declarations,
            "mul_res",
            f"{self.type_name}({self.bits + value_bits} downto 0)",
        )
        common.signal_declaration(
            declarations,
            "res_arith_0",
            f"{self.type_name}({self.bits + value_bits + 1} downto 0)",
        )
        common.signal_declaration(
            declarations,
            "res_arith_1",
            f"{self.type_name}({self.bits + value_bits + 1} downto 0)",
        )

        # u0 = op_1 - op_0
        common.write(
            code,
            1,
            f"u0 <= resize(op_1, {self._dt.bits + 1}) - resize(op_0, {self._dt.bits + 1});",
        )

        common.write(code, 1, "mul_res <= u0 * value;")

        # res_arith_1 = in0 + mul_res
        zero = "0"
        common.write(
            code,
            1,
            f"res_arith_1 <= (resize(op_0, op_0'length + 1 + {value_int_bits + 1}) & \"{zero * value_frac_bits}\") + resize(mul_res, res_arith_0'length);",
        )
        # res_arith_0 = in0 + mul_res
        common.write(
            code,
            1,
            f"res_arith_0 <= (resize(op_1, op_1'length + 1 + {value_int_bits + 1}) & \"{zero * value_frac_bits}\") + resize(mul_res, res_arith_1'length);",
        )

        wls = [
            (self._dt.wl[0] + 3, self._dt.wl[1] + value_frac_bits),
            (self._dt.wl[0] + 3, self._dt.wl[1] + value_frac_bits),
        ]
        return wls, (declarations.getvalue(), code.getvalue())

    def print_Reciprocal_fixed_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[WLS, CODE]:
        declarations, code = io.StringIO(), io.StringIO()
        tmp_res_bits = self.int_bits + 2 * self.frac_bits
        res_bits = self.int_bits + 2 * self.frac_bits

        common.signal_declaration(declarations, "unity", signed_type(tmp_res_bits))
        common.signal_declaration(declarations, "a", self.type_str)
        common.signal_declaration(declarations, "tmp_res", signed_type(tmp_res_bits))
        common.signal_declaration(declarations, "res_arith_0", signed_type(res_bits))

        common.write(code, 1, "a <= op_0;")
        common.write(
            code,
            1,
            f"unity <= to_signed({2 ** (2 * self.frac_bits)}, {tmp_res_bits});",
        )
        common.write(code, 1, "tmp_res <= unity / a when a /= 0 else (others => '0');")
        common.write(
            code,
            1,
            f"res_arith_0 <= shift_left(resize(tmp_res, {res_bits}), {self.frac_bits});",
        )

        wls = [(self.int_bits, 2 * self.frac_bits)]
        return wls, (declarations.getvalue(), code.getvalue())

    # ------------------------------------------------------------------
    # Floating-point operations
    # ------------------------------------------------------------------
    def print_Input_floating_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[WLS, CODE]:
        declarations, code = io.StringIO(), io.StringIO()
        common.signal_declaration(declarations, "res_arith_0", self._dt.type_str)
        if self._vhdl_2008:
            common.write(
                code,
                1,
                "res_arith_0 <= to_float(p_0_in, res_arith_0'high, -res_arith_0'low);",
            )
        else:
            common.write(code, 1, "res_arith_0 <= p_0_in;")
        return [self._dt.wl], (declarations.getvalue(), code.getvalue())

    def print_Output_floating_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[WLS, CODE]:
        declarations, code = io.StringIO(), io.StringIO()
        common.signal_declaration(declarations, "res_arith_0", self._dt.type_str)
        common.write(code, 1, "res_arith_0 <= op_0;")
        if self._vhdl_2008:
            common.write(code, 1, "p_0_out <= to_slv(res_overflow_0);")
        else:
            common.write(code, 1, "p_0_out <= res_overflow_0;")
        return [self._dt.wl], (declarations.getvalue(), code.getvalue())

    def print_Addition_floating_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[WLS, CODE]:
        if self._fp_backend != "amd":
            return self.print_default()
        return self._amd_fp_backend("u_fp_add")

    def print_AddSub_floating_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[WLS, CODE]:
        if self._fp_backend != "amd":
            return self.print_default()
        return self._amd_fp_backend(
            "u_fp_addsub",
            component_name="fp_addsub",
            operation_signal='"0000000" & not is_add',
        )

    def print_Multiplication_floating_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[WLS, CODE]:
        if self._fp_backend != "amd":
            return self.print_default()
        return self._amd_fp_backend("u_fp_mul", component_name="fp_mul")

    def print_Reciprocal_floating_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[WLS, CODE]:
        if self._fp_backend != "amd":
            return self.print_default()
        return self._amd_fp_backend(
            "u_fp_rec", component_name="fp_rec", two_inputs=False
        )

    def print_Negation_floating_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[WLS, CODE]:
        declarations, code = io.StringIO(), io.StringIO()
        common.signal_declaration(declarations, "res_arith_0", self._slv_type_str)
        common.write(
            code,
            1,
            f"res_arith_0 <= (not op_0({self.bits - 1})) & op_0({self.bits - 2} downto 0);",
        )
        return [self._dt.wl], (declarations.getvalue(), code.getvalue())

    def print_MADS_floating_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[WLS, CODE]:
        if self._fp_backend != "amd":
            return self.print_default()
        # check when inputs arrive and use the appropriate topology
        op = pe.processes[0].operation
        in_offsets = op.input_latency_offsets
        delta = in_offsets[0] - min(in_offsets[1], in_offsets[2])
        if delta > 0:
            return self._amd_fp_mads_chained_backend()
        elif delta == 0:
            return self._amd_fp_mads_fma()
        else:
            raise NotImplementedError(
                "MADS where a arrives before b and c is not supported with AMD FP backend."
            )

    def _amd_fp_backend(
        self,
        label: str,
        *,
        component_name: str = "floating_point_0",
        two_inputs: bool = True,
        operation_signal: str | None = None,
    ) -> "tuple[WLS, CODE]":
        declarations, code = io.StringIO(), io.StringIO()
        # Component declaration
        common.write(declarations, 1, f"component {component_name}")
        common.write(declarations, 2, "port (")
        common.write(declarations, 3, "aclk : in std_logic;")
        common.write(declarations, 3, f"s_axis_a_tdata : in {self._slv_type_str};")
        common.write(declarations, 3, "s_axis_a_tvalid : in std_logic;")
        if two_inputs:
            common.write(declarations, 3, f"s_axis_b_tdata : in {self._slv_type_str};")
            common.write(declarations, 3, "s_axis_b_tvalid : in std_logic;")
        if operation_signal is not None:
            common.write(
                declarations,
                3,
                "s_axis_operation_tdata : in std_logic_vector(7 downto 0);",
            )
            common.write(declarations, 3, "s_axis_operation_tvalid : in std_logic;")
        common.write(
            declarations, 3, f"m_axis_result_tdata : out {self._slv_type_str};"
        )
        common.write(declarations, 3, "m_axis_result_tvalid : out std_logic")
        common.write(declarations, 2, ");")
        common.write(declarations, 1, f"end component {component_name};")
        common.signal_declaration(declarations, "res_arith_0", self._slv_type_str)
        common.signal_declaration(declarations, "fp_result_tvalid", "std_logic")
        if operation_signal is not None:
            common.signal_declaration(
                declarations, "fp_operation", "std_logic_vector(7 downto 0)"
            )

        def slv(sig: str) -> str:
            return f"to_slv({sig})" if self._vhdl_2008 else sig

        # Component instantiation
        if operation_signal is not None:
            common.write(code, 1, f"fp_operation <= {operation_signal};")
        common.write(code, 1, f"{label} : {component_name}")
        common.write(code, 2, "port map (")
        common.write(code, 3, "aclk => clk,")
        common.write(code, 3, f"s_axis_a_tdata => {slv('op_0')},")
        common.write(code, 3, "s_axis_a_tvalid => en,")
        if two_inputs:
            common.write(code, 3, f"s_axis_b_tdata => {slv('op_1')},")
            common.write(code, 3, "s_axis_b_tvalid => en,")
        if operation_signal is not None:
            common.write(code, 3, "s_axis_operation_tdata => fp_operation,")
            common.write(code, 3, "s_axis_operation_tvalid => en,")
        common.write(code, 3, "m_axis_result_tdata => res_arith_0,")
        common.write(code, 3, "m_axis_result_tvalid => fp_result_tvalid")
        common.write(code, 2, ");")

        return [self._dt.wl], (declarations.getvalue(), code.getvalue())

    def _amd_fp_mads_fma(self) -> "tuple[WLS, CODE]":
        declarations, code = io.StringIO(), io.StringIO()
        # For MADS with FMA, we should place one pipeline stage at the inputs of the FMA
        # Due to some combinatorial logic for swapping inputs
        n_in, n_out = self._register_split
        self._register_split = (n_in - 1, n_out) if n_in > 0 else (0, n_out)

        def slv(sig: str) -> str:
            return f"to_slv({sig})" if self._vhdl_2008 else sig

        # Component declaration
        common.write(declarations, 1, "component fp_fma")
        common.write(declarations, 2, "port (")
        common.write(declarations, 3, "aclk : in std_logic;")
        common.write(declarations, 3, f"s_axis_a_tdata : in {self._slv_type_str};")
        common.write(declarations, 3, "s_axis_a_tvalid : in std_logic;")
        common.write(declarations, 3, f"s_axis_b_tdata : in {self._slv_type_str};")
        common.write(declarations, 3, "s_axis_b_tvalid : in std_logic;")
        common.write(declarations, 3, f"s_axis_c_tdata : in {self._slv_type_str};")
        common.write(declarations, 3, "s_axis_c_tvalid : in std_logic;")
        common.write(
            declarations, 3, "s_axis_operation_tdata : in std_logic_vector(7 downto 0);"
        )
        common.write(declarations, 3, "s_axis_operation_tvalid : in std_logic;")
        common.write(
            declarations, 3, f"m_axis_result_tdata : out {self._slv_type_str};"
        )
        common.write(declarations, 3, "m_axis_result_tvalid : out std_logic")
        common.write(declarations, 2, ");")
        common.write(declarations, 1, "end component fp_fma;")

        common.signal_declaration(declarations, "res_arith_0", self._slv_type_str)
        common.signal_declaration(declarations, "fp_result_tvalid", "std_logic")
        common.signal_declaration(declarations, "fp_fma_c_comb", self._slv_type_str)
        common.signal_declaration(declarations, "fp_fma_a_comb", self._slv_type_str)
        common.signal_declaration(declarations, "fp_fma_b_comb", self._slv_type_str)
        common.signal_declaration(
            declarations, "fp_fma_operation_comb", "std_logic_vector(7 downto 0)"
        )

        bits = self._dt.bits

        # FMA
        common.write(
            code,
            1,
            f"fp_fma_c_comb <= (others => '0') when do_addsub = '0' else {slv('op_0')};",
        )
        common.write(
            code,
            1,
            f"fp_fma_a_comb <= (op_1({bits - 1}) xor (not is_add)) & op_1({bits - 2} downto 0);",
        )
        common.write(code, 1, f"fp_fma_b_comb <= {slv('op_2')};")
        common.write(code, 1, 'fp_fma_operation <= "00000000";')

        # Shift chain output declarations
        common.signal_declaration(declarations, "fp_fma_c_in", self._slv_type_str)
        common.signal_declaration(declarations, "fp_fma_a_in", self._slv_type_str)
        common.signal_declaration(declarations, "fp_fma_b_in", self._slv_type_str)
        common.signal_declaration(
            declarations, "fp_fma_operation", "std_logic_vector(7 downto 0)"
        )

        # Build registers / Shift chain
        if n_in == 0:
            common.write(code, 1, "fp_fma_c_in <= fp_fma_c_comb;")
            common.write(code, 1, "fp_fma_a_in <= fp_fma_a_comb;")
            common.write(code, 1, "fp_fma_b_in <= fp_fma_b_comb;")
        else:
            common.signal_declaration(declarations, "fp_fma_c_reg", self._slv_type_str)
            common.signal_declaration(declarations, "fp_fma_a_reg", self._slv_type_str)
            common.signal_declaration(declarations, "fp_fma_b_reg", self._slv_type_str)

            common.synchronous_process_prologue(code)
            common.write(code, 3, "if en = '1' then")
            common.write(code, 4, "fp_fma_c_reg <= fp_fma_c_comb;")
            common.write(code, 4, "fp_fma_a_reg <= fp_fma_a_comb;")
            common.write(code, 4, "fp_fma_b_reg <= fp_fma_b_comb;")
            common.write(code, 3, "end if;")
            common.synchronous_process_epilogue(code)

            common.write(code, 1, "fp_fma_c_in <= fp_fma_c_reg;")
            common.write(code, 1, "fp_fma_a_in <= fp_fma_a_reg;")
            common.write(code, 1, "fp_fma_b_in <= fp_fma_b_reg;")

        common.write(code, 1, "u_fp_fma : fp_fma")
        common.write(code, 2, "port map (")
        common.write(code, 3, "aclk => clk,")
        common.write(code, 3, "s_axis_a_tdata => fp_fma_a_in,")
        common.write(code, 3, "s_axis_a_tvalid => en,")
        common.write(code, 3, "s_axis_b_tdata => fp_fma_b_in,")
        common.write(code, 3, "s_axis_b_tvalid => en,")
        common.write(code, 3, "s_axis_c_tdata => fp_fma_c_in,")
        common.write(code, 3, "s_axis_c_tvalid => en,")
        common.write(code, 3, "s_axis_operation_tdata => fp_fma_operation,")
        common.write(code, 3, "s_axis_operation_tvalid => en,")
        common.write(code, 3, "m_axis_result_tdata => res_arith_0,")
        common.write(code, 3, "m_axis_result_tvalid => fp_result_tvalid")
        common.write(code, 2, ");")

        return [self._dt.wl], (declarations.getvalue(), code.getvalue())

    def _amd_fp_mads_chained_backend(self) -> "tuple[WLS, CODE]":
        """
        Chained fp_mul + fp_addsub for MADS.

        Used when in0 (a) has a positive latency offset.
        """
        declarations, code = io.StringIO(), io.StringIO()

        def slv(sig: str) -> str:
            return f"to_slv({sig})" if self._vhdl_2008 else sig

        # --- fp_mul component ---
        common.write(declarations, 1, "component fp_mul")
        common.write(declarations, 2, "port (")
        common.write(declarations, 3, "aclk : in std_logic;")
        common.write(declarations, 3, f"s_axis_a_tdata : in {self._slv_type_str};")
        common.write(declarations, 3, "s_axis_a_tvalid : in std_logic;")
        common.write(declarations, 3, f"s_axis_b_tdata : in {self._slv_type_str};")
        common.write(declarations, 3, "s_axis_b_tvalid : in std_logic;")
        common.write(
            declarations, 3, f"m_axis_result_tdata : out {self._slv_type_str};"
        )
        common.write(declarations, 3, "m_axis_result_tvalid : out std_logic")
        common.write(declarations, 2, ");")
        common.write(declarations, 1, "end component fp_mul;")

        # --- fp_addsub component ---
        common.write(declarations, 1, "component fp_addsub")
        common.write(declarations, 2, "port (")
        common.write(declarations, 3, "aclk : in std_logic;")
        common.write(declarations, 3, f"s_axis_a_tdata : in {self._slv_type_str};")
        common.write(declarations, 3, "s_axis_a_tvalid : in std_logic;")
        common.write(declarations, 3, f"s_axis_b_tdata : in {self._slv_type_str};")
        common.write(declarations, 3, "s_axis_b_tvalid : in std_logic;")
        common.write(
            declarations,
            3,
            "s_axis_operation_tdata : in std_logic_vector(7 downto 0);",
        )
        common.write(declarations, 3, "s_axis_operation_tvalid : in std_logic;")
        common.write(
            declarations, 3, f"m_axis_result_tdata : out {self._slv_type_str};"
        )
        common.write(declarations, 3, "m_axis_result_tvalid : out std_logic")
        common.write(declarations, 2, ");")
        common.write(declarations, 1, "end component fp_addsub;")

        # Signal declarations
        common.signal_declaration(declarations, "mul_result", self._slv_type_str)
        common.signal_declaration(declarations, "mul_result_tvalid", "std_logic")
        common.signal_declaration(declarations, "res_arith_0", self._slv_type_str)
        common.signal_declaration(declarations, "fp_result_tvalid", "std_logic")
        common.signal_declaration(declarations, "addsub_a", self._slv_type_str)
        common.signal_declaration(
            declarations, "addsub_op", "std_logic_vector(7 downto 0)"
        )

        # Multiplier
        common.write(code, 1, "u_fp_mul : fp_mul")
        common.write(code, 2, "port map (")
        common.write(code, 3, "aclk => clk,")
        common.write(code, 3, f"s_axis_a_tdata => {slv('op_1')},")
        common.write(code, 3, "s_axis_a_tvalid => en,")
        common.write(code, 3, f"s_axis_b_tdata => {slv('op_2')},")
        common.write(code, 3, "s_axis_b_tvalid => en,")
        common.write(code, 3, "m_axis_result_tdata => mul_result,")
        common.write(code, 3, "m_axis_result_tvalid => mul_result_tvalid")
        common.write(code, 2, ");")

        # Addsub
        common.write(
            code,
            1,
            f"addsub_a <= (others => '0') when do_addsub = '0' else {slv('op_0')};",
        )
        common.write(code, 1, 'addsub_op <= "0000000" & (not is_add and do_addsub);')
        common.write(code, 1, "u_fp_addsub : fp_addsub")
        common.write(code, 2, "port map (")
        common.write(code, 3, "aclk => clk,")
        common.write(code, 3, "s_axis_a_tdata => addsub_a,")
        common.write(code, 3, "s_axis_a_tvalid => en,")
        common.write(code, 3, "s_axis_b_tdata => mul_result,")
        common.write(code, 3, "s_axis_b_tvalid => mul_result_tvalid,")
        common.write(code, 3, "s_axis_operation_tdata => addsub_op,")
        common.write(code, 3, "s_axis_operation_tvalid => en,")
        common.write(code, 3, "m_axis_result_tdata => res_arith_0,")
        common.write(code, 3, "m_axis_result_tvalid => fp_result_tvalid")
        common.write(code, 2, ");")

        return [self._dt.wl], (declarations.getvalue(), code.getvalue())

    # ------------------------------------------------------------------
    # Casting (quantization and overflow handling)
    # ------------------------------------------------------------------

    def print_cast(
        self, wl: tuple[int, int], port_number: int, pe: "ProcessingElement"
    ) -> CODE:
        """Generate quantization and overflow code for a single output signal."""
        wl_out, quant_code = self._print_quantization_signal(wl, port_number, pe)
        overflow_code = self._print_overflow_signal(wl_out, port_number, pe)
        return tuple(q + o for q, o in zip(quant_code, overflow_code, strict=True))

    def _print_quantization_signal(
        self, wl: tuple[int, int], port_number: int, pe: "ProcessingElement"
    ) -> tuple[tuple[int, int], CODE]:
        """Handle quantization for a single output signal."""
        declarations, code = io.StringIO(), io.StringIO()

        # Check if this is an Output operation to use output_wl
        is_output = pe is not None and any(
            isinstance(p.operation, Output) for p in pe.collection
        )
        target_wl = self._dt.output_wl if is_output else self._dt.wl
        parts = ("_re", "_im") if self.is_complex else ("",)

        bits_in = (
            wl[0]
            + wl[1]
            + (1 if self._dt.num_repr == NumRepresentation.FLOATING_POINT else 0)
        )
        frac_diff = wl[1] - target_wl[1]
        new_high = bits_in - 1
        new_low = frac_diff
        # If applicable, adjust new_high to account for addition growth
        if (
            self._dt.quantization_mode == QuantizationMode.MAGNITUDE_TRUNCATION
            and frac_diff > 0
        ):
            new_high = new_high + 1
        # Declare output signals
        if self.is_complex:
            common.signal_declaration(
                declarations,
                f"res_quant_{port_number}_re, res_quant_{port_number}_im",
                f"{self.scalar_type_name}({new_high - new_low} downto 0)",
            )
        else:
            common.signal_declaration(
                declarations,
                f"res_quant_{port_number}",
                f"{self.type_name}({new_high - new_low} downto 0)",
            )

        # Mode-specific assignments
        if frac_diff > 0:
            if self._dt.quantization_mode == QuantizationMode.TRUNCATION:
                # Truncation: throw away excess LSBs
                for part in parts:
                    common.write(
                        code,
                        1,
                        f"res_quant_{port_number}{part} <= res_arith_{port_number}{part}({new_high} downto {new_low});",
                    )
                wl_out = (wl[0], wl[1] - frac_diff)
            elif self._dt.quantization_mode == QuantizationMode.MAGNITUDE_TRUNCATION:
                # Magnitude Truncation: round towards zero
                # Add sign bit to position $W + 1$
                type_name = self.scalar_type_name if self.is_complex else self.type_name
                for part in parts:
                    common.signal_declaration(
                        declarations,
                        f"mag_trunc_tmp_{port_number}{part}",
                        f"{type_name}({bits_in} downto 0)",
                    )
                    # Add sign bit at position new_low (LSB+1 position)
                    # Create proper bit string: sign bit at position new_low, zeros below
                    zeros_low = "0" * (new_low - 1)
                    zeros_high = "0" * (bits_in - new_low + 1)
                    sign_value = f'("{zeros_high}" & res_arith_{port_number}{part}({bits_in - 1}) & "{zeros_low}")'
                    common.write(
                        code,
                        1,
                        f"mag_trunc_tmp_{port_number}{part} <= resize(res_arith_{port_number}{part}, {bits_in + 1}) "
                        f"+ {sign_value};",
                    )
                    # Truncate to target word length - use new_high + 1 because addition can grow by 1 bit
                    common.write(
                        code,
                        1,
                        f"res_quant_{port_number}{part} <= mag_trunc_tmp_{port_number}{part}({new_high} downto {new_low});",
                    )
                wl_out = (wl[0] + 1, wl[1] - frac_diff)
            else:
                raise NotImplementedError(
                    f"Quantization mode {self._dt.quantization_mode.name} not implemented for VHDL"
                )
        else:
            # No fractional bits to remove, just pass through
            for part in parts:
                common.write(
                    code,
                    1,
                    f"res_quant_{port_number}{part} <= res_arith_{port_number}{part}({new_high} downto {new_low});",
                )
            wl_out = (wl[0], wl[1])
        return wl_out, (declarations.getvalue(), code.getvalue())

    def _print_overflow_signal(
        self, wl: tuple[int, int], port_number: int, pe: "ProcessingElement"
    ) -> CODE:
        """Handle overflow for a single output signal."""
        declarations, code = io.StringIO(), io.StringIO()

        # Check if this is an Output operation to use output_wl
        is_output = pe is not None and any(
            isinstance(p.operation, Output) for p in pe.collection
        )
        target_bits = self._dt.output_bits if is_output else self._dt.bits

        parts = ("_re", "_im") if self.is_complex else ("",)

        # Declare output signals
        if self.is_complex:
            common.signal_declaration(
                declarations,
                f"res_overflow_{port_number}_re, res_overflow_{port_number}_im",
                f"{self.get_scalar_type(target_bits)}",
            )
            common.signal_declaration(
                declarations, f"res_overflow_{port_number}", self.type_str
            )
        else:
            common.signal_declaration(
                declarations,
                f"res_overflow_{port_number}",
                f"{self.type_name}({target_bits - 1} downto 0)",
            )

        # Mode-specific assignments
        if self._dt.overflow_mode == OverflowMode.WRAPPING:
            # Wrapping: throw away excess MSBs
            for part in parts:
                common.write(
                    code,
                    1,
                    f"res_overflow_{port_number}{part} <= res_quant_{port_number}{part}({target_bits - 1} downto 0);",
                )
        elif self._dt.overflow_mode == OverflowMode.SATURATION:
            # Saturation: check guard bits for overflow
            quant_bits = wl[0] + wl[1]
            guard_bits = quant_bits - target_bits

            for part in parts:
                if guard_bits > 0:
                    # Check if guard bits match the sign bit of target value
                    # If all is fine, throw away guard bits
                    # Otherwise, set to max or min value based on sign
                    sign_bit_pos = target_bits - 1
                    guard_high = quant_bits - 1
                    guard_low = target_bits

                    if self._dt.is_signed:
                        # For signed: overflow if guard bits != sign bit (MSB of target)
                        max_val = 2 ** (target_bits - 1) - 1
                        min_val = -(2 ** (target_bits - 1))
                        common.write(
                            code,
                            1,
                            f"res_overflow_{port_number}{part} <= "
                            f"to_signed({max_val}, {target_bits}) when res_quant_{port_number}{part}({guard_high} downto {guard_low}) /= "
                            f"({guard_bits - 1} downto 0 => res_quant_{port_number}{part}({sign_bit_pos})) and "
                            f"res_quant_{port_number}{part}({guard_high}) = '0' else "
                            f"to_signed({min_val}, {target_bits}) when res_quant_{port_number}{part}({guard_high} downto {guard_low}) /= "
                            f"({guard_bits - 1} downto 0 => res_quant_{port_number}{part}({sign_bit_pos})) else "
                            f"res_quant_{port_number}{part}({target_bits - 1} downto 0);",
                        )
                    else:
                        # For unsigned: overflow if any guard bit is 1
                        zeros = "0" * guard_bits
                        max_val = 2**target_bits - 1
                        common.write(
                            code,
                            1,
                            f"res_overflow_{port_number}{part} <= "
                            f"to_unsigned({max_val}, {target_bits}) when res_quant_{port_number}{part}({guard_high} downto {guard_low}) /= "
                            f'"{zeros}" else '
                            f"res_quant_{port_number}{part}({target_bits - 1} downto 0);",
                        )
                else:
                    # No guard bits, just pass through
                    common.write(
                        code,
                        1,
                        f"res_overflow_{port_number}{part} <= res_quant_{port_number}{part}({target_bits - 1} downto 0);",
                    )
        else:
            raise NotImplementedError(
                f"Overflow mode {self._dt.overflow_mode.name} not implemented for VHDL"
            )
        if self.is_complex:
            # Combine real and imaginary parts into output signal with type complex
            common.write(
                code,
                1,
                f"res_overflow_{port_number} <= (re => res_overflow_{port_number}_re, im => res_overflow_{port_number}_im);",
            )
        return declarations.getvalue(), code.getvalue()

    def get_scalar_type(self, bits: int) -> str:
        return f"{self.scalar_type_name}({bits - 1} downto 0)"

    @property
    def scalar_type_str(self) -> str:
        return self._dt.scalar_type_str

    @property
    def vhdl_2008(self) -> bool:
        return self._dt.vhdl_2008

    @property
    def output_bits(self) -> int:
        return self._dt.output_bits

    @property
    def type_name(self):
        return self._dt.type_str.split("(")[0]

    @property
    def scalar_type_name(self) -> str:
        if self.is_complex:
            return self._dt.scalar_type_str.split("(")[0]
        return self._dt.scalar_type_str
