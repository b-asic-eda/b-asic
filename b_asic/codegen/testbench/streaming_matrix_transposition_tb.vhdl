--
-- Generic streaming transposition testbench using VUnit
-- Author: Mikael Henriksson (2023)
--

library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_tester is
    generic(
        WL          : integer;
        ROWS        : integer;
        COLS        : integer
    );
    port(
        clk, rst, en : out std_logic;
        input : out std_logic_vector(WL-1 downto 0);
        output : in std_logic_vector(WL-1 downto 0);
        done : out boolean
    );
end entity streaming_matrix_transposition_tester;

architecture behav of streaming_matrix_transposition_tester is
    signal clk_sig : std_logic;
begin

    -- Clock (100 MHz), enable and reset generation.
    clk <= clk_sig;
    rst <= '1', '0' after 40 ns;
    en <= '0', '1' after 100 ns;
    process begin
        clk_sig <= '0';
        loop
            wait for 5 ns; clk_sig <= not(clk_sig);
        end loop;
    end process;

    -- Input generation
    input_gen_proc: process begin
        wait until en = '1';
        for i in 0 to 4*ROWS*COLS-1 loop
            wait until clk = '0';
            input <= std_logic_vector(to_unsigned(i, input'length));
        end loop;
        wait;
    end process;

    -- Output testing
    output_test_proc: process begin
        wait until en = '1';
        wait until output = std_logic_vector(to_unsigned(0, output'length));
        for i in 0 to 3 loop
            for col in 0 to COLS-1 loop
                for row in 0 to ROWS-1 loop
                    wait until clk = '0';
                    check(
                        output =
                        std_logic_vector(
                            to_unsigned(i*ROWS*COLS + row*COLS + col, output'length)
                        )
                    );
                end loop;
            end loop;
        end loop;
        done <= true;
        wait;
    end process;

end architecture behav;


----------------------------------------------------------------------------------------
---                                TEST INSTANCES                                    ---
----------------------------------------------------------------------------------------

--
-- 2x2 memory based matrix transposition
--
library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_memory_2x2_tb is
    generic (
        runner_cfg  : string;   -- VUnit python pipe
        tb_path     : string    -- Absolute path to this testbench
    );
end entity streaming_matrix_transposition_memory_2x2_tb;

architecture behav of streaming_matrix_transposition_memory_2x2_tb is
    constant WL : integer := 16;
    signal done : boolean;
    signal input, output : std_logic_vector(WL-1 downto 0);
    signal clk, rst, en : std_logic;
begin

    -- VUnit test runner
    process begin
        test_runner_setup(runner, runner_cfg);
        wait until done = true;
        test_runner_cleanup(runner);
    end process;

    -- Run the test baby!
    dut : entity work.streaming_matrix_transposition_memory_2x2
        generic map(WL=>WL) port map(clk, rst, en, input, output);
    tb : entity work.streaming_matrix_transposition_tester
        generic map (WL=>WL, ROWS=>2, COLS=>2) port map(clk, rst, en, input, output, done);

end architecture behav;

--
-- 3x3 memory based matrix transposition
--
library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_memory_3x3_tb is
    generic (
        runner_cfg  : string;   -- VUnit python pipe
        tb_path     : string    -- Absolute path to this testbench
    );
end entity streaming_matrix_transposition_memory_3x3_tb;

architecture behav of streaming_matrix_transposition_memory_3x3_tb is
    constant WL : integer := 16;
    signal done : boolean;
    signal input, output : std_logic_vector(WL-1 downto 0);
    signal clk, rst, en : std_logic;
begin

    -- VUnit test runner
    process begin
        test_runner_setup(runner, runner_cfg);
        wait until done = true;
        test_runner_cleanup(runner);
    end process;

    -- Run the test baby!
    dut : entity work.streaming_matrix_transposition_memory_3x3
        generic map(WL=>WL) port map(clk, rst, en, input, output);
    tb : entity work.streaming_matrix_transposition_tester
        generic map (WL=>WL, ROWS=>3, COLS=>3) port map(clk, rst, en, input, output, done);

end architecture behav;

--
-- 4x4 memory based matrix transposition
--
library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_memory_4x4_tb is
    generic (
        runner_cfg  : string;   -- VUnit python pipe
        tb_path     : string    -- Absolute path to this testbench
    );
end entity streaming_matrix_transposition_memory_4x4_tb;

architecture behav of streaming_matrix_transposition_memory_4x4_tb is
    constant WL : integer := 16;
    signal done : boolean;
    signal input, output : std_logic_vector(WL-1 downto 0);
    signal clk, rst, en : std_logic;
begin

    -- VUnit test runner
    process begin
        test_runner_setup(runner, runner_cfg);
        wait until done = true;
        test_runner_cleanup(runner);
    end process;

    -- Run the test baby!
    dut : entity work.streaming_matrix_transposition_memory_4x4
        generic map(WL=>WL) port map(clk, rst, en, input, output);
    tb : entity work.streaming_matrix_transposition_tester
        generic map (WL=>WL, ROWS=>4, COLS=>4) port map(clk, rst, en, input, output, done);

end architecture behav;

--
-- 5x5 memory based matrix transposition
--
library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_memory_5x5_tb is
    generic (
        runner_cfg  : string;   -- VUnit python pipe
        tb_path     : string    -- Absolute path to this testbench
    );
end entity streaming_matrix_transposition_memory_5x5_tb;

architecture behav of streaming_matrix_transposition_memory_5x5_tb is
    constant WL : integer := 16;
    signal done : boolean;
    signal input, output : std_logic_vector(WL-1 downto 0);
    signal clk, rst, en : std_logic;
begin

    -- VUnit test runner
    process begin
        test_runner_setup(runner, runner_cfg);
        wait until done = true;
        test_runner_cleanup(runner);
    end process;

    -- Run the test baby!
    dut : entity work.streaming_matrix_transposition_memory_5x5
        generic map(WL=>WL) port map(clk, rst, en, input, output);
    tb : entity work.streaming_matrix_transposition_tester
        generic map (WL=>WL, ROWS=>5, COLS=>5) port map(clk, rst, en, input, output, done);

end architecture behav;

--
-- 7x7 memory based matrix transposition
--
library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_memory_7x7_tb is
    generic (
        runner_cfg  : string;   -- VUnit python pipe
        tb_path     : string    -- Absolute path to this testbench
    );
end entity streaming_matrix_transposition_memory_7x7_tb;

architecture behav of streaming_matrix_transposition_memory_7x7_tb is
    constant WL : integer := 16;
    signal done : boolean;
    signal input, output : std_logic_vector(WL-1 downto 0);
    signal clk, rst, en : std_logic;
begin

    -- VUnit test runner
    process begin
        test_runner_setup(runner, runner_cfg);
        wait until done = true;
        test_runner_cleanup(runner);
    end process;

    -- Run the test baby!
    dut : entity work.streaming_matrix_transposition_memory_7x7
        generic map(WL=>WL) port map(clk, rst, en, input, output);
    tb : entity work.streaming_matrix_transposition_tester
        generic map (WL=>WL, ROWS=>7, COLS=>7) port map(clk, rst, en, input, output, done);

end architecture behav;


--
-- 4x8 memory based matrix transposition
--
library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_memory_4x8_tb is
    generic (
        runner_cfg  : string;   -- VUnit python pipe
        tb_path     : string    -- Absolute path to this testbench
    );
end entity streaming_matrix_transposition_memory_4x8_tb;

architecture behav of streaming_matrix_transposition_memory_4x8_tb is
    constant WL : integer := 16;
    signal done : boolean;
    signal input, output : std_logic_vector(WL-1 downto 0);
    signal clk, rst, en : std_logic;
begin

    -- VUnit test runner
    process begin
        test_runner_setup(runner, runner_cfg);
        wait until done = true;
        test_runner_cleanup(runner);
    end process;

    -- Run the test baby!
    dut : entity work.streaming_matrix_transposition_memory_4x8
        generic map(WL=>WL) port map(clk, rst, en, input, output);
    tb : entity work.streaming_matrix_transposition_tester
        generic map (WL=>WL, ROWS=>4, COLS=>8) port map(clk, rst, en, input, output, done);

end architecture behav;

--
-- 2x2 register based matrix transposition
--
library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_register_2x2_tb is
    generic (
        runner_cfg  : string;   -- VUnit python pipe
        tb_path     : string    -- Absolute path to this testbench
    );
end entity streaming_matrix_transposition_register_2x2_tb;

architecture behav of streaming_matrix_transposition_register_2x2_tb is
    constant WL : integer := 16;
    signal done : boolean;
    signal input, output : std_logic_vector(WL-1 downto 0);
    signal clk, rst, en : std_logic;
begin

    -- VUnit test runner
    process begin
        test_runner_setup(runner, runner_cfg);
        wait until done = true;
        test_runner_cleanup(runner);
    end process;

    -- Run the test baby!
    dut : entity work.streaming_matrix_transposition_register_2x2
        generic map(WL=>WL) port map(clk, rst, en, input, output);
    tb : entity work.streaming_matrix_transposition_tester
        generic map (WL=>WL, ROWS=>2, COLS=>2) port map(clk, rst, en, input, output, done);

end architecture behav;

--
-- 3x3 register based matrix transposition
--
library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_register_3x3_tb is
    generic (
        runner_cfg  : string;   -- VUnit python pipe
        tb_path     : string    -- Absolute path to this testbench
    );
end entity streaming_matrix_transposition_register_3x3_tb;

architecture behav of streaming_matrix_transposition_register_3x3_tb is
    constant WL : integer := 16;
    signal done : boolean;
    signal input, output : std_logic_vector(WL-1 downto 0);
    signal clk, rst, en : std_logic;
begin

    -- VUnit test runner
    process begin
        test_runner_setup(runner, runner_cfg);
        wait until done = true;
        test_runner_cleanup(runner);
    end process;

    -- Run the test baby!
    dut : entity work.streaming_matrix_transposition_register_3x3
        generic map(WL=>WL) port map(clk, rst, en, input, output);
    tb : entity work.streaming_matrix_transposition_tester
        generic map (WL=>WL, ROWS=>3, COLS=>3) port map(clk, rst, en, input, output, done);

end architecture behav;

--
-- 4x4 register based matrix transposition
--
library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_register_4x4_tb is
    generic (
        runner_cfg  : string;   -- VUnit python pipe
        tb_path     : string    -- Absolute path to this testbench
    );
end entity streaming_matrix_transposition_register_4x4_tb;

architecture behav of streaming_matrix_transposition_register_4x4_tb is
    constant WL : integer := 16;
    signal done : boolean;
    signal input, output : std_logic_vector(WL-1 downto 0);
    signal clk, rst, en : std_logic;
begin

    -- VUnit test runner
    process begin
        test_runner_setup(runner, runner_cfg);
        wait until done = true;
        test_runner_cleanup(runner);
    end process;

    -- Run the test baby!
    dut : entity work.streaming_matrix_transposition_register_4x4
        generic map(WL=>WL) port map(clk, rst, en, input, output);
    tb : entity work.streaming_matrix_transposition_tester
        generic map (WL=>WL, ROWS=>4, COLS=>4) port map(clk, rst, en, input, output, done);

end architecture behav;

--
-- 5x5 register based matrix transposition
--
library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_register_5x5_tb is
    generic (
        runner_cfg  : string;   -- VUnit python pipe
        tb_path     : string    -- Absolute path to this testbench
    );
end entity streaming_matrix_transposition_register_5x5_tb;

architecture behav of streaming_matrix_transposition_register_5x5_tb is
    constant WL : integer := 16;
    signal done : boolean;
    signal input, output : std_logic_vector(WL-1 downto 0);
    signal clk, rst, en : std_logic;
begin

    -- VUnit test runner
    process begin
        test_runner_setup(runner, runner_cfg);
        wait until done = true;
        test_runner_cleanup(runner);
    end process;

    -- Run the test baby!
    dut : entity work.streaming_matrix_transposition_register_5x5
        generic map(WL=>WL) port map(clk, rst, en, input, output);
    tb : entity work.streaming_matrix_transposition_tester
        generic map (WL=>WL, ROWS=>5, COLS=>5) port map(clk, rst, en, input, output, done);

end architecture behav;

--
-- 7x7 register based matrix transposition
--
library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_register_7x7_tb is
    generic (
        runner_cfg  : string;   -- VUnit python pipe
        tb_path     : string    -- Absolute path to this testbench
    );
end entity streaming_matrix_transposition_register_7x7_tb;

architecture behav of streaming_matrix_transposition_register_7x7_tb is
    constant WL : integer := 16;
    signal done : boolean;
    signal input, output : std_logic_vector(WL-1 downto 0);
    signal clk, rst, en : std_logic;
begin

    -- VUnit test runner
    process begin
        test_runner_setup(runner, runner_cfg);
        wait until done = true;
        test_runner_cleanup(runner);
    end process;

    -- Run the test baby!
    dut : entity work.streaming_matrix_transposition_register_7x7
        generic map(WL=>WL) port map(clk, rst, en, input, output);
    tb : entity work.streaming_matrix_transposition_tester
        generic map (WL=>WL, ROWS=>7, COLS=>7) port map(clk, rst, en, input, output, done);

end architecture behav;

--
-- 4x8 register based matrix transposition
--
library ieee, vunit_lib;
context vunit_lib.vunit_context;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity streaming_matrix_transposition_register_4x8_tb is
    generic (
        runner_cfg  : string;   -- VUnit python pipe
        tb_path     : string    -- Absolute path to this testbench
    );
end entity streaming_matrix_transposition_register_4x8_tb;

architecture behav of streaming_matrix_transposition_register_4x8_tb is
    constant WL : integer := 16;
    signal done : boolean;
    signal input, output : std_logic_vector(WL-1 downto 0);
    signal clk, rst, en : std_logic;
begin

    -- VUnit test runner
    process begin
        test_runner_setup(runner, runner_cfg);
        wait until done = true;
        test_runner_cleanup(runner);
    end process;

    -- Run the test baby!
    dut : entity work.streaming_matrix_transposition_register_4x8
        generic map(WL=>WL) port map(clk, rst, en, input, output);
    tb : entity work.streaming_matrix_transposition_tester
        generic map (WL=>WL, ROWS=>4, COLS=>8) port map(clk, rst, en, input, output, done);

end architecture behav;
