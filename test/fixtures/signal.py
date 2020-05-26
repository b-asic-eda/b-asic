import pytest

from b_asic import Signal


@pytest.fixture
def signal():
    """Return a signal with no connections."""
    return Signal()

@pytest.fixture
def signals():
    """Return 3 signals with no connections."""
    return [Signal() for _ in range(0, 3)]
