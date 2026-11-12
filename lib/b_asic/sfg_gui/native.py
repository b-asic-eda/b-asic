"""Send design deltas to the persistent C++ place-and-route engine."""

from b_asic._sfg_gui import PlaceRouteEngine, TerminalKind
from b_asic.core_operations import Constant
from b_asic.sfg_gui._preferences import GRID, LAYOUT_SPACING
from b_asic.special_operations import Delay, Input, Output
from b_asic.utility_operations import DontCare, Sink


def _terminal_kind(operation):
    if isinstance(operation, Input):
        return TerminalKind.INPUT
    if isinstance(operation, Output):
        return TerminalKind.OUTPUT
    if isinstance(operation, Sink):
        return TerminalKind.SINK
    if isinstance(operation, (Constant, DontCare)):
        return TerminalKind.LOCAL_SOURCE
    return TerminalKind.OPERATION


def _node_record(button):
    rect = button.graphicsProxyWidget().sceneBoundingRect()
    return (
        id(button),
        (rect.left(), rect.top(), rect.right(), rect.bottom()),
        (button.width(), button.height()),
        isinstance(button.operation, Delay),
        button.default_rotation(),
        button.rotation_angle(),
        button.is_flipped(),
        _terminal_kind(button.operation),
    )


def _port_records(button):
    for port in button.port_list:
        point = port.anchor()
        yield (
            id(port),
            id(button),
            (point.x(), point.y()),
            port.scene_direction(),
        )


class NativeDesign:
    """
    Qt owns graphics; C++ owns the graph, geometry, routes and reservations.

    Python retains only object IDs and change fingerprints. A drag sends the
    changed node and its ports once, and receives only paths that changed.
    """

    def __init__(self) -> None:
        self.engine = PlaceRouteEngine(GRID, LAYOUT_SPACING)
        self._nodes = {}
        self._ports = set()
        self._wires = {}
        self.arrows = {}
        self._dirty_nodes = set()

    def mark_dirty(self, button) -> None:
        """Record a geometry change without scanning the rest of the design."""
        self._dirty_nodes.add(button)

    def _sync_dirty(self, window) -> None:
        nodes, node_updates, port_updates = {}, [], []
        for button in self._dirty_nodes:
            if button not in window._drag_operation_scenes:
                continue
            identity = id(button)
            port_ids = tuple(id(port) for port in button.port_list)
            previous = self._nodes.get(identity)
            if previous is None or port_ids != previous[-1]:
                # New operations or changed port sets require topology sync.
                self.sync(window)
                return
            record = _node_record(button)
            fingerprint = (*record, port_ids)
            if fingerprint != previous:
                nodes[identity] = fingerprint
                node_updates.append(record)
                port_updates.extend(_port_records(button))
        if node_updates:
            self.engine.update(node_updates, port_updates, [])
            self._nodes.update(nodes)
        self._dirty_nodes.clear()

    def sync(self, window, *, incremental: bool = False) -> None:
        if incremental:
            self._sync_dirty(window)
            return
        nodes, ports, wires = {}, set(), {}
        node_updates, port_updates, wire_updates = [], [], []
        for button in window._drag_buttons.values():
            record = _node_record(button)
            fingerprint = (*record, tuple(id(port) for port in button.port_list))
            nodes[id(button)] = fingerprint
            ports.update(fingerprint[-1])
            if fingerprint != self._nodes.get(id(button)):
                node_updates.append(record)
                port_updates.extend(_port_records(button))
        arrows = {id(arrow): arrow for arrow in window._arrow_ports}
        for identity, arrow in arrows.items():
            record = (
                identity,
                id(arrow.source_port_button),
                id(arrow.destination_port_button),
                id(arrow.branch_parent) if arrow.branch_parent is not None else 0,
                arrow.branch_fraction,
            )
            wires[identity] = record
            if record != self._wires.get(identity):
                wire_updates.append(record)
        removed_nodes = self._nodes.keys() - nodes.keys()
        removed_ports = self._ports - ports
        removed_wires = self._wires.keys() - wires.keys()
        if (
            node_updates
            or port_updates
            or wire_updates
            or removed_nodes
            or removed_ports
            or removed_wires
        ):
            self.engine.update(
                node_updates,
                port_updates,
                wire_updates,
                list(removed_nodes),
                list(removed_ports),
                list(removed_wires),
            )
        self._nodes, self._ports, self._wires, self.arrows = nodes, ports, wires, arrows
        self._dirty_nodes.clear()

    def clear(self) -> None:
        self.engine.reset()
        self._nodes.clear()
        self._ports.clear()
        self._wires.clear()
        self.arrows.clear()
        self._dirty_nodes.clear()
