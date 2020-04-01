"""
B-ASIC test suite for Inputport
"""

import pytest

from b_asic import InputPort, OutputPort
from b_asic import Signal

@pytest.fixture
def inp_port():
    return InputPort(0, None)

@pytest.fixture
def out_port():
    return OutputPort(0, None)

@pytest.fixture
def out_port2():
    return OutputPort(1, None)

@pytest.fixture
def dangling_sig():
    return Signal()

@pytest.fixture
def s_w_source():
    out_port = OutputPort(0, None)
    return Signal(source=out_port)

@pytest.fixture
def sig_with_dest():
    inp_port = InputPort(0, None)
    return Signal(destination=out_port)

@pytest.fixture
def connected_sig():
    out_port = OutputPort(0, None)
    inp_port = InputPort(0, None)
    return Signal(source=out_port, destination=inp_port)

def test_connect_then_disconnect(inp_port, out_port):
    """Test connect unused port to port."""
    s1 = inp_port.connect(out_port)

    assert inp_port.connected_ports == [out_port]
    assert out_port.connected_ports == [inp_port]
    assert inp_port.signals == [s1]
    assert out_port.signals == [s1]
    assert s1.source is out_port
    assert s1.destination is inp_port

    inp_port.remove_signal(s1)

    assert inp_port.connected_ports == []
    assert out_port.connected_ports == []
    assert inp_port.signals == []
    assert out_port.signals == [s1]
    assert s1.source is out_port
    assert s1.destination is None

def test_connect_used_port_to_new_port(inp_port, out_port, out_port2):
    """Does connecting multiple ports to an inputport throw error?"""
    inp_port.connect(out_port)
    with pytest.raises(AssertionError):
        inp_port.connect(out_port2)

def test_add_signal_then_disconnect(inp_port, s_w_source):
    """Can signal be connected then disconnected properly?"""
    inp_port.add_signal(s_w_source)

    assert inp_port.connected_ports == [s_w_source.source]
    assert s_w_source.source.connected_ports == [inp_port]
    assert inp_port.signals == [s_w_source]
    assert s_w_source.source.signals == [s_w_source]
    assert s_w_source.destination is inp_port

    inp_port.remove_signal(s_w_source)

    assert inp_port.connected_ports == []
    assert s_w_source.source.connected_ports == []
    assert inp_port.signals == []
    assert s_w_source.source.signals == [s_w_source]
    assert s_w_source.destination is None

def test_connect_then_disconnect(inp_port, out_port):
    """Can port be connected and then disconnected properly?"""
    inp_port.connect(out_port)

    inp_port.disconnect(out_port)

    print("outport signals:", out_port.signals, "count:", out_port.signal_count())
    assert inp_port.signal_count() == 1
    assert len(inp_port.connected_ports) == 0
    assert out_port.signal_count() == 0
