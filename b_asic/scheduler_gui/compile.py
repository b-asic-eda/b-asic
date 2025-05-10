#!/usr/bin/env python3
"""
B-ASIC Scheduler-gui Resource and Form Compiler Module.

Compile Qt6 resource and form files. Requires PySide6 or PyQt6 to be installed.
If no arguments is given, the compiler search for and compiles all form (.ui)
files.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from qtpy import uic
from setuptools_scm import get_version

try:
    from b_asic import logger

    log = logger.getLogger()
    sys.excepthook = logger.handle_exceptions
except ModuleNotFoundError:
    log = None


def _check_filenames(*filenames: str) -> None:
    """
    Check if the filename(s) exist, otherwise raise FileNotFoundError
    exception.
    """
    for filename in filenames:
        Path(filename).resolve(strict=True)


def _check_qt_version() -> None:
    """
    Check if PySide6 or PyQt6 is installed.

    Otherwise, raise AssertionError exception.
    """
    assert uic.PYSIDE6 or uic.PYQT6, "Python QT bindings must be installed"


def replace_qt_bindings(filename: str) -> None:
    """
    Replace qt-binding API in *filename* from PySide6 or PyQt6 to qtpy.

    Parameters
    ----------
    filename : str
        The name of the file to replace bindings in.
    """
    with Path(filename).open() as file:
        filedata = file.read()
        filedata = filedata.replace("from PyQt6", "from qtpy")
        filedata = filedata.replace("from PySide6", "from qtpy")
    with Path(filename).open("w") as file:
        file.write(filedata)


def compile_rc(*filenames: str) -> None:
    """
    Compile resource file(s) given by *filenames*.

    If no arguments are given, the compiler will search for resource (.qrc) files and
    compile accordingly.

    Parameters
    ----------
    *filenames : str
        One or more file names.
    """
    _check_qt_version()

    def _compile(filename: str) -> None:
        outfile = f"{os.path.splitext(filename)[0]}_rc.py"
        rcc = shutil.which("pyside2-rcc")
        arguments = f"-g python -o {outfile} {filename}"

        if rcc is None:
            rcc = shutil.which("rcc")
        if rcc is None:
            rcc = shutil.which("pyrcc5")
            arguments = f"-o {outfile} {filename}"
        assert rcc, (
            "Qt Resource compiler failed, cannot find pyside2-rcc, rcc, or pyrcc5"
        )

        os_ = sys.platform
        if os_.startswith("linux"):  # Linux
            cmd = f"{rcc} {arguments}"
            subprocess.call(cmd.split())

        elif os_.startswith("win32"):  # Windows
            # TODO: implement
            if log is not None:
                log.error("Windows RC compiler not implemented")
            else:
                print("Windows RC compiler not implemented")
            raise NotImplementedError

        elif os_.startswith("darwin"):  # macOS
            # TODO: implement
            if log is not None:
                log.error("macOS RC compiler not implemented")
            else:
                print("macOS RC compiler not implemented")
            raise NotImplementedError

        else:  # other OS
            if log is not None:
                log.error("%s RC compiler not supported", os_)
            else:
                print(f"{os_} RC compiler not supported")
            raise NotImplementedError

        replace_qt_bindings(outfile)  # replace qt-bindings with qtpy

    if not filenames:
        rc_files = [
            os.path.join(root, name)
            for root, _, files in os.walk(".")
            for name in files
            if name.endswith(".qrc")
        ]

        for filename in rc_files:
            _compile(filename)

    else:
        _check_filenames(*filenames)
        for filename in filenames:
            _compile(filename)


def compile_ui(*filenames: str) -> None:
    """
    Compile form file(s) given by *filenames*.

    If no arguments are given, the compiler will search for form (.ui) files and
    compile accordingly.

    Parameters
    ----------
    *filenames : str
        One or more file names.
    """
    _check_qt_version()

    def _compile(filename: str) -> None:
        directory, file = os.path.split(filename)
        file = os.path.splitext(file)[0]
        directory = directory if directory else "."
        outfile = f"{directory}/ui_{file}.py"

        if uic.PYQT6:
            from qtpy.uic import compileUi

            with Path(outfile).open("w") as ofile:
                compileUi(filename, ofile)

        elif uic.PYSIDE6:
            uic_ = shutil.which("pyside6-uic")
            arguments = f"-g python -o {outfile} {filename}"

            if uic_ is None:
                uic_ = shutil.which("uic")
            if uic_ is None:
                uic_ = shutil.which("pyuic6")
                arguments = f"-o {outfile} {filename}"
            assert uic_, (
                "Qt User Interface Compiler failed, cannot find pyside6-uic,"
                " uic, or pyuic6"
            )

            os_ = sys.platform
            if os_.startswith("linux") or os_.startswith("win32"):
                cmd = f"{uic_} {arguments}"
                subprocess.call(cmd.split())

            elif os_.startswith("darwin"):  # macOS
                # TODO: implement
                log.error("macOS UI compiler not implemented")
                raise NotImplementedError

            else:
                log.error("%s UI compiler not supported", os_)
                raise NotImplementedError

        replace_qt_bindings(outfile)  # replace qt-bindings with qtpy

    if not filenames:
        ui_files = [
            os.path.join(root, name)
            for root, _, files in os.walk(".")
            for name in files
            if name.endswith(".ui")
        ]
        for filename in ui_files:
            _compile(filename)
    else:
        _check_filenames(*filenames)
        for filename in filenames:
            _compile(filename)


def compile_all() -> None:
    """
    Compile all .qrc and .ui files.

    The compiler will search for resource (.qrc) files and form (.ui) files
    and compile accordingly.
    """
    compile_rc()
    compile_ui()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=f"{__doc__}", formatter_class=argparse.RawTextHelpFormatter
    )

    version = get_version(root="../..", relative_to=__file__)

    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s v{version}"
    )

    parser.add_argument(
        "--ui",
        metavar="<file>",
        action="extend",
        nargs="*",
        help=(
            "compile form file(s) if <file> is given, otherwise search\n"
            "for all form (*.ui) files and compile them all (default)"
        ),
    )
    parser.add_argument(
        "--rc",
        metavar="<file>",
        action="extend",
        nargs="*",
        help=(
            "compile resource file(s) if <file> is given, otherwise\n"
            "search for all resource (*.ui) files and compile them all"
        ),
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="search and compile all resource and form file(s)",
    )

    if len(sys.argv) == 1:
        compile_ui()

    args = parser.parse_args()

    if args.ui is not None:
        compile_ui(*args.ui)
    if args.rc is not None:
        compile_rc(*args.rc)
    if args.all:
        compile_all()
