"""Interactive SVG rendering and browser launch tests."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET

import pytest

from b_asic import SFG, Input, Output
from b_asic._sfg_svg import interactive_svg
from b_asic.core_operations import Absolute, Negation
from b_asic.fft_operations import R2Butterfly

SVG = "{http://www.w3.org/2000/svg}"


_DOM_HARNESS = r"""
(() => {
const elements = new Map();
function makeElement(id, initialClasses = [], attributes = {}) {
    const classes = new Set(initialClasses);
    const element = {
        id,
        attributes,
        parentElement: null,
        classList: {
            add: (...names) => names.forEach(name => classes.add(name)),
            remove: (...names) => names.forEach(name => classes.delete(name)),
            contains: name => classes.has(name)
        },
        setAttribute: (name, value) => { attributes[name] = value; },
        getAttribute: name => attributes[name] ?? null,
        querySelectorAll: () => [],
        closest(selector) {
            for (let current = this; current; current = current.parentElement) {
                if (selector.split(',').some(name => current.classList.contains(name.trim().slice(1)))) {
                    return current;
                }
            }
            return null;
        }
    };
    elements.set(id, element);
    return element;
}
for (const id of new Set([...data.operations, ...[].concat(...data.nets.map(net => net.elements))])) {
    makeElement(id);
}
makeElement('background');
if (data.types.length) {
    makeElement('sfg-legend-toggle', ['sfg-legend-toggle'], {'aria-expanded': 'true'});
    makeElement('sfg-legend-items');
    makeElement('sfg-legend-marker');
    for (const [index] of data.types.entries()) {
        makeElement('sfg-legend-type-' + index, ['sfg-legend-item'], {
            'data-sfg-type': String(index), 'aria-pressed': 'false'
        });
    }
}
const handlers = {};
const document = {
    documentElement: {
        querySelectorAll: selector => [...elements.values()].filter(element =>
            selector.startsWith('[id^=') ? element.id.startsWith('sfg-op-') :
            selector.split(',').some(name => element.classList.contains(name.trim().slice(1)))) ,
        addEventListener: (event, handler) => { handlers[event] = handler; }
    },
    getElementById: id => id === 'sfg-connectivity'
        ? {textContent: JSON.stringify(data.nets)} : id === 'sfg-operation-types' && data.types.length
        ? {textContent: JSON.stringify(data.types)} : elements.get(id),
    addEventListener: (event, handler) => { handlers[event] = handler; }
};
eval(data.script);
const withClass = name => [...elements.values()].filter(element =>
    element.classList.contains(name)).map(element => element.id);
return JSON.stringify(data.events.map(event => {
    let target = elements.get(event.target || event.click || 'background');
    if (event.child) {
        const child = makeElement('clicked-text');
        child.parentElement = target;
        target = child;
    }
    if (event.key) handlers.keydown({key: event.key, target, preventDefault() {}});
    else handlers.click({target});
    return {
        selected: withClass('sfg-selected'),
        connected: withClass('sfg-connected'),
        highlighted: withClass('sfg-highlight'),
        pressed: [...elements.values()].filter(element => element.getAttribute('aria-pressed') === 'true').map(element => element.id),
        legendVisible: !!elements.get('sfg-legend-items') && elements.get('sfg-legend-items').getAttribute('display') !== 'none'
    };
}));
})()
"""


def _run_svg_events(graph, root, events):
    type_data = root.find(f"{SVG}metadata[@id='sfg-operation-types']")
    payload = {
        "nets": json.loads(root.find(f"{SVG}metadata[@id='sfg-connectivity']").text),
        "types": json.loads(type_data.text) if type_data is not None else [],
        "operations": [
            f"sfg-op-{op.graph_id}" for op in dict.fromkeys(graph.operations)
        ],
        "script": root.find(SVG + "script").text,
        "events": events,
        "harness": _DOM_HARNESS,
    }
    node = shutil.which("node")
    if node is not None:
        program = "const data = JSON.parse(require('fs').readFileSync(0, 'utf8')); process.stdout.write(eval(data.harness));"
        command = [node, "-e", program]
    else:
        pytest.importorskip(
            "qtpy.QtQml",
            reason="Node.js or QtQml is required to execute SVG JavaScript",
        )
        # Keep the Qt application in a child process so later GUI tests can
        # still create their own QApplication.
        program = """
import json
import sys
from qtpy.QtCore import QCoreApplication
from qtpy.QtQml import QJSEngine
data = json.load(sys.stdin)
application = QCoreApplication([])
engine = QJSEngine()
result = engine.evaluate('const data = ' + json.dumps(data) + ';\\n' + data['harness'])
if result.isError():
    raise RuntimeError(result.toString() + '\\n' + result.property('stack').toString())
print(result.toString())
"""
        command = [sys.executable, "-c", program]
    try:
        result = subprocess.run(
            command,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        pytest.fail(error.stderr)
    return json.loads(result.stdout)


def test_operation_selection_excludes_sibling_consumers():
    x = Input()
    graph = SFG(x, [Output(Negation(x)), Output(Absolute(x))])
    root = ET.fromstring(
        interactive_svg(graph, b'<svg xmlns="http://www.w3.org/2000/svg"/>', False)
    )
    nets = json.loads(root.find(SVG + "metadata").text)
    source = f"sfg-op-{graph.input_operations[0].graph_id}"
    selected = f"sfg-op-{graph.find_by_type(Negation)[0].graph_id}"
    sibling = f"sfg-op-{graph.find_by_type(Absolute)[0].graph_id}"
    output = f"sfg-op-{graph.output_operations[0].graph_id}"
    incoming = next(net for net in nets if net["operations"][0] == source)
    results = _run_svg_events(
        graph,
        root,
        [{"click": selected}, {"click": source}, {"click": incoming["elements"][0]}],
    )
    consumer_selection, source_selection, signal_selection = [
        set(result["connected"]) for result in results
    ]
    assert consumer_selection == {source, output}
    assert source_selection == {selected, sibling}
    assert signal_selection == {source, selected, sibling}


def test_legend_highlights_only_operations_and_clears_previous_selections():
    x, y = Input(), Input()
    graph = SFG([x, y], [Output(Negation(x)), Output(Negation(y)), Output(Absolute(x))])
    root = ET.fromstring(
        interactive_svg(graph, b'<svg xmlns="http://www.w3.org/2000/svg"/>', True)
    )
    types = json.loads(root.find(f"{SVG}metadata[@id='sfg-operation-types']").text)
    negative_index = next(
        index for index, entry in enumerate(types) if entry["name"] == "Negation"
    )
    absolute_index = next(
        index for index, entry in enumerate(types) if entry["name"] == "Absolute"
    )
    negative_button = f"sfg-legend-type-{negative_index}"
    absolute_button = f"sfg-legend-type-{absolute_index}"
    negatives = {f"sfg-op-{op.graph_id}" for op in graph.find_by_type(Negation)}
    absolute = f"sfg-op-{graph.find_by_type(Absolute)[0].graph_id}"
    wire = json.loads(root.find(f"{SVG}metadata[@id='sfg-connectivity']").text)[0][
        "elements"
    ][0]
    results = _run_svg_events(
        graph,
        root,
        [
            {"click": wire},
            {"click": negative_button, "child": True},
            {"click": absolute_button},
            {"click": absolute_button},
            {"click": negative_button},
            {"key": "Escape"},
            {"click": negative_button},
            {"click": min(negatives)},
            {"click": "background"},
        ],
    )
    assert results[0]["highlighted"]
    assert set(results[1]["selected"]) == negatives
    assert results[1]["pressed"] == [negative_button]
    assert results[1]["connected"] == results[1]["highlighted"] == []
    assert results[2]["selected"] == [absolute]
    assert results[2]["connected"] == results[2]["highlighted"] == []
    for index in (3, 5, 8):
        assert results[index]["selected"] == results[index]["pressed"] == []
        assert results[index]["connected"] == results[index]["highlighted"] == []
    assert len(results[7]["selected"]) == 1
    assert results[7]["highlighted"]
    assert results[7]["pressed"] == []


def test_legend_keyboard_selection_and_show_hide_control():
    source = Input()
    graph = SFG(source, Output(Negation(source)))
    root = ET.fromstring(
        interactive_svg(graph, b'<svg xmlns="http://www.w3.org/2000/svg"/>', False)
    )
    types = json.loads(root.find(f"{SVG}metadata[@id='sfg-operation-types']").text)
    index = next(
        index for index, entry in enumerate(types) if entry["name"] == "Negation"
    )
    button = f"sfg-legend-type-{index}"
    results = _run_svg_events(
        graph,
        root,
        [
            {"key": "Enter", "target": button},
            {"key": " ", "target": "sfg-legend-toggle"},
            {"key": "Enter", "target": "sfg-legend-toggle"},
            {"key": " ", "target": button},
        ],
    )
    assert results[0]["selected"] == types[index]["operations"]
    assert results[0]["legendVisible"]
    assert not results[1]["legendVisible"]
    assert results[1]["selected"] == results[0]["selected"]
    assert results[2]["legendVisible"]
    assert results[3]["selected"] == []


def test_disabling_legend_preserves_svg_bounds_and_operation_selection():
    source = Input()
    graph = SFG(source, Output(Negation(source)))
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="400pt" height="200pt" viewBox="0 0 200 100"/>'
    root = ET.fromstring(interactive_svg(graph, svg, False, legend=False))
    original = ET.fromstring(svg)

    assert root.attrib == original.attrib
    assert root.find(f"{SVG}metadata[@id='sfg-operation-types']") is None
    assert root.find(f"{SVG}g[@id='sfg-legend']") is None
    operation = f"sfg-op-{graph.find_by_type(Negation)[0].graph_id}"
    result = _run_svg_events(graph, root, [{"click": operation}])[0]
    assert result["selected"] == [operation]
    assert result["highlighted"]
    assert not result["legendVisible"]


def test_legend_preserves_svg_scale_and_deduplicates_operations():
    source = Input()
    graph = SFG(source, Output(source))
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="400pt" height="200pt" viewBox="0 0 200 100"/>'
    root = ET.fromstring(interactive_svg(graph, svg, False))
    _, _, width, height = map(float, root.get("viewBox").split())

    assert width > 200
    assert height >= 100
    assert float(root.get("width").removesuffix("pt")) / width == pytest.approx(2)
    assert float(root.get("height").removesuffix("pt")) / height == pytest.approx(2)
    types = json.loads(root.find(f"{SVG}metadata[@id='sfg-operation-types']").text)
    assert {entry["name"] for entry in types} == {"Input", "Output"}
    assert all(len(entry["operations"]) == 1 for entry in types)
    assert len(root.findall(f".//{SVG}g[@class='sfg-legend-item']")) == 2


def test_legend_distinguishes_operation_classes_with_same_type_name():
    class CustomNegation(Negation):
        __slots__ = ()

    source = Input()
    graph = SFG(source, [Output(Negation(source)), Output(CustomNegation(source))])
    root = ET.fromstring(
        interactive_svg(graph, b'<svg xmlns="http://www.w3.org/2000/svg"/>', False)
    )
    types = json.loads(root.find(f"{SVG}metadata[@id='sfg-operation-types']").text)
    index = next(
        index for index, entry in enumerate(types) if entry["name"] == "CustomNegation"
    )
    result = _run_svg_events(graph, root, [{"click": f"sfg-legend-type-{index}"}])[0]

    assert result["selected"] == types[index]["operations"]
    assert len(result["selected"]) == 1
    assert result["connected"] == result["highlighted"] == []


@pytest.mark.parametrize("legend", [False, True])
def test_empty_svg_has_no_legend(legend):
    root = ET.fromstring(
        interactive_svg(
            SFG(), b'<svg xmlns="http://www.w3.org/2000/svg"/>', False, legend=legend
        )
    )

    assert root.find(f"{SVG}g[@id='sfg-legend']") is None


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz dot is required")
@pytest.mark.parametrize(
    ("name", "title", "expected"),
    [
        ("", None, None),
        ("Example SFG", None, "Example SFG"),
        ("Example SFG", "Custom title", "Custom title"),
        ("Example SFG", "", None),
        ("<b>A & B</b> \\N", None, "<b>A & B</b> \\N"),
    ],
)
def test_graph_title_uses_graphviz_label(name, title, expected):
    source = Input()
    graph = SFG(source, Output(source), name=name)
    drawing = graph.display(title=title)
    root = ET.fromstring(drawing.pipe(format="svg"))
    graph_group = root.find(f"{SVG}g[@class='graph']")
    labels = [text.text for text in graph_group.findall(SVG + "text")]

    assert labels == ([] if expected is None else [expected])
    assert "sfg-legend" not in drawing.source
    assert graph.name == name


@pytest.mark.skipif(
    shutil.which("dot") is None,
    reason="Graphviz dot executable is required to render SVG",
)
@pytest.mark.parametrize("fmt", [None, "svg"])
@pytest.mark.parametrize("branch_node", [False, True])
@pytest.mark.parametrize("direction", ["LR", "TB"])
@pytest.mark.filterwarnings(
    "error:^Two signals connected to the same output port$:UserWarning"
)
def test_show_interactive_svg(monkeypatch, fmt, branch_node, direction):
    x, y = Input(), Input()
    butterfly = R2Butterfly(x, y, name="A < B & C")
    graph = SFG(
        [x, y],
        [
            Output(butterfly.output(0)),
            Output(butterfly.output(0)),
            Output(butterfly.output(1)),
        ],
        name="Example SFG",
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
    assert "Example SFG" in "".join(root.itertext())
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
    assert root.find(f"{SVG}g[@id='sfg-legend']") is not None
    types = json.loads(root.find(f"{SVG}metadata[@id='sfg-operation-types']").text)
    assert {entry["name"]: len(entry["operations"]) for entry in types} == {
        "Input": 2,
        "Output": 3,
        "R2Butterfly": 1,
    }
    assert all(set(entry["operations"]) <= ids for entry in types)


def test_show_explicit_format_uses_viewer(monkeypatch):
    x = Input()
    graph = SFG(x, Output(x), name="Default title")
    viewed = []

    def capture_graph(graph):
        viewed.append(graph)

    monkeypatch.setattr("graphviz.Digraph.view", capture_graph)
    graph.show(fmt="png", title="Custom title", legend=False)
    assert viewed[0].format == "png"
    assert "sfg-signal-" not in viewed[0].source
    assert 'label="Custom title"' in viewed[0].source
    assert "sfg-legend" not in viewed[0].source


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz dot is required")
def test_show_passes_title_and_disables_svg_legend(monkeypatch):
    source = Input()
    graph = SFG(source, Output(source), name="Default title")
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)

    graph.show(title="Custom title", legend=False)

    url = urlparse(opened[0])
    path = Path(
        unquote(url.path).lstrip("/") if url.path[2:3] == ":" else unquote(url.path)
    )
    try:
        root = ET.fromstring(path.read_bytes())
    finally:
        path.unlink()
    assert "Custom title" in "".join(root.itertext())
    assert "Default title" not in "".join(root.itertext())
    assert root.find(f"{SVG}g[@id='sfg-legend']") is None
