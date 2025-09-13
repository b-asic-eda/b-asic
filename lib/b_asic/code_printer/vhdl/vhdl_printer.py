"""
Module for generating VHDL code for described architectures.
"""

import io
from pathlib import Path
from typing import TYPE_CHECKING

from b_asic.code_printer.printer import Printer
from b_asic.code_printer.vhdl import (
    common,
    memory_storage,
    processing_element,
    test_bench,
    top_level,
)
from b_asic.code_printer.vhdl.util import signed_type
from b_asic.data_type import DataType, VhdlDataType

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
        tb: bool = False,
        **kwargs,
    ) -> None:
        path = Path(path)
        counter = 0
        dir_path = path / f"{arch.entity_name}_{counter}"
        while dir_path.exists():
            counter += 1
            dir_path = path / f"{arch.entity_name}_{counter}"
        dir_path.mkdir(parents=True)

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

        if tb:
            with (dir_path / f"{arch.entity_name}_tb.vhdl").open("w") as f:
                common.write(f, 0, self.print_vhdl_tb(arch))

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

    def print_vhdl_tb(self, arch: "Architecture") -> str:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self.vhdl_2008)
        if self.is_complex:
            common.package_header(f, "types")

        test_bench.entity(f, arch)
        test_bench.architecture(f, arch, self._dt)
        return f.getvalue()

    def print_Input_fixed_point_real(self, pe: "ProcessingElement") -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        common.write(code, 1, f"res_0 <= resize(signed(p_0_in), {self.bits});")
        return declarations.getvalue(), code.getvalue()

    def print_Input_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        code = io.StringIO()
        common.write(
            code,
            1,
            f"res_0 <= (re => resize(signed(p_0_in_re), {self.bits}), "
            f"im => resize(signed(p_0_in_im), {self.bits}));",
        )
        return "", code.getvalue()

    def print_Output_fixed_point_real(self, pe: "ProcessingElement") -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()
        common.signal_declaration(declarations, "res_0", self._dt.output_type_str)
        common.write(code, 1, "p_0_out <= res_0;")
        common.write(
            code,
            1,
            f"res_0 <= std_logic_vector(resize(signed(p_0_in), {self.output_bits}));\n",
        )
        return declarations.getvalue(), code.getvalue()

    def print_Output_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        code = io.StringIO()
        common.write(
            code,
            1,
            f"p_0_out_re <= std_logic_vector(resize(signed(p_0_in.re), {self.output_bits}));",
        )
        common.write(
            code,
            1,
            f"p_0_out_im <= std_logic_vector(resize(signed(p_0_in.im), {self.output_bits}));",
        )
        return "", code.getvalue()

    def print_DontCare(self, pe: "ProcessingElement") -> tuple[str, str]:
        code = io.StringIO()
        common.write(code, 1, f"res_0 <= {self._dt.dontcare_str};")
        return "", code.getvalue()

    def print_Addition_fixed_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        code = io.StringIO()
        common.write(code, 1, "res_0 <= op_0 + op_1;")
        return "", code.getvalue()

    def print_AddSub_fixed_point_real(self, pe: "ProcessingElement") -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()

        common.signal_declaration(declarations, "tmp_res", signed_type(self.bits + 1))
        common.signal_declaration(declarations, "op_b", self.type_str)

        common.write(code, 1, "op_b <= op_1 when is_add = '1' else not op_1;")

        common.write(code, 1, "tmp_res <= (op_0 & '1') + (op_b & not is_add);")
        common.write(
            code,
            1,
            f"res_0 <= resize(shift_right(tmp_res, 1), {self.bits});",
        )

        return declarations.getvalue(), code.getvalue()

    def print_AddSub_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()

        for part in "re", "im":
            common.signal_declaration(
                declarations, f"{part}_op_a, {part}_op_b", signed_type(self.bits)
            )
            common.signal_declaration(
                declarations, f"{part}_res", signed_type(self.bits + 1)
            )
            common.write(code, 1, f"{part}_op_a <= op_0.{part};")
            common.write(
                code,
                1,
                f"{part}_op_b <= op_1.{part} when is_add = '1' else not op_1.{part};",
            )
            common.write(
                code,
                1,
                f"{part}_res <= ({part}_op_a & '1') + ({part}_op_b & not is_add);",
            )
        common.write(
            code,
            1,
            f"res_0 <= (re => resize(shift_right(re_res, 1), {self.bits}), im => resize(shift_right(im_res, 1), {self.bits}));",
        )
        return declarations.getvalue(), code.getvalue()

    def print_ShiftAddSub_fixed_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()

        common.signal_declaration(declarations, "tmp_res", signed_type(self.bits + 1))
        common.signal_declaration(declarations, "op_b", self.type_str)

        common.write(code, 1, "op_b <= op_1 when is_add = '1' else not op_1;")

        common.write(
            code,
            1,
            "tmp_res <= (op_0 & '1') + (shift_right(op_b, to_integer(unsigned(shift))) & not is_add);",
        )
        common.write(
            code,
            1,
            f"res_0 <= resize(shift_right(tmp_res, 1), {self.bits});",
        )

        return declarations.getvalue(), code.getvalue()

    def print_ShiftAddSub_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        declarations, code = io.StringIO(), io.StringIO()

        for part in "re", "im":
            common.signal_declaration(
                declarations, f"{part}_op_a, {part}_op_b", signed_type(self.bits)
            )
            common.signal_declaration(
                declarations, f"{part}_res", signed_type(self.bits + 1)
            )
            common.write(code, 1, f"{part}_op_a <= op_0.{part};")
            common.write(
                code,
                1,
                f"{part}_op_b <= op_1.{part} when is_add = '1' else not op_1.{part};",
            )
            common.write(
                code,
                1,
                f"{part}_res <= ({part}_op_a & '1') + (shift_right({part}_op_b, to_integer(unsigned(shift))){part} & not is_add);",
            )
        common.write(
            code,
            1,
            f"res_0 <= (re => resize(shift_right(re_res, 1), {self.bits}), im => resize(shift_right(im_res, 1), {self.bits}));",
        )
        return declarations.getvalue(), code.getvalue()

    def print_ConstantMultiplication_fixed_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        coeff_bits = pe.control_table["value"].bits
        declarations, code = io.StringIO(), io.StringIO()
        common.signal_declaration(
            declarations,
            "mul_res",
            signed_type(self.bits + coeff_bits),
        )

        common.write(code, 1, "mul_res <= op_0 * value;")
        common.write(
            code,
            1,
            "res_0 <= mul_res(mul_res'high - WL_VALUE_INT downto mul_res'high - WL_VALUE_INT - res_0'high);",
        )
        return declarations.getvalue(), code.getvalue()

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

        real_entry = pe.control_table["value_real"]
        bits = real_entry.bits
        frac_bits = real_entry.frac_bits

        common.signal_declaration(declarations, "a, b", self.scalar_type_str)
        common.signal_declaration(
            declarations, "res_0_re, res_0_im", self.scalar_type_str
        )

        if pe._latency > 2 and not is_complex and is_real and is_imag:
            # Handle a special case where pipelining is done in the middle
            common.write(code, 1, f"a <= p_0_in_reg_{pe._latency - 3}.re;")
            common.write(code, 1, f"b <= p_0_in_reg_{pe._latency - 3}.im;")
        else:
            common.write(code, 1, "a <= op_0.re;")
            common.write(code, 1, "b <= op_0.im;")

        def result_declarations(bits):
            common.signal_declaration(declarations, "res_re", signed_type(bits))
            common.signal_declaration(declarations, "res_im", signed_type(bits))

        # Multiplication logic
        if is_complex:
            result_declarations(self.bits + bits)
            muL_type = signed_type(self.bits + bits)
            common.signal_declaration(declarations, "ac", muL_type)
            common.signal_declaration(declarations, "bc", muL_type)
            common.signal_declaration(declarations, "ad", muL_type)
            common.signal_declaration(declarations, "bd", muL_type)

            common.write(code, 1, "ac <= a * value_real;")
            common.write(code, 1, "bc <= b * value_real;")
            common.write(code, 1, "ad <= a * value_imag;")
            common.write(code, 1, "bd <= b * value_imag;")
            common.write(code, 1, "res_re <= ac - bd;")
            common.write(code, 1, "res_im <= ad + bc;")
            common.write(
                code,
                1,
                f"res_0_re <= res_re({self.bits + frac_bits - 1} downto {frac_bits - 1});",
            )
            common.write(
                code,
                1,
                f"res_0_im <= res_im({self.bits + frac_bits - 1} downto {frac_bits - 1});",
            )
        else:
            if is_real and not is_imag:
                result_declarations(self.bits + bits)

                common.write(code, 1, "res_re <= a * value_real;")
                common.write(code, 1, "res_im <= b * value_real;")
                for part in "re", "im":
                    common.write(
                        code,
                        1,
                        f"res_0_{part} <= resize(shift_right(res_{part}, {frac_bits}), {self.bits});",
                    )

            elif is_imag and not is_real:
                result_declarations(self.bits + bits)

                common.write(code, 1, "res_re <= a * value_imag;")
                common.write(code, 1, "res_im <= b * value_imag;")
                for part in "re", "im":
                    common.write(
                        code,
                        1,
                        f"res_0_{part} <= resize(shift_right(res_{part}, {frac_bits}), {self.bits});",
                    )

            elif is_real and is_imag:
                result_declarations(bits + bits)

                common.signal_declaration(
                    declarations,
                    "op_a_re, op_a_re_reg, op_b_re, op_b_re_reg,  op_a_im, op_a_im_reg, op_b_im, op_b_im_reg",
                    signed_type(max(self.bits, bits)),
                )
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
                    "op_b_re <= resize(value_real, op_b_re'length) when is_real = '1' else resize(value_imag, op_b_re'length);",
                )
                common.write(
                    code,
                    1,
                    "op_a_im <= resize(b, op_a_im'length) when is_real = '1' else resize(a, op_a_im'length);",
                )
                common.write(
                    code,
                    1,
                    "op_b_im <= resize(value_real, op_b_im'length) when is_real = '1' else resize(value_imag, op_b_im'length);",
                )

                if pe._latency > 2:
                    common.write(code, 1, "res_re <= op_a_re_reg * op_b_re_reg;")
                    common.write(code, 1, "res_im <= op_a_im_reg * op_b_im_reg;")
                else:
                    common.write(code, 1, "res_re <= op_a_re * op_b_re;")
                    common.write(code, 1, "res_im <= op_a_im * op_b_im;")

                common.write(
                    code,
                    1,
                    f"res_0_re <= resize(shift_right(res_re, {frac_bits}), res_0_re'length);",
                )
                common.write(
                    code,
                    1,
                    f"res_0_im <= resize(shift_right(res_im, {frac_bits}), res_0_im'length);",
                )

                if pe._latency > 2:
                    common.synchronous_process_prologue(code)
                    common.write(code, 3, "op_a_re_reg <= op_a_re;")
                    common.write(code, 3, "op_b_re_reg <= op_b_re;")
                    common.write(code, 3, "op_a_im_reg <= op_a_im;")
                    common.write(code, 3, "op_b_im_reg <= op_b_im;")
                    common.synchronous_process_epilogue(code)

        common.write(code, 1, "res_0 <= (re => res_0_re,  im => res_0_im);")

        return declarations.getvalue(), code.getvalue()

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

    def print_default(self) -> tuple[str, str]:
        return "", ""

    @property
    def scalar_type_str(self) -> str:
        return self._dt.scalar_type_str

    @property
    def vhdl_2008(self) -> str:
        return self._dt.vhdl_2008

    @property
    def output_bits(self) -> int:
        return self._dt.output_bits
