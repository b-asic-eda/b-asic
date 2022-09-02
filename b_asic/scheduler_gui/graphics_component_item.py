#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-ASIC Scheduler-gui Graphics Component Item Module.

Contains the scheduler-gui GraphicsComponentItem class for drawing and maintain a component in a graph.
"""
from typing import (
    Union, Optional, Dict, List)

# QGraphics and QPainter imports
from qtpy.QtCore    import Qt, QPointF
from qtpy.QtGui     import QPainterPath, QColor, QBrush, QPen, QCursor
from qtpy.QtWidgets import (
    QGraphicsItem, QGraphicsItemGroup, QGraphicsPathItem, QGraphicsRectItem,
    QGraphicsSimpleTextItem, QGraphicsEllipseItem)

# B-ASIC
from b_asic.graph_component     import GraphComponent


class GraphicsComponentItem(QGraphicsItemGroup):
    """A class to represent an component in a graph."""
    _scale:                 float = 1.0
    """Static, changed from MainWindow."""
    _operation:             GraphComponent
    _height:                float
    _ports:                 Dict[str, Dict[str, Union[float, QPointF]]]     # ['port-id']['latency/pos']
    _end_time:              int
    _component_item:        QGraphicsPathItem
    _execution_time_item:   QGraphicsRectItem
    _label_item:            QGraphicsSimpleTextItem
    _port_items:            List[QGraphicsEllipseItem]


    def __init__(self, operation: GraphComponent, height: float = 0.75, parent: Optional[QGraphicsItem] = None):
        """Constructs a GraphicsComponentItem. 'parent' is passed to QGraphicsItemGroup's constructor."""
        super().__init__(parent=parent)
        self._operation = operation
        self._height = height
        self._ports = {k:{'latency':float(v)} for k,v in operation.latency_offsets.items()}
        self._end_time = max(operation.latency_offsets.values())
        self._port_items = []

        self.setFlag(QGraphicsItem.ItemIsMovable)       # mouse move events
        self.setFlag(QGraphicsItem.ItemIsSelectable)    # mouse move events
        # self.setAcceptHoverEvents(True)                 # mouse hover events
        self.setAcceptedMouseButtons(Qt.LeftButton)     # accepted buttons for movements
        self.setCursor(QCursor(Qt.OpenHandCursor))      # default cursor when hovering over object

        self._make_component()

    # def sceneEvent(self, event: QEvent) -> bool:
    #     print(f'Component -->\t\t\t\t{event.type()}')
    #     # event.accept()
    #     # QApplication.sendEvent(self.scene(), event)
    #     return True


    def clear(self) -> None:
        """Sets all children's parent to 'None' and delete the axis."""
        for item in self.childItems():
            item.setParentItem(None)
            del item


    @property
    def op_id(self) -> str:
        """Get the op-id."""
        return self._operation.graph_id

    @property
    def operation(self) -> GraphComponent:
        """Get the operation."""
        return self._operation

    @property
    def height(self) -> float:
        """Get or set the current component height. Setting the height to a new
        value will update the component automatically."""
        return self._height

    @height.setter
    def height(self, height: float) -> None:
        if self._height != height:
            self.clear()
            self._height = height
            self._make_component()

    @property
    def end_time(self) -> int:
        """Get the relative end time."""
        return self._end_time

    @property
    def event_items(self) -> List[QGraphicsItem]:
        """Returnes a list of objects, that receives events."""
        return [self]

    def get_port_location(self, key) -> QPointF:
        return self.mapToParent(self._ports[key]['pos'])

    def _make_component(self) -> None:
        """Makes a new component out of the stored attributes."""
        brush1 = QBrush(Qt.lightGray)       # used by component filling
        pen1 = QPen(Qt.black)               # used by component outline
        pen1.setWidthF(2/self._scale)
        # pen1.setCapStyle(Qt.RoundCap)     # Qt.FlatCap, Qt.SquareCap (default), Qt.RoundCap
        pen1.setJoinStyle(Qt.RoundJoin)     # Qt.MiterJoin, Qt.BevelJoin (default), Qt.RoundJoin, Qt.SvgMiterJoin

        brush2 = QBrush(Qt.black)           # used by port filling
        pen2 = QPen(Qt.black)               # used by port outline
        pen2.setWidthF(0)
        # pen2.setCosmetic(True)
        port_size = 7/self._scale           # the diameter of an port

        gray = QColor(Qt.gray)
        gray.setAlpha(100)                  # 0-255
        green = QColor(Qt.magenta)
        green.setAlpha(200)                 # 0-255
        pen3 = QPen()                       # used by execution time outline
        pen3.setColor(green)
        pen3.setWidthF(3/self._scale)


        ## component path
        def draw_component_path(keys: List[str], revered: bool) -> None:
            """Draws component path and also register port positions in self._ports dictionary."""
            nonlocal x
            nonlocal y
            nonlocal old_x
            nonlocal old_y
            neg = 1
            if revered: neg = -1
            for key in keys:
                # draw 1 or 2 lines
                x = self._ports[key]['latency']
                if x != old_x:                                  # Draw horizontal line only
                    component_path.lineTo(x, y)                 # if we need to.
                y = old_y + neg*(self._height / len(keys))
                component_path.lineTo(x, y)                     # vertical line
                # register the port pos in dictionary
                port_x = x                                      # Port coords is at the center
                port_y = y - neg*abs(y - old_y)/2               # of previous vertical line.
                self._ports[key]['pos'] = QPointF(port_x, port_y)
                # update last pos
                old_x = x
                old_y = y

        # make lists of sorted keys. reverse output port list.
        input_keys = [key for key in self._ports.keys() if key.lower().startswith("in")]
        input_keys = sorted(input_keys)
        output_keys = [key for key in self._ports.keys() if key.lower().startswith("out")]
        output_keys = sorted(output_keys, reverse=True)

        # Set the starting position
        if input_keys:
            x = self._ports[input_keys[0]]['latency']
        else:
            x = 0
        y = 0
        old_x = x
        old_y = y
        component_path = QPainterPath(QPointF(x, y))            # starting point

        # draw the path
        draw_component_path(input_keys, False)                  # draw input side
        draw_component_path(output_keys, True)                  # draw ouput side
        component_path.closeSubpath()


        ## component item
        self._component_item = QGraphicsPathItem(component_path)
        self._component_item.setPen(pen1)
        self._component_item.setBrush(brush1)

        ## ports item
        for port_dict in self._ports.values():
            port_pos = self.mapToParent(port_dict['pos'])
            port = QGraphicsEllipseItem(-port_size/2, -port_size/2, port_size, port_size)   # center of circle is in origo
            port.setPen(pen2)
            port.setBrush(brush2)
            port.setPos(port_pos.x(), port_pos.y())
            self._port_items.append(port)

        ## op-id/label
        self._label_item = QGraphicsSimpleTextItem(self._operation.graph_id)
        self._label_item.setScale(self._label_item.scale() / self._scale)
        center = self._component_item.boundingRect().center()
        center -= self._label_item.boundingRect().center() / self._scale
        self._label_item.setPos(self._component_item.pos() + center)

        ## execution time
        if self._operation.execution_time:
            self._execution_time_item = QGraphicsRectItem(0, 0, self._operation.execution_time, self._height)
            self._execution_time_item.setPen(pen3)
            # self._execution_time_item.setBrush(brush3)

        ## item group, consist of component_item, port_items and execution_time_item
        self.addToGroup(self._component_item)
        for port in self._port_items:
            self.addToGroup(port)
        self.addToGroup(self._label_item)
        if self._operation.execution_time:
            self.addToGroup(self._execution_time_item)
