"""
B-ASIC test suite for Inputport.
"""

import pytest


def test_connect_then_disconnect(input_port, output_port):
    """Test connect unused port to port."""
    s1 = input_port.connect(output_port)

    assert input_port.connected_source == output_port
    assert input_port.signals == [s1]
    assert output_port.signals == [s1]
    assert s1.source is output_port
    assert s1.destination is input_port

    input_port.remove_signal(s1)

    assert input_port.connected_source is None
    assert input_port.signals == []
    assert output_port.signals == [s1]
    assert s1.source is output_port
    assert s1.destination is None


def test_connect_used_port_to_new_port(input_port, output_port, output_port2):
    """Multiple connections to an input port should throw an error."""
    input_port.connect(output_port)
    with pytest.raises(ValueError, match="Cannot connect already connected input port"):
        input_port.connect(output_port2)


def test_add_signal_then_disconnect(input_port, s_w_source):
    """Test if signal be connected then disconnected properly."""
    input_port.add_signal(s_w_source)

    assert input_port.connected_source == s_w_source.source
    assert input_port.signals == [s_w_source]
    assert s_w_source.source.signals == [s_w_source]
    assert s_w_source.destination is input_port

    input_port.remove_signal(s_w_source)

    assert input_port.connected_source is None
    assert input_port.signals == []
    assert s_w_source.source.signals == [s_w_source]
    assert s_w_source.destination is None
