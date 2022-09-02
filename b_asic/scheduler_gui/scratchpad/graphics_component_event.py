#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""TODO"""

import os
import sys
from typing     import Any, Optional
from pprint     import pprint
from typing     import Any, AnyStr, Generic, Protocol, TypeVar, Union, Optional, overload, Final, final
# from typing_extensions import Self, Final, Literal, LiteralString, TypeAlias, final
import numpy    as np
from copy       import deepcopy
from itertools  import combinations

import qtpy
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets

# QGraphics and QPainter imports
from qtpy.QtCore    import (
    Qt, QObject, QRect, QRectF, QPoint, QSize, QSizeF, QByteArray, Slot)
from qtpy.QtGui     import (
    QPaintEvent, QPainter, QPainterPath, QColor, QBrush, QPen, QFont, QPolygon, QIcon, QPixmap,
    QLinearGradient, QTransform, QCursor)
from qtpy.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsWidget,
    QGraphicsLayout, QGraphicsLinearLayout, QGraphicsGridLayout, QGraphicsLayoutItem, QGraphicsAnchorLayout,
    QGraphicsItem, QGraphicsItemGroup, QGraphicsPathItem, QGraphicsLineItem, QGraphicsRectItem,
    QStyleOptionGraphicsItem, QWidget,
    QGraphicsObject, QGraphicsSceneMouseEvent, QGraphicsSceneHoverEvent, QGraphicsSceneContextMenuEvent)
from qtpy.QtCore    import (
    QPoint, QPointF)



class GraphicsComponentEvent(QGraphicsItem):
    """Event handler for GraphicsComponentItem"""

    current_pos: QPointF
    # _scale: float

    def __init__(self, parent):
        super().__init__()
        # self.setAcceptedMouseButtons(Qt.LeftButton)
        # self.setAcceptedMouseButtons(Qt.NoButton)
        # self.setFlag(QGraphicsItem.ItemIsMovable)
        # self.setFlag(QGraphicsItem.ItemIsSelectable)
        # self.setAcceptHoverEvents(True)
        # self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Set the position of the graphical element in the graphic scene, 
        translate coordinates of the cursor within the graphic element 
        in the coordinate system of the parent object"""
        # Qt.DragMoveCursor
        dx = (self.mapToParent(event.pos()) - self.current_pos).x()
        if dx > 5.05:
            # TODO: send signal
            self.setX(self.x() + 10.0)
            self.current_pos.setX(self.current_pos.x() + 10.0)
        elif dx < -5.05:
            # TODO: send signal
            self.setX(self.x() - 10-0)
            self.current_pos.setX(self.current_pos.x() - 10.0)

 
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Changes the cursor to ClosedHandCursor when grabbing an object"""
        print('GraphicsComponentEvent.mousePressEvent()')
        self.current_pos = self.mapToParent(event.pos())
        self.setCursor(QCursor(Qt.ClosedHandCursor))
        event.accept()
 
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Changes the cursor to OpenHandCursor when releasing an object"""
        print('GraphicsComponentEvent.mouseReleaseEvent()')
        self.setCursor(QCursor(Qt.OpenHandCursor))
        event.accept()
    
    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Changes the cursor to OpenHandCursor when hovering an object"""
        print('GraphicsComponentEvent.hoverEnterEvent()')
        self.setCursor(QCursor(Qt.OpenHandCursor))

    # def hoverMoveEvent(event: QGraphicsSceneHoverEvent) -> None: ...
    # def contextMenuEvent(event: QGraphicsSceneContextMenuEvent) -> None: ...

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Changes the cursor to ArrowCursor when leaving an object"""
        print('GraphicsComponentEvent.hoverLeaveEvent()')
        self.setCursor(QCursor(Qt.ArrowCursor))

    # # https://www.qtcentre.org/threads/25486-QGraphicsItem-Horizontal-Vertical-move-only
    # QVariant Component::itemChange(GraphicsItemChange change, const QVariant &value)
    # {
    #     if (change == ItemPositionChange && scene()) {
    #         // value is the new position.
    #         QPointF newPos = value.toPointF();
    #         QRectF rect = scene()->sceneRect();
    #         if (!rect.contains(newPos)) {
    #             // Keep the item inside the scene rect.
    #             newPos.setX(qMin(rect.right(), qMax(newPos.x(), rect.left())));
    #             newPos.setY(qMin(rect.bottom(), qMax(newPos.y(), rect.top())));
    #             return newPos;
    #         }
    #     }
    #     return QGraphicsItem::itemChange(change, value);
    # }