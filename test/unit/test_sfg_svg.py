"""Interactive SVG rendering and browser launch tests."""

import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET

import pytest

from b_asic import SFG, Input, Output
from b_asic._sfg_svg import interactive_svg
from b_asic.core_operations import Absolute, Negation
from b_asic.fft_operations import R2Butterfly

SVG = "{http://www.w3.org/2000/svg}"


def test_operation_selection_excludes_sibling_consumers():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the SVG click handler")
    x = Input()
    graph = SFG(x, [Output(Negation(x)), Output(Absolute(x))])
    root = ET.fromstring(
        interactive_svg(graph, b'<svg xmlns="http://www.w3.org/2000/svg"/>', False)
    )
    nets = json.loads(root.find(SVG + "metadata").text)
    operation_ids = [f"sfg-op-{op.graph_id}" for op in graph.operations]
    source = f"sfg-op-{graph.input_operations[0].graph_id}"
    selected = f"sfg-op-{graph.find_by_type(Negation)[0].graph_id}"
    sibling = f"sfg-op-{graph.find_by_type(Absolute)[0].graph_id}"
    output = f"sfg-op-{graph.output_operations[0].graph_id}"
    incoming = next(net for net in nets if net["operations"][0] == source)
    payload = {
        "nets": nets,
        "operations": operation_ids,
        "script": root.find(SVG + "script").text,
        "clicks": [selected, source, incoming["elements"][0]],
    }
    # Execute the emitted handler against a small DOM double, including repeated
    # clicks so stale highlights are also covered.
    harness = r"""
const data = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const elements = new Map();
for (const id of [...data.operations, ...data.nets.flatMap(net => net.elements)]) {
    const classes = new Set();
    elements.set(id, {
        id,
        classList: {
            add: (...names) => names.forEach(name => classes.add(name)),
            remove: (...names) => names.forEach(name => classes.delete(name)),
            contains: name => classes.has(name)
        },
        querySelectorAll: () => [],
        closest() { return this; }
    });
}
const handlers = {};
global.document = {
    documentElement: {
        querySelectorAll: selector => [...elements.values()].filter(element =>
            selector.startsWith('[id^=') ? element.id.startsWith('sfg-op-') :
            selector.split(', ').some(name => element.classList.contains(name.slice(1)))) ,
        addEventListener: (event, handler) => { handlers[event] = handler; }
    },
    getElementById: id => id === 'sfg-connectivity'
        ? {textContent: JSON.stringify(data.nets)} : elements.get(id),
    addEventListener: () => {}
};
eval(data.script);
const results = data.clicks.map(id => {
    handlers.click({target: elements.get(id)});
    return [...elements.values()].filter(element =>
        element.classList.contains('sfg-connected')).map(element => element.id);
});
process.stdout.write(JSON.stringify(results));
"""
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    consumer_selection, source_selection, signal_selection = map(
        set, json.loads(result.stdout)
    )
    assert consumer_selection == {source, output}
    assert source_selection == {selected, sibling}
    assert signal_selection == {source, selected, sibling}


@pytest.mark.skipif(
    shutil.which("dot") is None,
    reason="Graphviz dot executable is required to render SVG",
)
@pytest.mark.parametrize("fmt", [None, "svg"])
@pytest.mark.parametrize("branch_node", [False, True])
@pytest.mark.parametrize("direction", ["LR", "TB"])
def test_show_interactive_svg(monkeypatch, fmt, branch_node, direction):
    x, y = Input(), Input()
    butterfly = R2Butterfly(x, y, name="A < B & C")
    with pytest.warns(
        UserWarning, match="Two signals connected to the same output port"
    ):
        graph = SFG(
            [x, y],
            [
                Output(butterfly.output(0)),
                Output(butterfly.output(0)),
                Output(butterfly.output(1)),
            ],
        )
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    graph.show(fmt=fmt, branch_node=branch_node, direction=direction, fontname="Arial")
    assert len(opened) == 1
    url = urlparse(opened[0])
    assert url.scheme == "file"
    path = Path(
        unquote(url.path).lstrip("/") if url.path[2:3] == ":" else unquote(url.path)
    )
    try:
        assert path.suffix == ".svg"
        root = ET.fromstring(path.read_bytes())
    finally:
        path.unlink()
    assert root.tag == SVG + "svg"
    assert "A < B & C" in "".join(root.itertext())
    assert "Arial" in {text.get("font-family") for text in root.iter(SVG + "text")}
    nets = json.loads(root.find(SVG + "metadata").text)
    ids = {element.get("id") for element in root.iter()}
    for net in nets:
        assert set(net["elements"]) <= ids
        assert set(net["operations"]) <= ids
    op = graph.find_by_type(R2Butterfly)[0]
    output_nets = [
        net for net in nets if net["operations"][0] == f"sfg-op-{op.graph_id}"
    ]
    assert len(output_nets) == 2
    branched = next(net for net in output_nets if len(net["operations"]) == 3)
    assert len(branched["elements"]) == (4 if branch_node else 2)
    assert len(set(output_nets[0]["elements"]) & set(output_nets[1]["elements"])) == 0
    assert root.find(SVG + "script") is not None


def test_show_explicit_format_uses_viewer(monkeypatch):
    x = Input()
    graph = SFG(x, Output(x))
    viewed = []

    def capture_graph(graph):
        viewed.append(graph)

    monkeypatch.setattr("graphviz.Digraph.view", capture_graph)
    graph.show(fmt="png")
    assert viewed[0].format == "png"
    assert "sfg-signal-" not in viewed[0].source
