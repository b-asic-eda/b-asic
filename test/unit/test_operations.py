"""Tests for the built-in operations module."""

from inspect import isclass

from b_asic import (
    core_operations,
    fft_operations,
    operations,
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

    assert set(operations.__all__) == set(builtin_operations)
    for name, operation in builtin_operations.items():
        assert getattr(operations, name) is operation
