"""
Test helpers.
"""

import pytest


def cocotb_test(*cocotb_args, **cocotb_kwargs):
    """Decorate with cocotb.test if available, else skips the test."""
    try:
        import cocotb  # noqa: PLC0415

        # Return the real decorator if available
        return cocotb.test(*cocotb_args, **cocotb_kwargs)
    except ImportError:
        # Return a decorator that skips the test
        def skip_decorator(func):
            return pytest.mark.skip(reason="cocotb is not available")(func)

        return skip_decorator
