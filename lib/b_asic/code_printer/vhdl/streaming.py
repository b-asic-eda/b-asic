"""Elastic streaming I/O and clock-domain crossing for scheduled cores."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TextIO

from b_asic.code_printer.vhdl import common
from b_asic.special_operations import Input, Output

if TYPE_CHECKING:
    from b_asic.architecture import Architecture, ProcessingElement
    from b_asic.data_type import _VhdlDataType


@dataclass(frozen=True)
class StreamInterface:
    """
    VHDL I/O selection; the default preserves fixed-interval ports.

    Avalon-ST uses ready latency zero. Independent clocks require power-of-two
    FIFO depths >= 4. ``stallable`` gates the complete core and schedule counter
    when a scheduled transfer is unavailable. Rigid cores instead latch an
    error on starvation/overflow and require reset. ``frame_length`` generates
    output TLAST/EOP; input framing is retained alongside each FIFO sample.
    """

    protocol: Literal["synchronous", "axi4_stream", "avalon_st"] = "synchronous"
    clock_mode: Literal["synchronous", "asynchronous"] = "synchronous"
    fifo_depth: int = 16
    startup_threshold: int = 1
    stallable: bool = True
    frame_length: int | None = None

    def __post_init__(self) -> None:
        if self.protocol not in ("synchronous", "axi4_stream", "avalon_st"):
            raise ValueError("Unknown interface protocol")
        if self.clock_mode not in ("synchronous", "asynchronous"):
            raise ValueError("Unknown interface clock_mode")
        for name in ("fifo_depth", "startup_threshold"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.startup_threshold > self.fifo_depth:
            raise ValueError("startup_threshold must not exceed fifo_depth")
        if self.clock_mode == "asynchronous" and (
            self.fifo_depth < 4 or self.fifo_depth & (self.fifo_depth - 1)
        ):
            raise ValueError("Asynchronous FIFO depth must be a power of two >= 4")
        if self.frame_length is not None and (
            type(self.frame_length) is not int or self.frame_length < 1
        ):
            raise ValueError("frame_length must be a positive integer or None")


@dataclass
class Endpoint:
    name: str
    pes: list["ProcessingElement"]
    config: StreamInterface

    @property
    def input(self) -> bool:
        return self.pes[0].operation_type == Input

    def pin(self, kind: str) -> str:
        names = {"data": "tdata", "valid": "tvalid", "ready": "tready", "last": "tlast"}
        if self.config.protocol == "avalon_st":
            names = {
                "data": "data",
                "valid": "valid",
                "ready": "ready",
                "last": "endofpacket",
            }
        return f"{self.name}_{names[kind]}"


def endpoints(
    arch: "Architecture",
    override: StreamInterface | None = None,
    input_groups: dict[str, list[str]] | None = None,
    output_groups: dict[str, list[str]] | None = None,
) -> list[Endpoint]:
    """Validate shared physical ports before any source files are written."""
    if override is not None and not isinstance(override, StreamInterface):
        raise TypeError("interface must be a StreamInterface")
    config = override or StreamInterface()
    if config.protocol == "synchronous":
        if input_groups or output_groups:
            raise ValueError("Stream grouping requires a streaming interface")
        return []
    result = []
    for op_type, groups in ((Input, input_groups), (Output, output_groups)):
        resources = {
            pe.entity_name: pe
            for pe in arch.processing_elements
            if pe.operation_type == op_type
        }
        used = set()
        for name, members in (groups or {}).items():
            if not common.is_valid_vhdl_identifier(name) or not members:
                raise ValueError(
                    "Stream groups need a valid VHDL name and nonempty members"
                )
            if any(
                member not in resources or member in used for member in members
            ) or len(set(members)) != len(members):
                raise ValueError(
                    "Stream members must name distinct I/O resources of the correct direction"
                )
            used.update(members)
            result.append(
                Endpoint(name, [resources[member] for member in members], config)
            )
        result.extend(
            Endpoint(name, [pe], config)
            for name, pe in resources.items()
            if name not in used
        )
    if len({ep.name.lower() for ep in result}) != len(result):
        raise ValueError("Stream names must be unique")
    for ep in result:
        times = [
            p.start_time % arch.schedule_time for pe in ep.pes for p in pe.collection
        ]
        if len(times) != len(set(times)):
            raise ValueError(
                f"Stream {ep.name} requires multiple transfers in the same cycle"
            )
    return result


def ports(items: list[Endpoint], dt: "_VhdlDataType") -> list[str]:
    result = ["core_active : out std_logic", "stream_error : out std_logic"]
    for ep in items:
        direction, reverse = ("in", "out") if ep.input else ("out", "in")
        bits = (dt.input_bits if ep.input else dt.output_bits) * (
            2 if dt.is_complex else 1
        )
        # AXI TDATA is byte aligned. Unused high bits are zero on output.
        if ep.config.protocol == "axi4_stream":
            bits = ((bits + 7) // 8) * 8
        result += [
            f"{ep.pin('data')} : {direction} std_logic_vector({bits - 1} downto 0)",
            f"{ep.pin('valid')} : {direction} std_logic",
            f"{ep.pin('ready')} : {reverse} std_logic",
            f"{ep.pin('last')} : {direction} std_logic",
        ]
        if ep.config.clock_mode == "asynchronous":
            result.append(f"{ep.name}_clk : in std_logic")
        if ep.input:
            result += [
                f"{ep.name}_core_last : out std_logic",
                f"{ep.name}_core_valid : out std_logic",
            ]
    return result


def declarations(f: TextIO, items: list[Endpoint], dt: "_VhdlDataType") -> None:
    common.write(f, 1, "signal core_en, stream_started : std_logic := '0';")
    limit = max(
        process.start_time for ep in items for pe in ep.pes for process in pe.collection
    )
    common.write(f, 1, f"signal stream_cycle : natural range 0 to {limit} := 0;")
    for ep in items:
        n = ep.name
        bits = (dt.input_bits if ep.input else dt.output_bits) * (
            2 if dt.is_complex else 1
        )
        for pe in ep.pes:
            decls = (
                dt.get_input_port_declaration(pe.entity_name)
                if ep.input
                else dt.get_output_port_declaration(pe.entity_name)
            )
            for decl in decls:
                common.write(
                    f,
                    1,
                    "signal "
                    + decl.replace(" : in ", " : ").replace(" : out ", " : ")
                    + ";",
                )
        common.write(
            f, 1, f"signal {n}_din, {n}_dout : std_logic_vector({bits} downto 0);"
        )
        common.write(
            f, 1, f"signal {n}_push, {n}_pop, {n}_full, {n}_empty, {n}_due : std_logic;"
        )
        common.write(f, 1, f"signal {n}_fault : std_logic := '0';")
        common.write(
            f, 1, f"signal {n}_count : natural range 0 to {ep.config.fifo_depth};"
        )
        if not ep.input and ep.config.frame_length is not None:
            common.write(
                f,
                1,
                f"signal {n}_frame : natural range 0 to {ep.config.frame_length - 1} := 0;",
            )


def statements(
    f: TextIO,
    arch: "Architecture",
    items: list[Endpoint],
    dt: "_VhdlDataType",
    enable_pin: bool,
) -> None:
    def emit(line: str) -> None:
        common.write(f, 1, line)

    thresholds = [
        f"{ep.name}_count >= {ep.config.startup_threshold}" for ep in items if ep.input
    ]
    faults = " or ".join(f"{ep.name}_fault = '1'" for ep in items)
    available = [
        f"({ep.name}_due = '0' or {ep.name}_{'empty' if ep.input else 'full'} = '0')"
        for ep in items
        if ep.config.stallable
    ]
    conditions = ["rst = '0'", "stream_started = '1'", f"not ({faults})", *available]
    if enable_pin:
        conditions.append("en = '1'")
    emit("core_en <= '1' when " + " and ".join(conditions) + " else '0';")
    emit("core_active <= core_en;")
    emit(f"stream_error <= '1' when {faults} else '0';")
    limit = max(
        process.start_time for ep in items for pe in ep.pes for process in pe.collection
    )
    emit("stream_start: process(clk) begin")
    emit("    if rising_edge(clk) then")
    emit("        if rst = '1' then")
    emit("            stream_started <= '0'; stream_cycle <= 0;")
    emit("        else")
    emit(
        "            if "
        + (" and ".join(thresholds) or "true")
        + " then stream_started <= '1'; end if;"
    )
    emit(
        f"            if core_en = '1' and stream_cycle < {limit} then stream_cycle <= stream_cycle + 1; end if;"
    )
    emit("        end if;")
    emit("    end if;")
    emit("end process;")
    for ep in items:
        n, cfg = ep.name, ep.config
        bits = (dt.input_bits if ep.input else dt.output_bits) * (
            2 if dt.is_complex else 1
        )
        scalar = dt.input_bits if ep.input else dt.output_bits
        times = sorted(
            {process.start_time for pe in ep.pes for process in pe.collection}
        )
        due = " or ".join(
            f"(to_integer(schedule_cnt) = {time % arch.schedule_time} and stream_cycle >= {time})"
            for time in times
        )
        emit(f"{n}_due <= '1' when {due} else '0';")
        bus_clk = f"{n}_clk" if cfg.clock_mode == "asynchronous" else "clk"
        wc, rc = (bus_clk, "clk") if ep.input else ("clk", bus_clk)
        emit(f"{n}_fifo: entity work.{arch.entity_name}_stream_fifo")
        emit(
            f"    generic map (WIDTH => {bits + 1}, DEPTH => {cfg.fifo_depth}, DUAL_CLOCK => {str(cfg.clock_mode == 'asynchronous').lower()})"
        )
        emit(
            f"    port map (rst => rst, wclk => {wc}, rclk => {rc}, push => {n}_push, pop => {n}_pop,"
        )
        emit(
            f"        din => {n}_din, dout => {n}_dout, full => {n}_full, empty => {n}_empty,"
        )
        emit(
            f"        {'read_count' if ep.input else 'write_count'} => {n}_count, {'write_count' if ep.input else 'read_count'} => open);"
        )
        if ep.input:
            emit(
                f"{n}_din <= {ep.pin('last')} & {ep.pin('data')}({bits - 1} downto 0);"
            )
            emit(f"{ep.pin('ready')} <= not {n}_full and not rst;")
            emit(f"{n}_push <= {ep.pin('valid')} and not {n}_full and not rst;")
            emit(f"{n}_pop <= core_en and {n}_due and not {n}_empty;")
            for pe in ep.pes:
                if dt.is_complex:
                    emit(
                        f"{pe.entity_name}_0_in_re <= {n}_dout({scalar - 1} downto 0);"
                    )
                    emit(
                        f"{pe.entity_name}_0_in_im <= {n}_dout({bits - 1} downto {scalar});"
                    )
                else:
                    emit(f"{pe.entity_name}_0_in <= {n}_dout({bits - 1} downto 0);")
            emit(f"{n}_core_last <= {n}_dout({bits});")
            emit(f"{n}_core_valid <= {n}_pop;")
        else:
            last = (
                f"'1' when {n}_frame = {cfg.frame_length - 1} else '0'"
                if cfg.frame_length
                else "'0'"
            )
            emit(f"{n}_din({bits}) <= {last};")
            choices = []
            for pe in ep.pes:
                pn = pe.entity_name
                data = (
                    f"{pn}_0_out_im & {pn}_0_out_re" if dt.is_complex else f"{pn}_0_out"
                )
                selected = " or ".join(
                    f"to_integer(schedule_cnt) = {p.start_time % arch.schedule_time}"
                    for p in pe.collection
                )
                choices.append(f"{data} when {selected} else ")
            emit(
                f"{n}_din({bits - 1} downto 0) <= "
                + "".join(choices)
                + "(others => '0');"
            )
            bus_bits = ((bits + 7) // 8) * 8 if cfg.protocol == "axi4_stream" else bits
            emit(
                f"{ep.pin('data')} <= std_logic_vector(resize(unsigned({n}_dout({bits - 1} downto 0)), {bus_bits}));"
            )
            emit(f"{ep.pin('last')} <= {n}_dout({bits});")
            emit(f"{ep.pin('valid')} <= not {n}_empty and not rst;")
            emit(f"{n}_pop <= {ep.pin('ready')} and not {n}_empty and not rst;")
            emit(f"{n}_push <= core_en and {n}_due and not {n}_full;")
        emit(f"{n}_status: process(clk) begin")
        emit("    if rising_edge(clk) then")
        emit(f"        if rst = '1' then {n}_fault <= '0';")
        if not ep.input and cfg.frame_length:
            emit(f"            {n}_frame <= 0;")
        emit("        else")
        flag = "empty" if ep.input else "full"
        emit(
            f"            if core_en = '1' and {n}_due = '1' and {n}_{flag} = '1' then {n}_fault <= '1'; end if;"
        )
        if not ep.input and cfg.frame_length:
            emit(f"            if {n}_push = '1' then")
            emit(
                f"                if {n}_frame = {cfg.frame_length - 1} then {n}_frame <= 0; else {n}_frame <= {n}_frame + 1; end if;"
            )
            emit("            end if;")
        emit("        end if;")
        emit("    end if;")
        emit("end process;")


def fifo_source(name: str) -> str:
    """
    Generate a show-ahead FIFO for one or two clocks.

    The dual-clock implementation synchronizes Gray pointers through two flops.
    Occupancy flags are deliberately conservative during synchronization delay.
    """
    return _FIFO.replace("FIFO_ENTITY", name + "_stream_fifo")


_FIFO = """
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity FIFO_ENTITY is
    generic (WIDTH : positive; DEPTH : positive; DUAL_CLOCK : boolean := false);
    port (rst, wclk, rclk, push, pop : in std_logic;
          din : in std_logic_vector(WIDTH-1 downto 0);
          dout : out std_logic_vector(WIDTH-1 downto 0);
          full, empty : out std_logic;
          write_count, read_count : out natural range 0 to DEPTH);
end entity;

architecture rtl of FIFO_ENTITY is
    function addr_bits(n : positive) return positive is
        variable bits : positive := 1;
    begin
        while 2**bits < n loop bits := bits + 1; end loop;
        return bits;
    end function;
    type ram_type is array (0 to DEPTH-1) of std_logic_vector(WIDTH-1 downto 0);
    signal ram : ram_type;
begin
    single_clock: if not DUAL_CLOCK generate
        signal wr, rd : natural range 0 to DEPTH-1 := 0;
        signal count : natural range 0 to DEPTH := 0;
    begin
        full <= '1' when count = DEPTH else '0';
        empty <= '1' when count = 0 else '0';
        write_count <= count;
        read_count <= count;
        dout <= ram(rd);
        process(wclk)
            variable writing, reading : boolean;
        begin
            if rising_edge(wclk) then
                if rst = '1' then
                    wr <= 0; rd <= 0; count <= 0;
                else
                    writing := push = '1' and count < DEPTH;
                    reading := pop = '1' and count > 0;
                    if writing then
                        ram(wr) <= din;
                        if wr = DEPTH-1 then wr <= 0; else wr <= wr+1; end if;
                    end if;
                    if reading then
                        if rd = DEPTH-1 then rd <= 0; else rd <= rd+1; end if;
                    end if;
                    if writing and not reading then count <= count+1;
                    elsif reading and not writing then count <= count-1;
                    end if;
                end if;
            end if;
        end process;
    end generate;

    dual_clocks: if DUAL_CLOCK generate
        constant A : positive := addr_bits(DEPTH);
        subtype pointer is unsigned(A downto 0);
        signal wr, rd, wg, rg : pointer := (others => '0');
        signal rg1, rg2, wg1, wg2 : pointer := (others => '0');
        signal wc, rc : pointer;
        signal wreset, rreset : std_logic_vector(1 downto 0) := "11";
        attribute async_reg : string;
        attribute async_reg of rg1, rg2, wg1, wg2, wreset, rreset : signal is "true";
        function binary(g : pointer) return pointer is
            variable b : pointer := g;
        begin
            for i in A-1 downto 0 loop b(i) := b(i+1) xor g(i); end loop;
            return b;
        end function;
    begin
        assert DEPTH >= 4 and DEPTH = 2**A report "Dual-clock depth must be a power of two >= 4" severity failure;
        wc <= wr - binary(rg2);
        rc <= binary(wg2) - rd;
        write_count <= to_integer(wc);
        read_count <= to_integer(rc);
        full <= '1' when wc = DEPTH or wreset(1) = '1' else '0';
        empty <= '1' when rc = 0 or rreset(1) = '1' else '0';
        dout <= ram(to_integer(rd(A-1 downto 0)));
        -- Assert reset in both domains; release it through local synchronizers.
        process(wclk, rst) begin
            if rst = '1' then wreset <= "11";
            elsif rising_edge(wclk) then wreset <= wreset(0) & '0'; end if;
        end process;
        process(rclk, rst) begin
            if rst = '1' then rreset <= "11";
            elsif rising_edge(rclk) then rreset <= rreset(0) & '0'; end if;
        end process;
        process(wclk)
            variable next_wr : pointer;
        begin
            if rising_edge(wclk) then
                if wreset(1) = '1' then
                    wr <= (others => '0'); wg <= (others => '0');
                    rg1 <= (others => '0'); rg2 <= (others => '0');
                else
                    rg1 <= rg; rg2 <= rg1;
                    if push = '1' and wc < DEPTH then
                        ram(to_integer(wr(A-1 downto 0))) <= din;
                        next_wr := wr + 1;
                        wr <= next_wr; wg <= next_wr xor shift_right(next_wr, 1);
                    end if;
                end if;
            end if;
        end process;
        process(rclk)
            variable next_rd : pointer;
        begin
            if rising_edge(rclk) then
                if rreset(1) = '1' then
                    rd <= (others => '0'); rg <= (others => '0');
                    wg1 <= (others => '0'); wg2 <= (others => '0');
                else
                    wg1 <= wg; wg2 <= wg1;
                    if pop = '1' and rc > 0 then
                        next_rd := rd + 1;
                        rd <= next_rd; rg <= next_rd xor shift_right(next_rd, 1);
                    end if;
                end if;
            end if;
        end process;
    end generate;
end architecture;
"""
