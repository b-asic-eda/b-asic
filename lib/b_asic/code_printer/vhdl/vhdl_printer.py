"""
Module for generating VHDL code for described architectures.
"""

import io
from pathlib import Path
from typing import TYPE_CHECKING

from b_asic.code_printer.printer import CODE, WLS, Printer
from b_asic.code_printer.vhdl import (
    common,
    memory_storage,
    processing_element,
    top_level,
)
from b_asic.code_printer.vhdl.util import signed_type
from b_asic.data_type import DataType, VhdlDataType
from b_asic.special_operations import Output

if TYPE_CHECKING:
    from b_asic.architecture import Architecture, Memory, ProcessingElement


class VhdlPrinter(Printer):
    _dt: VhdlDataType

    CUSTOM_PRINTER_PREFIX = "_vhdl"

    def __init__(self, dt: DataType | VhdlDataType) -> None:
        super().__init__(dt=dt)

    def set_data_type(self, dt: DataType | VhdlDataType) -> None:
        if isinstance(dt, DataType):
            dt = VhdlDataType.from_DataType(dt)
        self._dt = dt

    def print(
        self,
        arch: "Architecture",
        *,
        path: str | Path = Path(),
        **kwargs,
    ) -> None:
        dir_path = Path(path)

        if self.is_complex:
            with (dir_path / "types.vhdl").open("w") as f:
                common.write(f, 0, self.print_types(), end="")

        for pe in arch.processing_elements:
            with (dir_path / f"{pe.entity_name}.vhdl").open("w") as f:
                common.write(f, 0, self.print_ProcessingElement(pe))

        for mem in arch.memories:
            with (dir_path / f"{mem.entity_name}.vhdl").open("w") as f:
                common.write(f, 0, self.print_Memory(mem))

        with (dir_path / f"{arch.entity_name}.vhdl").open("w") as f:
            common.write(f, 0, self.print_Architecture(arch))

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
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self.vhdl_2008)
        if self.is_complex:
            common.package_header(f, "types")

        top_level.entity(f, arch, self._dt)
        top_level.architecture(f, arch, self._dt)
        return f.getvalue()

    def print_Memory(self, mem: "Memory", **kwargs) -> str | None:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self.vhdl_2008)
        if self.is_complex:
            common.package_header(f, "types")

        memory_storage.entity(f, mem, self._dt)
        memory_storage.architecture(
            f, mem, self._dt, input_sync=False, output_sync=False
        )
        return f.getvalue()

    def print_ProcessingElement(self, pe: "ProcessingElement", **kwargs) -> str | None:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self.vhdl_2008)
        if self.is_complex:
            common.package_header(f, "types")
        processing_element.entity(f, pe, self._dt)
        core_code = self.print_operation(pe)
        processing_element.architecture(f, pe, self._dt, core_code)
        return f.getvalue()

    def print_operation(self, pe: "ProcessingElement") -> tuple[str, str]:
        wls, core_code = self.print_arith(pe)
        wls, quant_code = self.print_quantization(wls, pe)
        core_code = tuple(x + y for x, y in zip(core_code, quant_code, strict=True))
        return tuple(
            x + y for x, y in zip(core_code, self.print_overflow(wls, pe), strict=True)
        )

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
        common.signal_declaration(
            declarations, "res_arith_0", signed_type(self.bits + 1)
        )
        common.write(
            code,
            1,
            "res_arith_0 <= resize(op_0, op_0'length + 1) + resize(op_1, op_1'length + 1);",
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
            declarations, "res_arith_0", f"{self.type_name}({self.bits} downto 0)"
        )
        common.write(
            code,
            1,
            f"op_b <= resize(op_1, {self.bits + 1}) when is_add = '1' else not resize(op_1, {self.bits + 1});",
        )
        common.write(code, 1, "tmp_res <= (op_0 & '1') + (op_b & not is_add);")
        common.write(code, 1, f"res_arith_0 <= tmp_res({self.bits + 1} downto 1);")
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
                f"res_arith_0_{part} <= {part}_tmp_res({self.bits + 1} downto 1);",
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
        common.write(
            code,
            1,
            f"res_arith_0 <= tmp_res({self.bits + 1} downto 1);",
        )
        wls = [(self.int_bits + 1, self.frac_bits)]
        return wls, (declarations.getvalue(), code.getvalue())

    def print_ShiftAddSub_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        # declare the operands and results
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
            # common.signal_declaration(
            #     declarations,
            #     f"res_arith_{part}",
            #     f"{self.scalar_type_name}({self.bits} downto 0)",
            # )
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
        # calculate tmp_res_re and tmp_res_im

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
        # slice and assign the parts to res_arith_0
        for part in "re", "im":
            common.write(
                code,
                1,
                f"res_arith_0_{part} <= tmp_res_{part}({self.bits + 1} downto 1);",
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

        def mul_statement(res: str, op: str, value: str, extend: bool) -> None:
            if extend:
                common.write(code, 1, f"{res} <= {op} * signed('0' & {value});")
            else:
                common.write(code, 1, f"{res} <= {op} * {value};")

        # Multiplication logic
        if is_complex:
            common.signal_declaration(declarations, "ac, bc, ad, bd", res_type)
            common.signal_declaration(
                declarations, "res_arith_0_re, res_arith_0_im", res_type
            )

            mul_statement("ac", "a", "value_real", extend_real)
            mul_statement("bc", "b", "value_real", extend_real)
            mul_statement("ad", "a", "value_imag", extend_imag)
            mul_statement("bd", "b", "value_imag", extend_imag)

            common.write(code, 1, "res_arith_0_re <= ac - bd;")
            common.write(code, 1, "res_arith_0_im <= ad + bc;")

        else:
            common.signal_declaration(
                declarations, "res_arith_0_re, res_arith_0_im", res_type
            )

            if is_real and not is_imag:
                mul_statement("res_arith_0_re", "a", "value", extend_real)
                mul_statement("res_arith_0_im", "b", "value", extend_real)

            elif is_imag and not is_real:
                # (a + jb) * (j*c) = -bc + j*ac
                common.signal_declaration(declarations, "tmp_re, tmp_im", res_type)
                mul_statement("tmp_re", "b", "value_imag", extend_imag)
                mul_statement("tmp_im", "a", "value_imag", extend_imag)
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

                common.signal_declaration(
                    declarations,
                    "op_a_re, op_a_re_reg, op_b_re, op_b_re_reg, op_a_im, op_a_im_reg, op_b_im, op_b_im_reg",
                    signed_type(max(self.bits, max_coeff_bits)),
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

    def print_MADS_fixed_point_real(self, pe: "ProcessingElement") -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()

        common.signal_declaration(
            declarations,
            "mul_res",
            "signed(op_1'length + op_2'length - 1 downto 0)",
        )
        common.signal_declaration(declarations, "mul_res_quant", self.type_str)
        common.signal_declaration(declarations, "add_res", self.type_str)

        common.write(code, 1, "mul_res <= op_1 * op_2;")
        common.write(
            code,
            1,
            f"mul_res_quant <= mul_res(mul_res'high - {self.int_bits} downto mul_res'high - {self.int_bits} - mul_res_quant'high);",
        )
        common.write(
            code,
            1,
            "add_res <= op_0 + mul_res_quant when is_add = '1' else op_0 - mul_res_quant;",
        )
        common.write(
            code, 1, "res_0 <= add_res when do_addsub = '1' else mul_res_quant;\n"
        )

        return declarations.getvalue(), code.getvalue()

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

        def mul_statement(
            res: str, op: str, value: str, op_signed: bool, value_signed: bool
        ) -> None:
            common.write(code, 1, f"{res} <= {op} * signed({value});")

        # u0 = op_1 - op_0
        common.write(
            code,
            1,
            f"u0 <= resize(op_1, {self._dt.bits + 1}) - resize(op_0, {self._dt.bits + 1});",
        )

        # mul_res = u0 * value
        mul_statement("mul_res", "u0", "value", self._dt.is_signed, value.is_signed)

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
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()

        tmp_res_bits = self.int_bits + 2 * self.frac_bits
        common.signal_declaration(declarations, "unity", signed_type(tmp_res_bits))
        common.signal_declaration(declarations, "a", self.type_str)
        common.signal_declaration(declarations, "tmp_res", signed_type(tmp_res_bits))

        common.write(code, 1, "a <= op_0;")
        common.write(
            code,
            1,
            f"unity <= to_signed({2 ** (2 * self.frac_bits)}, {tmp_res_bits});",
        )
        common.write(code, 1, "tmp_res <= unity / a when a /= 0 else (others => '0');")
        common.write(code, 1, "res_0 <= tmp_res(res_0'high downto 0);")

        return declarations.getvalue(), code.getvalue()

    def print_default_arith(self) -> tuple[str, str]:
        return [self._dt.wl], ("", "")

    def print_TRUNCATION_fixed_point_real(
        self, wls: WLS, pe: "ProcessingElement" = None
    ) -> tuple[WLS, CODE]:
        declarations, code = io.StringIO(), io.StringIO()

        # Check if this is an Output operation to use output_wl
        is_output = pe is not None and any(
            isinstance(p.operation, Output) for p in pe.collection
        )
        target_wl = self._dt.output_wl if is_output else self._dt.wl

        wls_out = []
        for wl, port_number in zip(wls, range(len(wls)), strict=True):
            # throw away excess LSBs
            bits_in = wl[0] + wl[1]
            frac_diff = wl[1] - target_wl[1]

            new_high = bits_in - 1
            new_low = frac_diff
            common.signal_declaration(
                declarations,
                f"res_quant_{port_number}",
                f"{self.type_name}({new_high - new_low} downto 0)",
            )
            common.write(
                code,
                1,
                f"res_quant_{port_number} <= res_arith_{port_number}({new_high} downto {new_low});",
            )
            wls_out.append((target_wl[0], target_wl[1] - frac_diff))

        return wls_out, (declarations.getvalue(), code.getvalue())

    def print_TRUNCATION_fixed_point_complex(
        self, wls: WLS, pe: "ProcessingElement" = None
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        is_output = pe is not None and any(
            isinstance(p.operation, Output) for p in pe.collection
        )
        target_wl = self._dt.output_wl if is_output else self._dt.wl
        wls_out = []
        for wl, port_number in zip(wls, range(len(wls)), strict=True):
            # throw away excess LSBs for both real and imaginary parts
            bits_in = wl[0] + wl[1]
            frac_diff = wl[1] - target_wl[1]

            new_high = bits_in - 1
            new_low = frac_diff
            common.signal_declaration(
                declarations,
                f"res_quant_{port_number}_re, res_quant_{port_number}_im",
                f"{self.scalar_type_name}({new_high - new_low} downto 0)",
            )
            common.write(
                code,
                1,
                f"res_quant_{port_number}_re <= res_arith_{port_number}_re({new_high} downto {new_low});",
            )
            common.write(
                code,
                1,
                f"res_quant_{port_number}_im <= res_arith_{port_number}_im({new_high} downto {new_low});",
            )
            wls_out.append((target_wl[0], target_wl[1] - frac_diff))
        return wls_out, (declarations.getvalue(), code.getvalue())

    def print_WRAPPING_fixed_point_real(
        self, wls: WLS, pe: "ProcessingElement" = None
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        is_output = pe is not None and any(
            isinstance(p.operation, Output) for p in pe.collection
        )
        target_bits = sum(self._dt.output_wl) if is_output else self._dt.bits
        for port_number in range(len(wls)):
            # throw away excess MSBs
            common.signal_declaration(
                declarations,
                f"res_overflow_{port_number}",
                f"{self.type_name}({target_bits - 1} downto 0)",
            )
            common.write(
                code,
                1,
                f"res_overflow_{port_number} <= res_quant_{port_number}({target_bits - 1} downto 0);",
            )
        return declarations.getvalue(), code.getvalue()

    def print_WRAPPING_fixed_point_complex(
        self, wls: WLS, pe: "ProcessingElement" = None
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        is_output = pe is not None and any(
            isinstance(p.operation, Output) for p in pe.collection
        )
        target_bits = sum(self._dt.output_wl) if is_output else self._dt.bits
        for port_number in range(len(wls)):
            # throw away excess MSBs for both real and imaginary parts
            common.signal_declaration(
                declarations,
                f"res_overflow_{port_number}_re, res_overflow_{port_number}_im",
                f"{self.get_scalar_type(target_bits)}",
            )
            common.signal_declaration(
                declarations, f"res_overflow_{port_number}", self.type_str
            )
            common.write(
                code,
                1,
                f"res_overflow_{port_number}_re <= res_quant_{port_number}_re({target_bits - 1} downto 0);",
            )
            common.write(
                code,
                1,
                f"res_overflow_{port_number}_im <= res_quant_{port_number}_im({target_bits - 1} downto 0);",
            )
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
