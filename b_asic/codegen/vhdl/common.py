"""
Generation of common VHDL constructs
"""

from datetime import datetime
from io import TextIOWrapper
from subprocess import PIPE, Popen
from typing import Any, Optional, Set, Tuple

from b_asic.codegen import vhdl


def write_b_asic_vhdl_preamble(f: TextIOWrapper):
    """
    Write a standard BASIC VHDL preamble comment.

    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The file object to write the header to.
    """
    # Try to acquire the current git commit hash
    git_commit_id = None
    try:
        process = Popen(['git', 'rev-parse', '--short', 'HEAD'], stdout=PIPE)
        git_commit_id = process.communicate()[0].decode('utf-8').strip()
    except:
        pass
    vhdl.write_lines(
        f,
        [
            (0, f'--'),
            (0, f'-- This code was automatically generated by the B-ASIC toolbox.'),
            (0, f'-- Code generation timestamp: ({datetime.now()})'),
        ],
    )
    if git_commit_id:
        vhdl.write(f, 0, f'-- B-ASIC short commit hash: {git_commit_id}')
    vhdl.write_lines(
        f,
        [
            (0, f'-- URL: https://gitlab.liu.se/da/B-ASIC'),
            (0, f'--', '\n\n'),
        ],
    )


def write_ieee_header(
    f: TextIOWrapper,
    std_logic_1164: bool = True,
    numeric_std: bool = True,
):
    """
    Write the standard IEEE VHDL use header with includes of std_logic_1164 and numeric_std.

    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The TextIOWrapper object to write the IEEE header to.
    std_logic_1164 : bool, default: True
        Include the std_logic_1164 header.
    numeric_std : bool, default: True
        Include the numeric_std header.
    """
    vhdl.write(f, 0, 'library ieee;')
    if std_logic_1164:
        vhdl.write(f, 0, 'use ieee.std_logic_1164.all;')
    if numeric_std:
        vhdl.write(f, 0, 'use ieee.numeric_std.all;')
    vhdl.write(f, 0, '')


def write_signal_decl(
    f: TextIOWrapper,
    name: str,
    type: str,
    default_value: Optional[str] = None,
    name_pad: Optional[int] = None,
    vivado_ram_style: Optional[str] = None,
    quartus_ram_style: Optional[str] = None,
):
    """
    Create a VHDL signal declaration: ::

        signal {name} : {type} [:= {default_value}];

    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The TextIOWrapper object to write the IEEE header to.
    name : str
        Signal name.
    type : str
        Signal type.
    default_value : string, optional
        An optional default value to the signal.
    name_pad : int, optional
        An optional left padding value applied to the name.
    vivado_ram_style : string, optional
        An optional Xilinx Vivado RAM style attribute to apply to this signal delcaration.
        If set, exactly one of: "block", "distributed", "registers", "ultra", "mixed" or "auto".
    quartus_ram_style : string, optional
        An optional Quartus Prime RAM style attribute to apply to this signal delcaration.
        If set, exactly one of: "M4K", "M9K", "M10K", "M20K", "M144K", "MLAB" or "logic".
    """
    # Spacing of VHDL signals declaration always with a single tab
    name_pad = name_pad or 0
    vhdl.write(f, 1, f'signal {name:<{name_pad}} : {type}', end='')
    if default_value is not None:
        vhdl.write(f, 0, f' := {default_value}', end='')
    vhdl.write(f, 0, ';')
    if vivado_ram_style is not None:
        vhdl.write_lines(
            f,
            [
                (1, f'attribute ram_style : string;'),
                (1, f'attribute ram_style of {name} : signal is "{vivado_ram_style}";'),
            ],
        )
    if quartus_ram_style is not None:
        vhdl.write_lines(
            f,
            [
                (1, f'attribute ramstyle : string;'),
                (1, f'attribute ramstyle of {name} : signal is "{quartus_ram_style}";'),
            ],
        )


def write_constant_decl(
    f: TextIOWrapper,
    name: str,
    type: str,
    value: Any,
    name_pad: Optional[int] = None,
    type_pad: Optional[int] = None,
):
    """
    Write a VHDL constant declaration with a name, a type and a value.

    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The TextIOWrapper object to write the constant declaration to.
    name : str
        Signal name.
    type : str
        Signal type.
    value : anything convertable to str
        Default value to the signal.
    name_pad : int, optional
        An optional left padding value applied to the name.
    """
    name_pad = 0 if name_pad is None else name_pad
    vhdl.write(f, 1, f'constant {name:<{name_pad}} : {type} := {str(value)};')


def write_type_decl(
    f: TextIOWrapper,
    name: str,
    alias: str,
):
    """
    Write a VHDL type declaration with a name tied to an alias.

    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The TextIOWrapper object to write the type declaration to.
    name : str
        Type name alias.
    alias : str
        The type to tie the new name to.
    """
    vhdl.write(f, 1, f'type {name} is {alias};')


def write_process_prologue(
    f: TextIOWrapper,
    sensitivity_list: str,
    indent: int = 1,
    name: Optional[str] = None,
):
    """
    Write only the prologue of a regular VHDL process with a user provided sensitivity list.
    This method should almost always guarantely be followed by a write_process_epilogue.

    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The TextIOWrapper object to write the type declaration to.
    sensitivity_list : str
        Content of the process sensitivity list.
    indent : int, default: 1
        Indentation level to use for this process.
    name : Optional[str]
        An optional name for the process.
    """
    if name is not None:
        vhdl.write(f, indent, f'{name}: process({sensitivity_list})')
    else:
        vhdl.write(f, indent, f'process({sensitivity_list})')
    vhdl.write(f, indent, f'begin')


def write_process_epilogue(
    f: TextIOWrapper,
    sensitivity_list: Optional[str] = None,
    indent: int = 1,
    name: Optional[str] = None,
):
    """
    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The TextIOWrapper object to write the type declaration to.
    sensitivity_list : str
        Content of the process sensitivity list. Not needed when writing the epligoue.
    indent : int, default: 1
        Indentation level to use for this process.
    indent : int, default: 1
        Indentation level to use for this process.
    name : Optional[str]
        An optional name of the ending process.
    """
    _ = sensitivity_list
    vhdl.write(f, indent, f'end process', end="")
    if name is not None:
        vhdl.write(f, 0, ' ' + name, end="")
    vhdl.write(f, 0, ';')


def write_synchronous_process_prologue(
    f: TextIOWrapper,
    clk: str,
    indent: int = 1,
    name: Optional[str] = None,
):
    """
    Write only the prologue of a regular VHDL synchronous process with a single clock object in the sensitivity list
    triggering a rising edge block by some body of VHDL code.
    This method should almost always guarantely be followed by a write_synchronous_process_epilogue.

    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The TextIOWrapper to write the VHDL code onto.
    clk : str
        Name of the clock.
    indent : int, default: 1
        Indentation level to use for this process.
    name : Optional[str]
        An optional name for the process.
    """
    write_process_prologue(f, sensitivity_list=clk, indent=indent, name=name)
    vhdl.write(f, indent + 1, f'if rising_edge(clk) then')


def write_synchronous_process_epilogue(
    f: TextIOWrapper,
    clk: Optional[str],
    indent: int = 1,
    name: Optional[str] = None,
):
    """
    Write only the epilogue of a regular VHDL synchronous process with a single clock object in the sensitivity list
    triggering a rising edge block by some body of VHDL code.
    This method should almost always guarantely be followed by a write_synchronous_process_epilogue.

    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The TextIOWrapper to write the VHDL code onto.
    clk : str
        Name of the clock.
    indent : int, default: 1
        Indentation level to use for this process.
    name : Optional[str]
        An optional name for the process
    """
    _ = clk
    vhdl.write(f, indent + 1, f'end if;')
    write_process_epilogue(f, sensitivity_list=clk, indent=indent, name=name)


def write_synchronous_process(
    f: TextIOWrapper,
    clk: str,
    body: str,
    indent: int = 1,
    name: Optional[str] = None,
):
    """
    Write a regular VHDL synchronous process with a single clock object in the sensitivity list triggering
    a rising edge block by some body of VHDL code.

    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The TextIOWrapper to write the VHDL code onto.
    clk : str
        Name of the clock.
    body : str
        Body of the `if rising_edge(clk) then` block.
    indent : int, default: 1
        Indentation level to use for this process.
    name : Optional[str]
        An optional name for the process
    """
    write_synchronous_process_prologue(f, clk, indent, name)
    for line in body.split('\n'):
        if len(line):
            vhdl.write(f, indent + 2, f'{line}')
    write_synchronous_process_epilogue(f, clk, indent, name)


def write_synchronous_memory(
    f: TextIOWrapper,
    clk: str,
    read_ports: Set[Tuple[str, str, str]],
    write_ports: Set[Tuple[str, str, str]],
    name: Optional[str] = None,
):
    """
    Infer a VHDL synchronous reads and writes.

    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The TextIOWrapper to write the VHDL code onto.
    clk : str
        Name of clock identifier to the synchronous memory.
    read_ports : Set[Tuple[str,str]]
        A set of strings used as identifiers for the read ports of the memory.
    write_ports : Set[Tuple[str,str,str]]
        A set of strings used as identifiers for the write ports of the memory.
    name : Optional[str]
        An optional name for the memory process.
    """
    assert len(read_ports) >= 1
    assert len(write_ports) >= 1
    write_synchronous_process_prologue(f, clk=clk, name=name)
    for read_name, address, re in read_ports:
        vhdl.write_lines(
            f,
            [
                (3, f'if {re} = \'1\' then'),
                (4, f'{read_name} <= memory({address});'),
                (3, f'end if;'),
            ],
        )
    for write_name, address, we in write_ports:
        vhdl.write_lines(
            f,
            [
                (3, f'if {we} = \'1\' then'),
                (4, f'memory({address}) <= {write_name};'),
                (3, f'end if;'),
            ],
        )
    write_synchronous_process_epilogue(f, clk=clk, name=name)


def write_asynchronous_read_memory(
    f: TextIOWrapper,
    clk: str,
    read_ports: Set[Tuple[str, str, str]],
    write_ports: Set[Tuple[str, str, str]],
    name: Optional[str] = None,
):
    """
    Infer a VHDL memory with synchronous writes and asynchronous reads.

    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The TextIOWrapper to write the VHDL code onto.
    clk : str
        Name of clock identifier to the synchronous memory.
    read_ports : Set[Tuple[str,str]]
        A set of strings used as identifiers for the read ports of the memory.
    write_ports : Set[Tuple[str,str,str]]
        A set of strings used as identifiers for the write ports of the memory.
    name : Optional[str]
        An optional name for the memory process.
    """
    assert len(read_ports) >= 1
    assert len(write_ports) >= 1
    write_synchronous_process_prologue(f, clk=clk, name=name)
    for write_name, address, we in write_ports:
        vhdl.write_lines(
            f,
            [
                (3, f'if {we} = \'1\' then'),
                (4, f'memory({address}) <= {write_name};'),
                (3, f'end if;'),
            ],
        )
    write_synchronous_process_epilogue(f, clk=clk, name=name)
    for read_name, address, _ in read_ports:
        vhdl.write(f, 1, f'{read_name} <= memory({address});')