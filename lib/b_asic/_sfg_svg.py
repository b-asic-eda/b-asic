"""Standalone SVG interaction for signal flow graphs."""

import json
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from b_asic.signal import Signal

if TYPE_CHECKING:
    from b_asic.operation import Operation
    from b_asic.sfg import SFG


_SVG = "{http://www.w3.org/2000/svg}"


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
.sfg-legend-toggle, .sfg-legend-item { cursor: pointer; }
.sfg-legend-toggle rect, .sfg-legend-item rect {
    fill: white; stroke: #cbd5e1; stroke-width: 1;
}
.sfg-legend-toggle:hover rect, .sfg-legend-item:hover rect { fill: #eff6ff; }
.sfg-legend-item[aria-pressed="true"] rect { fill: #ffedd5; stroke: #ea580c; }
.sfg-legend-toggle:focus rect, .sfg-legend-item:focus rect {
    stroke: #2563eb; stroke-width: 2;
}
.sfg-legend text { fill: #334155; }
"""

_SCRIPT = """
(() => {
    const svg = document.documentElement;
    const nets = JSON.parse(document.getElementById('sfg-connectivity').textContent);
    const operations = new Map();
    const signals = new Map();
    const byId = id => document.getElementById(id);
    const types = JSON.parse(byId('sfg-operation-types')?.textContent || '[]');
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
        for (const item of svg.querySelectorAll('.sfg-legend-item')) {
            item.setAttribute('aria-pressed', 'false');
        }
    }
    function select(target) {
        const toggle = target.closest('.sfg-legend-toggle');
        if (toggle) {
            const expanded = toggle.getAttribute('aria-expanded') === 'true';
            byId('sfg-legend-items').setAttribute('display', expanded ? 'none' : 'inline');
            toggle.setAttribute('aria-expanded', String(!expanded));
            byId('sfg-legend-marker').textContent = expanded ? '+' : '-';
            return;
        }
        const item = target.closest('.sfg-legend-item');
        const pressed = item?.getAttribute('aria-pressed') === 'true';
        clear();
        if (item) {
            if (!pressed) {
                item.setAttribute('aria-pressed', 'true');
                for (const id of types[Number(item.getAttribute('data-sfg-type'))].operations) {
                    byId(id)?.classList.add('sfg-selected');
                }
            }
            return;
        }
        const element = target.closest('.sfg-operation, .sfg-signal');
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
    }
    svg.addEventListener('click', event => select(event.target));
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') clear();
        else if ((event.key === 'Enter' || event.key === ' ') &&
                 event.target.closest?.('.sfg-legend-item, .sfg-legend-toggle')) {
            event.preventDefault();
            select(event.target);
        }
    });
})();
"""


def _add_legend(root: ET.Element, labels: Sequence[str]) -> None:
    """Place native SVG controls beside the Graphviz drawing and extend its bounds."""
    viewbox = [
        float(value)
        for value in root.get("viewBox", "0 0 0 0").replace(",", " ").split()
    ]
    x, y, width, height = viewbox
    sample_text = next(root.iter(_SVG + "text"), None)
    family = (
        sample_text.get("font-family", "sans-serif")
        if sample_text is not None
        else "sans-serif"
    )
    size = float(sample_text.get("font-size", "14")) if sample_text is not None else 14
    text_attributes = {"font-family": family, "font-size": f"{size:g}"}
    row_height = size * 1.8
    panel_width = max(170, max(map(len, labels)) * size * 0.8 + 32)
    panel_height = row_height * (len(labels) + 1) + 4
    group = ET.SubElement(
        root,
        _SVG + "g",
        {
            "id": "sfg-legend",
            "class": "sfg-legend",
            "transform": f"translate({x + width + 12:g} {y + 8:g})",
        },
    )
    toggle = ET.SubElement(
        group,
        _SVG + "g",
        {
            "id": "sfg-legend-toggle",
            "class": "sfg-legend-toggle",
            "role": "button",
            "tabindex": "0",
            "aria-expanded": "true",
            "aria-controls": "sfg-legend-items",
            "aria-label": "Show or hide operation types",
        },
    )
    ET.SubElement(
        toggle,
        _SVG + "rect",
        {"width": f"{panel_width:g}", "height": f"{row_height:g}", "rx": "4"},
    )
    ET.SubElement(
        toggle, _SVG + "text", {"x": "10", "y": f"{size * 1.25:g}", **text_attributes}
    ).text = "Operation types"
    ET.SubElement(
        toggle,
        _SVG + "text",
        {
            "id": "sfg-legend-marker",
            "x": f"{panel_width - 12:g}",
            "y": f"{size * 1.25:g}",
            "text-anchor": "end",
            **text_attributes,
        },
    ).text = "-"
    items = ET.SubElement(
        group,
        _SVG + "g",
        {"id": "sfg-legend-items", "transform": f"translate(0 {row_height + 4:g})"},
    )
    for index, label in enumerate(labels):
        item = ET.SubElement(
            items,
            _SVG + "g",
            {
                "id": f"sfg-legend-type-{index}",
                "class": "sfg-legend-item",
                "data-sfg-type": str(index),
                "role": "button",
                "tabindex": "0",
                "aria-pressed": "false",
                "aria-label": f"Highlight {label}",
                "transform": f"translate(0 {index * row_height:g})",
            },
        )
        ET.SubElement(
            item,
            _SVG + "rect",
            {"width": f"{panel_width:g}", "height": f"{row_height - 1:g}", "rx": "3"},
        )
        ET.SubElement(
            item, _SVG + "text", {"x": "10", "y": f"{size * 1.25:g}", **text_attributes}
        ).text = label
    new_width = width + panel_width + 32
    new_height = max(height, panel_height + 16)
    root.set("viewBox", f"{x:g} {y:g} {new_width:g} {new_height:g}")
    for attribute, old, new in (
        ("width", width, new_width),
        ("height", height, new_height),
    ):
        value = root.get(attribute, "")
        if value.endswith("%"):
            continue
        match = re.fullmatch(r"([0-9.eE+\-]+)([a-zA-Z]*)", value)
        physical = float(match[1]) * new / old if match and old else new
        unit = match[2] if match else "pt"
        root.set(attribute, f"{physical:g}{unit}")


def interactive_svg(
    sfg: "SFG", svg: bytes, branch_node: bool, legend: bool = True
) -> bytes:
    """Embed connectivity, an optional operation-type legend, and SVG click handlers."""
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
    if legend:
        groups: dict[type[Operation], list[str]] = {}
        for operation in dict.fromkeys(sfg.operations):
            groups.setdefault(type(operation), []).append(
                f"sfg-op-{operation.graph_id}"
            )
        types = []
        labels = []
        for operation_type, identifiers in sorted(
            groups.items(), key=lambda pair: (pair[0].type_name(), pair[0].__name__)
        ):
            types.append(
                {
                    "name": operation_type.__name__,
                    "type": operation_type.type_name(),
                    "operations": identifiers,
                }
            )
            labels.append(
                f"{operation_type.__name__} ({operation_type.type_name()}) · {len(identifiers)}"
            )
        if types:
            ET.SubElement(
                root, _SVG + "metadata", id="sfg-operation-types"
            ).text = json.dumps(types)
            _add_legend(root, labels)
    ET.SubElement(root, f"{{{namespace}}}script").text = _SCRIPT
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
