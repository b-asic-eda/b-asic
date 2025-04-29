#!/usr/bin/env python3
"""
B-ASIC Logger Module.

Contains a logger that logs to the console and a file using levels. It is based
on the :mod:`logging` module and has predefined levels of logging.

Usage:
------

    >>> import b_asic.logger as logger
    >>> log = logger.getLogger()
    >>> log.info('This is a log post with level INFO')

.. list-table::
   :widths: 50 25 25
   :header-rows: 1

   * - Function call
     - Level
     - Numeric value
   * - debug(str)
     - DEBUG
     - 10
   * - info(str)
     - INFO
     - 20
   * - warning(str)
     - WARNING
     - 30
   * - error(str)
     - ERROR
     - 40
   * - critical(str)
     - CRITICAL
     - 50
   * - exception(str)
     - ERROR
     - 40

The last `exception(str)` is used to capture exceptions output, that normally
will not be captured.
See https://docs.python.org/3/howto/logging.html for more information.

Log Uncaught Exceptions:
------------------------
To log uncaught exceptions, implement the following in your program.
  `sys.excepthook = logger.log_exceptions`"""

import logging
import os
import sys
from logging import Logger
from types import TracebackType
from typing import Literal


def getLogger(
    console_log_level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "WARNING",
    filename: str | None = "",
) -> Logger:
    """
    Create console- and filehandler and from those, create a logger object.

    Parameters
    ----------
    console_log_level : str, optional
        The minimum level that the logger will log. Defaults to 'WARNING'.
    filename : str, optional
        Name of output logfile. Defaults to "".

    Returns
    -------
    Logger : 'logging.Logger' object.
    """
    logger = logging.getLogger(__name__)

    logger.setLevel(console_log_level)

    # set up the console logger
    c_fmt_date = "%T"
    c_fmt = (
        "[%(process)d] %(asctime)s %(filename)18s:%(lineno)-4s"
        " %(funcName)20s() %(levelname)-8s: %(message)s"
    )
    c_formatter = logging.Formatter(c_fmt, c_fmt_date)
    c_handler = logging.StreamHandler()
    c_handler.setFormatter(c_formatter)
    c_handler.setLevel(console_log_level)
    logger.addHandler(c_handler)

    # setup the file logger
    f_fmt_date = "%Y-%m-%dT%T%Z"
    f_fmt = (
        "%(asctime)s %(filename)18s:%(lineno)-4s %(funcName)20s()"
        " %(levelname)-8s: %(message)s"
    )

    if filename:
        f_formatter = logging.Formatter(f_fmt, f_fmt_date)
        f_handler = logging.FileHandler(filename, mode="w")
        f_handler.setFormatter(f_formatter)
        f_handler.setLevel(logging.DEBUG)
        logger.addHandler(f_handler)

    if logger.name == "scheduler-gui.log":
        logger.info(
            "Running: %s %s",
            os.path.basename(sys.argv[0]),
            " ".join(sys.argv[1:]),
        )

    return logger


def handle_exceptions(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    """
    Helper function to log uncaught exceptions.

    Install with: `sys.excepthook = <module>.handle_exceptions`
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.exception(
        "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
    )
