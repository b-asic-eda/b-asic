"""
B-ASIC test suite for graph id generator.
"""

from b_asic.graph_id import GraphIDGenerator, GraphID
import pytest

@pytest.fixture
def graph_id_generator():
    return GraphIDGenerator()

class TestGetNextId:
    def test_empty_string_generator(self, graph_id_generator):
        """Test the graph id generator for an empty string type."""
        assert graph_id_generator.get_next_id("") == "1"
        assert graph_id_generator.get_next_id("") == "2"

    def test_normal_string_generator(self, graph_id_generator):
        """"Test the graph id generator for a normal string type."""
        assert graph_id_generator.get_next_id("add") == "add1"
        assert graph_id_generator.get_next_id("add") == "add2"

    def test_different_strings_generator(self, graph_id_generator):
        """Test the graph id generator for different strings."""
        assert graph_id_generator.get_next_id("sub") == "sub1"
        assert graph_id_generator.get_next_id("mul") == "mul1"
        assert graph_id_generator.get_next_id("sub") == "sub2"
        assert graph_id_generator.get_next_id("mul") == "mul2"
