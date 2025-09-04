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
from b_asic.data_type import VhdlDataType

if TYPE_CHECKING:
    from b_asic.architecture import Architecture, Memory, ProcessingElement


class VhdlPrinter(Printer):
    _dt: VhdlDataType

    def __init__(self, dt: VhdlDataType) -> None:
        super().__init__(dt=dt)
        self._dt = dt

    def print(self, path: str | Path, arch: "Architecture", **kwargs) -> None:
        path = Path(path)
        counter = 0
        dir_path = path / f"{arch.entity_name}_{counter}"
        while dir_path.exists():
            counter += 1
            dir_path = path / f"{arch.entity_name}_{counter}"
        dir_path.mkdir(parents=True)

        if self._dt.is_complex:
            with (dir_path / "types.vhd").open("w") as f:
                common.write(f, 0, self.print_types(), end="")

        for pe in arch.processing_elements:
            with (dir_path / f"{pe.entity_name}.vhd").open("w") as f:
                common.write(f, 0, self.print_ProcessingElement(pe))

        for mem in arch.memories:
            with (dir_path / f"{mem.entity_name}.vhd").open("w") as f:
                common.write(f, 0, self.print_Memory(mem))

        with (dir_path / f"{arch.entity_name}.vhd").open("w") as f:
            common.write(f, 0, self.print_Architecture(arch))

        vhdl_tb = kwargs.get("vhdl_tb", False)
        if vhdl_tb:
            with (dir_path / f"{arch.entity_name}_tb.vhd").open("w") as f:
                common.write(f, 0, self.print_vhdl_tb(arch))

    def print_types(self) -> str:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self._dt.vhdl_2008)

        common.write(f, 0, "package types is")
        common.write(f, 1, "type complex is record")
        common.write(f, 2, f"re : {self._dt.get_scalar_type_str()};")
        common.write(f, 2, f"im : {self._dt.get_scalar_type_str()};")
        common.write(f, 1, "end record;")
        common.write(f, 0, "end package types;")

        return f.getvalue()

    def print_Architecture(self, arch: "Architecture", **kwargs) -> str | None:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self._dt.vhdl_2008)
        if self._dt.is_complex:
            common.package_header(f, "types")

        top_level.entity(f, arch, self._dt)
        top_level.architecture(f, arch, self._dt)
        return f.getvalue()

    def print_Memory(self, mem: "Memory", **kwargs) -> str | None:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self._dt.vhdl_2008)
        if self._dt.is_complex:
            common.package_header(f, "types")

        memory_storage.entity(f, mem, self._dt)
        memory_storage.architecture(
            f, mem, self._dt, input_sync=False, output_sync=False
        )
        return f.getvalue()

    def print_ProcessingElement(self, pe: "ProcessingElement", **kwargs) -> str | None:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self._dt.vhdl_2008)
        if self._dt.is_complex:
            common.package_header(f, "types")

        processing_element.entity(f, pe, self._dt)

        core_code = self.print_operation(pe)
        processing_element.architecture(f, pe, self._dt, core_code)

        return f.getvalue()

    def print_vhdl_tb(self, arch: "Architecture") -> str:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self._dt.vhdl_2008)
        if self._dt.is_complex:
            common.package_header(f, "types")

        test_bench.entity(f, arch)
        test_bench.architecture(f, arch, self._dt)
        return f.getvalue()

    def print_Input_fixed_point_real(self, pe: "ProcessingElement") -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())
        common.write(
            code[1], 1, f"res_0 <= resize(signed(p_0_in), {self._dt.internal_length});"
        )
        return code[0].getvalue(), code[1].getvalue()

    def print_Input_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        code = io.StringIO()
        common.write(
            code,
            1,
            f"res_0 <= (re => resize(signed(p_0_in_re), {self._dt.internal_length}), "
            f"im => resize(signed(p_0_in_im), {self._dt.internal_length}));",
        )
        return "", code.getvalue()

    def print_Output_fixed_point_real(self, pe: "ProcessingElement") -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())
        common.write(code[0], 1, f"signal res_0 : {self._dt.get_output_type_str()};")
        common.write(code[1], 1, "p_0_out <= res_0;")
        common.write(
            code[1],
            1,
            f"res_0 <= std_logic_vector(resize(signed(p_0_in), {self._dt.output_length}));\n",
        )
        return code[0].getvalue(), code[1].getvalue()

    def print_Output_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        code = io.StringIO()
        common.write(
            code,
            1,
            f"p_0_out_re <= std_logic_vector(resize(signed(p_0_in.re), {self._dt.output_length}));",
        )
        common.write(
            code,
            1,
            f"p_0_out_im <= std_logic_vector(resize(signed(p_0_in.im), {self._dt.output_length}));",
        )
        return "", code.getvalue()

    def print_DontCare(self, pe: "ProcessingElement") -> tuple[str, str]:
        code = io.StringIO()
        common.write(code, 1, f"res_0 <= {self._dt.get_dontcare_str()};")
        return "", code.getvalue()

    def print_Addition_fixed_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())
        common.write(code[1], 1, "res_0 <= op_0 + op_1;")
        return code[0].getvalue(), code[1].getvalue()

    def print_AddSub_fixed_point_real(self, pe: "ProcessingElement") -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())

        common.signal_declaration(
            code[0], "tmp_res", f"signed({self._dt.input_length} downto 0)"
        )
        common.signal_declaration(code[0], "op_b", self._dt.get_type_str())

        common.write(code[1], 1, "op_b <= op_1 when is_add = '1' else not op_1;")

        common.write(code[1], 1, "tmp_res <= (op_0 & '1') + (op_b & not is_add);")
        common.write(code[1], 1, f"res_0 <= tmp_res({self._dt.input_length} downto 1);")

        return code[0].getvalue(), code[1].getvalue()

    def print_AddSub_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())

        common.write(
            code[0],
            1,
            f"signal re_op_a, re_op_b, im_op_a, im_op_b : signed({self._dt.internal_length - 1} downto 0);",
        )
        common.write(
            code[0],
            1,
            f"signal re_res, im_res : signed({self._dt.internal_length} downto 0);",
        )

        common.write(code[1], 1, "re_op_a <= op_0.re;")
        common.write(code[1], 1, "im_op_a <= op_0.im;")
        common.write(
            code[1],
            1,
            "re_op_b <= op_1.re when is_add = '1' else not op_1.re;",
        )
        common.write(
            code[1],
            1,
            "im_op_b <= op_1.im when is_add = '1' else not op_1.im;",
        )

        common.write(code[1], 1, "re_res <= (re_op_a & '1') + (re_op_b & not is_add);")
        common.write(code[1], 1, "im_res <= (im_op_a & '1') + (im_op_b & not is_add);")
        common.write(
            code[1],
            1,
            f"res_0 <= (re => re_res({self._dt.input_length} downto 1), im => im_res({self._dt.input_length} downto 1));",
        )
        return code[0].getvalue(), code[1].getvalue()

    def print_ConstantMultiplication_fixed_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())
        common.write(
            code[0],
            1,
            f"signal mul_res : signed({self._dt.internal_length} + value'length - 1 downto 0);",
        )

        common.write(code[1], 1, "mul_res <= op_0 * value;")
        common.write(
            code[1],
            1,
            "res_0 <= mul_res(mul_res'high - WL_VALUE_INT downto mul_res'high - WL_VALUE_INT - res_0'high);",
        )
        return code[0].getvalue(), code[1].getvalue()

    def print_ConstantMultiplication_fixed_point_complex(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())

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

        real_entry = next((e for e in pe.control_table if e.name == "value_real"), None)
        bits = real_entry.int_bits + real_entry.frac_bits
        frac_bits = real_entry.frac_bits

        common.write(code[0], 1, f"signal a, b : {self._dt.get_scalar_type_str()};")
        common.write(
            code[0],
            1,
            f"signal res_0_re, res_0_im : signed({self._dt.internal_high} downto 0);",
        )

        if pe._latency > 2 and not is_complex and is_real and is_imag:
            # Handle a special case where pipelining is done in the middle
            common.write(code[1], 1, f"a <= p_0_in_reg_{pe._latency - 3}.re;")
            common.write(code[1], 1, f"b <= p_0_in_reg_{pe._latency - 3}.im;")
        else:
            common.write(code[1], 1, "a <= op_0.re;")
            common.write(code[1], 1, "b <= op_0.im;")

        # Multiplication logic
        if is_complex:
            common.write(
                code[0],
                1,
                f"signal res_re : signed({self._dt.internal_length + bits - 1} downto 0);",
            )
            common.write(
                code[0],
                1,
                f"signal res_im : signed({self._dt.internal_length + bits - 1} downto 0);",
            )

            common.write(
                code[0],
                1,
                f"signal ac : signed({self._dt.internal_length + bits - 1} downto 0);",
            )
            common.write(
                code[0],
                1,
                f"signal bc : signed({self._dt.internal_length + bits - 1} downto 0);",
            )
            common.write(
                code[0],
                1,
                f"signal ad : signed({self._dt.internal_length + bits - 1} downto 0);",
            )
            common.write(
                code[0],
                1,
                f"signal bd : signed({self._dt.internal_length + bits - 1} downto 0);",
            )
            common.write(code[1], 1, "ac <= a * value_real;")
            common.write(code[1], 1, "bc <= b * value_real;")
            common.write(code[1], 1, "ad <= a * value_imag;")
            common.write(code[1], 1, "bd <= b * value_imag;")
            common.write(code[1], 1, "res_re <= ac - bd;")
            common.write(code[1], 1, "res_im <= ad + bc;")
            common.write(
                code[1],
                1,
                f"res_0_re <= res_re({self._dt.internal_length + frac_bits - 1} downto {frac_bits - 1});",
            )
            common.write(
                code[1],
                1,
                f"res_0_im <= res_im({self._dt.internal_length + frac_bits - 1} downto {frac_bits - 1});",
            )
        else:
            if is_real and not is_imag:
                common.write(
                    code[0],
                    1,
                    f"signal res_re : signed({self._dt.internal_length + bits - 1} downto 0);",
                )
                common.write(
                    code[0],
                    1,
                    f"signal res_im : signed({self._dt.internal_length + bits - 1} downto 0);",
                )

                common.write(code[1], 1, "res_re <= a * value_real;")
                common.write(code[1], 1, "res_im <= b * value_real;")
                common.write(
                    code[1],
                    1,
                    f"res_0_re <= res_re({self._dt.internal_length + frac_bits - 1} downto {frac_bits});",
                )
                common.write(
                    code[1],
                    1,
                    f"res_0_im <= res_im({self._dt.internal_length + frac_bits - 1} downto {frac_bits});",
                )

            elif is_imag and not is_real:
                common.write(
                    code[0],
                    1,
                    f"signal res_re : signed({self._dt.internal_length + bits - 1} downto 0);",
                )
                common.write(
                    code[0],
                    1,
                    f"signal res_im : signed({self._dt.internal_length + bits - 1} downto 0);",
                )

                common.write(code[1], 1, "res_re <= a * value_imag;")
                common.write(code[1], 1, "res_im <= b * value_imag;")
                common.write(
                    code[1],
                    1,
                    f"res_0_re <= res_re({self._dt.internal_length + frac_bits - 1} downto {frac_bits});",
                )
                common.write(
                    code[1],
                    1,
                    f"res_0_im <= res_im({self._dt.internal_length + frac_bits - 1} downto {frac_bits});",
                )

            elif is_real and is_imag:
                common.write(
                    code[0], 1, f"signal res_re : signed({bits + bits - 1} downto 0);"
                )
                common.write(
                    code[0], 1, f"signal res_im : signed({bits + bits - 1} downto 0);"
                )

                common.write(
                    code[0],
                    1,
                    f"signal op_a_re, op_a_re_reg : signed({max(self._dt.internal_length, bits) - 1} downto 0);",
                )
                common.write(
                    code[0],
                    1,
                    f"signal op_b_re, op_b_re_reg : signed({max(self._dt.internal_length, bits) - 1} downto 0);",
                )
                common.write(
                    code[0],
                    1,
                    f"signal op_a_im, op_a_im_reg : signed({max(self._dt.internal_length, bits) - 1} downto 0);",
                )
                common.write(
                    code[0],
                    1,
                    f"signal op_b_im, op_b_im_reg : signed({max(self._dt.internal_length, bits) - 1} downto 0);",
                )

                common.write(code[0], 1, "signal is_real : std_logic;")
                common.write(code[1], 1, "is_real <= '1' when value_imag = 0 else '0';")

                common.write(
                    code[1],
                    1,
                    "op_a_re <= resize(a, op_a_re'length) when is_real = '1' else resize(-b, op_a_re'length);",
                )
                common.write(
                    code[1],
                    1,
                    "op_b_re <= resize(value_real, op_b_re'length) when is_real = '1' else resize(value_imag, op_b_re'length);",
                )
                common.write(
                    code[1],
                    1,
                    "op_a_im <= resize(b, op_a_im'length) when is_real = '1' else resize(a, op_a_im'length);",
                )
                common.write(
                    code[1],
                    1,
                    "op_b_im <= resize(value_real, op_b_im'length) when is_real = '1' else resize(value_imag, op_b_im'length);",
                )

                if pe._latency > 2:
                    common.write(code[1], 1, "res_re <= op_a_re_reg * op_b_re_reg;")
                    common.write(code[1], 1, "res_im <= op_a_im_reg * op_b_im_reg;")
                else:
                    common.write(code[1], 1, "res_re <= op_a_re * op_b_re;")
                    common.write(code[1], 1, "res_im <= op_a_im * op_b_im;")

                common.write(
                    code[1],
                    1,
                    f"res_0_re <= resize(shift_right(res_re, {frac_bits}), res_0_re'length);",
                )
                common.write(
                    code[1],
                    1,
                    f"res_0_im <= resize(shift_right(res_im, {frac_bits}), res_0_im'length);",
                )

                if pe._latency > 2:
                    common.write(code[1], 1, "process(clk)")
                    common.write(code[1], 1, "begin")
                    common.write(code[1], 2, "if rising_edge(clk) then")
                    common.write(code[1], 3, "op_a_re_reg <= op_a_re;")
                    common.write(code[1], 3, "op_b_re_reg <= op_b_re;")
                    common.write(code[1], 3, "op_a_im_reg <= op_a_im;")
                    common.write(code[1], 3, "op_b_im_reg <= op_b_im;")
                    common.write(code[1], 2, "end if;")
                    common.write(code[1], 1, "end process;", end="\n\n")

        common.write(code[1], 1, "res_0 <= (re => res_0_re,  im => res_0_im);")

        return code[0].getvalue(), code[1].getvalue()

    def print_MADS_fixed_point_real(self, pe: "ProcessingElement") -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())

        common.write(
            code[0],
            1,
            "signal mul_res : signed(op_1'length + op_2'length - 1 downto 0);",
        )
        common.write(code[0], 1, "signal mul_res_quant : signed(res_0'high downto 0);")
        common.write(code[0], 1, "signal add_res : signed(res_0'high downto 0);")

        common.write(code[1], 1, "mul_res <= op_1 * op_2;")
        common.write(
            code[1],
            1,
            f"mul_res_quant <= mul_res(mul_res'high - {self._dt.internal_wl[0]} downto mul_res'high - {self._dt.internal_wl[0]} - mul_res_quant'high);",
        )
        common.write(
            code[1],
            1,
            "add_res <= op_0 + mul_res_quant when is_add = '1' else op_0 - mul_res_quant;",
        )
        common.write(
            code[1], 1, "res_0 <= add_res when do_addsub = '1' else mul_res_quant;\n"
        )

        return code[0].getvalue(), code[1].getvalue()

    def print_Reciprocal_fixed_point_real(
        self, pe: "ProcessingElement"
    ) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())

        common.write(
            code[0],
            1,
            f"signal unity : signed({self._dt.internal_wl[0] + 2 * self._dt.internal_wl[1] - 1} downto 0);",
        )
        common.write(
            code[0], 1, f"signal a : signed({self._dt.internal_high} downto 0);"
        )
        common.write(
            code[0],
            1,
            f"signal tmp_res : signed({self._dt.internal_wl[0] + 2 * self._dt.internal_wl[1] - 1} downto 0);",
        )

        common.write(code[1], 1, "a <= op_0;")
        common.write(
            code[1],
            1,
            f"unity <= to_signed({2 ** (2 * self._dt.internal_wl[1])}, {self._dt.internal_wl[0] + 2 * self._dt.internal_wl[1]});",
        )
        common.write(
            code[1], 1, "tmp_res <= unity / a when a /= 0 else (others => '0');"
        )
        common.write(code[1], 1, "res_0 <= tmp_res(res_0'high downto 0);")

        return code[0].getvalue(), code[1].getvalue()

    def print_default(self, pe: "ProcessingElement") -> tuple[str, str]:
        return "", ""
