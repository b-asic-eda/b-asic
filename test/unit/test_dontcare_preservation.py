"""Rebuilding and flattening preserve DontCare-fed disconnected branches."""

import pytest

from b_asic.core_operations import ConstantMultiplication
from b_asic.sfg import SFG
from b_asic.special_operations import Input, Output
from b_asic.utility_operations import DontCare


def _graph_with_disconnected_branch():
    source = Input()
    graph = SFG([source], [Output(source)])
    # This is the intermediate state produced when a transformation detaches
    # a branch from the interface but retains its DontCare source.
    branch = ConstantMultiplication(2, DontCare("placeholder"))
    graph._add_operation_connected_tree_copy(branch)
    return graph


@pytest.mark.parametrize("copy_method", ["call", "copy"])
def test_copy_retains_dontcare_branch(copy_method):
    original = _graph_with_disconnected_branch()
    result = original() if copy_method == "call" else original.copy()
    assert len(result.find_by_type(DontCare)) == 1
    assert len(result.find_by_type(ConstantMultiplication)) == 1
    assert result.find_by_type(DontCare)[0].name == "placeholder"
    assert result.evaluate_outputs([3]) == [3]


@pytest.mark.parametrize("expand", [False, True])
def test_flatten_nested_dontcare_branch(expand):
    inner = _graph_with_disconnected_branch()
    source = Input()
    original = SFG([source], [Output(inner(source))])
    result = original.flatten(expand)
    assert not result.find_by_type(SFG)
    assert len(result.find_by_type(DontCare)) == 1
    assert len(result.find_by_type(ConstantMultiplication)) == 1
    assert result.evaluate_outputs([3]) == [3]
