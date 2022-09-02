# This Python file uses the following encoding: utf-8
"""B-ASIC Scheduler-gui GraphicsScene Module.

Contains the GraphicsScene class for drawing items on.
"""


import os
import sys
from typing             import Any
from pprint             import pprint
from typing import Any, AnyStr, Generic, Protocol, TypeVar, Union, Optional, overload, Final, final
# from typing_extensions import Self, Final, Literal, LiteralString, TypeAlias, final
from copy               import deepcopy
import numpy as np

import qtpy
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets

# QGraphics and QPainter imports
from qtpy.QtCore    import (
    Qt, QObject, QRect, QRectF, QPoint, QSize, QByteArray)
from qtpy.QtGui     import (
    QPaintEvent, QPainter, QPainterPath, QColor, QBrush, QPen, QFont, QPolygon, QIcon, QPixmap,
    QLinearGradient, QTransform)
from qtpy.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsWidget,
    QGraphicsLayout, QGraphicsLinearLayout, QGraphicsGridLayout, QGraphicsLayoutItem, QGraphicsAnchorLayout,
    QGraphicsItem, QGraphicsItemGroup, QGraphicsPathItem)
from qtpy.QtCore    import (
    QPoint, QPointF)

# B-ASIC
import logger
from b_asic.schedule    import Schedule
from component_item     import ComponentItem



@final
class GraphicsScene(QGraphicsScene):
    """GraphicsScene subclass of QGraphicsScene acts as a scene to place items on"""
    _id: Final[int]
    _schedule: Final[Schedule]
    _scale: float
    # _schedule: Final[Schedule]
    
    # def __init__(self, id: int, schedule: Optional["Schedule"] = None, *args, **kwargs):
    # def __init__(self, id: int, schedule: Optional["Schedule"] = None):
    def __init__(self, id: int, schedule: Schedule = None, *args, **kwargs):
        # QGraphicsScene.__init__(self)
        super().__init__(*args, **kwargs)
        
        self._id = id
        if isinstance(schedule, Schedule):
            self._schedule = deepcopy(schedule)
            self._scale = 10.0
            
            print('From GraphicsScene/schedule:\t\t', end='')
            pprint(schedule)
            print('From GraphicsScene/self._schedule:\t', end='')
            pprint(self._schedule)
            print('')
            
            
            # print('########### _start_times:')
            # pprint(self._schedule._start_times)
            # print('########### _laps:')
            # pprint(self._schedule._laps.items())
            # print('########### _schedule_time:\t', self._schedule._schedule_time)
            # print('########### _cyclic:\t\t', self._schedule._cyclic)
            # print('########### _resolution:\t', self._schedule._resolution)
            # for op_id, op_start_time in self._schedule._start_times.items():
            #     print(op_id, op_start_time)

            
            # pprint(ComponentItem.__mro__)
            component = ComponentItem(self._scale)
            
            # add item group to the scene
            self.addItem(component)
            
            
            ####################################################################
            print('boundingRect():', component.boundingRect())
            print('sceneBoundingRect():', component.sceneBoundingRect())
            print('childrenBoundingRect():', component.childrenBoundingRect())
            print('Qt.MinimumSize:  ', component.sizeHint(Qt.MinimumSize))
            print('Qt.PreferredSize:', component.sizeHint(Qt.PreferredSize))
            print('Qt.MaximumSize:  ', component.sizeHint(Qt.MaximumSize))
            
            
            # # add the component group to scene
            # group_layout_item = QGraphicsLayoutItem()
            # group_layout_item.setGraphicsItem(item_group)
            
            # grid_layout = QGraphicsGridLayout()
            # print('ContentsMargins:', grid_layout.getContentsMargins())
            # print('Spacing: [{}, {}]'.format(grid_layout.horizontalSpacing() , grid_layout.verticalSpacing()))
            # grid_layout.setContentsMargins(10.0, 10.0, 10.0, 10.0)
            # grid_layout.setSpacing(10.0)
            # grid_layout.addItem(group_layout_item, 0, 1)
            # linear_layout = QGraphicsLinearLayout()
            
            # self.addItem(grid_layout)
            
    # def drawBackground(self, painter: QPainter, exposed_rect: QRectF):
    #     pen = QPen(Qt.DotLine)
    #     # pen = QPen(Qt.DotLine)
    #     # pen.setDashOffset(self._scale)
    #     pen.setDashPattern([1, self._scale])
    #     pen.setBrush(Qt.lightGray)
    #     pen.setCosmetic(True)
        
    #     # vertical lines
    #     for x in np.arange(0, exposed_rect.width() - self._scale, self._scale):
    #         self.addLine(x, 0, x, exposed_rect.height() - self._scale, pen)
        
    #     # horizontal lines
    #     # for y in np.arange(0, exposed_rect.height() - self._scale, self._scale):
    #     #     self.addLine(0, y, exposed_rect.width() - self._scale, y, pen)
        
    #     # self._ view->fitInView(scene->itemsVBoundingRect())
    #     # print(type(self.parent))
    #     # self.parent.fitInView(self.itemsVBoundingRect())
                
                
    def plot_schedule(self):
       self._schedule.plot_schedule()
    
    @property
    def id(self) -> int:
        return self._id

    @property
    def schedule(self) -> Schedule:
        print('From GraphicsScene.schedule:\t\t', end='')
        pprint(self._schedule)
        # print('')
        # print(callable(self._schedule))
        return self._schedule
    
    # @schedule_.setter
    # def schedule_(self, schedule: Schedule):
    #     self._schedule = schedule


# print('\nGraphicsScene.__mro__')
# pprint(GraphicsScene.__mro__)
# print('')