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

    def sync(self, window) -> None:
        nodes, ports, wires = {}, set(), {}
        node_updates, port_updates, wire_updates = [], [], []
        for operation, button in window._drag_buttons.items():
            rect = button.graphicsProxyWidget().sceneBoundingRect()
            record = (
                id(button),
                (rect.left(), rect.top(), rect.right(), rect.bottom()),
                (button.width(), button.height()),
                isinstance(operation, Delay),
                button.default_rotation(),
                button.rotation_angle(),
                button.is_flipped(),
                _terminal_kind(operation),
            )
            fingerprint = (*record, tuple(id(port) for port in button.port_list))
            nodes[id(button)] = fingerprint
            ports.update(fingerprint[-1])
            if fingerprint != self._nodes.get(id(button)):
                node_updates.append(record)
                for port in button.port_list:
                    point = port.anchor()
                    port_updates.append(
                        (
                            id(port),
                            id(button),
                            (point.x(), point.y()),
                            port.scene_direction(),
                        )
                    )
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

    def clear(self) -> None:
        self.engine.reset()
        self._nodes.clear()
        self._ports.clear()
        self._wires.clear()
        self.arrows.clear()
