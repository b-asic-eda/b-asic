from b_asic.core_operations import Constant, Addition
from b_asic.signal import Signal
from b_asic.port import InputPort, OutputPort

import pytest

class TestTraverse:
    def test_traverse_single_tree(self, operation):
        """Traverse a tree consisting of one operation."""
        constant = Constant(None)
        assert list(constant.traverse()) == [constant]

    def test_traverse_tree(self, operation_tree):
        """Traverse a basic addition tree with two constants."""
        assert len(list(operation_tree.traverse())) == 3

    def test_traverse_large_tree(self, large_operation_tree):
        """Traverse a larger tree."""
        assert len(list(large_operation_tree.traverse())) == 7

    def test_traverse_type(self, large_operation_tree):
        traverse = list(large_operation_tree.traverse())
        assert len(list(filter(lambda type_: isinstance(type_, Addition), traverse))) == 3
        assert len(list(filter(lambda type_: isinstance(type_, Constant), traverse))) == 4

    def test_traverse_loop(self, operation_tree):
        add_oper_signal = Signal()
        operation_tree._output_ports[0].add_signal(add_oper_signal)
        operation_tree._input_ports[0].remove_signal(add_oper_signal)
        operation_tree._input_ports[0].add_signal(add_oper_signal)
        assert len(list(operation_tree.traverse())) == 2
