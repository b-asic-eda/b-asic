"""Tests for the built-in ops module."""

from inspect import isclass

from b_asic import (
    core_operations,
    fft_operations,
    ops,
    special_operations,
    utility_operations,
    wdf_operations,
)
from b_asic.operation import Operation


def test_module_exports_all_builtin_operations():
    modules = (
        core_operations,
        fft_operations,
        special_operations,
        utility_operations,
        wdf_operations,
    )
    builtin_operations = {
        name: value
        for module in modules
        for name, value in vars(module).items()
        if isclass(value)
        and value.__module__ == module.__name__
        and issubclass(value, Operation)
    }

    assert set(ops.__all__) == set(builtin_operations)
    for name, operation in builtin_operations.items():
        assert getattr(ops, name) is operation
