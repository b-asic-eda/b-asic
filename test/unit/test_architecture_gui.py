from itertools import chain

import pytest
from qtpy.QtCore import QPointF

from b_asic.architecture import Architecture, Memory, ProcessingElement
from b_asic.core_operations import Addition, ConstantMultiplication
from b_asic.special_operations import Input, Output

try:
    from b_asic.architecture_gui.arrow import get_port_edges
    from b_asic.architecture_gui.main_window import ArchitectureMainWindow
except ImportError:
    pytestmark = pytest.mark.skip("Qt not setup")


def _build_architecture(schedule_direct_form_iir_lp_filter):
    mvs = schedule_direct_form_iir_lp_filter.get_memory_variables()
    operations = schedule_direct_form_iir_lp_filter.get_operations()
    adders1, adders2 = operations.get_by_type_name(Addition.type_name()).split_on_ports(
        strategy="left_edge", total_ports=1
    )
    adders1 = [adders1]
    adders2 = [adders2]
    const_mults = operations.get_by_type_name(
        ConstantMultiplication.type_name()
    ).split_on_execution_time()
    inputs = operations.get_by_type_name(Input.type_name()).split_on_execution_time()
    outputs = operations.get_by_type_name(Output.type_name()).split_on_execution_time()

    processing_elements = [
        ProcessingElement(operation, entity_name=f"pe{i}")
        for i, operation in enumerate(chain(adders1, adders2, const_mults))
    ]
    for i, pc in enumerate(inputs):
        processing_elements.append(ProcessingElement(pc, entity_name=f"input{i}"))
    for i, pc in enumerate(outputs):
        processing_elements.append(ProcessingElement(pc, entity_name=f"output{i}"))

    direct_conn, mvs = mvs.split_on_length()
    memories = [
        Memory(pc, entity_name=f"mem{i}") for i, pc in enumerate(mvs.split_on_length(6))
    ]

    return Architecture(processing_elements, memories, direct_interconnects=direct_conn)


def test_get_port_edges_matches_interconnects(schedule_direct_form_iir_lp_filter):
    architecture = _build_architecture(schedule_direct_form_iir_lp_filter)
    edges = get_port_edges(architecture)
    assert edges

    expected_count = 0
    for pe in architecture.processing_elements:
        inputs, outputs = architecture.get_interconnects_for_pe(pe)
        expected_count += sum(len(d) for d in inputs) + sum(len(d) for d in outputs)
    assert len(edges) >= expected_count


def test_start(qtbot):
    widget = ArchitectureMainWindow()
    qtbot.addWidget(widget)


def test_open_architecture(qtbot, schedule_direct_form_iir_lp_filter):
    architecture = _build_architecture(schedule_direct_form_iir_lp_filter)
    widget = ArchitectureMainWindow()
    qtbot.addWidget(widget)
    widget.open(architecture)

    assert set(widget._resource_items) == {
        r.entity_name
        for r in chain(architecture.processing_elements, architecture.memories)
    }
    for item in widget._process_items.values():
        assert item.resource_name in widget._resource_items


def test_try_move_process_updates_model_and_scene(
    qtbot, schedule_direct_form_iir_lp_filter, capsys
):
    architecture = _build_architecture(schedule_direct_form_iir_lp_filter)
    widget = ArchitectureMainWindow()
    qtbot.addWidget(widget)
    widget.open(architecture)

    mem0 = architecture.resource_from_name("mem0")
    mem1 = architecture.resource_from_name("mem1")
    proc = mem1.collection.from_name("cmul3.0")

    assert widget.try_move_process(proc, "mem1", "mem0")
    assert mem0.collection.from_name("cmul3.0") is proc
    with pytest.raises(KeyError):
        mem1.collection.from_name("cmul3.0")
    assert (
        "architecture.move_process('cmul3.0', 'mem1', 'mem0')"
        in capsys.readouterr().out
    )
    assert widget._process_items[proc].resource_name == "mem0"


def test_try_move_process_rejects_incompatible_resource(
    qtbot, schedule_direct_form_iir_lp_filter
):
    architecture = _build_architecture(schedule_direct_form_iir_lp_filter)
    widget = ArchitectureMainWindow()
    qtbot.addWidget(widget)
    widget.open(architecture)

    mem0 = architecture.resource_from_name("mem0")
    proc = next(iter(mem0.collection))

    assert not widget.try_move_process(proc, "mem0", "pe0")
    assert mem0.collection.from_name(proc.name) is proc
    assert "Could not move process" in widget.statusBar().currentMessage()


def test_inspectors_do_not_crash(qtbot, schedule_direct_form_iir_lp_filter):
    architecture = _build_architecture(schedule_direct_form_iir_lp_filter)
    widget = ArchitectureMainWindow()
    qtbot.addWidget(widget)
    widget.open(architecture)

    mem0 = architecture.resource_from_name("mem0")
    proc = next(iter(mem0.collection))

    widget.show_resource_inspector(mem0)
    assert mem0.entity_name in widget._inspector_title.toPlainText()

    widget.show_process_inspector(proc, "mem0")
    assert proc.name in widget._inspector_title.toPlainText()


class _FakeMouseEvent:
    """
    Stand-in for a QGraphicsSceneMouseEvent, since ProcessItem only uses
    scenePos() and accept().
    """

    def __init__(self, scene_pos):
        self._scene_pos = scene_pos

    def scenePos(self):
        return self._scene_pos

    def accept(self):
        pass


def test_drag_process_item_reassigns_on_drop(qtbot, schedule_direct_form_iir_lp_filter):
    architecture = _build_architecture(schedule_direct_form_iir_lp_filter)
    widget = ArchitectureMainWindow()
    qtbot.addWidget(widget)
    widget.open(architecture)

    mem0 = architecture.resource_from_name("mem0")
    mem1 = architecture.resource_from_name("mem1")
    proc = mem1.collection.from_name("cmul3.0")
    process_item = widget._process_items[proc]
    drop_pos = widget._resource_items["mem0"].sceneBoundingRect().center()

    process_item.mousePressEvent(
        _FakeMouseEvent(process_item.sceneBoundingRect().center())
    )
    process_item.mouseMoveEvent(_FakeMouseEvent(drop_pos))
    process_item.mouseReleaseEvent(_FakeMouseEvent(drop_pos))

    assert mem0.collection.from_name("cmul3.0") is proc
    with pytest.raises(KeyError):
        mem1.collection.from_name("cmul3.0")


def test_drag_process_item_snaps_back_without_move(
    qtbot, schedule_direct_form_iir_lp_filter
):
    architecture = _build_architecture(schedule_direct_form_iir_lp_filter)
    widget = ArchitectureMainWindow()
    qtbot.addWidget(widget)
    widget.open(architecture)

    mem1 = architecture.resource_from_name("mem1")
    proc = mem1.collection.from_name("cmul3.0")
    process_item = widget._process_items[proc]
    same_resource_pos = process_item.sceneBoundingRect().center()

    nudged_pos = same_resource_pos + QPointF(5, 5)
    process_item.mousePressEvent(_FakeMouseEvent(same_resource_pos))
    process_item.mouseMoveEvent(_FakeMouseEvent(nudged_pos))
    process_item.mouseReleaseEvent(_FakeMouseEvent(nudged_pos))

    assert mem1.collection.from_name("cmul3.0") is proc
