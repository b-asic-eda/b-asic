import os
import sys
from typing             import Any, Optional
from pprint             import pprint
from typing import Any, AnyStr, Generic, Protocol, TypeVar, Union, Optional, overload, Final, final
# from typing_extensions import Self, Final, Literal, LiteralString, TypeAlias, final
import numpy as np

import qtpy
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets

# QGraphics and QPainter imports
from qtpy.QtCore    import (
    Qt, QObject, QRect, QRectF, QPoint, QSize, QSizeF, QByteArray)
from qtpy.QtGui     import (
    QPaintEvent, QPainter, QPainterPath, QColor, QBrush, QPen, QFont, QPolygon, QIcon, QPixmap,
    QLinearGradient, QTransform)
from qtpy.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsWidget,
    QGraphicsLayout, QGraphicsLinearLayout, QGraphicsGridLayout, QGraphicsLayoutItem, QGraphicsAnchorLayout,
    QGraphicsItem, QGraphicsItemGroup, QGraphicsPathItem,
    QStyleOptionGraphicsItem, QWidget)
from qtpy.QtCore    import (
    QPoint, QPointF)

# B-ASIC
import logger
from b_asic.schedule    import Schedule


# class ComponentItem(QGraphicsItemGroup, QGraphicsLayoutItem):
class ComponentItem(QGraphicsItemGroup, QGraphicsLayoutItem):
# class ComponentItem(QGraphicsLayoutItem, QGraphicsItemGroup):
# class ComponentItem(QGraphicsLayoutItem, QGraphicsItem):
    
    _scale: float
    _component_item: QGraphicsPathItem
    _execution_time_item: QGraphicsPathItem
    _item_group: QGraphicsItemGroup
    
    
    def __init__(self, scale: float, parent: QGraphicsWidget = None):
        QGraphicsItemGroup.__init__(self)
        QGraphicsLayoutItem.__init__(self, parent = parent)
        self.setGraphicsItem(self)

        self._scale = scale
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! A')
        self._item_group = QGraphicsItemGroup()
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! B')
        self._populate()
        
        # print(self.boundingRect().size())

    def _populate(self):
        # brush = QBrush(Qt.lightGray, bs=Qt.SolidPattern)
        brush = QBrush(Qt.lightGray)
        # brush.setStyle(Qt.SolidPattern)
        pen = QPen(Qt.SolidLine)
        pen.setWidthF(1/self._scale)
        pen.setBrush(Qt.darkGray)
        # pen.setCapStyle(Qt.RoundCap)      # Qt.FlatCap, Qt.SquareCap (default), Qt.RoundCap
        pen.setJoinStyle(Qt.RoundJoin)      # Qt.MiterJoin, Qt.BevelJoin (default), Qt.RoundJoin, Qt.SvgMiterJoin
        
        # component path
        component_path = QPainterPath(QPoint(0,0))
        component_path.lineTo(0, 1)
        component_path.lineTo(4, 1)
        component_path.lineTo(4, 0)
        component_path.closeSubpath()

        # component item
        self._component_item = QGraphicsPathItem(component_path)
        self._component_item.setPen(pen)
        self._component_item.setBrush(brush)
        self._component_item.setPos(0.5,0)               # in parent (i.e. item_group) coordinates
        
        # execution time square
        execution_time_path = QPainterPath(QPoint(0,0))
        execution_time_path.addRect(0, 0, 1.0, 1.0)

        # execution time item
        green_color = QColor(Qt.magenta)
        green_color.setAlpha(200)               # 0-255
        pen.setColor(green_color)
        self._execution_time_item = QGraphicsPathItem(execution_time_path)
        self._execution_time_item.setPen(pen)
        
        # item group, consist of time_item and component_item
        # item_group = QGraphicsItemGroup()
        
        # graphics_item = self.graphicsItem()
        # print(graphics_item)
        # self._item_group = graphics_item.childItems()[0]
        # print(self._item_group)
        # # item_group.setScale(self._scale)
        # print('############################# 1')
        # self._item_group.addToGroup(self._component_item)
        # print('############################# 2')
        # self._item_group.addToGroup(self._execution_time_item)
        
        print('############################# 1')
        self.addToGroup(self._component_item)
        print('############################# 2')
        self.addToGroup(self._execution_time_item)

        # self.setGraphicsItem(self)
        # QGraphicsItemGroup
        # self.setGroup(item_group)
        print('Populated!')

        
    
    
    # reimplement QGraphicsLayoutItem virtual functions
    def updateGeometry(self):
        print('updateGeometry()')
        QGraphicsLayoutItem.updateGeometry(self)
    
    def setGeometry(self, geom: QRectF) -> None: 
        print(f'setGeometry({geom})')
        self.prepareGeometryChange()
        QGraphicsLayoutItem.setGeometry(self, geom)
        self.setPos(geom.topLeft())
    
    def sizeHint(self, which: Qt.SizeHint, constraint: QSizeF = QSizeF()) -> QSizeF:
        print(f'sizeHint(which={which}, constraint={constraint}')
        # return QSizeF(1000, 100)
    #     if self.isEmpty():
    #         pass

        # item = self.graphicsItem()
        switch = {
            Qt.MinimumSize:     self.boundingRect().size(),
            Qt.PreferredSize:   self.boundingRect().size(),
            # Qt.MinimumSize:     self.geometry().size(),
            # Qt.PreferredSize:     self.geometry().size(),
            Qt.MaximumSize:     QSizeF(float("inf"), float("inf"))
            # Qt.MaximumSize:     self.parentItem().boundingRect().size()
        }
        ret = switch.get(which, constraint)
        print(f'ret: {ret}')
        return switch.get(which, constraint)
    
    def minimumSize(self):
        print('minimumSize()')

    
    # # reimplement QGraphicsItem virtual functions
    # def boundingRect(self) -> QRectF:
    #     print('boundingRect()')
    #     # return self._item_group.boundingRect()
    #     return QRectF(QPointF(0,0), self.geometry().size())
    
    # def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget]= None) -> None:
    #     print(f'paint(painter={painter}, option={option}, widget={widget})')
    #     painter.drawRoundedRect(-10, -10, 20, 20, 5, 5)
    #     # self._item_group.paint(painter, option, widget)

# print("MRO:")
# pprint(ComponentItem.__mro__)