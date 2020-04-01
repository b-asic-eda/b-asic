"""
B-ASIC test suit for the signal module which consists of the Signal class.
"""

from b_asic.port import InputPort, OutputPort
from b_asic.signal import Signal

import pytest

def test_signal_creation_and_disconnction_and_connection_changing():
    in_port = InputPort(0, None)
    out_port = OutputPort(1, None)
    s = Signal(out_port, in_port)

    assert in_port.signals == [s]
    assert out_port.signals == [s]
    assert s.source is out_port
    assert s.destination is in_port

    in_port1 = InputPort(0, None)
    s.set_destination(in_port1)

    assert in_port.signals == []
    assert in_port1.signals == [s]
    assert out_port.signals == [s]
    assert s.source is out_port
    assert s.destination is in_port1

    s.remove_source()

    assert out_port.signals == []
    assert in_port1.signals == [s]
    assert s.source is None
    assert s.destination is in_port1

    s.remove_destination()

    assert out_port.signals == []
    assert in_port1.signals == []
    assert s.source is None
    assert s.destination is None

    out_port1 = OutputPort(0, None)
    s.set_source(out_port1)

    assert out_port1.signals == [s]
    assert s.source is out_port1
    assert s.destination is None

    s.set_source(out_port)

    assert out_port.signals == [s]
    assert out_port1.signals == []
    assert s.source is out_port
    assert s.destination is None

    s.set_destination(in_port)

    assert out_port.signals == [s]
    assert in_port.signals == [s]
    assert s.source is out_port
    assert s.destination is in_port
