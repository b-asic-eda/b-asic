"""
Test helpers.
"""

import os

import pytest


def cocotb_test(*cocotb_args, **cocotb_kwargs):
    """Decorate with cocotb.test if available, else skips the test."""
    try:
        from cocotb import test  # noqa: PLC0415

        # Return the real decorator if available
        return test(*cocotb_args, **cocotb_kwargs)
    except ImportError:
        # Return a decorator that skips the test
        def skip_decorator(func):
            return pytest.mark.skip(reason="cocotb is not available")(func)

        return skip_decorator


def get_runner():
    try:
        from cocotb_tools.runner import get_runner  # noqa: PLC0415

        sim = os.getenv("SIM", "ghdl")
        runner = get_runner(sim)

        # Return the real decorator if available
    except ImportError:
        pytest.skip("cocotb is not available")
    except ValueError as e:
        pytest.skip(f"{e}")
    except SystemExit as e:
        pytest.skip(f"{e}")
    return runner
