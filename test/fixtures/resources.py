import pytest

from b_asic.process import PlainMemoryVariable
from b_asic.resources import ProcessCollection


@pytest.fixture()
def simple_collection():
    NO_PORT = 0
    return ProcessCollection(
        {
            PlainMemoryVariable(4, NO_PORT, {NO_PORT: 2}),
            PlainMemoryVariable(2, NO_PORT, {NO_PORT: 6}),
            PlainMemoryVariable(3, NO_PORT, {NO_PORT: 5}),
            PlainMemoryVariable(6, NO_PORT, {NO_PORT: 2}),
            PlainMemoryVariable(0, NO_PORT, {NO_PORT: 3}),
            PlainMemoryVariable(0, NO_PORT, {NO_PORT: 2}),
            PlainMemoryVariable(0, NO_PORT, {NO_PORT: 6}),
        }
    )


@pytest.fixture()
def collection():
    NO_PORT = 0
    return ProcessCollection(
        {
            PlainMemoryVariable(4, NO_PORT, {NO_PORT: 2}),
            PlainMemoryVariable(2, NO_PORT, {NO_PORT: 6}),
            PlainMemoryVariable(3, NO_PORT, {NO_PORT: 5}),
            PlainMemoryVariable(6, NO_PORT, {NO_PORT: 2}),
            PlainMemoryVariable(0, NO_PORT, {NO_PORT: 3}),
            PlainMemoryVariable(0, NO_PORT, {NO_PORT: 2}),
            PlainMemoryVariable(0, NO_PORT, {NO_PORT: 6}),
        }
    )
