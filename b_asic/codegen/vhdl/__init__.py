"""
Module for basic VHDL code generation.
"""

from typing import List, Optional, TextIO, Tuple, Union

# VHDL code generation tab length
VHDL_TAB = r"    "


def write(
    f: TextIO,
    indent_level: int,
    text: str,
    *,
    end: str = "\n",
    start: Optional[str] = None,
):
    """
    Base VHDL code generation utility.

    ``f'{VHDL_TAB*indent_level}'`` is first written to the TextIO
    object *f*. Immediately after the indentation, *text* is written to *f*. Finally,
    *text* is also written to *f*.

    Parameters
    ----------
    f : TextIO
        The file object to emit VHDL code to.
    indent_level : int
        Indentation level to use. Exactly ``f'{VHDL_TAB*indent_level}`` is written
        before the text is written.
    text : str
        The text to write to.
    end : str, default: '\n'
        Text to write exactly after *text* is written to *f*.
    start : str, optional
        Text to write before both indentation and *text*.
    """
    if start is not None:
        f.write(start)
    f.write(f"{VHDL_TAB * indent_level}{text}{end}")


def write_lines(f: TextIO, lines: List[Union[Tuple[int, str], Tuple[int, str, str]]]):
    """
    Multiline VHDL code generation utility.

    Each tuple ``(int, str, [int])`` in the list *lines* is written to the
    TextIO object *f* using the :function:`vhdl.write` function.

    Parameters
    ----------
    f : TextIO
        The file object to emit VHDL code to.
    lines : list of tuple (int,str) [1], or list of tuple (int,str,str) [2]
        [1]: The first ``int`` of the tuple is used as indentation level for the line
             and the second ``str`` of the tuple is the content of the line.
        [2]: Same as [1], but the third ``str`` of the tuple is passed to parameter
             *end* when calling :function:`vhdl.write`.
    """
    for tpl in lines:
        if len(tpl) == 2:
            write(f, indent_level=tpl[0], text=str(tpl[1]))
        elif len(tpl) == 3:
            write(f, indent_level=tpl[0], text=str(tpl[1]), end=str(tpl[2]))
        else:
            raise ValueError("All tuples in list `lines` must have length 2 or 3")
