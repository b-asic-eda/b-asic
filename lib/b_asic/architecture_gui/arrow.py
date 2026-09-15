"""
B-ASIC Architecture-GUI Arrow Module.

Contains the MuxItem class drawing a small numbered-input multiplexer node
for fan-in ports, a helper drawing the labeled stub used for every
interconnect (instead of a line crossing the whole diagram), and a helper to
derive port-level interconnects from an
:class:`~b_asic.architecture.Architecture`, reusing
:meth:`~b_asic.architecture.Architecture.get_interconnects_for_pe` rather than
re-deriving edge/multiplexer logic for the GUI.
"""

from collections import defaultdict
from dataclasses import dataclass

from qtpy.QtCore import QPointF, Qt
from qtpy.QtGui import QBrush, QColor, QPen
from qtpy.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
)

from b_asic._preferences import MUX_COLOR
from b_asic.architecture import Architecture
from b_asic.architecture_gui.resource_item import ResourceItem
from b_asic.process import MemoryOutputPort

MUX_GAP = 30.0


@dataclass(frozen=True)
class PortEdge:
    """A single interconnect edge between two specific resource ports."""

    source: str
    source_port: int
    destination: str
    destination_port: int
    count: str


def get_port_edges(architecture: Architecture) -> list[PortEdge]:
    """
    Derive port-level interconnect edges for *architecture*.

    Reuses :meth:`Architecture.get_interconnects_for_pe`, the same lookup used
    for the graphviz rendering, so the exact source/destination port of each
    connection (and whether a destination port has more than one source, i.e.
    is multiplexed) is known without re-deriving the logic for the GUI.
    """
    edges: list[PortEdge] = []

    for pe in architecture.processing_elements:
        inputs, outputs = architecture.get_interconnects_for_pe(pe)
        for i, port_sources in enumerate(inputs):
            for (source, source_port), count in port_sources.items():
                edges.append(
                    PortEdge(
                        source.entity_name, source_port, pe.entity_name, i, str(count)
                    )
                )
        for o, port_destinations in enumerate(outputs):
            for (destination, dest_port), count in port_destinations.items():
                edges.append(
                    PortEdge(
                        pe.entity_name,
                        o,
                        destination.entity_name,
                        dest_port,
                        str(count),
                    )
                )

    # Memory-to-memory edges for chained lifetime-split variables, mirroring
    # Architecture._build_interconnect_edges but in terms of Resource objects.
    # Memory ports are not individually tracked by the model, so port 0 is
    # used, the same convention the private method itself uses.
    for dst_mem in architecture.memories:
        for mv in dst_mem:
            if not isinstance(mv.write_port, MemoryOutputPort):
                continue
            source_var = mv.write_port.source_variable
            for src_mem in architecture.memories:
                if any(v is source_var for v in src_mem):
                    edges.append(
                        PortEdge(src_mem.entity_name, 0, dst_mem.entity_name, 0, "1")
                    )
                    break

    return edges


class MuxItem(QGraphicsRectItem):
    """
    Small multiplexer node: a rectangle with *n_inputs* numbered rows on the
    left (one per source) and a single output on the right, in the same
    spirit as :meth:`Architecture._create_multiplexer_node`'s numbered-input
    table used for the graphviz rendering, simplified for the small scale of
    the GUI canvas.

    Parameters
    ----------
    n_inputs : int
        Number of multiplexer inputs.
    """

    WIDTH = 24.0
    ROW_HEIGHT = 16.0

    def __init__(self, n_inputs: int) -> None:
        self._n_inputs = max(n_inputs, 1)
        height = self._n_inputs * self.ROW_HEIGHT
        super().__init__(0, 0, self.WIDTH, height)
        self._height = height
        self.setBrush(QBrush(QColor(*MUX_COLOR)))
        self.setPen(QPen(Qt.GlobalColor.black, 1.0))
        self.setZValue(1)

        for i in range(self._n_inputs):
            y = (i + 0.5) * self.ROW_HEIGHT
            if i > 0:
                divider = QGraphicsLineItem(
                    0, i * self.ROW_HEIGHT, self.WIDTH, i * self.ROW_HEIGHT, self
                )
                divider.setPen(QPen(Qt.GlobalColor.black, 0.75))
            label = QGraphicsSimpleTextItem(str(i), self)
            label.setScale(0.7)
            label_rect = label.boundingRect()
            label.setPos(
                self.WIDTH / 2 - label_rect.width() * 0.7 / 2,
                y - label_rect.height() * 0.7 / 2,
            )

    @property
    def height(self) -> float:
        """Total height of the multiplexer symbol."""
        return self._height

    def input_point(self, index: int) -> QPointF:
        """Scene position of the *index*-th input (left side)."""
        return self.mapToScene(QPointF(0, (index + 0.5) * self.ROW_HEIGHT))

    def output_point(self) -> QPointF:
        """Scene position of the output (right side, mid-height)."""
        return self.mapToScene(QPointF(self.WIDTH, self._height / 2))


STUB_LENGTH = 16.0
MUX_MIN_GAP = 10.0


def _draw_stub(point: QPointF, text: str) -> list[QGraphicsItem]:
    """
    Draw a short dangling stub labeled with the other end's resource name,
    pointing left (towards where the signal "comes from") from an input
    port, instead of a full line connecting all the way back to its source.

    This is always used, for every connection, rather than only for
    long/backward ones: a label is cheap to read and never crosses other
    items, while a line spanning the whole left-to-right layout would.
    """
    end = QPointF(point.x() - STUB_LENGTH, point.y())
    line = QGraphicsLineItem(point.x(), point.y(), end.x(), end.y())
    line.setPen(QPen(QColor("black"), 1.2, Qt.PenStyle.DashLine))
    line.setZValue(-1)

    label = QGraphicsSimpleTextItem(text)
    label.setScale(0.8)
    label_width = label.boundingRect().width() * 0.8
    label.setPos(end.x() - label_width, end.y() - 9)
    return [line, label]


def _pack_mux_centers(specs: list[tuple[float, float, float]]) -> dict[int, float]:
    """
    Given a list of ``(x, desired_y, height)`` mux specs (indexed implicitly
    by their position in *specs*), return ``{index: y}`` with the minimum
    downward shift needed so muxes that share (approximately) the same x
    column never overlap vertically, instead of all being anchored on their
    own destination port and piling on top of each other.
    """
    by_x: dict[float, list[int]] = defaultdict(list)
    for index, (x, _, _) in enumerate(specs):
        by_x[round(x)].append(index)

    final_y: dict[int, float] = {}
    for indices in by_x.values():
        indices.sort(key=lambda i: specs[i][1])
        last_bottom = None
        for i in indices:
            _, desired_y, height = specs[i]
            top = desired_y - height / 2
            if last_bottom is not None and top < last_bottom + MUX_MIN_GAP:
                top = last_bottom + MUX_MIN_GAP
            last_bottom = top + height
            final_y[i] = top + height / 2
    return final_y


def build_interconnect_items(
    resource_items: dict[str, ResourceItem], edges: list[PortEdge]
) -> list[QGraphicsItem]:
    """
    Build the graphics items (mux nodes and labeled stubs) representing
    *edges*.

    Every destination port is always labeled with the entity name of each
    source that feeds it, via a short stub (see :func:`_draw_stub`) rather
    than a line connecting all the way back to the source: with a layout
    that can span many columns and feedback loops, a handful of crossing
    lines per resource reads far worse than a label. A destination port fed
    by more than one source (multiplexed) gets a :class:`MuxItem` with one
    such stub per numbered input, placed just before the destination port;
    muxes that would otherwise land on top of each other (because their
    destination ports are close together) are packed into the same column
    with a minimum gap between them, via :func:`_pack_mux_centers`.

    Parameters
    ----------
    resource_items : dict
        Mapping from resource entity name to its :class:`ResourceItem`,
        reflecting their current (possibly user-moved) positions.
    edges : list of :class:`PortEdge`
        Edges as returned by :func:`get_port_edges`.
    """
    by_destination_port: dict[tuple[str, int], list[PortEdge]] = defaultdict(list)
    for edge in edges:
        by_destination_port[(edge.destination, edge.destination_port)].append(edge)

    items: list[QGraphicsItem] = []
    mux_groups: list[tuple[QPointF, list[PortEdge]]] = []
    mux_specs: list[tuple[float, float, float]] = []

    for (destination, dest_port), port_edges in by_destination_port.items():
        dest_item = resource_items.get(destination)
        if dest_item is None:
            continue
        dest_point = dest_item.mapToScene(dest_item.input_port_pos(dest_port))

        sources = [edge for edge in port_edges if edge.source in resource_items]
        if not sources:
            continue

        if len(sources) == 1:
            items.extend(_draw_stub(dest_point, sources[0].source))
            continue

        height = len(sources) * MuxItem.ROW_HEIGHT
        mux_groups.append((dest_point, sources))
        mux_specs.append(
            (dest_point.x() - MUX_GAP - MuxItem.WIDTH / 2, dest_point.y(), height)
        )

    mux_centers_y = _pack_mux_centers(mux_specs)

    for index, (dest_point, sources) in enumerate(mux_groups):
        x_center, _, _ = mux_specs[index]
        y_center = mux_centers_y[index]

        mux_item = MuxItem(len(sources))
        mux_item.setPos(x_center - MuxItem.WIDTH / 2, y_center - mux_item.height / 2)
        items.append(mux_item)

        for i, edge in enumerate(sources):
            items.extend(_draw_stub(mux_item.input_point(i), edge.source))

        output_point = mux_item.output_point()
        out_line = QGraphicsLineItem(
            output_point.x(), output_point.y(), dest_point.x(), dest_point.y()
        )
        out_line.setPen(QPen(QColor("black"), 1.2))
        out_line.setZValue(-1)
        items.append(out_line)

    return items
