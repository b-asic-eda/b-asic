#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B-ASIC Scheduler-gui Graphics Timeline Item Module.

Contains the a scheduler-gui GraphicsTimelineItem class for drawing and maintain the timeline in a graph.
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
    Qt, QObject, QRect, QRectF, QPoint, QSize, QSizeF, QByteArray, qAbs, QLineF)
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



class GraphicsTimelineItem(QGraphicsLineItem):
    """A class to represent the timeline in GraphicsAxesItem."""
    
    # _scale:             float
    _delta_time_label:  QGraphicsTextItem
    
    @overload
    def __init__(self, line: QLineF, parent: Optional[QGraphicsItem] = None) -> None:
        """Constructs a GraphicsTimelineItem out of 'line'. 'parent' is passed to
        QGraphicsLineItem's constructor."""
        ...
    @overload
    def __init__(self, parent:Optional[QGraphicsItem] = None) -> None:
        """Constructs a GraphicsTimelineItem. 'parent' is passed to
        QGraphicsLineItem's constructor."""
        ...
    @overload
    def __init__(self, x1: float, y1: float, x2: float, y2: float, parent:Optional[QGraphicsItem] = None) -> None:
        """Constructs a GraphicsTimelineItem from (x1, y1) to (x2, y2). 'parent' is
        passed to QGraphicsLineItem's constructor."""
        ...
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
            
        self.setFlag(QGraphicsItem.ItemIsMovable)       # mouse move events
        self.setAcceptHoverEvents(True)                 # mouse hover events
        self.setAcceptedMouseButtons(Qt.LeftButton)     # accepted buttons for movements
        
        self._delta_time_label = QGraphicsTextItem()
        self._delta_time_label.hide()
        self._delta_time_label.setScale(1.05/75)        # TODO: dont hardcode scale
        self._delta_time_label.setParentItem(self)
        x_pos = - self._delta_time_label.mapRectToParent(self._delta_time_label.boundingRect()).width()/2
        y_pos = 1.05 * self.line().dy()
        self._delta_time_label.setPos(x_pos, y_pos)
        # pen = QPen(Qt.black)
        # self._delta_time_label.setPen(pen)
        
        
    # @property
    # def label(self) -> None:
    #     return self._delta_time_label
    
    def set_text(self, number: int) -> None:
        """Set the label text to 'number'."""
        # self.prepareGeometryChange()
        self._delta_time_label.setPlainText(f'( {number:+} )')
        self._delta_time_label.setX(- self._delta_time_label.mapRectToParent(self._delta_time_label.boundingRect()).width()/2)
        
    # def set_text_pen(self, pen: QPen) -> None:
    #     """Set the label pen to 'pen'."""
    #     self._delta_time_label.setPen(pen)
        
    # def set_label_visible(self, visible: bool) -> None:
    #     """If visible is True, the item is made visible. Otherwise, the item is
    #     made invisible"""
    #     self._delta_time_label.setVisible(visible)
    
    def show_label(self) -> None:
        """Show the label (label are not visible by default). This convenience
        function is equivalent to calling set_label_visible(True)."""
        self._delta_time_label.show()
    
    def hide_label(self) -> None:
        """Hide the label (label are not visible by default). This convenience
        function is equivalent to calling set_label_visible(False)."""
        self._delta_time_label.hide()
        
    def set_text_scale(self, scale: float) -> None:
        self._delta_time_label.setScale(scale)

    @property
    def event_items(self) -> List[QGraphicsItem]:
        """Returnes a list of objects, that receives events."""
        return [self]
