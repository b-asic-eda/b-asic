#!/usr/bin/env python3
"""
B-ASIC Scheduler-gui Logger Module.

Contains a logger that logs to the console and a file using levels. It is based
on the :mod:`logging` module and has predefined levels of logging.

Usage:
------

    >>> import b_asic.scheduler_gui.logger as logger
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
import logging.handlers
import os
import sys
from logging import Logger
from types import TracebackType
from typing import Type, Union


def getLogger(filename: str = "scheduler-gui.log", loglevel: str = "INFO") -> Logger:
    """
    This function creates console- and filehandler and from those, creates a logger
    object.

    Parameters
    ----------
    filename : str optional
        Output filename. Defaults to 'scheduler-gui.log'.
    loglevel : str, optional
        The minimum level that the logger will log. Defaults to 'INFO'.

    Returns
    -------
    Logger : 'logging.Logger' object.
    """

    # logger = logging.getLogger(name)
    # logger = logging.getLogger('root')
    logger = logging.getLogger()

    # if logger 'name' already exists, return it to avoid logging duplicate
    # messages by attaching multiple handlers of the same type
    if logger.handlers:
        return logger
    # if logger 'name' does not already exist, create it and attach handlers
    else:
        # set logLevel to loglevel or to INFO if requested level is incorrect
        loglevel = getattr(logging, loglevel.upper(), logging.INFO)
        logger.setLevel(loglevel)

        # set up the console logger
        c_fmt_date = "%T"
        c_fmt = (
            "[%(process)d] %(asctime)s %(filename)18s:%(lineno)-4s"
            " %(funcName)20s() %(levelname)-8s: %(message)s"
        )
        c_formatter = logging.Formatter(c_fmt, c_fmt_date)
        c_handler = logging.StreamHandler()
        c_handler.setFormatter(c_formatter)
        c_handler.setLevel(logging.WARNING)
        logger.addHandler(c_handler)

        # setup the file logger
        f_fmt_date = "%Y-%m-%dT%T%Z"
        f_fmt = (
            "%(asctime)s %(filename)18s:%(lineno)-4s %(funcName)20s()"
            " %(levelname)-8s: %(message)s"
        )
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


# log uncaught exceptions
def handle_exceptions(
    exc_type: Type[BaseException],
    exc_value: BaseException,
    exc_traceback: Union[TracebackType, None],
) -> None:
    # def log_exceptions(type, value, tb):
    """This function is a helper function to log uncaught exceptions. Install with:
    `sys.excepthook = <module>.handle_exceptions`"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.exception(
        "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
    )


# def qt_message_handler(mode, context, message):
#     if mode == QtCore.QtInfoMsg:
#         mode = 'INFO'
#     elif mode == QtCore.QtWarningMsg:
#         mode = 'WARNING'
#     elif mode == QtCore.QtCriticalMsg:
#         mode = 'CRITICAL'
#     # elif mode == QtCore.QtErrorMsg:
#     #     mode = 'ERROR'
#     elif mode == QtCore.QtFatalMsg:
#         mode = 'FATAL'
#     else:
#         mode = 'DEBUG'
#     print('qt_message_handler: line: %d, func: %s(), file: %s' % (
#           context.line, context.function, context.file))
#     print('  %s: %s\n' % (mode, message))
