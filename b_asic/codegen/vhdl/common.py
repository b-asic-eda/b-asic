"""
Generation of common VHDL constructs
"""

import re
from datetime import datetime
from subprocess import PIPE, Popen
from typing import Any, Optional, Set, TextIO, Tuple

from b_asic.codegen.vhdl import write, write_lines


def b_asic_preamble(f: TextIO):
    """
    Write a standard BASIC VHDL preamble comment.

    Parameters
    ----------
    f : TextIO
        The file object to write the header to.
    """
    # Try to acquire the current git commit hash
    git_commit_id = None
    try:
        process = Popen(['git', 'rev-parse', '--short', 'HEAD'], stdout=PIPE)
        git_commit_id = process.communicate()[0].decode('utf-8').strip()
    except:  # noqa: E722
        pass
    write_lines(
        f,
        [
            (0, '--'),
            (0, '-- This code was automatically generated by the B-ASIC toolbox.'),
            (0, f'-- Code generation timestamp: ({datetime.now()})'),
        ],
    )
    if git_commit_id:
        write(f, 0, f'-- B-ASIC short commit hash: {git_commit_id}')
    write_lines(
        f,
        [
            (0, '-- URL: https://gitlab.liu.se/da/B-ASIC'),
            (0, '--', '\n\n'),
        ],
    )


def ieee_header(
    f: TextIO,
    std_logic_1164: bool = True,
    numeric_std: bool = True,
):
    """
    Write the standard IEEE VHDL use header with includes of std_logic_1164 and
    numeric_std.

    Parameters
    ----------
    f : TextIO
        The TextIO object to write the IEEE header to.
    std_logic_1164 : bool, default: True
        Include the std_logic_1164 header.
    numeric_std : bool, default: True
        Include the numeric_std header.
    """
    write(f, 0, 'library ieee;')
    if std_logic_1164:
        write(f, 0, 'use ieee.std_logic_1164.all;')
    if numeric_std:
        write(f, 0, 'use ieee.numeric_std.all;')
    write(f, 0, '')


def signal_declaration(
    f: TextIO,
    name: str,
    signal_type: str,
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
    f : TextIO
        The TextIO object to write the IEEE header to.
    name : str
        Signal name.
    signal_type : str
        Signal type.
    default_value : string, optional
        An optional default value to the signal.
    name_pad : int, optional
        An optional left padding value applied to the name.
    vivado_ram_style : string, optional
        An optional Xilinx Vivado RAM style attribute to apply to this signal
        declaration. If set, exactly one of: "block", "distributed", "registers",
        "ultra", "mixed" or "auto".
    quartus_ram_style : string, optional
        An optional Quartus Prime RAM style attribute to apply to this signal
        declaration. If set, exactly one of: "M4K", "M9K", "M10K", "M20K", "M144K",
        "MLAB" or "logic".
    """
    # Spacing of VHDL signals declaration always with a single tab
    name_pad = name_pad or 0
    write(f, 1, f'signal {name:<{name_pad}} : {signal_type}', end='')
    if default_value is not None:
        write(f, 0, f' := {default_value}', end='')
    write(f, 0, ';')
    if vivado_ram_style is not None:
        write_lines(
            f,
            [
                (1, 'attribute ram_style : string;'),
                (1, f'attribute ram_style of {name} : signal is "{vivado_ram_style}";'),
            ],
        )
    if quartus_ram_style is not None:
        write_lines(
            f,
            [
                (1, 'attribute ramstyle : string;'),
                (1, f'attribute ramstyle of {name} : signal is "{quartus_ram_style}";'),
            ],
        )


def constant_declaration(
    f: TextIO,
    name: str,
    signal_type: str,
    value: Any,
    name_pad: Optional[int] = None,
    type_pad: Optional[int] = None,
):
    """
    Write a VHDL constant declaration with a name, a type and a value.

    Parameters
    ----------
    f : TextIO
        The TextIO object to write the constant declaration to.
    name : str
        Signal name.
    signal_type : str
        Signal type.
    value : anything convertable to str
        Default value to the signal.
    name_pad : int, optional
        An optional left padding value applied to the name.
    """
    name_pad = 0 if name_pad is None else name_pad
    write(f, 1, f'constant {name:<{name_pad}} : {signal_type} := {str(value)};')


def type_declaration(
    f: TextIO,
    name: str,
    alias: str,
):
    """
    Write a VHDL type declaration with a name tied to an alias.

    Parameters
    ----------
    f : TextIO
        The TextIO object to write the type declaration to.
    name : str
        Type name alias.
    alias : str
        The type to tie the new name to.
    """
    write(f, 1, f'type {name} is {alias};')


def process_prologue(
    f: TextIO,
    sensitivity_list: str,
    indent: int = 1,
    name: Optional[str] = None,
):
    """
    Write the prologue of a regular VHDL process with a user provided sensitivity list.

    This method should almost always be followed by a :func:`process_epilogue`.

    Parameters
    ----------
    f : TextIO
        The TextIO object to write the type declaration to.
    sensitivity_list : str
        Content of the process sensitivity list.
    indent : int, default: 1
        Indentation level to use for this process.
    name : Optional[str]
        An optional name for the process.
    """
    if name is not None:
        write(f, indent, f'{name}: process({sensitivity_list})')
    else:
        write(f, indent, f'process({sensitivity_list})')
    write(f, indent, 'begin')


def process_epilogue(
    f: TextIO,
    sensitivity_list: Optional[str] = None,
    indent: int = 1,
    name: Optional[str] = None,
):
    """
    Parameters
    ----------
    f : TextIO
        The TextIO object to write the type declaration to.
    sensitivity_list : str
        Content of the process sensitivity list. Not needed when writing the epilogue.
    indent : int, default: 1
        Indentation level to use for this process.
    indent : int, default: 1
        Indentation level to use for this process.
    name : Optional[str]
        An optional name of the ending process.
    """
    _ = sensitivity_list
    write(f, indent, 'end process', end="")
    if name is not None:
        write(f, 0, ' ' + name, end="")
    write(f, 0, ';')


def synchronous_process_prologue(
    f: TextIO,
    clk: str,
    indent: int = 1,
    name: Optional[str] = None,
):
    """
    Write the prologue of a regular VHDL synchronous process with a single clock object.

    The clock is the only item in the sensitivity list and is triggering a rising edge
    block by some body of VHDL code.

    This method is almost always followed by a :func:`synchronous_process_epilogue`.

    Parameters
    ----------
    f : TextIO
        The TextIO to write the VHDL code onto.
    clk : str
        Name of the clock.
    indent : int, default: 1
        Indentation level to use for this process.
    name : Optional[str]
        An optional name for the process.
    """
    process_prologue(f, sensitivity_list=clk, indent=indent, name=name)
    write(f, indent + 1, 'if rising_edge(clk) then')


def synchronous_process_epilogue(
    f: TextIO,
    clk: Optional[str],
    indent: int = 1,
    name: Optional[str] = None,
):
    """
    Write only the epilogue of a regular VHDL synchronous process with a single clock.

    The clock is the only item in the sensitivity list and is triggering a rising edge
    block by some body of VHDL code.

    Parameters
    ----------
    f : TextIO
        The TextIO to write the VHDL code onto.
    clk : str
        Name of the clock.
    indent : int, default: 1
        Indentation level to use for this process.
    name : Optional[str]
        An optional name for the process
    """
    _ = clk
    write(f, indent + 1, 'end if;')
    process_epilogue(f, sensitivity_list=clk, indent=indent, name=name)


def synchronous_process(
    f: TextIO,
    clk: str,
    body: str,
    indent: int = 1,
    name: Optional[str] = None,
):
    """
    Write a regular VHDL synchronous process with a single clock.

    The clock is the only item in the sensitivity list and is triggering a rising edge
    block by some body of VHDL code.

    Parameters
    ----------
    f : TextIO
        The TextIO to write the VHDL code onto.
    clk : str
        Name of the clock.
    body : str
        Body of the `if rising_edge(clk) then` block.
    indent : int, default: 1
        Indentation level to use for this process.
    name : Optional[str]
        An optional name for the process
    """
    synchronous_process_prologue(f, clk, indent, name)
    for line in body.split('\n'):
        if len(line):
            write(f, indent + 2, f'{line}')
    synchronous_process_epilogue(f, clk, indent, name)


def synchronous_memory(
    f: TextIO,
    clk: str,
    read_ports: Set[Tuple[str, str, str]],
    write_ports: Set[Tuple[str, str, str]],
    name: Optional[str] = None,
):
    """
    Infer a VHDL synchronous reads and writes.

    Parameters
    ----------
    f : TextIO
        The TextIO to write the VHDL code onto.
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
    synchronous_process_prologue(f, clk=clk, name=name)
    for read_name, address, read_enable in read_ports:
        write_lines(
            f,
            [
                (3, f'if {read_enable} = \'1\' then'),
                (4, f'{read_name} <= memory({address});'),
                (3, 'end if;'),
            ],
        )
    for write_name, address, we in write_ports:
        write_lines(
            f,
            [
                (3, f'if {we} = \'1\' then'),
                (4, f'memory({address}) <= {write_name};'),
                (3, 'end if;'),
            ],
        )
    synchronous_process_epilogue(f, clk=clk, name=name)


def asynchronous_read_memory(
    f: TextIO,
    clk: str,
    read_ports: Set[Tuple[str, str, str]],
    write_ports: Set[Tuple[str, str, str]],
    name: Optional[str] = None,
):
    """
    Infer a VHDL memory with synchronous writes and asynchronous reads.

    Parameters
    ----------
    f : TextIO
        The TextIO to write the VHDL code onto.
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
    synchronous_process_prologue(f, clk=clk, name=name)
    for write_name, address, we in write_ports:
        write_lines(
            f,
            [
                (3, f'if {we} = \'1\' then'),
                (4, f'memory({address}) <= {write_name};'),
                (3, 'end if;'),
            ],
        )
    synchronous_process_epilogue(f, clk=clk, name=name)
    for read_name, address, _ in read_ports:
        write(f, 1, f'{read_name} <= memory({address});')


def is_valid_vhdl_identifier(identifier: str) -> bool:
    """
    Test if identifier is a valid VHDL identifier, as specified by VHDL 2019.

    An identifier is a valid VHDL identifier if it is not a VHDL reserved keyword and
    it is a valid basic identifier as specified by IEEE STD 1076-2019 (VHDL standard).

    Parameters
    ----------
    identifier : str
        The identifier to test.

    Returns
    -------
    Returns True if identifier is a valid VHDL identifier, False otherwise.
    """
    # IEEE STD 1076-2019:
    # Sec. 15.4.2, Basic identifiers:
    # * A basic identifier consists only of letters, digits, and underlines.
    # * A basic identifier is not a reserved VHDL keyword
    is_basic_identifier = (
        re.fullmatch(pattern=r'[a-zA-Z][0-9a-zA-Z_]*', string=identifier) is not None
    )
    return is_basic_identifier and not is_vhdl_reserved_keyword(identifier)


def is_vhdl_reserved_keyword(identifier: str) -> bool:
    """
    Test if identifier is a reserved VHDL keyword.

    Parameters
    ----------
    identifier : str
        The identifier to test.

    Returns
    -------
    Returns True if identifier is reserved, False otherwise.
    """
    # List of reserved keyword in IEEE STD 1076-2019.
    # Sec. 15.10, Reserved words:
    reserved_keywords = (
        "abs",
        "access",
        "after",
        "alias",
        "all",
        "and",
        "architecture",
        "array",
        "assert",
        "assume",
        "attribute",
        "begin",
        "block",
        "body",
        "buffer",
        "bus",
        "case",
        "component",
        "configuration",
        "constant",
        "context",
        "cover",
        "default",
        "disconnect",
        "downto",
        "else",
        "elsif",
        "end",
        "entity",
        "exit",
        "fairness",
        "file",
        "for",
        "force",
        "function",
        "generate",
        "generic",
        "group",
        "guarded",
        "if",
        "impure",
        "in",
        "inertial",
        "inout",
        "is",
        "label",
        "library",
        "linkage",
        "literal",
        "loop",
        "map",
        "mod",
        "nand",
        "new",
        "next",
        "nor",
        "not",
        "null",
        "of",
        "on",
        "open",
        "or",
        "others",
        "out",
        "package",
        "parameter",
        "port",
        "postponed",
        "procedure",
        "process",
        "property",
        "protected",
        "private",
        "pure",
        "range",
        "record",
        "register",
        "reject",
        "release",
        "rem",
        "report",
        "restrict",
        "return",
        "rol",
        "ror",
        "select",
        "sequence",
        "severity",
        "signal",
        "shared",
        "sla",
        "sll",
        "sra",
        "srl",
        "strong",
        "subtype",
        "then",
        "to",
        "transport",
        "type",
        "unaffected",
        "units",
        "until",
        "use",
        "variable",
        "view",
        "vpkg",
        "vmode",
        "vprop",
        "vunit",
        "wait",
        "when",
        "while",
        "with",
        "xnor",
        "xor",
    )
    return identifier.lower() in reserved_keywords
