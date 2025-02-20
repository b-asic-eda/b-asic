"""
B-ASIC test suite for graph id generator.
"""

import pytest

from b_asic import GraphIDGenerator


@pytest.fixture
def graph_id_generator():
    return GraphIDGenerator()


class TestGetNextId:
    def test_empty_string_generator(self, graph_id_generator):
        """Test the graph id generator for an empty string type."""
        assert graph_id_generator.next_id("") == "0"
        assert graph_id_generator.next_id("") == "1"

    def test_normal_string_generator(self, graph_id_generator):
        """ "Test the graph id generator for a normal string type."""
        assert graph_id_generator.next_id("add") == "add0"
        assert graph_id_generator.next_id("add") == "add1"

    def test_different_strings_generator(self, graph_id_generator):
        """Test the graph id generator for different strings."""
        assert graph_id_generator.next_id("sub") == "sub0"
        assert graph_id_generator.next_id("mul") == "mul0"
        assert graph_id_generator.next_id("sub") == "sub1"
        assert graph_id_generator.next_id("mul") == "mul1"
