"""
Module for basic VHDL code generation.
"""

from io import TextIOWrapper

# VHDL code generation tab length
VHDL_TAB = r"    "


def write(
    f: TextIOWrapper,
    indent_level: int,
    text: str,
    end: str = '\n',
):
    """
    Base VHDL code generation utility. `f'{VHDL_TAB*indent_level}'` is first written to the :class:`io.TextIOWrapper`
    object `f`. Immediatly after the indentation, `text` is written to `f`. Finally, `text` is also written to `f`.

    Parameters
    ----------
    f : :class:`io.TextIOWrapper`
        The file object to emit the VHDL code to.
    indent_level : int
        Indentation level to use. Exactly `f'{VHDL_TAB*indent_level}` is written before the text is written.
    text : str
        The text to write to.
    end : str, default: '\n'
        Text to write exactly after `text` is written to `f`.
    """
    f.write(f'{VHDL_TAB*indent_level}{text}{end}')


from b_asic.codegen.vhdl import architecture, common, entity
