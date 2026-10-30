#!/usr/bin/env python3
"""
B-ASIC Architecture-GUI Module.

Contains the architecture_gui MainWindow class for visualizing an
Architecture: click on resources/processes to inspect them, drag processes
between resources to reassign them, and have the interconnects redraw
automatically.

Start main-window with ``start_architecture_gui()``.
"""

import sys
from collections import defaultdict, deque
from itertools import chain

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from qtpy.QtCore import QPointF
from qtpy.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QMainWindow,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from b_asic.architecture import Architecture, Process, Resource
from b_asic.architecture_gui.arrow import (
    STUB_LENGTH,
    build_interconnect_items,
    get_port_edges,
)
from b_asic.architecture_gui.process_item import ProcessItem
from b_asic.architecture_gui.resource_item import ResourceItem

ROW_GAP = 30.0
COLUMN_GAP_MARGIN = 40.0
MIN_COLUMN_GAP = 90.0


def _label_width(text: str) -> float:
    """Compute the rendered width of a stub label (see ``arrow._draw_stub``), in scene units."""
    item = QGraphicsSimpleTextItem(text)
    item.setScale(0.8)
    return item.boundingRect().width() * 0.8


def _compute_layers(resource_names: list[str], edges: list) -> dict[str, int]:
    """
    Assign each resource a left-to-right column (layer) by data flow, so
    dataflow runs left-to-right like :meth:`Architecture._digraph`'s default
    ``rankdir=LR`` rendering, without depending on graphviz for layout.

    A breadth-first search from the resources with no predecessors (the
    "source" resources, typically inputs) assigns each resource the distance
    (in edges) from the nearest such root. Self-loops are ignored, and BFS
    naturally tolerates feedback cycles since each resource is only leveled
    once.
    """
    successors: dict[str, set[str]] = defaultdict(set)
    has_predecessor: set[str] = set()
    for edge in edges:
        if edge.source == edge.destination:
            continue
        successors[edge.source].add(edge.destination)
        has_predecessor.add(edge.destination)

    roots = [name for name in resource_names if name not in has_predecessor]
    if not roots:
        roots = resource_names[:1]

    layer: dict[str, int] = dict.fromkeys(roots, 0)
    frontier = deque(roots)
    while frontier:
        name = frontier.popleft()
        for successor in successors[name]:
            if successor not in layer:
                layer[successor] = layer[name] + 1
                frontier.append(successor)

    for name in resource_names:
        layer.setdefault(name, 0)
    return layer


class ArchitectureMainWindow(QMainWindow):
    """Visual editor for an :class:`~b_asic.architecture.Architecture`."""

    def __init__(self, architecture: Architecture | None = None) -> None:
        super().__init__()
        self.setWindowTitle("B-ASIC Architecture GUI")
        self._architecture: Architecture | None = None
        self._resource_items: dict[str, ResourceItem] = {}
        self._process_items: dict[Process, ProcessItem] = {}
        self._interconnect_items: list = []
        self._resource_positions: dict[str, QPointF] = {}

        self._scene = QGraphicsScene()
        self._view = QGraphicsView(self._scene)

        self._inspector_title = QPlainTextEdit()
        self._inspector_title.setReadOnly(True)
        self._inspector_title.setMaximumHeight(120)
        self._inspector_figure = Figure(figsize=(6, 5), layout="constrained")
        self._inspector_canvas = FigureCanvas(self._inspector_figure)
        self._inspector_canvas.setMinimumWidth(350)

        inspector = QWidget()
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.addWidget(self._inspector_title)
        inspector_layout.addWidget(self._inspector_canvas, stretch=1)

        self._splitter = QSplitter()
        self._splitter.addWidget(self._view)
        self._splitter.addWidget(inspector)
        self._splitter.setStretchFactor(0, 2)
        self._splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self._splitter)

        self.statusBar().showMessage("Ready")
        self.resize(1400, 800)
        self._splitter.setSizes([900, 500])

        if architecture is not None:
            self.open(architecture)

    @property
    def architecture(self) -> Architecture | None:
        """The currently displayed architecture."""
        return self._architecture

    def open(self, architecture: Architecture) -> None:
        """Display *architecture*."""
        self._architecture = architecture
        self.rebuild_scene()

    def rebuild_scene(self) -> None:
        """Rebuild the entire scene from the current state of the architecture."""
        self._scene.clear()
        self._resource_items.clear()
        self._process_items.clear()
        self._interconnect_items.clear()
        if self._architecture is None:
            return
        self._layout_resources()
        self._layout_processes()
        self.redraw_interconnects()
        self._scene.setSceneRect(
            self._scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
        )

    def _layout_resources(self) -> None:
        """
        Lay resources out left-to-right in columns by data-flow layer (see
        :func:`_compute_layers`), except for resources the user has manually
        dragged, which keep their last position (see
        :meth:`on_resource_moved`).
        """
        architecture = self._architecture
        resources = {
            r.entity_name: r
            for r in chain(architecture.processing_elements, architecture.memories)
        }
        edges = get_port_edges(architecture)
        layer = _compute_layers(list(resources), edges)

        by_layer: dict[int, list[str]] = defaultdict(list)
        for name in resources:
            by_layer[layer[name]].append(name)
        for names in by_layer.values():
            names.sort()

        # Every interconnect is drawn as a labeled stub (see arrow.py), so the
        # gap between columns must fit the longest resource name used as a
        # label, or labels overlap the next column's boxes.
        column_gap = max(
            MIN_COLUMN_GAP,
            2 * STUB_LENGTH
            + COLUMN_GAP_MARGIN
            + max((_label_width(name) for name in resources), default=0.0),
        )

        x = 0.0
        for layer_index in sorted(by_layer):
            y = 0.0
            max_width = 0.0
            for name in by_layer[layer_index]:
                item = ResourceItem(resources[name], self)
                item.setPos(self._resource_positions.get(name, QPointF(x, y)))
                self._scene.addItem(item)
                self._resource_items[name] = item
                y += item.rect().height() + ROW_GAP
                max_width = max(max_width, item.rect().width())
            x += max_width + column_gap

    def _layout_processes(self) -> None:
        architecture = self._architecture
        for resource in chain(architecture.processing_elements, architecture.memories):
            resource_item = self._resource_items[resource.entity_name]
            for i, process in enumerate(resource.collection):
                process_item = ProcessItem(process, resource.entity_name, self)
                local_pos = resource_item.process_slot_pos(i)
                scene_pos = resource_item.mapToScene(local_pos)
                process_item.setPos(scene_pos)
                self._scene.addItem(process_item)
                self._process_items[process] = process_item

    def redraw_interconnects(self) -> None:
        """
        Redraw all interconnects (arrows and mux symbols) from the resource
        items' current positions, without touching the resources or
        processes themselves.
        """
        for item in self._interconnect_items:
            self._scene.removeItem(item)
        self._interconnect_items.clear()
        edges = get_port_edges(self._architecture)
        self._interconnect_items = build_interconnect_items(self._resource_items, edges)
        for item in self._interconnect_items:
            self._scene.addItem(item)

    def on_resource_moved(self, resource_item: ResourceItem) -> None:
        """
        Keep *resource_item*'s processes attached and remember its new position
        while it is being dragged, so it survives the next :meth:`rebuild_scene`,
        and redraw the interconnects to follow it.
        """
        self._resource_positions[resource_item.resource.entity_name] = (
            resource_item.pos()
        )
        for i, process in enumerate(resource_item.resource.collection):
            process_item = self._process_items.get(process)
            if process_item is not None:
                local_pos = resource_item.process_slot_pos(i)
                process_item.setPos(resource_item.mapToScene(local_pos))
        self.redraw_interconnects()

    def snap_process_back(self, process_item: ProcessItem) -> None:
        """
        Reset *process_item* to its slot position within its current
        resource (used when a drag ends without changing resources), without
        rebuilding the rest of the scene.
        """
        resource_item = self._resource_items[process_item.resource_name]
        index = list(resource_item.resource.collection).index(process_item.process)
        process_item.setPos(
            resource_item.mapToScene(resource_item.process_slot_pos(index))
        )
        self.redraw_interconnects()

    def resource_item_at(self, scene_pos: QPointF) -> ResourceItem | None:
        """Return the :class:`ResourceItem` whose box contains *scene_pos*, if any."""
        for item in self._resource_items.values():
            if item.sceneBoundingRect().contains(scene_pos):
                return item
        return None

    def try_move_process(
        self, process: Process, source_name: str, destination_name: str
    ) -> bool:
        """
        Attempt to move *process* from resource *source_name* to *destination_name*.

        On success, the scene is rebuilt and interconnects are redrawn. On
        failure (e.g. incompatible resource type), the scene is rebuilt
        unchanged, which snaps the dragged item back to its original
        position, and an error is shown in the status bar.
        """
        try:
            self._architecture.move_process(
                process, source_name, destination_name, assign=False
            )
        except (TypeError, KeyError) as e:
            self.statusBar().showMessage(f"Could not move process: {e}", 5000)
            self.rebuild_scene()
            return False
        print(
            f"architecture.move_process({process.name!r}, {source_name!r},"
            f" {destination_name!r})"
        )
        self.statusBar().showMessage(
            f"Moved {process.name!r} to {destination_name!r}", 3000
        )
        self.rebuild_scene()
        return True

    def show_resource_inspector(self, resource: Resource) -> None:
        """Show information about *resource* and plot its content."""
        lines = [f"Resource: {resource.entity_name}"]
        lines.append(f"Type: {type(resource).__name__}")
        lines.append(f"Processes ({len(resource.collection)}):")
        lines.extend(f"  {process.name}" for process in resource.collection)
        self._inspector_title.setPlainText("\n".join(lines))

        self._inspector_figure.clear()
        ax = self._inspector_figure.add_subplot(111)
        resource.plot_content(ax)
        self._inspector_canvas.draw()

    def show_process_inspector(self, process: Process, resource_name: str) -> None:
        """Show information about a single *process*."""
        lines = [
            f"Process: {process.name}",
            f"On resource: {resource_name}",
            f"Start time: {process.start_time}",
            f"Execution time: {process.execution_time}",
        ]
        self._inspector_title.setPlainText("\n".join(lines))
        self._inspector_figure.clear()
        self._inspector_canvas.draw()


def start_architecture_gui(
    architecture: Architecture | None = None,
) -> "ArchitectureMainWindow":
    """
    Start the Architecture GUI.

    Parameters
    ----------
    architecture : :class:`~b_asic.architecture.Architecture`, optional
        The architecture to start the editor with.

    Returns
    -------
    ArchitectureMainWindow
        The main window (kept open until the application exits).
    """
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()

    window = ArchitectureMainWindow(architecture)
    window.show()
    app.exec_()
    return window


if __name__ == "__main__":
    start_architecture_gui()
