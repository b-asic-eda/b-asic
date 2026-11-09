"""Standalone SVG interaction for signal flow graphs."""

import json
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from b_asic.signal import Signal

if TYPE_CHECKING:
    from b_asic.sfg import SFG


_STYLE = """
.sfg-operation, .sfg-signal { cursor: pointer; }
.sfg-connected :is(ellipse, polygon, path, rect, circle) {
    fill: #dbeafe; stroke: #2563eb; stroke-width: 2.5;
}
.sfg-selected :is(ellipse, polygon, path, rect, circle) {
    fill: #ffedd5; stroke: #ea580c; stroke-width: 3;
}
.sfg-connected text { fill: #1d4ed8; }
.sfg-selected text { fill: #9a3412; }
.sfg-highlight path:not(.sfg-hit) { stroke: #c026d3; stroke-width: 3; }
.sfg-highlight :is(polygon, ellipse, circle) {
    fill: #c026d3; stroke: #c026d3;
}
.sfg-highlight text { fill: #a21caf; }
.sfg-hit { fill: none; stroke: transparent; stroke-width: 14; pointer-events: stroke; }
"""

_SCRIPT = """
(() => {
    const svg = document.documentElement;
    const nets = JSON.parse(document.getElementById('sfg-connectivity').textContent);
    const operations = new Map();
    const signals = new Map();
    const byId = id => document.getElementById(id);
    for (const [index, net] of nets.entries()) {
        for (const id of net.elements) {
            const element = byId(id);
            if (!element) continue;
            element.classList.add('sfg-signal');
            signals.set(element, index);
            // Give narrow splines a generous click target, including their labels.
            for (const path of [...element.querySelectorAll('path')]) {
                const hit = path.cloneNode(false);
                hit.removeAttribute('id');
                hit.setAttribute('class', 'sfg-hit');
                element.insertBefore(hit, element.firstChild);
            }
        }
        for (const id of net.operations) {
            const element = byId(id);
            if (!element) continue;
            element.classList.add('sfg-operation');
            if (!operations.has(element)) operations.set(element, new Set());
            operations.get(element).add(index);
        }
    }
    // Include disconnected operations as selectable nodes too.
    for (const element of svg.querySelectorAll('[id^="sfg-op-"]')) {
        element.classList.add('sfg-operation');
        if (!operations.has(element)) operations.set(element, new Set());
    }
    function clear() {
        for (const element of svg.querySelectorAll(
            '.sfg-selected, .sfg-connected, .sfg-highlight'
        )) element.classList.remove('sfg-selected', 'sfg-connected', 'sfg-highlight');
    }
    svg.addEventListener('click', event => {
        clear();
        const element = event.target.closest('.sfg-operation, .sfg-signal');
        if (!element) return;
        const selected = operations.has(element) ? element : null;
        const indices = selected ? operations.get(element) : [signals.get(element)];
        for (const index of indices) {
            for (const id of nets[index].elements) byId(id)?.classList.add('sfg-highlight');
            // The source is first; other operations consume this signal.
            // Selecting a consumer must not also select its sibling consumers.
            const source = nets[index].operations[0];
            const connected = !selected || selected.id === source
                ? nets[index].operations : [source];
            for (const id of connected) byId(id)?.classList.add('sfg-connected');
        }
        if (selected) {
            selected.classList.remove('sfg-connected');
            selected.classList.add('sfg-selected');
        }
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') clear();
    });
})();
"""


def interactive_svg(sfg: "SFG", svg: bytes, branch_node: bool) -> bytes:
    """Embed connectivity, styles and click handlers into a Graphviz SVG."""
    namespace = "http://www.w3.org/2000/svg"
    ET.register_namespace("", namespace)
    root = ET.fromstring(svg)
    nets: dict[str, dict[str, list[str]]] = {}
    for signal in sfg.components:
        if not isinstance(signal, Signal):
            continue
        source = signal.source
        destination = signal.destination
        if source is None or destination is None:
            continue
        net = nets.setdefault(source.name, {"elements": [], "operations": []})
        net["elements"].append(f"sfg-signal-{signal.graph_id}")
        for operation in (source.operation, destination.operation):
            identifier = f"sfg-op-{operation.graph_id}"
            if identifier not in net["operations"]:
                net["operations"].append(identifier)
        if branch_node and source.signal_count > 1:
            for prefix in ("branch", "trunk"):
                identifier = f"sfg-{prefix}-{source.name}"
                if identifier not in net["elements"]:
                    net["elements"].append(identifier)
    ET.SubElement(root, f"{{{namespace}}}style").text = _STYLE
    ET.SubElement(
        root, f"{{{namespace}}}metadata", id="sfg-connectivity"
    ).text = json.dumps(list(nets.values()))
    ET.SubElement(root, f"{{{namespace}}}script").text = _SCRIPT
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
