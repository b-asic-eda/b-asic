"""Module for generating VHDL test benches."""

from collections import defaultdict
from pathlib import Path

from apytypes import APyCFixed, APyCFloat

from b_asic.architecture import Architecture
from b_asic.code_printer.util import bin_str
from b_asic.data_type import DataType
from b_asic.simulation import ResultArrayMap
from b_asic.special_operations import Input, Output


class VhdlTbPrinter:
    """
    Class for generating VHDL test benches.

    Parameters
    ----------
    sim_results : ResultArrayMap
        Simulation results mapping graph IDs to their output values over iterations.
    """

    _sim_results: ResultArrayMap

    def __init__(self, sim_results: ResultArrayMap):
        self._sim_results = sim_results

    def print(
        self,
        arch: Architecture,
        dt: DataType,
        *,
        path: str | Path = Path(),
        asserts: bool = True,
    ) -> None:
        """
        Generate the VHDL test bench file.

        Parameters
        ----------
        arch : Architecture
            The architecture to generate the testbench for.
        dt : DataType
            The data type used for port widths in signal declarations.
        path : str or Path, default Path()
            The output directory path, defaults to the current directory.
        asserts : bool, default True
            Whether to include output assertions in the testbench.
        """
        path = Path(path)

        is_complex = any(
            isinstance(v[0], (complex, APyCFixed, APyCFloat))
            for v in self._sim_results.values()
        )

        # Track which graph_ids have been marked as input/output and their schedule
        io_marked = {}
        for pe in arch.processing_elements:
            if pe.operation_type not in (Input, Output):
                continue
            for pe_process in pe.collection:
                gid = pe_process.operation.graph_id
                io_marked[gid] = {
                    "is_input": pe.operation_type is Input,
                    "pe_name": pe.entity_name,
                    "start_time": pe_process.start_time,
                }

        seq_map = defaultdict(dict)
        input_signal_names: set[str] = set()

        for gid in io_marked:
            values = self._sim_results[gid]
            pe_name = io_marked[gid]["pe_name"]
            is_input = io_marked[gid]["is_input"]
            start_time = io_marked[gid]["start_time"]
            schedule_time = arch.schedule_time

            for sample_idx in range(len(values)):
                value = values[sample_idx]
                time = start_time + sample_idx * schedule_time

                if is_complex:
                    if is_input:
                        sig_re = f"{pe_name}_0_in_re"
                        sig_im = f"{pe_name}_0_in_im"
                        seq_map[time][sig_re] = value.to_bits()[0]
                        seq_map[time][sig_im] = value.to_bits()[1]
                        input_signal_names.update([sig_re, sig_im])
                    else:
                        seq_map[time][f"{pe_name}_0_out_re"] = value.to_bits()[0]
                        seq_map[time][f"{pe_name}_0_out_im"] = value.to_bits()[1]
                else:
                    if is_input:
                        sig = f"{pe_name}_0_in"
                        seq_map[time][sig] = value.to_bits()
                        input_signal_names.add(sig)
                    else:
                        seq_map[time][f"{pe_name}_0_out"] = value.to_bits()

        seq_map = dict(seq_map)

        vhdl_content = self._generate_vhdl(
            arch, dt, seq_map, input_signal_names, is_complex, asserts
        )

        with (path / "tb.vhdl").open("w") as f:
            f.write(vhdl_content)

    def _generate_vhdl(
        self,
        arch: Architecture,
        dt: DataType,
        seq_map: dict,
        input_signal_names: set[str],
        is_complex: bool,
        asserts: bool = True,
    ) -> str:
        lines = []

        # Header
        lines += [
            "-- B-ASIC generated VHDL testbench",
            "library ieee;",
            "use ieee.std_logic_1164.all;",
            "use ieee.numeric_std.all;",
            "",
            "entity tb is",
            "end entity tb;",
            "",
            "architecture sim of tb is",
            "",
            "    constant CLK_PERIOD : time := 2 ns;",
            "",
            "    signal clk : std_logic := '0';",
            "    signal rst : std_logic := '1';",
            "",
        ]

        # Signal declarations and port map entries
        input_port_maps = ["clk => clk", "rst => rst"]
        output_port_maps = []

        for pe in arch.processing_elements:
            if pe.operation_type is Input:
                if is_complex:
                    for suffix in ("re", "im"):
                        sig = f"{pe.entity_name}_0_in_{suffix}"
                        lines.append(
                            f"    signal {sig} : std_logic_vector("
                            f"{dt.input_bits - 1} downto 0) := (others => '0');"
                        )
                        input_port_maps.append(f"{sig} => {sig}")
                else:
                    sig = f"{pe.entity_name}_0_in"
                    lines.append(
                        f"    signal {sig} : std_logic_vector("
                        f"{dt.input_bits - 1} downto 0) := (others => '0');"
                    )
                    input_port_maps.append(f"{sig} => {sig}")
            elif pe.operation_type is Output:
                if is_complex:
                    for suffix in ("re", "im"):
                        sig = f"{pe.entity_name}_0_out_{suffix}"
                        lines.append(
                            f"    signal {sig} : std_logic_vector("
                            f"{dt.output_bits - 1} downto 0);"
                        )
                        output_port_maps.append(f"{sig} => {sig}")
                else:
                    sig = f"{pe.entity_name}_0_out"
                    lines.append(
                        f"    signal {sig} : std_logic_vector("
                        f"{dt.output_bits - 1} downto 0);"
                    )
                    output_port_maps.append(f"{sig} => {sig}")

        lines.append("")
        lines.append("begin")
        lines.append("")

        # DUT instantiation
        all_port_maps = input_port_maps + output_port_maps
        lines.append(f"    dut : entity work.{arch.entity_name}")
        lines.append("        port map (")
        for i, pm in enumerate(all_port_maps):
            sep = "," if i < len(all_port_maps) - 1 else ""
            lines.append(f"            {pm}{sep}")
        lines.append("        );")
        lines.append("")

        # Clock
        lines.append("    clk <= not clk after CLK_PERIOD / 2;")
        lines.append("")

        # Stimulus process
        lines += [
            "    stimulus : process",
            "    begin",
            "        -- Assert reset for two clock cycles",
            "        rst <= '1';",
            "        wait until falling_edge(clk);",
            "        wait until falling_edge(clk);",
            "        rst <= '0';",
            "",
            # "        -- Sync to first active falling edge",
            # "        wait until falling_edge(clk);",
            "",
        ]

        max_cycle = max(seq_map.keys()) if seq_map else 0

        for cycle in range(max_cycle + 1):
            lines.append(f"        -- Cycle {cycle}")
            if cycle in seq_map:
                step = seq_map[cycle]

                # Check outputs first, then drive inputs
                for signal_name, value in step.items():
                    if signal_name not in input_signal_names and asserts:
                        bits = dt.output_bits
                        lines.append(
                            f'        assert {signal_name} = "{bin_str(value, bits)}";'
                        )
                        # TODO: Fix!
                        # lines.append(
                        #     f'            report "Cycle {cycle}: {signal_name}'
                        #     f' expected {value}, got "'
                        #     f" & integer'image(to_integer(unsigned({signal_name})))"
                        #     f" severity failure;"
                        # )

                for signal_name, value in step.items():
                    if signal_name in input_signal_names:
                        bits = dt.input_bits
                        lines.append(
                            f'        {signal_name} <= "{bin_str(value, bits)}";'
                        )

            lines.append("        wait until falling_edge(clk);")
            lines.append("")

        lines += [
            '        report "SUCCESS: All assertions passed" severity note;',
            "        wait;",
            "    end process stimulus;",
            "",
            "end architecture sim;",
            "",
        ]

        return "\n".join(lines)
