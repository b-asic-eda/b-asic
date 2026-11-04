"""
B-ASIC Operations Module.

Contains built-in operations for constructing SFGs.
"""

from inspect import isclass as _isclass
from typing import TYPE_CHECKING as _TYPE_CHECKING

from b_asic import core_operations as _core_operations
from b_asic import fft_operations as _fft_operations
from b_asic import special_operations as _special_operations
from b_asic import utility_operations as _utility_operations
from b_asic import wdf_operations as _wdf_operations
from b_asic.operation import Operation as _Operation

if _TYPE_CHECKING:
    from b_asic.core_operations import *  # noqa: F403
    from b_asic.fft_operations import *  # noqa: F403
    from b_asic.special_operations import *  # noqa: F403
    from b_asic.utility_operations import *  # noqa: F403
    from b_asic.wdf_operations import *  # noqa: F403

_operations = {
    name: value
    for module in (
        _core_operations,
        _fft_operations,
        _special_operations,
        _utility_operations,
        _wdf_operations,
    )
    for name, value in vars(module).items()
    if _isclass(value)
    and value.__module__ == module.__name__
    and issubclass(value, _Operation)
}

globals().update(_operations)
__all__: list[str] = []
__all__.extend(sorted(_operations))
