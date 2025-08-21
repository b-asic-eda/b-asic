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
from b_asic.data_type import VhdlDataType


class VhdlPrinter(Printer):
    def __init__(self, dt: VhdlDataType) -> None:
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
        common.ieee_header(f, fixed_pkg=self._dt.vhdl_2008)
        # lines.append("use work.types.all;") # TODO: USE?

        top_level.entity(f, arch, self._dt)
        top_level.architecture(f, arch, self._dt)
        return f.getvalue()

    def print_Memory(self, mem: Memory, *args, **kwargs) -> str | None:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self._dt.vhdl_2008)

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
        common.ieee_header(f, fixed_pkg=self._dt.vhdl_2008)

        processing_element.entity(f, pe, self._dt)

        method = getattr(
            self, f"print_{pe.operation_type.__name__}", self.print_default
        )
        core_code = method()
        processing_element.architecture(f, pe, self._dt.get_type_str(), core_code)

        return f.getvalue()

    def print_test_bench(self, arch: Architecture, *args, **kwargs) -> str | None:
        f = io.StringIO()
        common.b_asic_preamble(f)
        common.ieee_header(f, fixed_pkg=self._dt.vhdl_2008)

        test_bench.entity(f, arch)
        test_bench.architecture(f, arch, self._dt)
        return f.getvalue()

    def print_Input(self) -> tuple[str, str]:
        return getattr(
            self,  # TODO: Default to operation._vhdl somewhere...
            f"print_Input_{self._dt.num_repr.name.lower()}_{'complex' if self._dt.is_complex else 'real'}",
        )()

    def print_Input_fixed_point_real(self) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())
        common.write(
            code[1], 1, f"res_0 <= resize(signed(p_0_in), {self._dt.internal_length});"
        )
        return code[0].getvalue(), code[1].getvalue()

    def print_Input_fixed_point_complex(self) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())

        common.write(
            code[0],
            1,
            f"signal in_re, in_im : std_logic_vector({self._dt.input_length - 1} downto 0);",
        )

        common.write(
            code[1],
            1,
            f"in_re <= p_0_in({2 * self._dt.input_length - 1} downto {self._dt.input_length});",
        )
        common.write(
            code[1], 1, f"in_im <= p_0_in({self._dt.input_length - 1} downto 0);"
        )

        common.write(
            code[1],
            1,
            f"res_0 <= std_logic_vector(resize(signed(in_re), {self._dt.internal_length})) & "
            f"std_logic_vector(resize(signed(in_im), {self._dt.internal_length}));",
        )
        return code[0].getvalue(), code[1].getvalue()

    def print_Output(self) -> tuple[str, str]:
        return getattr(
            self,  # TODO: Default to operation._vhdl somewhere...
            f"print_Output_{self._dt.num_repr.name.lower()}_{'complex' if self._dt.is_complex else 'real'}",
        )()

    def print_Output_fixed_point_real(self) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())
        common.write(code[0], 1, f"signal res_0 : {self._dt.get_output_type_str()};")
        common.write(code[1], 1, "p_0_out <= res_0;")
        common.write(
            code[1],
            1,
            f"res_0 <= std_logic_vector(resize(signed(p_0_in), {self._dt.output_length}));\n",
        )
        return code[0].getvalue(), code[1].getvalue()

    def print_Output_fixed_point_complex(self) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())
        common.write(code[0], 1, f"signal res_0 : {self._dt.get_output_type_str()};")
        common.write(
            code[1],
            1,
            f"res_0 <= std_logic_vector(resize(signed(p_0_in), {2 * self._dt.output_length}));\n",
        )
        common.write(code[1], 1, "p_0_out <= res_0;")
        return code[0].getvalue(), code[1].getvalue()

    def print_DontCare(self) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())
        common.write(code[1], 1, "res_0 <= (others => '-');")
        return code[0].getvalue(), code[1].getvalue()

    def print_Addition(self) -> tuple[str, str]:
        return getattr(
            self,  # TODO: Default to operation._vhdl somewhere...
            f"print_Addition_{self._dt.num_repr.name.lower()}_{'complex' if self._dt.is_complex else 'real'}",
        )()

    def print_Addition_fixed_point_real(self) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())
        common.write(code[1], 1, "res_0 <= p_0_in_reg_0 + p_1_in_reg_0;")
        return code[0].getvalue(), code[1].getvalue()

    # def print_Subtraction_fixed_point_real(self) -> tuple[str, str]:
    #     code = (io.StringIO(), io.StringIO())
    #     common.write(code[1], 1, "res_0 <= p_0_in_reg_0 - p_1_in_reg_0;")
    #     return code

    # def _print_add_sub(self, op: str) -> tuple[str, str]:
    #     return "", f"res_0 <= p_0_in_reg_0 {op} p_1_in_reg_0;"

    # print_Addition_fixed_point_real = functools.partial(_print_add_sub, op="+")
    # print_Subtraction_fixed_point_real = functools.partial(_print_add_sub, op="-")

    def print_AddSub(self) -> tuple[str, str]:
        return getattr(
            self,  # TODO: Default to operation._vhdl somewhere...
            f"print_AddSub_{self._dt.num_repr.name.lower()}_{'complex' if self._dt.is_complex else 'real'}",
        )()

    def print_AddSub_fixed_point_real(self) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())
        common.write(
            code[1],
            1,
            "res_0 <= p_0_in_reg_0 + p_1_in_reg_0 when is_add = '1' else p_0_in_reg_0 - p_1_in_reg_0;",
        )
        return code[0].getvalue(), code[1].getvalue()

    def print_AddSub_fixed_point_complex(self) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())

        common.write(
            code[0],
            1,
            f"signal re_op_a, re_op_b, im_op_a, im_op_b : signed({self._dt.internal_length - 1} downto 0);",
        )
        common.write(
            code[0],
            1,
            f"signal re_res, im_res : signed({self._dt.internal_length - 1} downto 0);",
        )

        common.write(
            code[1],
            1,
            f"re_op_a <= signed(p_0_in_reg_0({2 * self._dt.internal_length - 1} downto {self._dt.internal_length}));",
        )
        common.write(
            code[1],
            1,
            f"im_op_a <= signed(p_0_in_reg_0({self._dt.internal_length - 1} downto 0));",
        )
        common.write(
            code[1],
            1,
            f"re_op_b <= signed(p_1_in_reg_0({2 * self._dt.internal_length - 1} downto {self._dt.internal_length}));",
        )
        common.write(
            code[1],
            1,
            f"im_op_b <= signed(p_1_in_reg_0({self._dt.internal_length - 1} downto 0));",
        )

        common.write(
            code[1],
            1,
            "re_res <= re_op_a + re_op_b when is_add = '1' else re_op_a - re_op_b;",
        )
        common.write(
            code[1],
            1,
            "im_res <= im_op_a + im_op_b when is_add = '1' else im_op_a - im_op_b;",
        )

        common.write(
            code[1], 1, "res_0 <= std_logic_vector(re_res) & std_logic_vector(im_res);"
        )

        # p_0_out <= re_res & im_res;
        return code[0].getvalue(), code[1].getvalue()

    def print_ConstantMultiplication(self) -> tuple[str, str]:
        return getattr(
            self,  # TODO: Default to operation._vhdl somewhere...
            f"print_ConstantMultiplication_{self._dt.num_repr.name.lower()}_{'complex' if self._dt.is_complex else 'real'}",
        )()

    def print_ConstantMultiplication_fixed_point_real(self) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())
        common.write(
            code[0],
            1,
            f"signal mul_res : signed({self._dt.internal_length} + value'length - 1 downto 0);",
        )

        common.write(code[1], 1, "mul_res <= p_0_in_reg_0 * value;")
        common.write(
            code[1],
            1,
            "res_0 <= mul_res(mul_res'high - WL_VALUE_INT downto mul_res'high - WL_VALUE_INT - res_0'high);",
        )
        return code[0].getvalue(), code[1].getvalue()

    def print_ConstantMultiplication_fixed_point_complex(self) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())

        print(self._dt)
        common.write(
            code[0],
            1,
            f"signal a, b : signed({self._dt.internal_length - 1} downto 0);",
        )

        common.write(
            code[0],
            1,
            f"signal ac : signed({self._dt.internal_length} + value_real'length - 1 downto 0);",
        )
        common.write(
            code[0],
            1,
            f"signal ad : signed({self._dt.internal_length} + value_imag'length - 1 downto 0);",
        )
        common.write(
            code[0],
            1,
            f"signal bc : signed({self._dt.internal_length} + value_real'length - 1 downto 0);",
        )
        common.write(
            code[0],
            1,
            f"signal bd : signed({self._dt.internal_length} + value_imag'length - 1 downto 0);",
        )
        common.write(
            code[0],
            1,
            f"signal res_re : signed({self._dt.internal_length} + value_real'length - 1 downto 0);",
        )
        common.write(
            code[0],
            1,
            f"signal res_im : signed({self._dt.internal_length} + value_imag'length - 1 downto 0);",
        )
        common.write(
            code[0],
            1,
            f"signal res_0_re, res_0_im : signed({self._dt.internal_high} downto 0);",
        )

        common.write(
            code[1],
            1,
            f"a <= signed(p_0_in_reg_0({2 * sum(self._dt.internal_wl) - 1} downto {sum(self._dt.internal_wl)}));",
        )
        common.write(
            code[1],
            1,
            f"b <= signed(p_0_in_reg_0({sum(self._dt.internal_wl) - 1} downto 0));",
        )

        common.write(code[1], 1, "ac <= a * value_real;")
        common.write(code[1], 1, "ad <= a * value_imag;")
        common.write(code[1], 1, "bc <= b * value_real;")
        common.write(code[1], 1, "bd <= b * value_imag;")

        common.write(code[1], 1, "res_re <= ac - bd;")
        common.write(code[1], 1, "res_im <= ad + bc;")

        common.write(
            code[1],
            1,
            "res_0_re <= res_re(res_re'high - WL_VALUE_REAL_INT downto res_re'high - WL_VALUE_REAL_INT - res_0_re'high);",
        )
        common.write(
            code[1],
            1,
            "res_0_im <= res_im(res_im'high - WL_VALUE_IMAG_INT downto res_im'high - WL_VALUE_IMAG_INT - res_0_im'high);",
        )

        common.write(
            code[1],
            1,
            "res_0 <= std_logic_vector(res_0_re) & std_logic_vector(res_0_im);",
        )
        return code[0].getvalue(), code[1].getvalue()

    def print_MADS(self) -> tuple[str, str]:
        return getattr(
            self,  # TODO: Default to operation._vhdl somewhere...
            f"print_MADS_{self._dt.num_repr.name.lower()}_{'complex' if self._dt.is_complex else 'real'}",
        )()

    def print_MADS_fixed_point_real(self) -> tuple[str, str]:
        code = (io.StringIO(), io.StringIO())

        common.write(
            code[0],
            1,
            "signal mul_res : signed(p_1_in'length + p_2_in'length - 1 downto 0);",
        )
        common.write(code[0], 1, "signal mul_res_quant : signed(res_0'high downto 0);")
        common.write(code[0], 1, "signal add_res : signed(res_0'high downto 0);")

        common.write(code[1], 1, "mul_res <= p_1_in_reg_0 * p_2_in_reg_0;")
        common.write(
            code[1],
            1,
            f"mul_res_quant <= mul_res(mul_res'high - {self._dt.internal_wl[0]} downto mul_res'high - {self._dt.internal_wl[0]} - mul_res_quant'high);",
        )
        common.write(
            code[1],
            1,
            "add_res <= p_0_in_reg_0 + mul_res_quant when is_add = '1' else p_0_in_reg_0 - mul_res_quant;",
        )
        common.write(
            code[1], 1, "res_0 <= add_res when do_addsub = '1' else mul_res_quant;\n"
        )

        return code[0].getvalue(), code[1].getvalue()

    def print_Reciprocal(self) -> tuple[str, str]:
        return getattr(
            self,  # TODO: Default to operation._vhdl somewhere...
            f"print_Reciprocal_{self._dt.num_repr.name.lower()}_{'complex' if self._dt.is_complex else 'real'}",
        )()

    def print_Reciprocal_fixed_point_real(self) -> tuple[str, str]:
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

        common.write(code[1], 1, "a <= p_0_in_reg_0;")
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

    def print_default(self) -> tuple[str, str]:
        return "", ""
