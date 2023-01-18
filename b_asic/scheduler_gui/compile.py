#!/usr/bin/env python3
"""
B-ASIC Scheduler-gui Resource and Form Compiler Module.

Compiles Qt5 resource and form files. Requires PySide2 or PyQt5 to be installed.
If no arguments is given, the compiler search for and compiles all form (.ui)
files.
"""

from qtpy import uic
import sys
import os
import shutil
import subprocess
import argparse
from setuptools_scm import get_version

try:
    import b_asic.scheduler_gui.logger as logger

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
        if not os.path.exists(filename):
            raise FileNotFoundError(filename)


def _check_qt_version() -> None:
    """
    Check if PySide2 or PyQt5 is installed, otherwise raise AssertionError
    exception.
    """
    assert uic.PYSIDE2 or uic.PYQT5, "PySide2 or PyQt5 need to be installed"


def replace_qt_bindings(filename: str) -> None:
    """Raplaces qt-binding api in 'filename' from PySide2/PyQt5 to qtpy."""
    with open(f"{filename}", "r") as file:
        filedata = file.read()
        filedata = filedata.replace("from PyQt5", "from qtpy")
        filedata = filedata.replace("from PySide2", "from qtpy")
    with open(f"{filename}", "w") as file:
        file.write(filedata)


def compile_rc(*filenames: str) -> None:
    """
    Compile resource file(s) given by 'filenames'. If no arguments are given,
    the compiler will search for resource (.qrc) files and compile accordingly.
    """
    _check_qt_version()

    def compile(filename: str = None) -> None:
        outfile = f"{os.path.splitext(filename)[0]}_rc.py"
        rcc = shutil.which("pyside2-rcc")
        args = f"-g python -o {outfile} {filename}"

        if rcc is None:
            rcc = shutil.which("rcc")
        if rcc is None:
            rcc = shutil.which("pyrcc5")
            args = f"-o {outfile} {filename}"
        assert rcc, "PySide2 compiler failed, can't find rcc"

        os_ = sys.platform
        if os_.startswith("linux"):  # Linux
            cmd = f"{rcc} {args}"
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
                log.error(f"{os_} RC compiler not supported")
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
            compile(filename)

    else:
        _check_filenames(*filenames)
        for filename in filenames:
            compile(filename)


def compile_ui(*filenames: str) -> None:
    """
    Compile form file(s) given by 'filenames'. If no arguments are given, the
    compiler will search for form (.ui) files and compile accordingly.
    """
    _check_qt_version()

    def compile(filename: str) -> None:
        dir, file = os.path.split(filename)
        file = os.path.splitext(file)[0]
        dir = dir if dir else "."
        outfile = f"{dir}/ui_{file}.py"

        if uic.PYSIDE2:
            uic_ = shutil.which("pyside2-uic")
            args = f"-g python -o {outfile} {filename}"

            if uic_ is None:
                uic_ = shutil.which("uic")
            if uic_ is None:
                uic_ = shutil.which("pyuic5")
                args = f"-o {outfile} {filename}"
            assert uic_, "PySide2 compiler failed, can't find uic"

            os_ = sys.platform
            if os_.startswith("linux"):  # Linux
                cmd = f"{uic_} {args}"
                subprocess.call(cmd.split())

            elif os_.startswith("win32"):  # Windows
                # TODO: implement
                log.error("Windows UI compiler not implemented")
                raise NotImplementedError

            elif os_.startswith("darwin"):  # macOS
                # TODO: implement
                log.error("macOS UI compiler not implemented")
                raise NotImplementedError

            else:  # other OS
                log.error(f"{os_} UI compiler not supported")
                raise NotImplementedError

        else:  # uic.PYQT5
            from qtpy.uic import compileUi

            with open(outfile, "w") as ofile:
                compileUi(filename, ofile)

        replace_qt_bindings(outfile)  # replace qt-bindings with qtpy

    if not filenames:
        ui_files = [
            os.path.join(root, name)
            for root, _, files in os.walk(".")
            for name in files
            if name.endswith(".ui")
        ]
        for filename in ui_files:
            compile(filename)
    else:
        _check_filenames(*filenames)
        for filename in filenames:
            compile(filename)


def compile_all():
    """
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

    if sys.version_info >= (3, 8):
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
    else:
        parser.add_argument(
            "--ui", metavar="<file>", action="append", help="compile form file"
        )
        parser.add_argument(
            "--rc",
            metavar="<file>",
            action="append",
            help="compile resource file",
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
