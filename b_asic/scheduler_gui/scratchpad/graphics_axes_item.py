#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-ASIC Scheduler-gui Graphics Axes Item Module.

Contains the scheduler-gui GraphicsAxesItem class for drawing and maintain the axes in a graph.
"""
from operator import contains
import os
import sys
from typing     import Any, Optional
from pprint     import pprint
from typing     import Any, Union, Optional, overload, Final, final, Dict, List
# from typing_extensions import Self, Final, Literal, LiteralString, TypeAlias, final
import numpy    as np
from copy       import deepcopy
from math       import cos, sin, pi

import qtpy
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets

# QGraphics and QPainter imports
from qtpy.QtCore    import (
    Qt, QObject, QRect, QRectF, QPoint, QSize, QSizeF, QByteArray, qAbs)
from qtpy.QtGui     import (
    QPaintEvent, QPainter, QPainterPath, QColor, QBrush, QPen, QFont, QPolygon, QIcon, QPixmap,
    QLinearGradient, QTransform, QPolygonF)
from qtpy.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsWidget,
    QGraphicsLayout, QGraphicsLinearLayout, QGraphicsGridLayout, QGraphicsLayoutItem, QGraphicsAnchorLayout,
    QGraphicsItem, QGraphicsItemGroup, QGraphicsPathItem, QGraphicsLineItem, QGraphicsTextItem, QGraphicsRectItem,
    QStyleOptionGraphicsItem, QWidget, QGraphicsObject, QGraphicsSimpleTextItem, QGraphicsPolygonItem)
from qtpy.QtCore    import (
    QPoint, QPointF)

# B-ASIC
import logger
from graphics_timeline_item import GraphicsTimelineItem



class GraphicsAxesItem(QGraphicsItemGroup):
    """A class to represent axes in a graph."""
    _scale:         float = 1.0
    """Static, changed from MainWindow."""
    _width:         float
    _width_padding: float
    _height:        float
    _dy_height:     float
    _x_indent:      float
    _axes:          Dict[str, Union[QGraphicsItemGroup, QGraphicsLineItem]]
    _event_items:   List[QGraphicsItem]
    _timeline:      GraphicsTimelineItem
    

    def __init__(self, width: float, height: float, x_indent: float  = 0.2, parent: Optional[QGraphicsItem] = None):
        """Constructs a GraphicsAxesItem. 'parent' is passed to QGraphicsItemGroup's constructor."""
        super().__init__(parent)

        self._width = width
        self._width_padding = 0.6
        self._padded_width = width + self._width_padding
        self._height = height
        self._dy_height = 5/self._scale
        self._x_indent = x_indent
        self._axes = {}
        self._event_items = []
        # self._timeline = GraphicsTimelineItem()
        # self._event_items.append(self._timeline)

        self._make_axes()


    def clear(self) -> None:
        """Sets all children's parent to 'None' and delete the axes."""
        # self._timeline.setParentItem(None)
        self._event_items = []
        keys = list(self._axes.keys())
        for key in keys:
            self._axes[key].setParentItem(None)
            del self._axes[key]
    

    @property
    def width(self) -> float:
        """Get or set the current x-axis width. Setting the width to a new
        value will update the axes automatically."""
        return self._width
    @width.setter
    def width(self, width: float) -> None:
        if self._width != width:
            self.update_axes(width = width)

    @property
    def height(self) -> float:
        """Get or set the current y-axis height. Setting the height to a new
        value will update the axes automatically."""
        return self._height
    @height.setter
    def height(self, height: float) -> None:
        if self._height != height:
            self.update_axes(height = height)
    
    @property
    def x_indent(self) -> float:
        """Get or set the current x-axis indent. Setting the indent to a new
        value will update the axes automatically."""
        return self._x_indent
    @x_indent.setter
    def x_indent(self, x_indent: float) -> None:
        if self._x_indent != x_indent:
            self.update_axes(x_indent = x_indent)
    
    @property
    def event_items(self) -> List[QGraphicsItem]:
        """Returnes a list of objects, that receives events."""
        return self._event_items
    
    @property
    def timeline(self) -> GraphicsTimelineItem:
        return self._timeline

    def _register_event_item(self, item: QGraphicsItem) -> None:
        """Register an object that receives events."""
        # item.setFlag(QGraphicsItem.ItemIsMovable)       # mouse move events
        # item.setAcceptHoverEvents(True)                 # mouse hover events
        # item.setAcceptedMouseButtons(Qt.LeftButton)     # accepted buttons for movements
        self._event_items.append(item)


    def update_axes(self, width: Optional[float] = None, height: Optional[float] = None, x_indent: Optional[float] = None) -> None:
        """Updates the current axes with the new 'width', 'height' and 'x_indent'. If any of the
        parameters is omitted, the stored value will be used."""
        if width is not None:
            self._width = width
            self._padded_width = width + self._width_padding
        if height is not None:   self._height = height
        if x_indent is not None: self._x_indent = x_indent
        print(width is not None or height is not None or x_indent is not None)
        if (width is not None
            or height is not None
            or x_indent is not None):
            self.clear()
            self._make_axes()


    def _make_axes(self) -> None:
        """Makes new axes out of the stored attributes."""
        # self.prepareGeometryChange()
        ## define pencils
        pen = QPen()
        pen.setWidthF(2/self._scale)
        pen.setJoinStyle(Qt.MiterJoin)
        ledger_pen = QPen(Qt.lightGray)
        ledger_pen.setWidthF(0)         # 0 = cosmetic pen 1px width
        
        ## x-axis
        self._axes['x'] = QGraphicsItemGroup()
        line = QGraphicsLineItem(0, 0, self._padded_width, 0)
        line.setPen(pen)
        self._axes['x'].addToGroup(line)
        # x-axis arrow
        arrow_size = 8/self._scale
        p0 = QPointF(0, sin(pi/6) * arrow_size)
        p1 = QPointF(arrow_size, 0)
        p2 = QPointF(0, -sin(pi/6) * arrow_size)
        polygon = QPolygonF([p0, p1, p2])
        arrow = QGraphicsPolygonItem(polygon)
        arrow.setPen(pen)
        arrow.setBrush(QBrush(Qt.SolidPattern))
        arrow.setPos(self._padded_width, 0)
        self._axes['x'].addToGroup(arrow)
        # x-axis scale
        x_scale = []
        x_scale_labels = []
        x_ledger = []
        self._axes['x_ledger'] = QGraphicsItemGroup()
        for i in range(int(self._padded_width) + 1):
            x_pos = QPointF(self.x_indent + i, 0)
            # vertical x-scale
            x_scale.append(QGraphicsLineItem(0, 0, 0, 0.05))
            x_scale[i].setPen(pen)
            x_scale[i].setPos(x_pos)
            self._axes['x'].addToGroup(x_scale[i])
            # numbers
            x_scale_labels.append(QGraphicsSimpleTextItem(str(i)))
            x_scale_labels[i].setScale(x_scale_labels[i].scale() / self._scale)
            center = x_pos - self.mapFromItem(x_scale_labels[i], x_scale_labels[i].boundingRect().center())
            x_scale_labels[i].setPos(center + QPointF(0, 0.2))
            self._axes['x'].addToGroup(x_scale_labels[i])
            # vertical x-ledger
            if i == int(self.width):                                       # last line is a timeline
                ledger_pen.setWidthF(2/self._scale)
                ledger_pen.setStyle(Qt.DashLine)
                ledger_pen.setColor(Qt.black)
                # self._timeline.setLine(0, 0, 0, self.height)
                # x_ledger.append(self._timeline)
                self._timeline = GraphicsTimelineItem(0, 0, 0, self.height)
                self._timeline.set_text_scale(1.05/self._scale)
                x_ledger.append(self._timeline)
                self._register_event_item(x_ledger[i])
            else:
                x_ledger.append(QGraphicsLineItem(0, 0, 0, self.height))
            x_ledger[i].setPen(ledger_pen)
            x_ledger[i].setPos(x_pos)
            self._axes['x_ledger'].addToGroup(x_ledger[i])
        # x-axis label
        label = QGraphicsSimpleTextItem('time')
        label.setScale(label.scale() / self._scale)
        center = self.mapFromItem(arrow, arrow.boundingRect().center())     # =center of arrow
        center -= self.mapFromItem(label, label.boundingRect().center())    # -center of label
        label.setPos(center + QPointF(0, 0.2))                              # move down under arrow
        self._axes['x'].addToGroup(label)

        # y-axis
        self._axes['y'] = QGraphicsLineItem(0, 0, 0, self.height + self._dy_height)
        self._axes['y'].setPen(pen)
        
        # put it all together
        self._axes['x_ledger'].setPos(0, self._dy_height)
        self.addToGroup(self._axes['x_ledger'])
        self._axes['x'].setPos(0, self.height + self._dy_height)
        self.addToGroup(self._axes['x'])
        self.addToGroup(self._axes['y'])
        